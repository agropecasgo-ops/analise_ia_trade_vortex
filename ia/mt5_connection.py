"""
Helpers for attaching to an already running MetaTrader 5 terminal.

The MetaTrader5 Python package can start terminal64.exe when initialize() is
called without an active terminal. FinanceAI only needs MT5 as a data provider,
so the default behavior here is attach-only.
"""

from __future__ import annotations

import ctypes
import os
import threading
from ctypes import wintypes


_INIT_LOCK = threading.Lock()


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "sim", "on"}


def mt5_launch_allowed() -> bool:
    return _truthy(os.getenv("FINANCEAI_MT5_ALLOW_TERMINAL_LAUNCH"))


def configured_process_names() -> set[str]:
    raw = os.getenv("FINANCEAI_MT5_PROCESS_NAMES", "terminal64.exe,terminal.exe")
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def is_mt5_terminal_running() -> bool:
    """Return True when a known MT5 terminal process is already running."""
    if os.name != "nt":
        return False

    process_names = configured_process_names()
    if not process_names:
        return False

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    snapshot = kernel32.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot == wintypes.HANDLE(-1).value:
        return False

    class PROCESSENTRY32W(ctypes.Structure):
        _fields_ = [
            ("dwSize", wintypes.DWORD),
            ("cntUsage", wintypes.DWORD),
            ("th32ProcessID", wintypes.DWORD),
            ("th32DefaultHeapID", ctypes.POINTER(wintypes.ULONG)),
            ("th32ModuleID", wintypes.DWORD),
            ("cntThreads", wintypes.DWORD),
            ("th32ParentProcessID", wintypes.DWORD),
            ("pcPriClassBase", wintypes.LONG),
            ("dwFlags", wintypes.DWORD),
            ("szExeFile", wintypes.WCHAR * 260),
        ]

    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
    try:
        has_entry = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
        while has_entry:
            if entry.szExeFile.lower() in process_names:
                return True
            has_entry = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
        return False
    finally:
        kernel32.CloseHandle(snapshot)


def initialize_mt5_attach_only(mt5, timeout: int = 5000) -> tuple[bool, str | None]:
    """
    Initialize MetaTrader5 without launching the terminal by default.

    If FINANCEAI_MT5_ALLOW_TERMINAL_LAUNCH=1 is set, this function allows the
    package's native launch behavior. Otherwise it requires an existing
    terminal64.exe/terminal.exe process and only then calls initialize().
    """
    if mt5 is None:
        return False, "MetaTrader5 Python API nao instalada."

    if not mt5_launch_allowed() and not is_mt5_terminal_running():
        return (
            False,
            "Terminal MT5 nao esta aberto; FinanceAI nao inicia terminal automaticamente.",
        )

    terminal_path = os.getenv("FINANCEAI_MT5_TERMINAL_PATH") or os.getenv("MT5_TERMINAL_PATH")
    with _INIT_LOCK:
        try:
            if terminal_path:
                ok = bool(mt5.initialize(path=terminal_path, timeout=timeout))
            else:
                ok = bool(mt5.initialize(timeout=timeout))
        except TypeError:
            ok = bool(mt5.initialize())
        except Exception as error:
            return False, str(error)

    if ok:
        return True, None
    try:
        return False, str(mt5.last_error())
    except Exception:
        return False, "MT5 initialize falhou."

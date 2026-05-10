"""
Persistencia local para usuarios, watchlist e alertas.
"""

import json
import os
import sqlite3
from datetime import datetime
from functools import wraps
from hashlib import pbkdf2_hmac
from secrets import token_hex

from flask import jsonify, redirect, session, url_for


DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "platform.db")


def _connect():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password, salt=None):
    salt = salt or token_hex(16)
    digest = pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120000)
    return salt, digest.hex()


def init_db():
    with _connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS watchlist (
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                created_at TEXT NOT NULL,
                UNIQUE(user_id, symbol)
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                condition_type TEXT NOT NULL,
                target REAL NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                user_id INTEGER NOT NULL,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                UNIQUE(user_id, key)
            )
        """)
        user = conn.execute("SELECT id FROM users WHERE username = ?", ("admin",)).fetchone()
        if not user:
            salt, digest = hash_password("admin123")
            conn.execute(
                "INSERT INTO users(username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
                ("admin", digest, salt, datetime.utcnow().isoformat()),
            )


def create_user(username, password):
    salt, digest = hash_password(password)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO users(username, password_hash, salt, created_at) VALUES (?, ?, ?, ?)",
            (username, digest, salt, datetime.utcnow().isoformat()),
        )


def authenticate(username, password):
    with _connect() as conn:
        user = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
    if not user:
        return None
    _, digest = hash_password(password, user["salt"])
    if digest != user["password_hash"]:
        return None
    return {"id": user["id"], "username": user["username"]}


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            if view.__name__.startswith("api_"):
                return jsonify({"success": False, "error": "login_required"}), 401
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapper


def current_user_id():
    return int(session.get("user_id", 0))


def get_watchlist(user_id):
    with _connect() as conn:
        rows = conn.execute("SELECT symbol FROM watchlist WHERE user_id = ? ORDER BY created_at", (user_id,)).fetchall()
    return [row["symbol"] for row in rows]


def add_watchlist(user_id, symbol):
    with _connect() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO watchlist(user_id, symbol, created_at) VALUES (?, ?, ?)",
            (user_id, symbol.upper(), datetime.utcnow().isoformat()),
        )
    return get_watchlist(user_id)


def remove_watchlist(user_id, symbol):
    with _connect() as conn:
        conn.execute("DELETE FROM watchlist WHERE user_id = ? AND symbol = ?", (user_id, symbol.upper()))
    return get_watchlist(user_id)


def create_alert(user_id, symbol, condition_type, target):
    with _connect() as conn:
        cursor = conn.execute(
            "INSERT INTO alerts(user_id, symbol, condition_type, target, active, created_at) VALUES (?, ?, ?, ?, 1, ?)",
            (user_id, symbol.upper(), condition_type, float(target), datetime.utcnow().isoformat()),
        )
        return cursor.lastrowid


def list_alerts(user_id):
    with _connect() as conn:
        rows = conn.execute("SELECT * FROM alerts WHERE user_id = ? ORDER BY id DESC", (user_id,)).fetchall()
    return [dict(row) for row in rows]


def save_setting(user_id, key, value):
    payload = json.dumps(value)
    with _connect() as conn:
        conn.execute(
            "INSERT INTO settings(user_id, key, value) VALUES (?, ?, ?) ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value",
            (user_id, key, payload),
        )


def get_setting(user_id, key, default=None):
    with _connect() as conn:
        row = conn.execute("SELECT value FROM settings WHERE user_id = ? AND key = ?", (user_id, key)).fetchone()
    return json.loads(row["value"]) if row else default

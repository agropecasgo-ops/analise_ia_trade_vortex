"""
Replay exclusivo da area Operacional Leitura Grafica.

Este modulo importa apenas o operacional_reader. Ele nao usa Live Trading IA,
LiveSignalManager, indicadores, SMC padrao, score geral ou sinais IA padrao.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd

from .operacional_reader import build_operacional_reading


DISCLAIMER = "Replay operacional educativo. Resultado passado nao garante resultado futuro."


class OperacionalReplaySession:
    def __init__(self, candles, symbol, market, timeframe, start_date=None, end_date=None, speed=1):
        self.id = uuid4().hex[:12]
        self.symbol = symbol
        self.market = market
        self.timeframe = timeframe
        self.speed = int(speed or 1)
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.paused = True
        self.finished = False
        self.candles = self._filter(candles, start_date, end_date)
        if len(self.candles) < 90:
            raise ValueError("Sem candles suficientes para replay operacional no periodo escolhido.")
        self.index = min(90, len(self.candles) - 1)
        self.operacional_signals = []

    def start(self):
        self.paused = False
        return self.status()

    def pause(self):
        self.paused = True
        return self.status()

    def reset(self):
        self.index = min(90, len(self.candles) - 1)
        self.paused = True
        self.finished = False
        self.operacional_signals = []
        return self.status()

    def step(self, direction=1):
        if direction >= 0:
            if self.index < len(self.candles) - 1:
                self.index += 1
            else:
                self.finished = True
                self.paused = True
        else:
            self.index = max(min(90, len(self.candles) - 1), self.index - 1)
            self.finished = False
        return self.status()

    def status(self):
        window = self.current_window()
        reading = build_operacional_reading(window, self.symbol, self.timeframe)
        signal = self._track_signal(reading, window)
        live = self._live_payload(reading, window)
        return {
            "success": True,
            "mode": "operacional",
            "engine": "operacional_replay",
            "session_id": self.id,
            "symbol": self.symbol,
            "market": self.market,
            "timeframe": self.timeframe,
            "speed": self.speed,
            "paused": self.paused,
            "finished": self.finished,
            "index": self.index,
            "total": len(self.candles),
            "progress": round(self.index / max(len(self.candles) - 1, 1) * 100, 2),
            "current_time": int(window.index[-1].timestamp()),
            "candles": self._chart_candles(window),
            "volumes": [],
            "live_status": live,
            "operacional_reading": reading,
            "operacional_replay": {
                "score": reading.get("operacional_score", 0),
                "context": reading.get("operacional_context", {}),
                "signal": signal,
                "live": reading.get("operacional_live", []),
            },
            "signal": signal,
            "signals": [signal] if signal else [],
            "history": self.operacional_signals[-200:],
            "stats": self.results()["stats"],
            "disclaimer": DISCLAIMER,
        }

    def results(self):
        signals = self.operacional_signals
        stats = {
            "total_signals": len(signals),
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "average_gain": 0,
            "average_loss": 0,
            "profit_factor": 0,
            "drawdown": 0,
            "estimated_return": 0,
            "best_signal": signals[-1] if signals else None,
            "worst_signal": None,
            "best_hours": [],
        }
        return {"success": True, "session_id": self.id, "stats": stats, "signals": signals, "disclaimer": DISCLAIMER}

    def current_window(self):
        return self.candles.iloc[: self.index + 1].copy()

    def _filter(self, candles, start_date, end_date):
        df = candles.copy().sort_index()
        if start_date:
            df = df[df.index >= pd.Timestamp(start_date, tz="UTC")]
        if end_date:
            df = df[df.index <= pd.Timestamp(end_date, tz="UTC")]
        return df.dropna(subset=["open", "high", "low", "close"])

    def _chart_candles(self, df):
        return [
            {"time": int(idx.timestamp()), "open": float(row.open), "high": float(row.high), "low": float(row.low), "close": float(row.close)}
            for idx, row in df.tail(260).iterrows()
        ]

    def _live_payload(self, reading, window):
        signal = reading.get("operacional_signal", {})
        score = reading.get("operacional_score", 0)
        messages = reading.get("operacional_live") or reading.get("narrative") or ["Aguardando leitura operacional."]
        return {
            "state": signal.get("status", "analisando").upper().replace(" ", "_"),
            "status": signal.get("status", "analisando"),
            "message": messages[0],
            "probable_direction": signal.get("direction", "NEUTRO"),
            "confluence_score": score,
            "confidence": score,
            "risk_reward": signal.get("risk_reward"),
            "entry_aggressive": signal.get("entry"),
            "entry_conservative": signal.get("entry"),
            "stop_loss": signal.get("stop"),
            "take_profit": signal.get("take_profit_1"),
            "reason": signal.get("operational_reason"),
            "engine": "operacional_leitura_grafica",
            "replay": True,
            "replay_index": self.index,
            "replay_total": len(self.candles),
            "replay_time": int(window.index[-1].timestamp()),
        }

    def _track_signal(self, reading, window):
        signal = dict(reading.get("operacional_signal") or {})
        if not signal:
            return None
        signal.update({
            "id": f"op-{self.id}-{self.index}",
            "timestamp": datetime.fromtimestamp(window.index[-1].timestamp(), tz=timezone.utc).isoformat(),
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "confluence_score": signal.get("score", reading.get("operacional_score", 0)),
            "confidence": signal.get("score", reading.get("operacional_score", 0)),
            "stop_loss": signal.get("stop"),
            "take_profit_3": signal.get("take_profit_2"),
            "explanation": signal.get("operational_reason"),
            "technical_reason": signal.get("operational_reason"),
            "partial_result": "--",
        })
        if signal.get("status") in ["entrada possivel", "entrada confirmada"]:
            last = self.operacional_signals[-1] if self.operacional_signals else {}
            if last.get("index") != self.index:
                signal["index"] = self.index
                self.operacional_signals.append(signal)
        return signal


class OperacionalReplayEngine:
    def __init__(self):
        self.sessions = {}

    def create(self, candles, symbol, market, timeframe, start_date=None, end_date=None, speed=1):
        session = OperacionalReplaySession(candles, symbol, market, timeframe, start_date, end_date, speed)
        self.sessions[session.id] = session
        return session

    def get(self, session_id):
        if not session_id or session_id not in self.sessions:
            raise KeyError("operacional_replay_session_not_found")
        return self.sessions[session_id]

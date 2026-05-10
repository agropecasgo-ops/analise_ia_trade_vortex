"""
Replay de Mercado IA.

Reproduz candles historicos passo a passo e chama a IA usando apenas os
candles disponiveis ate o ponto atual do replay.
"""

from datetime import datetime, timezone
from uuid import uuid4

import pandas as pd

from .live_signals import LiveSignalManager
from .live_trading import build_live_status


DISCLAIMER = "Replay baseado em dados historicos. Resultado passado nao garante resultado futuro."


class ReplaySession:
    def __init__(self, candles, symbol, market, timeframe, start_date=None, end_date=None, speed=1):
        self.id = uuid4().hex[:12]
        self.symbol = symbol
        self.market = market
        self.timeframe = timeframe
        self.speed = int(speed or 1)
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.paused = True
        self.finished = False
        self.signal_manager = LiveSignalManager(min_score=78, min_rr=1.5, min_confidence=70)
        self.candles = self._filter(candles, start_date, end_date)
        if len(self.candles) < 90:
            raise ValueError("Sem candles suficientes para replay no periodo escolhido.")
        self.index = min(90, len(self.candles) - 1)
        self.equity = [0.0]

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
        self.signal_manager = LiveSignalManager(min_score=78, min_rr=1.5, min_confidence=70)
        self.equity = [0.0]
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
        live_status = build_live_status(window, self.symbol, self.timeframe)
        live_status.update({
            "market": self.market,
            "replay": True,
            "replay_index": self.index,
            "replay_total": len(self.candles),
            "replay_time": int(window.index[-1].timestamp()),
        })
        signal = self.signal_manager.update_from_live_status(
            live_status,
            {"market": self.market, "market_label": self.market},
            {"strong_signal_allowed": True},
        )
        self._mark_equity()
        return {
            "success": True,
            "session_id": self.id,
            "mode": "complete",
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
            "volumes": self._chart_volumes(window),
            "live_status": live_status,
            "signal": signal,
            "signals": self.signal_manager.list_active(),
            "history": self.signal_manager.list_history(200),
            "stats": self.results()["stats"],
            "disclaimer": DISCLAIMER,
        }

    def results(self):
        closed = self.signal_manager.list_history(500)
        active_terminal = [
            item for item in self.signal_manager.list_active()
            if item.get("status") in ["tp1_hit", "tp2_hit", "tp3_hit", "stopped", "invalidated"]
        ]
        signals = closed + active_terminal
        wins = [item for item in signals if item.get("status") in ["tp1_hit", "tp2_hit", "tp3_hit"]]
        losses = [item for item in signals if item.get("status") in ["stopped", "invalidated"]]
        gains = [self._result_pct(item) for item in wins]
        loss_values = [abs(self._result_pct(item)) for item in losses]
        gross_gain = sum(gains)
        gross_loss = sum(loss_values)
        best = max(signals, key=self._result_pct, default=None)
        worst = min(signals, key=self._result_pct, default=None)
        stats = {
            "total_signals": len(signals),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(len(wins) / len(signals) * 100, 2) if signals else 0,
            "average_gain": round(sum(gains) / len(gains), 3) if gains else 0,
            "average_loss": round(sum(loss_values) / len(loss_values), 3) if loss_values else 0,
            "profit_factor": round(gross_gain / gross_loss, 3) if gross_loss else round(gross_gain, 3),
            "drawdown": round(self._drawdown(), 3),
            "estimated_return": round(sum(self._result_pct(item) for item in signals), 3),
            "best_signal": best,
            "worst_signal": worst,
            "best_hours": self._best_hours(signals),
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
        return df.dropna(subset=["open", "high", "low", "close", "volume"])

    def _chart_candles(self, df):
        return [
            {"time": int(idx.timestamp()), "open": float(row.open), "high": float(row.high), "low": float(row.low), "close": float(row.close)}
            for idx, row in df.tail(260).iterrows()
        ]

    def _chart_volumes(self, df):
        return [
            {
                "time": int(idx.timestamp()),
                "value": float(row.volume),
                "color": "rgba(38, 166, 154, 0.45)" if row.close >= row.open else "rgba(239, 83, 80, 0.45)",
            }
            for idx, row in df.tail(260).iterrows()
        ]

    def _result_pct(self, signal):
        value = str(signal.get("partial_result", "0")).replace("%", "")
        try:
            return float(value)
        except ValueError:
            return 0.0

    def _mark_equity(self):
        total = sum(self._result_pct(item) for item in self.signal_manager.list_history(500))
        self.equity.append(total)

    def _drawdown(self):
        peak = self.equity[0] if self.equity else 0
        max_dd = 0
        for value in self.equity:
            peak = max(peak, value)
            max_dd = min(max_dd, value - peak)
        return abs(max_dd)

    def _best_hours(self, signals):
        buckets = {}
        for signal in signals:
            timestamp = signal.get("timestamp")
            if not timestamp:
                continue
            hour = datetime.fromisoformat(timestamp).strftime("%H:00")
            buckets.setdefault(hour, []).append(self._result_pct(signal))
        ranked = sorted(
            ({"hour": hour, "result": round(sum(values), 3), "signals": len(values)} for hour, values in buckets.items()),
            key=lambda item: item["result"],
            reverse=True,
        )
        return ranked[:5]


class ReplayEngine:
    def __init__(self):
        self.sessions = {}

    def create(self, candles, symbol, market, timeframe, start_date=None, end_date=None, speed=1):
        session = ReplaySession(candles, symbol, market, timeframe, start_date, end_date, speed)
        self.sessions[session.id] = session
        return session

    def get(self, session_id):
        if not session_id or session_id not in self.sessions:
            raise KeyError("replay_session_not_found")
        return self.sessions[session_id]

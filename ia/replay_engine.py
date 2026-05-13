"""
Replay IA candle a candle.

The replay engine is additive and read-only: it receives historical candles,
walks forward one candle at a time and emits institutional events that the UI
can play back without touching live trading or realtime signal state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from .ai_score_engine import AIScoreEngine
from .confirmation_engine import ConfirmationEngine
from .macro_context_engine import MacroContextEngine
from .market_structure_engine import MarketStructureEngine


def _clean(candles: pd.DataFrame | None) -> pd.DataFrame:
    if candles is None or candles.empty:
        return pd.DataFrame(columns=["open", "high", "low", "close", "volume"])
    df = candles.copy()
    if "volume" not in df.columns:
        df["volume"] = 0
    return df.dropna(subset=["open", "high", "low", "close", "volume"])


def _num(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if number == number else default


def _timestamp(value: Any) -> int:
    try:
        return int(pd.Timestamp(value).timestamp())
    except Exception:
        return 0


class ReplayEngine:
    def __init__(
        self,
        candles: pd.DataFrame,
        symbol: str,
        timeframe: str,
        asset_type: str = "",
        max_candles: int = 160,
        warmup: int = 45,
    ) -> None:
        self.df = _clean(candles).tail(max(60, min(int(max_candles or 160), 400)))
        self.symbol = symbol
        self.timeframe = timeframe
        self.asset_type = asset_type
        self.warmup = max(35, min(int(warmup or 45), 120))

    def run(self) -> dict[str, Any]:
        candles = self._candles_payload(self.df)
        volumes = self._volumes_payload(self.df)
        if len(self.df) < self.warmup:
            return {
                "success": True,
                "symbol": self.symbol,
                "assetType": self.asset_type,
                "timeframe": self.timeframe,
                "candles": candles,
                "volumes": volumes,
                "frames": [],
                "events": [],
                "summary": "Candles insuficientes para replay institucional.",
                "createdAt": datetime.now(timezone.utc).isoformat(),
            }

        frames: list[dict[str, Any]] = []
        events: list[dict[str, Any]] = []
        previous = self._empty_previous()

        for position in range(self.warmup, len(self.df) + 1):
            window = self.df.iloc[:position]
            frame = self._frame(window, position - 1, previous)
            frames.append(frame)
            events.extend(frame["events"])
            previous = {
                "trend": frame["trend"],
                "direction": frame["direction"],
                "bos": frame["structure"].get("bos"),
                "choch": frame["structure"].get("choch"),
                "sweep": frame["liquidity"].get("sweep"),
                "order_block": frame["structure"].get("orderBlock"),
                "fvg": frame["structure"].get("fvg"),
                "score": frame["score"],
            }

        return {
            "success": True,
            "symbol": self.symbol,
            "assetType": self.asset_type,
            "timeframe": self.timeframe,
            "candles": candles,
            "volumes": volumes,
            "frames": frames,
            "events": events[-240:],
            "summary": self._summary(frames, events),
            "createdAt": datetime.now(timezone.utc).isoformat(),
        }

    def _frame(self, window: pd.DataFrame, index_position: int, previous: dict[str, Any]) -> dict[str, Any]:
        candles_by_tf = {
            "1m": window,
            "5m": window,
            "15m": window,
            "1h": window,
            self.timeframe: window,
        }
        macro = MacroContextEngine(candles_by_tf, self.symbol).analyze()
        structure = MarketStructureEngine(window, macro).analyze()
        confirmation = ConfirmationEngine(window, macro, structure).analyze()
        direction = self._direction(macro, structure, confirmation)
        score_payload = AIScoreEngine().score(
            macro,
            structure,
            confirmation,
            {"role": "auxiliary_filter_only", "can_generate_signal": False, "direction": direction},
        )
        score = int(_num(score_payload.get("score")))
        candle = window.iloc[-1]
        candle_time = _timestamp(window.index[-1])
        frame = {
            "index": index_position,
            "time": candle_time,
            "price": round(float(candle["close"]), 8),
            "direction": direction,
            "trend": macro.get("direction", "NEUTRAL"),
            "score": score,
            "scorePassed80": score >= 80 and _num(previous.get("score")) < 80,
            "marketPhase": self._market_phase(macro, structure, confirmation),
            "structure": {
                "bos": structure.get("bos", {}),
                "choch": structure.get("choch", {}),
                "orderBlock": structure.get("order_block", {}),
                "fvg": structure.get("fvg", {}),
                "valid": bool(structure.get("valid")),
            },
            "liquidity": {
                "zones": (structure.get("liquidity") or {}).get("zones", []),
                "nearest": (structure.get("liquidity") or {}).get("nearest"),
                "sweep": structure.get("liquidity_sweep", {}),
            },
            "confirmation": {
                "volumeStrong": bool((confirmation.get("volume") or {}).get("strong")),
                "volumeRatio": (confirmation.get("volume") or {}).get("ratio"),
                "candleStrong": bool((confirmation.get("candle") or {}).get("strong")),
                "falseBreakout": confirmation.get("false_breakout", {}),
            },
            "manipulation": self._manipulation(structure, confirmation),
            "macro": macro,
            "explanation": "",
            "events": [],
        }
        frame["events"] = self._events(frame, previous)
        frame["explanation"] = self._explanation(frame)
        return frame

    def _events(self, frame: dict[str, Any], previous: dict[str, Any]) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []

        def add(kind: str, title: str, importance: str, price: Any = None) -> None:
            events.append({
                "time": frame["time"],
                "index": frame["index"],
                "kind": kind,
                "title": title,
                "importance": importance,
                "price": price if price is not None else frame["price"],
                "score": frame["score"],
                "explanation": self._event_explanation(kind, frame, title),
            })

        if frame["trend"] != previous.get("trend") and frame["trend"] in ["BUY", "SELL"]:
            add("TREND", f"Tendencia {frame['trend']}", "medium")

        bos = frame["structure"].get("bos") or {}
        if bos.get("detected") and self._signature(bos) != self._signature(previous.get("bos")):
            add("BOS", f"BOS {bos.get('direction')}", "high", bos.get("level"))

        choch = frame["structure"].get("choch") or {}
        if choch.get("detected") and self._signature(choch) != self._signature(previous.get("choch")):
            add("CHOCH", f"CHOCH {choch.get('direction')}", "high", choch.get("level"))

        sweep = frame["liquidity"].get("sweep") or {}
        if sweep.get("detected") and self._signature(sweep) != self._signature(previous.get("sweep")):
            add("SWEEP", f"Sweep de liquidez {sweep.get('side')}", "high", sweep.get("level"))

        order_block = frame["structure"].get("orderBlock") or {}
        if order_block.get("valid") and self._signature(order_block) != self._signature(previous.get("order_block")):
            add("ORDER_BLOCK", f"Order block {order_block.get('direction')}", "medium", order_block.get("mid"))

        fvg = frame["structure"].get("fvg") or {}
        if fvg.get("valid") and self._signature(fvg) != self._signature(previous.get("fvg")):
            add("FVG", f"FVG {fvg.get('direction')}", "medium", fvg.get("low"))

        if frame["confirmation"].get("volumeStrong"):
            add("VOLUME", f"Volume forte {frame['confirmation'].get('volumeRatio')}x", "medium")

        if frame["manipulation"].get("detected"):
            add("MANIPULATION", frame["manipulation"].get("reason"), "high")

        if frame["scorePassed80"]:
            add("SCORE_80", "Score IA passou de 80", "critical")

        return events

    def _event_explanation(self, kind: str, frame: dict[str, Any], title: str) -> str:
        explanations = {
            "TREND": "A IA mudou o contexto direcional apos leitura de inclinacao e volatilidade.",
            "BOS": "Rompimento de estrutura detectado; a IA passa a observar continuidade e reteste.",
            "CHOCH": "Mudanca de carater detectada; pode sinalizar transicao de controle institucional.",
            "SWEEP": "Liquidez foi varrida; a IA aguarda confirmacao para evitar entrada em armadilha.",
            "ORDER_BLOCK": "Bloco institucional mapeado como possivel zona de defesa do preco.",
            "FVG": "Ineficiencia de preco detectada; pode atuar como area de retorno ou rejeicao.",
            "VOLUME": "Volume acima da media fortalece a leitura, mas nao garante direcao sozinho.",
            "MANIPULATION": "Sinais de armadilha/falso rompimento reduzem a permissao operacional.",
            "SCORE_80": "As camadas atingiram score minimo institucional; ainda depende de risco e timing.",
        }
        return explanations.get(kind, title) + f" Score atual: {frame['score']}."

    def _explanation(self, frame: dict[str, Any]) -> str:
        if frame["scorePassed80"]:
            return "Score IA cruzou 80 com camadas relevantes alinhadas; a IA marcaria este candle como ponto de atencao, nao promessa de acerto."
        if frame["manipulation"].get("detected"):
            return f"IA detecta risco de manipulacao: {frame['manipulation'].get('reason')}"
        if frame["direction"] in ["BUY", "SELL"] and frame["score"] >= 65:
            return f"Contexto {frame['direction']} em construcao com score {frame['score']}; aguardar confirmacao completa."
        return f"IA acompanha o candle com score {frame['score']} e sem confluencia institucional suficiente."

    def _direction(self, macro: dict[str, Any], structure: dict[str, Any], confirmation: dict[str, Any]) -> str:
        votes = [macro.get("direction"), structure.get("direction"), confirmation.get("direction") if confirmation.get("valid") else "NEUTRAL"]
        buy = votes.count("BUY")
        sell = votes.count("SELL")
        if buy >= 2 and buy > sell:
            return "BUY"
        if sell >= 2 and sell > buy:
            return "SELL"
        return "NEUTRAL"

    def _market_phase(self, macro: dict[str, Any], structure: dict[str, Any], confirmation: dict[str, Any]) -> str:
        if macro.get("lateral"):
            return "LATERAL"
        if self._manipulation(structure, confirmation).get("detected"):
            return "MANIPULATION"
        if structure.get("valid") and confirmation.get("valid"):
            return "CONFIRMATION"
        if structure.get("valid"):
            return "STRUCTURE"
        return "READING"

    def _manipulation(self, structure: dict[str, Any], confirmation: dict[str, Any]) -> dict[str, Any]:
        false_breakout = confirmation.get("false_breakout") or {}
        sweep = structure.get("liquidity_sweep") or {}
        detected = bool(false_breakout.get("detected") or (sweep.get("detected") and not confirmation.get("valid")))
        reason = false_breakout.get("reason") if false_breakout.get("detected") else "Sweep sem confirmacao completa." if detected else ""
        return {"detected": detected, "reason": reason}

    def _signature(self, value: Any) -> str:
        if not isinstance(value, dict):
            return "none"
        level = value.get("level", value.get("price", value.get("mid", value.get("low", value.get("high")))))
        return f"{value.get('direction')}:{value.get('side')}:{round(_num(level), 6)}:{value.get('valid')}:{value.get('detected')}"

    def _summary(self, frames: list[dict[str, Any]], events: list[dict[str, Any]]) -> str:
        score_events = [event for event in events if event["kind"] == "SCORE_80"]
        if score_events:
            return f"Replay encontrou {len(score_events)} momento(s) com score acima de 80."
        if events:
            return f"Replay mapeou {len(events)} evento(s) institucionais, sem cruzamento de score 80."
        return "Replay concluido sem eventos institucionais relevantes."

    def _candles_payload(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        return [
            {
                "time": _timestamp(index),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
            }
            for index, row in df.iterrows()
        ]

    def _volumes_payload(self, df: pd.DataFrame) -> list[dict[str, Any]]:
        return [
            {
                "time": _timestamp(index),
                "value": float(row["volume"]),
                "color": "rgba(32, 209, 140, 0.35)" if row["close"] >= row["open"] else "rgba(240, 82, 82, 0.35)",
            }
            for index, row in df.iterrows()
        ]

    def _empty_previous(self) -> dict[str, Any]:
        return {
            "trend": "NEUTRAL",
            "direction": "NEUTRAL",
            "bos": {},
            "choch": {},
            "sweep": {},
            "order_block": {},
            "fvg": {},
            "score": 0,
        }


def build_replay_analysis(
    candles: pd.DataFrame,
    symbol: str,
    timeframe: str,
    asset_type: str = "",
    max_candles: int = 160,
) -> dict[str, Any]:
    return ReplayEngine(candles, symbol, timeframe, asset_type, max_candles=max_candles).run()

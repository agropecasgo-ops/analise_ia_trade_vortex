"""
Candle Reading Engine institucional.

Camada incremental para leitura candle a candle no estilo Vortex AI. Ela nao
substitui os motores existentes; atua como filtro de timing, confirmacao,
anti-fake e plano estrutural para LiveTradingIA/Vortex.
"""

from __future__ import annotations

from typing import Any

import pandas as pd


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def _round(value: Any, digits: int = 8) -> float:
    return round(_num(value), digits)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


class CandleReadingEngine:
    MIN_SCORE = 85
    MIN_CONFIDENCE = 80
    MIN_RR = 2.0

    def __init__(
        self,
        candles: pd.DataFrame,
        symbol: str,
        timeframe: str,
        *,
        technical: dict[str, Any] | None = None,
        smc: dict[str, Any] | None = None,
        wyckoff: dict[str, Any] | None = None,
        volume: dict[str, Any] | None = None,
        flow: dict[str, Any] | None = None,
        mtf: dict[str, Any] | None = None,
    ) -> None:
        self.df = self._prepare(candles)
        self.symbol = symbol
        self.timeframe = timeframe
        self.technical = technical or {}
        self.smc = smc or {}
        self.wyckoff = wyckoff or {}
        self.volume = volume or {}
        self.flow = flow or {}
        self.mtf = mtf or {}

    def analyze(self) -> dict[str, Any]:
        if len(self.df) < 8:
            return self._empty("Aguardando candles suficientes para leitura candle a candle.")

        candles = [self._read_candle(i) for i in range(max(0, len(self.df) - 12), len(self.df))]
        current = candles[-1]
        sequence = self._sequence(candles)
        institutional = self._institutional_context(current, sequence)
        risk = self._risk_plan(current, sequence, institutional)
        anti_fake = self._anti_fake(current, sequence, institutional, risk)
        direction = self._direction(current, sequence, institutional)
        score = self._score(current, sequence, institutional, risk, anti_fake, direction)
        confidence = self._confidence(score, current, sequence, institutional, anti_fake)
        blockers = self._blockers(score, confidence, risk, anti_fake, direction)
        setup_validated = direction in ["BUY", "SELL"] and not blockers
        signal = "COMPRA" if direction == "BUY" and setup_validated else "VENDA" if direction == "SELL" and setup_validated else "AGUARDAR"

        return {
            "success": True,
            "engine": "candle_reading_vortex",
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "signal": signal,
            "direction": direction if setup_validated else "NEUTRAL",
            "raw_direction": direction,
            "setup_validated": setup_validated,
            "score": round(score, 2),
            "confidence": round(confidence, 2),
            "current_candle": current,
            "sequence": sequence,
            "last_candles": candles[-6:],
            "institutional_context": institutional,
            "risk": risk,
            "anti_fake": anti_fake,
            "blockers": blockers,
            "confirmations": self._confirmations(current, sequence, institutional, risk, direction),
            "narrative": self._narrative(signal, current, sequence, institutional, risk, anti_fake, blockers),
            "panel": self._panel(current, sequence, institutional, risk, blockers),
        }

    def _prepare(self, candles: pd.DataFrame) -> pd.DataFrame:
        df = candles.copy()
        for column in ["open", "high", "low", "close", "volume"]:
            if column not in df:
                df[column] = 0
            df[column] = pd.to_numeric(df[column], errors="coerce")
        return df.dropna(subset=["open", "high", "low", "close"]).tail(500)

    def _empty(self, message: str) -> dict[str, Any]:
        return {
            "success": False,
            "engine": "candle_reading_vortex",
            "signal": "AGUARDAR",
            "direction": "NEUTRAL",
            "raw_direction": "NEUTRAL",
            "setup_validated": False,
            "score": 0,
            "confidence": 0,
            "current_candle": {},
            "sequence": {},
            "last_candles": [],
            "institutional_context": {},
            "risk": {},
            "anti_fake": {"blocked": True, "filters": [message]},
            "blockers": [message],
            "confirmations": [],
            "narrative": [message],
            "panel": {"summary": message},
        }

    def _read_candle(self, index: int) -> dict[str, Any]:
        row = self.df.iloc[index]
        open_price = _num(row.open)
        high = _num(row.high)
        low = _num(row.low)
        close = _num(row.close)
        volume = _num(row.volume)
        prev_close = _num(self.df["close"].iloc[index - 1], open_price) if index > 0 else open_price
        candle_range = max(high - low, abs(close) * 0.00001, 0.00001)
        body = abs(close - open_price)
        upper = high - max(open_price, close)
        lower = min(open_price, close) - low
        volume_avg = _num(self.df["volume"].iloc[max(0, index - 20): index + 1].mean(), volume or 1)
        volume_ratio = volume / volume_avg if volume_avg else 1.0
        direction = "BUY" if close > open_price else "SELL" if close < open_price else "NEUTRAL"
        body_ratio = body / candle_range
        upper_ratio = upper / candle_range
        lower_ratio = lower / candle_range
        close_location = (close - low) / candle_range
        tags = []
        if body_ratio >= 0.62:
            tags.append("candle_de_forca")
        if upper_ratio >= 0.42:
            tags.append("rejeicao_superior")
        if lower_ratio >= 0.42:
            tags.append("rejeicao_inferior")
        if volume_ratio >= 1.45 and body_ratio <= 0.35:
            tags.append("absorcao")
        if volume_ratio >= 1.65 and body_ratio >= 0.55:
            tags.append("agressao")
        if body_ratio <= 0.22:
            tags.append("exaustao_indecisao")
        if close > prev_close and close_location >= 0.65:
            tags.append("fechamento_forte_comprador")
        if close < prev_close and close_location <= 0.35:
            tags.append("fechamento_forte_vendedor")
        return {
            "time": int(self.df.index[index].timestamp()) if hasattr(self.df.index[index], "timestamp") else index,
            "open": _round(open_price),
            "high": _round(high),
            "low": _round(low),
            "close": _round(close),
            "volume": _round(volume, 4),
            "direction": direction,
            "body_pct": round(body_ratio * 100, 2),
            "upper_wick_pct": round(upper_ratio * 100, 2),
            "lower_wick_pct": round(lower_ratio * 100, 2),
            "close_location_pct": round(close_location * 100, 2),
            "volume_ratio": round(volume_ratio, 2),
            "force": round(_clamp(body_ratio * 70 + volume_ratio * 12 + abs(close - prev_close) / candle_range * 18), 2),
            "tags": tags or ["candle_neutro"],
            "reading": self._candle_text(direction, body_ratio, upper_ratio, lower_ratio, volume_ratio),
        }

    def _candle_text(self, direction, body, upper, lower, volume_ratio) -> str:
        if volume_ratio >= 1.45 and body <= 0.35:
            return "Absorcao detectada: volume alto com corpo limitado."
        if upper >= 0.42:
            return "Rejeicao superior confirmada no candle atual."
        if lower >= 0.42:
            return "Rejeicao inferior confirmada no candle atual."
        if direction == "BUY" and body >= 0.62:
            return "Candle comprador forte com fechamento dominante."
        if direction == "SELL" and body >= 0.62:
            return "Candle vendedor forte com fechamento dominante."
        return "Candle atual ainda pede confirmacao."

    def _sequence(self, candles: list[dict[str, Any]]) -> dict[str, Any]:
        last3 = candles[-3:]
        directions = [item["direction"] for item in last3]
        buy_count = directions.count("BUY")
        sell_count = directions.count("SELL")
        trigger = next((item for item in reversed(candles[-5:]) if "rejeicao_superior" in item["tags"] or "rejeicao_inferior" in item["tags"] or "absorcao" in item["tags"]), None)
        confirmation = last3[-1] if last3[-1]["force"] >= 58 and last3[-1]["direction"] in ["BUY", "SELL"] else None
        pattern_3 = self._pattern_3(last3)
        highs = [item["high"] for item in candles[-5:]]
        lows = [item["low"] for item in candles[-5:]]
        continuation = buy_count >= 3 or sell_count >= 3
        reversal = bool(trigger and confirmation and trigger["direction"] != confirmation["direction"] and confirmation["direction"] != "NEUTRAL")
        force_loss = len(candles) >= 4 and candles[-1]["force"] < candles[-2]["force"] < candles[-3]["force"]
        pullback_failure = (
            candles[-1]["close"] < min(lows[:-1]) if candles[-2]["direction"] == "BUY" else
            candles[-1]["close"] > max(highs[:-1]) if candles[-2]["direction"] == "SELL" else False
        )
        return {
            "trigger_candle": trigger,
            "confirmation_candle": confirmation,
            "pattern_3_candles": pattern_3,
            "continuation": continuation,
            "reversal": reversal,
            "pullback_failure": bool(pullback_failure),
            "force_loss": force_loss,
            "direction": "BUY" if buy_count > sell_count else "SELL" if sell_count > buy_count else "NEUTRAL",
            "reading": self._sequence_text(trigger, confirmation, pattern_3, continuation, reversal, force_loss, pullback_failure),
        }

    def _pattern_3(self, last3: list[dict[str, Any]]) -> dict[str, Any]:
        if len(last3) < 3:
            return {"active": False}
        c1, c2, c3 = last3
        sell_pattern = c1["direction"] == "BUY" and ("rejeicao_superior" in c2["tags"] or c2["direction"] == "SELL") and (c3["upper_wick_pct"] >= 25 or c3["direction"] == "SELL")
        buy_pattern = c1["direction"] == "SELL" and ("rejeicao_inferior" in c2["tags"] or c2["direction"] == "BUY") and (c3["lower_wick_pct"] >= 25 or c3["direction"] == "BUY")
        return {
            "active": bool(buy_pattern or sell_pattern),
            "direction": "BUY" if buy_pattern else "SELL" if sell_pattern else "NEUTRAL",
            "stage": "alvo_negacao_teste" if buy_pattern or sell_pattern else "incompleto",
        }

    def _sequence_text(self, trigger, confirmation, pattern_3, continuation, reversal, force_loss, pullback_failure) -> str:
        if pullback_failure:
            return "Falha de pullback detectada."
        if pattern_3.get("active"):
            return "Padrao de 3 candles completo."
        if reversal:
            return "Sequencia sugere reversao apos gatilho."
        if continuation:
            return "Sequencia mostra continuidade direcional."
        if force_loss:
            return "Perda de forca na sequencia dos ultimos candles."
        if trigger and not confirmation:
            return "Aguardando candle de confirmacao."
        return "Sequencia ainda sem setup completo."

    def _institutional_context(self, current, sequence) -> dict[str, Any]:
        technical_signal = self.technical.get("signal")
        smc_bias = self.smc.get("institutional_bias", "neutral")
        flow_pressure = self.flow.get("pressure") or self.flow.get("order_flow_bias") or "BALANCED"
        mtf_direction = self.mtf.get("dominant_direction") or self.mtf.get("direction") or "NEUTRAL"
        wyckoff_phase = self.wyckoff.get("wyckoff_phase") or self.wyckoff.get("phase")
        smc_direction = "BUY" if smc_bias == "bullish" else "SELL" if smc_bias == "bearish" else "NEUTRAL"
        flow_direction = "BUY" if flow_pressure in ["BUYER", "BUY_FLOW"] else "SELL" if flow_pressure in ["SELLER", "SELL_FLOW"] else "NEUTRAL"
        mtf_dir = "BUY" if mtf_direction == "BULLISH" else "SELL" if mtf_direction == "BEARISH" else mtf_direction
        technical_dir = "BUY" if technical_signal == "BUY" else "SELL" if technical_signal == "SELL" else "NEUTRAL"
        votes = [technical_dir, smc_direction, flow_direction, mtf_dir]
        buy_votes = votes.count("BUY")
        sell_votes = votes.count("SELL")
        direction = "BUY" if buy_votes >= 2 and buy_votes > sell_votes else "SELL" if sell_votes >= 2 and sell_votes > buy_votes else "NEUTRAL"
        return {
            "direction": direction,
            "trend": (self.technical.get("trend") or {}).get("direction"),
            "bos": (self.smc.get("structure") or {}).get("bos"),
            "choch": (self.smc.get("structure") or {}).get("choch"),
            "liquidity": self.smc.get("liquidity_zone") or self.smc.get("internal_liquidity"),
            "sweep": self.smc.get("liquidity_sweep") or {},
            "order_block": self.smc.get("relevant_order_block") or self.smc.get("nearest_order_block"),
            "fvg": self.smc.get("relevant_fvg"),
            "wyckoff": wyckoff_phase,
            "flow_direction": flow_direction,
            "mtf_direction": mtf_dir,
            "votes": {"buy": buy_votes, "sell": sell_votes, "raw": votes},
            "aligned_with_candle": direction != "NEUTRAL" and direction in [current["direction"], sequence.get("direction"), sequence.get("pattern_3_candles", {}).get("direction")],
        }

    def _risk_plan(self, current, sequence, institutional) -> dict[str, Any]:
        direction = institutional.get("direction")
        price = _num(current.get("close"))
        recent = self.df.tail(18)
        sweep = institutional.get("sweep") or {}
        ob = institutional.get("order_block") or {}
        trigger = sequence.get("trigger_candle") or current
        if direction == "BUY":
            stop_candidates = [_num(recent["low"].min()), _num(trigger.get("low"))]
            if isinstance(sweep, dict) and sweep.get("price"):
                stop_candidates.append(_num(sweep.get("price")))
            if isinstance(ob, dict) and ob.get("low"):
                stop_candidates.append(_num(ob.get("low")))
            stop = min(item for item in stop_candidates if item)
            risk = abs(price - stop)
            take_partial = price + risk
            take = price + risk * 2.2
        elif direction == "SELL":
            stop_candidates = [_num(recent["high"].max()), _num(trigger.get("high"))]
            if isinstance(sweep, dict) and sweep.get("price"):
                stop_candidates.append(_num(sweep.get("price")))
            if isinstance(ob, dict) and ob.get("high"):
                stop_candidates.append(_num(ob.get("high")))
            stop = max(item for item in stop_candidates if item)
            risk = abs(stop - price)
            take_partial = price - risk
            take = price - risk * 2.2
        else:
            stop = None
            risk = 0
            take_partial = None
            take = None
        rr = abs((take or price) - price) / risk if risk else 0
        structural = bool(stop and risk > 0)
        return {
            "entry": _round(price),
            "stop_loss": _round(stop) if stop is not None else None,
            "take_partial": _round(take_partial) if take_partial is not None else None,
            "take_profit": _round(take) if take is not None else None,
            "risk_reward": round(rr, 2),
            "structural_stop_valid": structural,
            "invalidation": _round(stop) if stop is not None else None,
            "source": "fundo/topo estrutural + candle gatilho + sweep/order block quando disponivel",
        }

    def _anti_fake(self, current, sequence, institutional, risk) -> dict[str, Any]:
        details = self.technical.get("details", {})
        lateral = (details.get("lateralization") or {}).get("detected")
        low_volume = current.get("volume_ratio", 1) < 0.65
        false_breakout = (self.smc.get("false_breakout") or {}).get("detected")
        weak_candle = current.get("force", 0) < 48
        mtf_conflict = institutional.get("mtf_direction") not in [institutional.get("direction"), "NEUTRAL", None]
        filters = []
        if lateral:
            filters.append("lateralizacao")
        if weak_candle:
            filters.append("candle_fraco")
        if low_volume:
            filters.append("volume_baixo")
        if false_breakout:
            filters.append("falso_rompimento")
        if sequence.get("force_loss"):
            filters.append("perda_de_forca")
        if sequence.get("pullback_failure"):
            filters.append("falha_de_pullback")
        if mtf_conflict:
            filters.append("conflito_timeframes")
        if not risk.get("structural_stop_valid"):
            filters.append("stop_estrutural_invalido")
        if _num(risk.get("risk_reward")) < self.MIN_RR:
            filters.append("rr_abaixo_2")
        return {"blocked": bool(filters), "filters": filters, "score": max(0, 100 - len(filters) * 14)}

    def _direction(self, current, sequence, institutional) -> str:
        candidates = [
            institutional.get("direction"),
            current.get("direction"),
            sequence.get("pattern_3_candles", {}).get("direction"),
            sequence.get("direction"),
        ]
        buy = candidates.count("BUY")
        sell = candidates.count("SELL")
        if buy >= 2 and buy > sell:
            return "BUY"
        if sell >= 2 and sell > buy:
            return "SELL"
        return "NEUTRAL"

    def _score(self, current, sequence, institutional, risk, anti_fake, direction) -> float:
        score = 35
        score += min(current.get("force", 0) * 0.22, 22)
        score += 14 if sequence.get("confirmation_candle") else 0
        score += 12 if sequence.get("pattern_3_candles", {}).get("active") else 0
        score += 16 if institutional.get("aligned_with_candle") else 0
        score += 12 if institutional.get("direction") == direction and direction != "NEUTRAL" else 0
        score += 12 if risk.get("risk_reward", 0) >= self.MIN_RR and risk.get("structural_stop_valid") else 0
        score -= len(anti_fake.get("filters", [])) * 8
        return _clamp(score)

    def _confidence(self, score, current, sequence, institutional, anti_fake) -> float:
        confidence = score * 0.76
        confidence += 8 if sequence.get("confirmation_candle") else -8
        confidence += 8 if institutional.get("aligned_with_candle") else -8
        confidence += 5 if current.get("volume_ratio", 1) >= 1 else -6
        confidence -= len(anti_fake.get("filters", [])) * 4
        return _clamp(confidence)

    def _blockers(self, score, confidence, risk, anti_fake, direction) -> list[str]:
        blockers = []
        if direction == "NEUTRAL":
            blockers.append("Aguardando candle gatilho.")
        if score < self.MIN_SCORE:
            blockers.append(f"Score candle-a-candle abaixo de {self.MIN_SCORE}.")
        if confidence < self.MIN_CONFIDENCE:
            blockers.append(f"Confianca candle-a-candle abaixo de {self.MIN_CONFIDENCE}.")
        if _num(risk.get("risk_reward")) < self.MIN_RR:
            blockers.append("RR minimo 2:1 ainda nao validado.")
        if not risk.get("structural_stop_valid"):
            blockers.append("Stop estrutural ainda invalido.")
        blockers.extend(self._filter_text(item) for item in anti_fake.get("filters", []))
        return list(dict.fromkeys(blockers))

    def _confirmations(self, current, sequence, institutional, risk, direction) -> list[str]:
        items = []
        if sequence.get("trigger_candle"):
            items.append("Candle gatilho localizado.")
        if sequence.get("confirmation_candle"):
            items.append("Candle de confirmacao presente.")
        if sequence.get("pattern_3_candles", {}).get("active"):
            items.append("Padrao de 3 candles ativo.")
        if institutional.get("aligned_with_candle"):
            items.append("Candle alinhado ao contexto institucional.")
        if institutional.get("flow_direction") in [direction, "NEUTRAL"]:
            items.append("Fluxo compativel com o setup.")
        if risk.get("structural_stop_valid") and _num(risk.get("risk_reward")) >= self.MIN_RR:
            items.append("Stop estrutural e RR minimo 2:1 validados.")
        return items[:10]

    def _narrative(self, signal, current, sequence, institutional, risk, anti_fake, blockers) -> list[str]:
        messages = []
        if sequence.get("trigger_candle") and not sequence.get("confirmation_candle"):
            messages.append("Aguardando candle de confirmacao.")
        if (institutional.get("sweep") or {}).get("detected"):
            messages.append("Sweep detectado.")
        if "rejeicao_superior" in current.get("tags", []) or "rejeicao_inferior" in current.get("tags", []):
            messages.append("Rejeicao confirmada.")
        if institutional.get("flow_direction") == "BUY":
            messages.append("Fluxo comprador aumentando.")
        if institutional.get("flow_direction") == "SELL":
            messages.append("Fluxo vendedor aumentando.")
        if "volume_baixo" in anti_fake.get("filters", []):
            messages.append("Entrada cancelada por falta de volume.")
        if signal in ["COMPRA", "VENDA"]:
            messages.append("Setup validado.")
        elif blockers:
            messages.append(blockers[0])
        messages.append(current.get("reading", "Leitura do candle atual indisponivel."))
        return list(dict.fromkeys(messages))[:8]

    def _panel(self, current, sequence, institutional, risk, blockers) -> dict[str, Any]:
        return {
            "current_candle": current.get("reading"),
            "sequence": sequence.get("reading"),
            "active_confluences": self._confirmations(current, sequence, institutional, risk, institutional.get("direction")),
            "entry_reason": "Setup validado por candle + contexto institucional." if not blockers else "",
            "wait_reason": blockers[0] if blockers else "",
            "invalidation": risk.get("invalidation"),
            "entry": risk.get("entry"),
            "stop_loss": risk.get("stop_loss"),
            "take_partial": risk.get("take_partial"),
            "take_profit": risk.get("take_profit"),
        }

    def _filter_text(self, item: str) -> str:
        labels = {
            "lateralizacao": "Anti-fake: lateralizacao.",
            "candle_fraco": "Anti-fake: candle fraco.",
            "volume_baixo": "Anti-fake: volume baixo.",
            "falso_rompimento": "Anti-fake: falso rompimento.",
            "perda_de_forca": "Anti-fake: perda de forca.",
            "falha_de_pullback": "Anti-fake: falha de pullback.",
            "conflito_timeframes": "Anti-fake: conflito entre timeframes.",
            "stop_estrutural_invalido": "Anti-fake: stop estrutural invalido.",
            "rr_abaixo_2": "Anti-fake: RR abaixo de 2:1.",
        }
        return labels.get(item, item)


def build_candle_reading(candles: pd.DataFrame, symbol: str, timeframe: str, **kwargs: Any) -> dict[str, Any]:
    return CandleReadingEngine(candles, symbol, timeframe, **kwargs).analyze()

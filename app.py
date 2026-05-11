import os
import math

import requests
from flask import Flask, jsonify, redirect, render_template, request, session, url_for

from ia.analysis import (
    AISignalGenerator,
    BacktestEngine,
    OperationalScore,
    RiskManagement,
    TechnicalAnalysis,
    create_heatmap_data,
    generate_ai_reasoning,
)
from ia.ai_narrative_engine import AINarrativeEngine
from ia.binance_client import TimedCache
from ia.confluence_engine import DISCLAIMER, build_confluence_analysis
from ia.context_engine import ContextEngine
from ia.data_generator import generate_realistic_data
from ia.execution_engine import ExecutionEngine
from ia.final_score import calculate_final_score
from ia.institutional import OperationalValidator, PatternLearner, ProfessionalBacktest
from ia.flow_engine import build_flow_context
from ia.institutional_confluence_engine import build_institutional_confluence
from ia.institutional_decision_engine import build_institutional_decision
from ia.institutional_signal_engine import build_institutional_signal
from ia.live_trading import build_live_status
from ia.live_signals import LiveSignalManager
from ia.market_data_service import build_market_data_snapshot
from ia.market_data_router import MarketDataRouter
from ia.multi_timeframe_engine import build_institutional_mtf_context
from ia.narrative_engine import build_operational_narrative
from ia.operational_engine import build_operational_panel
from ia.operational_signal import build_operational_signal
from ia.operacional_live_engine import build_operacional_live_status
from ia.operacional_reader import build_candle_flow, build_operacional_context, build_operacional_reading
from ia.overlay_engine import OverlayEngine
from ia.risk_engine import build_risk_plan
from ia.smart_money import analyze_smart_money
from ia.smc_engine import build_smc_context
from ia.technical_reader import read_technical
from ia.elliott_wave import read_elliott_wave
from ia.tape_reading import read_tape
from ia.volume_reader import read_volume
from ia.websocket_manager import build_binance_kline_stream
from ia.wyckoff_reader import read_wyckoff_advanced
from ia.wyckoff_engine import build_wyckoff_context
from ia.user_store import (
    add_watchlist,
    authenticate,
    create_alert,
    create_user,
    current_user_id,
    get_setting,
    get_watchlist,
    init_db,
    list_alerts,
    login_required,
    remove_watchlist,
    save_setting,
)


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "dev-secret-change-me")
init_db()

market = MarketDataRouter()
candle_cache = TimedCache(ttl_seconds=12)
ticker_cache = TimedCache(ttl_seconds=8)
chart_payload_cache = TimedCache(ttl_seconds=8)
analysis_response_cache = TimedCache(ttl_seconds=10)
analysis_core_cache = TimedCache(ttl_seconds=10)
live_status_cache = TimedCache(ttl_seconds=3)
live_signal_manager = LiveSignalManager()
live_context_engine = ContextEngine()
analysis_context_engine = ContextEngine()
live_narrative_engine = AINarrativeEngine()
live_overlay_engine = OverlayEngine()
execution_engine = ExecutionEngine()
operacional_live_signals = []

SUPPORTED_TIMEFRAMES = ["1m", "5m", "15m", "1h", "4h", "1d", "1w"]
HEATMAP_TIMEFRAMES = ["5m", "15m", "1h", "4h", "1d"]
DEFAULT_SYMBOL = "BTCUSDT"


def normalize_symbol(symbol):
    value = (symbol or DEFAULT_SYMBOL).replace("-", "").replace("/", "").upper()
    if not value:
        return DEFAULT_SYMBOL
    return value


def normalize_timeframe(timeframe):
    return timeframe if timeframe in SUPPORTED_TIMEFRAMES else "1h"


def sanitize_json(value):
    if isinstance(value, dict):
        return {key: sanitize_json(item) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitize_json(item) for item in value]
    if isinstance(value, tuple):
        return [sanitize_json(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def default_signal(df):
    price = float(df["close"].iloc[-1]) if df is not None and len(df) else 0.0
    return {
        "signal_type": "neutro",
        "score": 0.0,
        "confidence": 0.0,
        "components": {"trend_signal": {"value": "sideways", "strength": 0}},
        "timestamp": None,
        "price": price,
        "indicators": {
            "rsi": 50.0,
            "macd": 0.0,
            "signal": 0.0,
            "histogram": 0.0,
            "ema9": price,
            "ema21": price,
            "ema200": price,
            "bollinger_upper": price,
            "bollinger_middle": price,
            "bollinger_lower": price,
            "atr": max(price * 0.01, 0.0001),
            "vwap": price,
            "volume": 0.0,
            "volume_sma": 0.0,
        },
    }


def default_smc():
    return {
        "smc_score": 50,
        "institutional_bias": "neutral",
        "has_bos": False,
        "bos": "none",
        "has_choch": False,
        "choch": "none",
        "liquidity_zone": None,
        "nearest_order_block": None,
        "relevant_order_block": None,
        "relevant_fvg": None,
        "liquidity_sweep": {"detected": False, "side": "none", "zone": None},
        "false_breakout": {"detected": False, "direction": "none", "level": None},
        "inducement": {"detected": False, "side": "none", "zone": None},
        "institutional_zone": None,
        "institutional_zones": [],
        "confirmed": False,
        "invalidated": False,
        "score_adjustment": 0,
        "reasons": [],
        "confirmations": [],
        "invalidations": [],
        "explanation": "Smart Money sem leitura suficiente.",
        "structure": {"trend": "neutral", "bos": "none", "choch": "none"},
        "order_blocks": [],
        "liquidity": [],
        "fair_value_gaps": [],
    }


def default_volume():
    return {
        "volume_above_average": False,
        "buyer_volume": 0,
        "seller_volume": 0,
        "dominant_side": "BALANCED",
        "abnormal_volume": False,
        "exhaustion": {"detected": False, "side": "NONE"},
        "absorption": {"detected": False, "side": "NONE"},
        "breakout_confirmation": {"confirmed": False, "direction": "NONE", "level": None},
        "price_volume_divergence": {"detected": False, "type": "NONE"},
        "score_adjustment": 0,
        "signal": "NEUTRAL_VOLUME",
        "confidence": 0,
        "reasons": [],
        "metrics": {},
    }


def default_validation():
    return {
        "entry_quality": {
            "quality": "neutra",
            "probability": 0,
            "invalidated": False,
            "aligned_with_smc": False,
        },
        "false_breakout": {"detected": False, "side": "none", "level": None},
        "pullback": {"detected": False, "side": "none", "strength": 0},
        "lateralization": {"detected": False, "range_pct": 0, "atr_pct": 0},
    }


def default_technical(df):
    price = float(df["close"].iloc[-1]) if df is not None and len(df) else 0
    return {
        "signal": "NEUTRAL",
        "score": 0,
        "confidence": 0,
        "trend": {"direction": "SIDEWAYS", "price_above_ema200": False, "ema_stack": {}},
        "confirmations": [],
        "invalidations": ["Analise tecnica indisponivel."],
        "entry_price": price,
        "stop_loss": price,
        "take_profit_1": price,
        "take_profit_2": price,
        "take_profit_3": price,
        "explanation": "Cenario neutro / sem entrada no momento.",
        "details": {},
    }


def default_final_score(levels=None):
    levels = levels or {}
    return {
        "score": 0,
        "confidence": 0,
        "signal": "NEUTRAL",
        "classification": "Nao operar",
        "entry_aggressive": False,
        "entry_conservative": False,
        "stop_loss": levels.get("stop_loss"),
        "take_profit_1": levels.get("alvo_1"),
        "take_profit_2": levels.get("alvo_2"),
        "take_profit_3": levels.get("alvo_2"),
        "technical_reasons": [],
        "invalidation_reasons": ["Score indisponivel; grafico mantido em modo neutro."],
        "components": {},
        "explanation": "Cenario neutro / sem entrada no momento.",
    }


def default_wyckoff():
    return {
        "phase": "indefinida",
        "wyckoff_phase": "indefinida",
        "probable_market_phase": "indefinida",
        "bias": "neutral",
        "accumulation": False,
        "distribution": False,
        "spring": False,
        "upthrust": False,
        "climax": False,
        "selling_climax": False,
        "buying_climax": False,
        "test": False,
        "range": {},
        "volume_ratio": 0,
        "score_adjustment": 0,
        "confirmations": [],
        "invalidations": [],
        "explanation": "Wyckoff sem leitura suficiente.",
    }


def default_elliott_wave():
    return {
        "wave_count": {},
        "current_wave": "indefinida",
        "wave_bias": "neutral",
        "impulse_structure": {"detected": False, "quality": 0, "direction": "neutral"},
        "corrective_structure": {"detected": False, "pattern": "indefinido", "quality": 0},
        "confidence": 0,
        "reversal_risk": "indefinido",
        "possible_stage": "indefinida",
        "confirmations": [],
        "invalidations": ["Elliott Wave indisponivel."],
        "score_adjustment": 0,
        "explanation": "Elliott Wave sem leitura suficiente.",
    }


def default_tape_reading():
    return {
        "source": "fallback_unavailable",
        "order_flow_bias": "BALANCED_FLOW",
        "buy_aggression": 0,
        "sell_aggression": 0,
        "absorption": {"detected": False, "side": "NONE"},
        "imbalance": 0,
        "pressure": "equilibrada",
        "aggressor_volume": 0,
        "flow_score": 50,
        "confirmations": [],
        "invalidations": ["Tape reading indisponivel."],
        "score_adjustment": 0,
        "metrics": {},
        "explanation": "Fluxo sem dados suficientes.",
    }


def build_advanced_confluence(score, technical, smc, volume, mtf_confluence, wyckoff, elliott_wave, tape_reading, levels):
    def norm(value, default=50):
        try:
            return max(0, min(100, float(value)))
        except Exception:
            return default

    technical_score = norm(technical.get("score", score))
    smc_score = norm(smc.get("smc_score", 50))
    volume_score = norm(volume.get("confidence", 50))
    tape_score = norm(tape_reading.get("flow_score", 50))
    volume_flow_score = (volume_score * 0.45) + (tape_score * 0.55)
    mtf_score = 85 if mtf_confluence.get("strong_signal_allowed") else norm(mtf_confluence.get("average_strength", 45))
    wyckoff_score = (norm(wyckoff.get("accumulation_score", 50)) + (100 - norm(wyckoff.get("distribution_score", 50)))) / 2
    elliott_score = norm(elliott_wave.get("confidence", 35))
    rr = levels.get("risco_retorno", 0)
    risk_score = 88 if rr >= 1.8 else 68 if rr >= 1.2 else 35
    weights = {
        "technical_indicators": 0.25,
        "smart_money": 0.20,
        "volume_flow": 0.20,
        "multi_timeframe": 0.15,
        "wyckoff": 0.10,
        "elliott_wave": 0.05,
        "risk_reward": 0.05,
    }
    components = {
        "technical_indicators": round(technical_score, 2),
        "smart_money": round(smc_score, 2),
        "volume_flow": round(volume_flow_score, 2),
        "multi_timeframe": round(mtf_score, 2),
        "wyckoff": round(wyckoff_score, 2),
        "elliott_wave": round(elliott_score, 2),
        "risk_reward": round(risk_score, 2),
    }
    advanced_score = round(sum(components[key] * weights[key] for key in weights), 2)
    confirmations = []
    invalidations = []
    for block in [wyckoff, elliott_wave, tape_reading]:
        confirmations.extend(block.get("confirmations", [])[:3])
        invalidations.extend(block.get("invalidations", [])[:3])
    return {
        "score": advanced_score,
        "weights": weights,
        "components": components,
        "confirmations": confirmations[:10],
        "invalidations": invalidations[:10],
        "explanation": (
            f"Confluencia avancada {advanced_score}/100 com Wyckoff {wyckoff.get('wyckoff_phase', '--')}, "
            f"Elliott {elliott_wave.get('current_wave', '--')} e fluxo {tape_reading.get('order_flow_bias', '--')}."
        ),
    }


def build_signal_cards_decision(signal, final_score, confluence_ai, operational_signal, operational_state,
                                advanced_confluence, smc, volume, mtf_confluence, wyckoff,
                                elliott_wave, tape_reading, levels, institutional_decision=None):
    def upper(value):
        return str(value or "").upper()

    def as_number(value, default=0):
        try:
            return float(value)
        except Exception:
            return default

    institutional_decision = institutional_decision or {}
    forces = institutional_decision.get("forces", {})
    score = as_number(institutional_decision.get("score"), as_number(advanced_confluence.get("score"), as_number(operational_signal.get("score"), 0)))
    confidence = max(
        as_number(institutional_decision.get("confidence"), 0),
        score,
        as_number(operational_signal.get("confidence"), 0),
        as_number(confluence_ai.get("confidence"), 0),
        as_number(final_score.get("confidence"), 0),
        as_number(signal.get("confidence"), 0),
    )
    rr = as_number(operational_signal.get("risk_reward"), as_number(levels.get("risco_retorno"), 0))
    raw_signals = [
        operational_signal.get("signal"),
        confluence_ai.get("signal"),
        final_score.get("signal"),
        signal.get("signal_type"),
        mtf_confluence.get("dominant_direction"),
        smc.get("institutional_bias"),
        volume.get("signal"),
        tape_reading.get("order_flow_bias"),
        wyckoff.get("bias"),
        elliott_wave.get("wave_bias"),
    ]

    bullish = 0
    bearish = 0
    waiting = 0
    reasons = []

    for item in map(upper, raw_signals):
        if item in ["BUY", "COMPRA", "BULLISH", "BULLISH_VOLUME", "BUY_FLOW"]:
            bullish += 2
        if item in ["SELL", "VENDA", "BEARISH", "BEARISH_VOLUME", "SELL_FLOW"]:
            bearish += 2
        if "AGUARDAR" in item or "WAIT" in item:
            waiting += 2

    if smc.get("confirmed"):
        if upper(smc.get("institutional_bias")) == "BULLISH":
            bullish += 2
            reasons.append("SMC confirma vies comprador.")
        elif upper(smc.get("institutional_bias")) == "BEARISH":
            bearish += 2
            reasons.append("SMC confirma vies vendedor.")
    if smc.get("has_bos") and smc.get("structure", {}).get("trend") == "bullish":
        bullish += 1
    if smc.get("has_bos") and smc.get("structure", {}).get("trend") == "bearish":
        bearish += 1
    if mtf_confluence.get("dominant_direction") == "BULLISH":
        bullish += 2 if mtf_confluence.get("confirmed_timeframes", 0) >= 3 else 1
    if mtf_confluence.get("dominant_direction") == "BEARISH":
        bearish += 2 if mtf_confluence.get("confirmed_timeframes", 0) >= 3 else 1
    if wyckoff.get("wyckoff_phase") == "acumulacao" or wyckoff.get("spring"):
        bullish += 1
    if wyckoff.get("wyckoff_phase") == "distribuicao" or wyckoff.get("upthrust"):
        bearish += 1
    if elliott_wave.get("impulse_structure", {}).get("detected") and elliott_wave.get("wave_bias") == "bullish":
        bullish += 1
    if elliott_wave.get("impulse_structure", {}).get("detected") and elliott_wave.get("wave_bias") == "bearish":
        bearish += 1
    if tape_reading.get("absorption", {}).get("detected"):
        waiting += 1
        reasons.append("Absorcao no fluxo pede confirmacao.")

    invalidated = (
        operational_state.get("state") == "invalidated"
        or smc.get("invalidated")
        or smc.get("false_breakout", {}).get("detected")
        or (rr > 0 and rr < 1)
    )
    if institutional_decision.get("invalidations"):
        invalidated = True
    weak_or_wait = (
        operational_state.get("state") in ["loading", "waiting_confirmation"]
        or volume.get("signal") == "NEUTRAL_VOLUME"
        or tape_reading.get("order_flow_bias") == "BALANCED_FLOW"
        or waiting > 0
    )
    conflict = bullish > 0 and bearish > 0 and abs(bullish - bearish) <= 2
    buy_force = as_number(forces.get("buy"), min(100, bullish * 8))
    sell_force = as_number(forces.get("sell"), min(100, bearish * 8))
    wait_force = as_number(forces.get("wait"), min(100, waiting * 12 + (35 if weak_or_wait else 0)))
    neutral_force = as_number(forces.get("neutral"), max(0, 55 - abs(buy_force - sell_force) * 0.5))
    dominant_key = "buy" if buy_force > sell_force else "sell" if sell_force > buy_force else "neutral"
    dominant_votes = max(bullish, bearish)

    institutional_signal = institutional_decision.get("signal")
    if institutional_signal == "COMPRA" and not invalidated:
        active = "buy"
        reason = institutional_decision.get("narrative") or "Compra liberada pela confluencia institucional."
    elif institutional_signal == "VENDA" and not invalidated:
        active = "sell"
        reason = institutional_decision.get("narrative") or "Venda liberada pela confluencia institucional."
    elif institutional_signal == "AGUARDAR":
        active = "wait"
        reason = institutional_decision.get("narrative") or "IA aguarda timing operacional."
    elif institutional_signal == "NEUTRO":
        active = "neutral"
        reason = institutional_decision.get("narrative") or "Mercado sem direcao institucional."
    elif invalidated:
        active = "wait"
        reason = "Cenario exige aguardar por invalidacao, falso rompimento ou risco/retorno ruim."
    elif score < 32 and dominant_votes < 4:
        active = "neutral"
        reason = "Sem vies dominante e score baixo."
    elif conflict:
        active = "wait"
        reason = "Conflito entre leituras compradoras e vendedoras."
    elif weak_or_wait and score < 68:
        active = "wait"
        reason = "Confluencia ainda sem confirmacao suficiente."
    elif dominant_key in ["buy", "sell"] and dominant_votes >= 4 and score >= 48:
        active = dominant_key
        reason = "Vies dominante alinhado com confluencia da IA Completa."
    elif score >= 40:
        active = "wait"
        reason = "Aguardar confirmacao para liberar direcao."
    else:
        active = "neutral"
        reason = "Mercado sem direcao clara."

    intensity = "forte" if confidence >= 76 else "moderada" if confidence >= 55 else "baixa"
    labels = {
        "buy": "COMPRA",
        "sell": "VENDA",
        "neutral": "NEUTRO",
        "wait": "AGUARDAR CONFIRMACAO",
    }
    cards = {}
    force_map = {
        "buy": buy_force,
        "sell": sell_force,
        "neutral": neutral_force,
        "wait": wait_force,
    }
    for key, label in labels.items():
        card_force = round(max(0, min(100, force_map.get(key, 0))), 1)
        cards[key] = {
            "label": label,
            "active": key == active,
            "confidence": round(confidence, 1) if key == active else card_force,
            "score": round(score, 1) if key == active else card_force,
            "force": card_force,
            "intensity": intensity if key == active else "inativa",
            "text": f"{card_force:.0f}% FORCA" if key in ["buy", "sell"] else f"{card_force:.0f}%",
        }
    return {
        "active": active,
        "label": labels[active],
        "confidence": round(confidence, 1),
        "score": round(score, 1),
        "intensity": intensity,
        "votes": {"bullish": bullish, "bearish": bearish, "waiting": waiting},
        "forces": {"buy": round(buy_force, 1), "sell": round(sell_force, 1), "neutral": round(neutral_force, 1), "wait": round(wait_force, 1)},
        "reason": reason if not reasons else f"{reason} {reasons[0]}",
        "cards": cards,
    }


def build_institutional_payload(smc, wyckoff):
    smc = smc or default_smc()
    wyckoff = wyckoff or default_wyckoff()
    confirmations = list(smc.get("confirmations") or [])
    confirmations.extend(wyckoff.get("confirmations") or [])
    invalidations = list(smc.get("invalidations") or [])
    invalidations.extend(wyckoff.get("invalidations") or [])
    explanation_parts = [text for text in [smc.get("explanation"), wyckoff.get("explanation")] if text]
    return {
        "smc_score": smc.get("smc_score", 50),
        "wyckoff_phase": wyckoff.get("wyckoff_phase") or wyckoff.get("phase", "indefinida"),
        "institutional_bias": smc.get("institutional_bias", wyckoff.get("bias", "neutral")),
        "relevant_order_block": smc.get("relevant_order_block") or smc.get("nearest_order_block"),
        "relevant_fvg": smc.get("relevant_fvg"),
        "liquidity_zone": smc.get("liquidity_zone"),
        "liquidity_sweep": smc.get("liquidity_sweep", {"detected": False, "side": "none", "zone": None}),
        "false_breakout": smc.get("false_breakout", {"detected": False, "direction": "none", "level": None}),
        "confirmations": confirmations[:12],
        "invalidations": invalidations[:12],
        "explanation": " ".join(explanation_parts) or "Sem contexto institucional dominante.",
    }


def load_market_data(symbol, timeframe, limit=500):
    symbol = normalize_symbol(symbol)
    timeframe = normalize_timeframe(timeframe)
    limit = max(60, min(int(limit or 500), 1000))
    key = f"klines:{symbol}:{timeframe}:{limit}"
    cached = candle_cache.get(key)
    if cached is not None:
        return cached
    try:
        return candle_cache.set(key, market.get_klines(symbol, timeframe, limit))
    except Exception:
        if market.identify_market(symbol) == "crypto":
            if symbol != DEFAULT_SYMBOL:
                fallback_key = f"klines:{DEFAULT_SYMBOL}:{timeframe}:{limit}"
                cached = candle_cache.get(fallback_key)
                if cached is not None:
                    return cached
                return candle_cache.set(fallback_key, market.get_klines(DEFAULT_SYMBOL, timeframe, limit))
            df = generate_realistic_data(DEFAULT_SYMBOL, days=90, interval=timeframe)
            return candle_cache.set(key, df.tail(limit))
        raise


def get_cached_chart_payload(symbol, timeframe, limit):
    symbol = normalize_symbol(symbol)
    timeframe = normalize_timeframe(timeframe)
    key = f"chart:{symbol}:{timeframe}:{limit}"
    cached = chart_payload_cache.get(key)
    if cached is not None:
        return cached
    df = load_market_data(symbol, timeframe, limit)
    payload = TechnicalAnalysis(df).chart_payload()
    result = {"df": df, "payload": payload}
    return chart_payload_cache.set(key, result)


def operacional_chart_payload(df, symbol, timeframe):
    candles = []
    for idx, row in df.tail(500).iterrows():
        timestamp = int(idx.timestamp()) if hasattr(idx, "timestamp") else len(candles)
        candles.append({
            "time": timestamp,
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
        })
    return {
        "success": True,
        "module": "operacional_leitura_grafica",
        "isolated": True,
        "symbol": symbol,
        "timeframe": timeframe,
        "operacional_chart": {
            "candles": candles,
            "overlays": {},
            "indicators": [],
        },
        "candles": candles,
        "overlays": {},
        "indicators": [],
        "message": "Candles puros para leitura grafica operacional, sem indicadores padrao.",
    }


def build_analysis(symbol, timeframe, limit=500):
    symbol = normalize_symbol(symbol)
    timeframe = normalize_timeframe(timeframe)
    limit = max(60, min(int(limit or 500), 1000))
    cache_key = f"analysis-core:{symbol}:{timeframe}:{limit}"
    cached = analysis_core_cache.get(cache_key)
    if cached is not None:
        return cached

    df = load_market_data(symbol, timeframe, limit)
    ta = TechnicalAnalysis(df)
    try:
        signal = AISignalGenerator(ta).generate_signal()
    except Exception:
        signal = default_signal(df)
    atr = signal["indicators"]["atr"]
    try:
        levels = RiskManagement(df["close"].iloc[-1], atr).calculate_levels(signal["signal_type"])
    except Exception:
        levels = RiskManagement(float(df["close"].iloc[-1]), max(float(df["close"].iloc[-1]) * 0.01, 0.0001)).calculate_levels("neutro")
    try:
        patterns = ta.identify_candle_patterns()
    except Exception:
        patterns = []
    try:
        score = OperationalScore.calculate_score(
            signal["indicators"],
            patterns,
            signal["components"]["trend_signal"]["value"],
            signal["score"],
        )
    except Exception:
        score = 50
    try:
        smc = analyze_smart_money(df, signal["signal_type"])
    except Exception:
        smc = default_smc()
    score = int(max(0, min(100, score + smc.get("score_adjustment", 0))))
    try:
        volume_analysis = read_volume(df)
    except Exception:
        volume_analysis = default_volume()
    try:
        wyckoff = read_wyckoff_advanced(df)
    except Exception:
        wyckoff = default_wyckoff()
    try:
        elliott_wave = read_elliott_wave(df)
    except Exception:
        elliott_wave = default_elliott_wave()
    try:
        tape_reading = read_tape(df)
    except Exception:
        tape_reading = default_tape_reading()
    score = int(max(0, min(100, score
        + volume_analysis.get("score_adjustment", 0)
        + wyckoff.get("score_adjustment", 0)
        + elliott_wave.get("score_adjustment", 0)
        + tape_reading.get("score_adjustment", 0)
    )))
    try:
        validation = OperationalValidator(df, signal, levels, smc).validate()
    except Exception:
        validation = default_validation()
    if smc.get("invalidated"):
        validation["entry_quality"]["invalidated"] = True
        validation["entry_quality"]["quality"] = "ruim"
        validation["entry_quality"]["probability"] = min(validation["entry_quality"]["probability"], 42)
    elif smc.get("confirmed"):
        validation["entry_quality"]["probability"] = min(95, validation["entry_quality"]["probability"] + 8)
    result = (df, ta, signal, levels, patterns, score, smc, validation, volume_analysis, wyckoff, elliott_wave, tape_reading)
    return analysis_core_cache.set(cache_key, result)


def direction_from_signal(signal_type, technical_signal=None):
    signal_text = (technical_signal or signal_type or "").lower()
    if any(word in signal_text for word in ["buy", "compra", "entrada"]):
        return "BULLISH"
    if any(word in signal_text for word in ["sell", "venda"]):
        return "BEARISH"
    return "NEUTRAL"


def direction_from_trend(trend):
    direction = trend.get("direction", "SIDEWAYS")
    if "BULLISH" in direction:
        return "BULLISH"
    if "BEARISH" in direction:
        return "BEARISH"
    return "NEUTRAL"


def build_multi_timeframe(symbol, timeframes=None):
    timeframes = timeframes or HEATMAP_TIMEFRAMES
    analysis = {}
    counts = {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0}
    strengths = {"BULLISH": [], "BEARISH": [], "NEUTRAL": []}

    for timeframe in timeframes:
        try:
            df, _, signal, _, _, score, _, validation, volume_analysis, _, _, _ = build_analysis(symbol, timeframe, limit=500)
        except Exception:
            df = load_market_data(DEFAULT_SYMBOL, timeframe, 500)
            signal = default_signal(df)
            score = 50
            validation = default_validation()
            volume_analysis = default_volume()
        try:
            technical = read_technical(df)
        except Exception:
            technical = {
                "signal": "NEUTRAL",
                "score": 0,
                "confidence": 0,
                "trend": {"direction": "SIDEWAYS"},
            }
        signal_direction = direction_from_signal(signal["signal_type"], technical["signal"])
        trend_direction = direction_from_trend(technical["trend"])
        direction = signal_direction if signal_direction != "NEUTRAL" else trend_direction
        strength = int(max(0, min(100, round((score * 0.55) + (technical["confidence"] * 0.35) + (abs(technical["score"]) * 3)))))
        counts[direction] += 1
        strengths[direction].append(strength)
        analysis[timeframe] = {
            "trend": technical["trend"]["direction"],
            "trend_direction": trend_direction,
            "signal": signal["signal_type"],
            "technical_signal": technical["signal"],
            "direction": direction,
            "strength": strength,
            "confidence": signal["confidence"],
            "score": signal["score"],
            "operational_score": score,
            "probability": validation["entry_quality"]["probability"],
            "volume_signal": volume_analysis["signal"],
        }

    dominant_direction = max(counts, key=lambda item: counts[item])
    dominant_count = counts[dominant_direction]
    strong_signal_allowed = dominant_direction != "NEUTRAL" and dominant_count >= 3
    average_strength = int(round(sum(strengths[dominant_direction]) / len(strengths[dominant_direction]))) if strengths[dominant_direction] else 0
    confluence = {
        "dominant_direction": dominant_direction,
        "confirmed_timeframes": dominant_count,
        "required_confirmations": 3,
        "strong_signal_allowed": strong_signal_allowed,
        "average_strength": average_strength,
        "counts": counts,
    }
    return analysis, confluence


def apply_mtf_gate(signal, score, validation, confluence):
    gated_signal = dict(signal)
    if confluence["strong_signal_allowed"]:
        if confluence["dominant_direction"] == "BULLISH" and any(word in signal["signal_type"] for word in ["compra", "entrada"]):
            gated_signal["signal_type"] = "entrada_agressiva" if score >= 70 else "entrada_conservadora"
        elif confluence["dominant_direction"] == "BEARISH" and "venda" in signal["signal_type"]:
            gated_signal["signal_type"] = "venda_agressiva" if score >= 70 else "venda"
        gated_signal["mtf_confirmed"] = True
    else:
        if signal["signal_type"] in ["entrada_agressiva", "entrada_conservadora", "venda_agressiva"]:
            gated_signal["signal_type"] = "compra" if any(word in signal["signal_type"] for word in ["compra", "entrada"]) else "venda"
        gated_signal["mtf_confirmed"] = False
        validation["entry_quality"]["probability"] = min(validation["entry_quality"]["probability"], 58)
    return gated_signal, validation


def build_operational_state(signal, validation, smc, volume_analysis, final_score, mtf_confluence, levels):
    signal_type = final_score.get("signal", "NEUTRAL")
    invalidation_reasons = []
    strong_invalidators = {
        "false_breakout": False,
        "support_loss": False,
        "choch_against_signal": False,
        "opposite_volume": False,
        "bad_risk_reward": False,
    }

    false_breakout = smc.get("false_breakout", {})
    if false_breakout.get("detected"):
        strong_invalidators["false_breakout"] = True
        invalidation_reasons.append("Falso rompimento detectado.")

    structure = smc.get("structure", {})
    choch = structure.get("choch", "none")
    if (signal_type == "BUY" and choch == "bearish") or (signal_type == "SELL" and choch == "bullish"):
        strong_invalidators["choch_against_signal"] = True
        invalidation_reasons.append("CHOCH contra o sinal atual.")

    dominant_volume = volume_analysis.get("dominant_side")
    if (signal_type == "BUY" and dominant_volume == "SELLER") or (signal_type == "SELL" and dominant_volume == "BUYER"):
        strong_invalidators["opposite_volume"] = True
        invalidation_reasons.append("Volume dominante contra o sinal.")

    rr = float(levels.get("risco_retorno", 0))
    if rr < 1:
        strong_invalidators["bad_risk_reward"] = True
        invalidation_reasons.append(f"Risco/retorno ruim: 1:{rr:.2f}.")

    technical_invalidations = final_score.get("invalidation_reasons", [])
    if any("suporte" in reason.lower() and "perda" in reason.lower() for reason in technical_invalidations):
        strong_invalidators["support_loss"] = True
        invalidation_reasons.append("Perda de suporte relevante.")

    has_strong_invalidation = any(strong_invalidators.values())
    confluence_ok = mtf_confluence.get("strong_signal_allowed", False)
    score = float(final_score.get("score", 0))

    if has_strong_invalidation:
        state = "invalidated"
        message = "Cenario invalidado por fator tecnico forte."
    elif signal_type == "NEUTRAL" or signal.get("signal_type") == "neutro":
        state = "neutral"
        message = "Cenario neutro / sem entrada no momento."
    elif not confluence_ok or score < 7:
        state = "waiting_confirmation"
        message = "Aguardar confirmacao."
    else:
        state = "confirmed"
        message = "Sinal confirmado."

    return {
        "state": state,
        "message": message,
        "strong_invalidators": strong_invalidators,
        "invalidation_reasons": invalidation_reasons,
        "confluence_ok": confluence_ok,
        "ready": True,
    }


def get_ticker(symbol):
    symbol = normalize_symbol(symbol)
    cached = ticker_cache.get(symbol)
    if cached:
        return cached
    try:
        return ticker_cache.set(symbol, market.get_24h_ticker(symbol))
    except Exception:
        if symbol != DEFAULT_SYMBOL and market.identify_market(symbol) == "crypto":
            return get_ticker(DEFAULT_SYMBOL)
        meta = market.last_meta(symbol)
        return {"lastPrice": 0, "priceChangePercent": 0, "quoteVolume": 0, "volume": 0, "count": 0, **meta}


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/advanced")
@login_required
def advanced():
    return render_template("advanced.html")


@app.route("/live")
@login_required
def live():
    return render_template("live.html")


@app.route("/operacional")
@login_required
def operacional():
    return render_template("operacional.html")


@app.route("/operacional-live")
@login_required
def operacional_live():
    return render_template("operacional_live.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        user = authenticate(username, password)
        if user:
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            return redirect(url_for("advanced"))
        return render_template("login.html", error="Usuario ou senha invalidos")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/api/register", methods=["POST"])
def api_register():
    payload = request.get_json(silent=True) or {}
    try:
        create_user(payload["username"], payload["password"])
        return jsonify({"success": True})
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 400


@app.route("/api/candles/<symbol>/<timeframe>")
def get_candles(symbol, timeframe):
    requested_symbol = normalize_symbol(symbol)
    timeframe = normalize_timeframe(timeframe)
    try:
        limit = int(request.args.get("limit", 200))
        cached_payload = get_cached_chart_payload(requested_symbol, timeframe, limit)
        df = cached_payload["df"]
        payload = cached_payload["payload"]
        ticker = get_ticker(requested_symbol)
        market_meta = market.last_meta(requested_symbol)
        response = {
            "success": True,
            "source": market_meta.get("source", "binance"),
            "requested_symbol": requested_symbol,
            "symbol": requested_symbol if requested_symbol == DEFAULT_SYMBOL else normalize_symbol(symbol),
            "market": market_meta.get("market"),
            "market_label": market_meta.get("market_label"),
            "market_status": market_meta.get("market_status", "unknown"),
            "market_message": market_meta.get("message"),
            "streaming": market_meta.get("streaming", False),
            "fallback": market_meta.get("fallback", False),
            "timeframe": timeframe,
            "candles": payload.get("candles", []),
            "volumes": payload.get("volumes", []),
            "overlays": payload.get("overlays", {}),
            "ticker": {
                "lastPrice": float(ticker.get("lastPrice", df["close"].iloc[-1])),
                "priceChangePercent": float(ticker.get("priceChangePercent", 0)),
                "quoteVolume": float(ticker.get("quoteVolume", 0)),
                "volume": float(ticker.get("volume", 0)),
                "count": int(ticker.get("count", 0)),
                "bid": ticker.get("bid"),
                "ask": ticker.get("ask"),
                "spread": ticker.get("spread"),
                "spread_points": ticker.get("spread_points"),
            },
            "quote": {
                "bid": market_meta.get("bid") or ticker.get("bid"),
                "ask": market_meta.get("ask") or ticker.get("ask"),
                "spread": market_meta.get("spread") or ticker.get("spread"),
                "provider_symbol": market_meta.get("provider_symbol") or ticker.get("provider_symbol"),
            },
        }
        return jsonify(sanitize_json(response))
    except Exception as error:
        if market.identify_market(requested_symbol) != "crypto":
            meta = market.last_meta(requested_symbol)
            return jsonify(sanitize_json({
                "success": False,
                "source": meta.get("source"),
                "requested_symbol": requested_symbol,
                "symbol": requested_symbol,
                "market": meta.get("market"),
                "market_label": meta.get("market_label"),
                "market_status": "no_data",
                "market_message": meta.get("message") or f"Nao ha dados disponiveis para {requested_symbol} agora.",
                "streaming": False,
                "timeframe": timeframe,
                "candles": [],
                "volumes": [],
                "overlays": {},
                "error": str(error),
                "ticker": {"lastPrice": 0, "priceChangePercent": 0, "quoteVolume": 0, "volume": 0, "count": 0},
            })), 200
        try:
            df = load_market_data(DEFAULT_SYMBOL, "1h", 500)
            payload = TechnicalAnalysis(df).chart_payload()
            return jsonify(sanitize_json({
                "success": True,
                "source": "fallback",
                "requested_symbol": requested_symbol,
                "symbol": DEFAULT_SYMBOL,
                "market": "crypto",
                "market_label": "Criptomoedas",
                "market_status": "fallback",
                "market_message": f"Nao foi possivel carregar {requested_symbol}. Exibindo BTCUSDT como fallback.",
                "streaming": True,
                "timeframe": "1h",
                "candles": payload.get("candles", []),
                "volumes": payload.get("volumes", []),
                "overlays": payload.get("overlays", {}),
                "warning": str(error),
                "ticker": {"lastPrice": float(df["close"].iloc[-1]), "priceChangePercent": 0, "quoteVolume": 0, "volume": 0, "count": 0},
            }))
        except Exception as fallback_error:
            return jsonify({"success": False, "error": str(fallback_error), "candles": [], "volumes": [], "overlays": {}}), 200


@app.route("/api/analysis/<symbol>/<timeframe>")
def get_analysis(symbol, timeframe):
    symbol = normalize_symbol(symbol)
    timeframe = normalize_timeframe(timeframe)
    cache_key = f"analysis:{symbol}:{timeframe}"
    force_refresh = request.args.get("refresh") is not None
    cached = None if force_refresh else analysis_response_cache.get(cache_key)
    if cached is not None:
        return jsonify(sanitize_json(cached))
    try:
        df, ta, signal, levels, patterns, score, smc, validation, volume_analysis, wyckoff, elliott_wave, tape_reading = build_analysis(symbol, timeframe)
        ticker = get_ticker(symbol)
        market_meta = market.last_meta(symbol)
        current_price = float(df["close"].iloc[-1])
        previous_price = float(df["close"].iloc[-2]) if len(df) > 1 else current_price
        price_change = ((current_price - previous_price) / previous_price * 100) if previous_price else 0
        try:
            mtf_analysis, mtf_confluence = build_multi_timeframe(symbol)
        except Exception:
            mtf_analysis, mtf_confluence = {}, {
                "dominant_direction": "NEUTRAL",
                "confirmed_timeframes": 0,
                "required_confirmations": 3,
                "strong_signal_allowed": False,
                "average_strength": 0,
                "counts": {"BULLISH": 0, "BEARISH": 0, "NEUTRAL": 0},
            }
        try:
            smc = build_smc_context(df, signal.get("signal_type", "neutro"))
        except Exception:
            pass
        flow_context = build_flow_context(volume_analysis, tape_reading)
        wyckoff_context = build_wyckoff_context(df, volume_analysis, tape_reading)
        wyckoff = {**wyckoff, **wyckoff_context}
        institutional_mtf = build_institutional_mtf_context(mtf_analysis, mtf_confluence)
        try:
            signal, validation = apply_mtf_gate(signal, score, validation, mtf_confluence)
        except Exception:
            signal = default_signal(df)
            validation = default_validation()
        markers = build_trade_markers(df, signal, levels)
        try:
            technical_reading = read_technical(df)
        except Exception:
            technical_reading = default_technical(df)
        try:
            final_score = calculate_final_score(
                technical=technical_reading,
                ai_signal=signal,
                levels=levels,
                smc=smc,
                volume=volume_analysis,
                mtf_analysis=mtf_analysis,
                mtf_confluence=mtf_confluence,
                wyckoff=wyckoff,
                elliott_wave=elliott_wave,
                tape_reading=tape_reading,
            )
        except Exception:
            final_score = default_final_score(levels)
        score = int(round(final_score["score"] * 10))
        try:
            operational_state = build_operational_state(signal, validation, smc, volume_analysis, final_score, mtf_confluence, levels)
        except Exception:
            operational_state = {
                "state": "neutral",
                "message": "Cenario neutro / sem entrada no momento.",
                "strong_invalidators": {},
                "invalidation_reasons": [],
                "confluence_ok": False,
                "ready": True,
            }
        confluence_ai = build_confluence_analysis(
            technical=technical_reading,
            smc=smc,
            volume=volume_analysis,
            wyckoff=wyckoff,
            mtf={"analysis": mtf_analysis, "confluence": mtf_confluence},
            levels=levels,
            final_score=final_score,
        )
        operational_signal = build_operational_signal(
            confluence_ai=confluence_ai,
            technical=technical_reading,
            volume=volume_analysis,
            smc=smc,
            mtf_confluence=mtf_confluence,
            levels=levels,
            operational_state=operational_state,
        )
        institutional_payload = build_institutional_payload(smc, wyckoff)
        advanced_confluence = build_advanced_confluence(
            score=score,
            technical=technical_reading,
            smc=smc,
            volume=volume_analysis,
            mtf_confluence=mtf_confluence,
            wyckoff=wyckoff,
            elliott_wave=elliott_wave,
            tape_reading=tape_reading,
            levels=levels,
        )
        institutional_decision = build_institutional_decision(
            technical=technical_reading,
            smc=smc,
            volume=volume_analysis,
            wyckoff=wyckoff,
            elliott_wave=elliott_wave,
            tape_reading=tape_reading,
            mtf_confluence=institutional_mtf,
            levels=levels,
            current_price=current_price,
        )
        risk_plan = build_risk_plan(
            institutional_decision.get("direction", "NEUTRAL"),
            current_price,
            levels,
            smc,
            technical_reading.get("details", {}).get("atr"),
        )
        institutional_confluence = build_institutional_confluence(
            smc=smc,
            wyckoff=wyckoff,
            elliott=elliott_wave,
            flow=flow_context,
            mtf=institutional_mtf,
            technical=technical_reading,
            risk=risk_plan,
        )
        institutional_signal = build_institutional_signal(
            institutional_confluence,
            institutional_decision.get("timing", {}),
            risk_plan,
        )
        institutional_narrative = build_operational_narrative(
            institutional_signal,
            smc,
            flow_context,
            institutional_mtf,
            risk_plan,
        )
        institutional_decision.update({
            "confluence": institutional_confluence,
            "signal_payload": institutional_signal,
            "risk_plan": {**institutional_decision.get("risk_plan", {}), **risk_plan},
            "flow": flow_context,
            "multi_timeframe": institutional_mtf,
            "narrative_payload": institutional_narrative,
        })
        persistent_context = analysis_context_engine.update(df, symbol, timeframe, {
            "technical": technical_reading,
            "probable_direction": institutional_decision.get("direction", "NEUTRAL"),
            "message": institutional_decision.get("narrative"),
            "stop_loss": institutional_decision.get("risk_plan", {}).get("invalidation"),
            "volume": volume_analysis,
            "tape_reading": tape_reading,
            "smc_context": smc,
            "wyckoff": wyckoff,
            "institutional_mtf": institutional_mtf,
        })
        signal_cards = build_signal_cards_decision(
            signal=signal,
            final_score=final_score,
            confluence_ai=confluence_ai,
            operational_signal=operational_signal,
            operational_state=operational_state,
            advanced_confluence=advanced_confluence,
            smc=smc,
            volume=volume_analysis,
            mtf_confluence=mtf_confluence,
            wyckoff=wyckoff,
            elliott_wave=elliott_wave,
            tape_reading=tape_reading,
            levels=levels,
            institutional_decision=institutional_decision,
        )

        response = {
            "success": True,
            "source": market_meta.get("source", "binance"),
            "symbol": normalize_symbol(symbol),
            "market": market_meta.get("market"),
            "market_label": market_meta.get("market_label"),
            "market_status": market_meta.get("market_status", "unknown"),
            "market_message": market_meta.get("message"),
            "streaming": market_meta.get("streaming", False),
            "timeframe": timeframe,
            "signal": signal,
            "levels": levels,
            "markers": markers,
            "support_resistance": ta.identify_support_resistance(lookback=20, num_levels=4),
            "patterns": patterns,
            "smc": smc,
            "volume_analysis": volume_analysis,
            "flow_context": flow_context,
            "wyckoff": wyckoff,
            "elliott_wave": elliott_wave,
            "tape_reading": tape_reading,
            "advanced_confluence": advanced_confluence,
            "institutional_confluence": institutional_confluence,
            "institutional_decision": institutional_decision,
            "institutional_signal": institutional_signal,
            "institutional_risk": risk_plan,
            "institutional_narrative": institutional_narrative,
            "institutional_mtf": institutional_mtf,
            "institutional_ai": {
                "context": persistent_context,
                "smc": smc,
                "wyckoff": wyckoff,
                "elliott": elliott_wave,
                "flow": flow_context,
                "multi_timeframe": institutional_mtf,
                "confluence": institutional_confluence,
                "signal": institutional_signal,
                "risk": risk_plan,
                "narrative": institutional_narrative,
            },
            "context_engine": persistent_context,
            "signal_cards": signal_cards,
            "institutional_context": institutional_payload,
            "smc_score": institutional_payload["smc_score"],
            "wyckoff_phase": institutional_payload["wyckoff_phase"],
            "institutional_bias": institutional_payload["institutional_bias"],
            "relevant_order_block": institutional_payload["relevant_order_block"],
            "relevant_fvg": institutional_payload["relevant_fvg"],
            "liquidity_zone": institutional_payload["liquidity_zone"],
            "liquidity_sweep": institutional_payload["liquidity_sweep"],
            "false_breakout": institutional_payload["false_breakout"],
            "confirmations": institutional_payload["confirmations"],
            "invalidations": institutional_payload["invalidations"],
            "explanation": institutional_payload["explanation"],
            "multi_timeframe": {
                "analysis": mtf_analysis,
                "confluence": mtf_confluence,
            },
            "validation": validation,
            "scenario": build_scenario(signal, validation, smc),
            "technical_reader": technical_reading,
            "final_score": final_score,
            "confluence_ai": confluence_ai,
            "operational_signal": operational_signal,
            "final_signal": operational_signal.get("signal") or confluence_ai.get("signal") or final_score.get("signal"),
            "market_bias": mtf_confluence.get("dominant_direction") or institutional_payload.get("institutional_bias"),
            "disclaimer": DISCLAIMER,
            "operational_state": operational_state,
            "candle_reading": ta.read_latest_candles(5),
            "reasoning": final_score["technical_reasons"] + final_score["invalidation_reasons"],
            "operational_score": score,
            "current_price": current_price,
            "price_change": price_change,
            "ticker": {
                "priceChangePercent": float(ticker.get("priceChangePercent", 0)),
                "quoteVolume": float(ticker.get("quoteVolume", 0)),
                "volume": float(ticker.get("volume", 0)),
                "count": int(ticker.get("count", 0)),
            },
        }
        analysis_response_cache.set(cache_key, response)
        return jsonify(sanitize_json(response))
    except Exception as error:
        institutional_payload = build_institutional_payload(default_smc(), default_wyckoff())
        market_meta = market.last_meta(symbol)
        return jsonify(sanitize_json({
            "success": False,
            "error": str(error),
            "symbol": normalize_symbol(symbol),
            "source": market_meta.get("source"),
            "market": market_meta.get("market"),
            "market_label": market_meta.get("market_label"),
            "market_status": "no_data",
            "market_message": market_meta.get("message") or f"Nao ha dados suficientes para analisar {normalize_symbol(symbol)} agora.",
            "streaming": market_meta.get("streaming", False),
            "signal": default_signal(None),
            "levels": {},
            "markers": [],
            "smc": default_smc(),
            "volume_analysis": default_volume(),
            "wyckoff": default_wyckoff(),
            "elliott_wave": default_elliott_wave(),
            "tape_reading": default_tape_reading(),
            "advanced_confluence": build_advanced_confluence(
                score=0,
                technical=default_technical(None),
                smc=default_smc(),
                volume=default_volume(),
                mtf_confluence={},
                wyckoff=default_wyckoff(),
                elliott_wave=default_elliott_wave(),
                tape_reading=default_tape_reading(),
                levels={},
            ),
            "signal_cards": {
                "active": "wait",
                "label": "AGUARDAR CONFIRMACAO",
                "confidence": 35,
                "score": 0,
                "intensity": "carregando",
                "votes": {"bullish": 0, "bearish": 0, "waiting": 1},
                "reason": "IA completa indisponivel; aguardando nova analise.",
                "cards": {},
            },
            "institutional_context": institutional_payload,
            "smc_score": institutional_payload["smc_score"],
            "wyckoff_phase": institutional_payload["wyckoff_phase"],
            "institutional_bias": institutional_payload["institutional_bias"],
            "relevant_order_block": institutional_payload["relevant_order_block"],
            "relevant_fvg": institutional_payload["relevant_fvg"],
            "liquidity_zone": institutional_payload["liquidity_zone"],
            "liquidity_sweep": institutional_payload["liquidity_sweep"],
            "false_breakout": institutional_payload["false_breakout"],
            "confirmations": institutional_payload["confirmations"],
            "invalidations": institutional_payload["invalidations"],
            "explanation": institutional_payload["explanation"],
            "validation": default_validation(),
            "technical_reader": default_technical(None),
            "final_score": default_final_score({}),
            "operational_signal": {},
            "confluence_ai": build_confluence_analysis(default_technical(None), default_smc(), default_volume(), default_wyckoff(), {}, {}, default_final_score({})),
            "disclaimer": DISCLAIMER,
            "operational_state": {
                "state": "neutral",
                "message": "Cenario neutro / sem entrada no momento.",
                "ready": False,
            },
            "operational_score": 0,
        })), 200


def build_scenario(signal, validation, smc):
    quality = validation["entry_quality"]
    invalidated = quality["invalidated"]
    signal_type = signal["signal_type"]
    if invalidated:
        action = "INVALIDAR"
    elif any(word in signal_type for word in ["compra", "entrada"]):
        action = "OPERAR_COMPRA"
    elif "venda" in signal_type:
        action = "OPERAR_VENDA"
    else:
        action = "AGUARDAR"
    return {
        "action": action,
        "probability": quality["probability"],
        "quality": quality["quality"],
        "invalidated": invalidated,
        "auto_recalc": True,
        "dominant_structure": smc.get("structure", {}).get("trend", "neutral"),
    }


def build_trade_markers(df, signal, levels):
    last_time = int(df.index[-1].timestamp())
    is_buy = any(word in signal["signal_type"] for word in ["compra", "entrada"])
    signal_text = {
        "entrada_agressiva": "Entrada agressiva",
        "entrada_conservadora": "Entrada conservadora",
        "compra": "Compra",
        "venda": "Venda",
        "venda_agressiva": "Venda agressiva",
        "neutro": "Neutro",
    }.get(signal["signal_type"], signal["signal_type"])
    return [{
        "time": last_time,
        "position": "belowBar" if is_buy else "aboveBar",
        "color": "#10b981" if is_buy else "#ef4444",
        "shape": "arrowUp" if is_buy else "arrowDown",
        "text": signal_text,
        "levels": levels,
    }]


@app.route("/api/multi-timeframe/<symbol>")
def get_multi_timeframe(symbol):
    try:
        analysis, confluence = build_multi_timeframe(symbol)
        consolidated = "NEUTRO"
        if confluence["strong_signal_allowed"] and confluence["dominant_direction"] == "BULLISH":
            consolidated = "COMPRA_FORTE_CONFIRMADA"
        elif confluence["strong_signal_allowed"] and confluence["dominant_direction"] == "BEARISH":
            consolidated = "VENDA_FORTE_CONFIRMADA"

        return jsonify({
            "success": True,
            "symbol": normalize_symbol(symbol),
            "analysis": analysis,
            "confluence": confluence,
            "consolidated_signal": consolidated,
            "alignment": f"{confluence['confirmed_timeframes']}/{len(HEATMAP_TIMEFRAMES)}",
        })
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 400


@app.route("/api/live/status/<symbol>/<timeframe>")
@login_required
def api_live_status(symbol, timeframe):
    symbol = normalize_symbol(symbol)
    timeframe = normalize_timeframe(timeframe)
    cache_key = f"live:{symbol}:{timeframe}"
    reason = request.args.get("reason", "heartbeat")
    force_refresh = reason in {"initial", "change", "new_candle", "support_resistance_break", "strong_change", "visibility_resume"}
    cached = None if force_refresh else live_status_cache.get(cache_key)
    if cached is not None:
        return jsonify(sanitize_json(cached))
    try:
        df = load_market_data(symbol, timeframe, 260)
        ticker = get_ticker(symbol)
        status = build_live_status(df, symbol, timeframe, ticker)
        market_meta = market.last_meta(symbol)
        try:
            live_smc = build_smc_context(df, (status.get("technical") or {}).get("signal") or status.get("probable_direction", "NEUTRAL"))
        except Exception:
            live_smc = status.get("smc_context") or default_smc()
        live_flow = build_flow_context(status.get("volume", {}), status.get("tape_reading", {}))
        live_wyckoff = build_wyckoff_context(df, status.get("volume", {}), status.get("tape_reading", {}))
        live_direction = {"BUY": "BULLISH", "SELL": "BEARISH"}.get(status.get("probable_direction"), "NEUTRAL")
        live_mtf = build_institutional_mtf_context({}, {"dominant_direction": live_direction, "average_strength": status.get("trend_strength", 0), "confirmed_timeframes": 0})
        live_risk = build_risk_plan(status.get("probable_direction", "NEUTRAL"), status.get("current_price", 0), {
            "entrada": status.get("entry_aggressive") or status.get("entry_conservative") or status.get("current_price"),
            "stop_loss": status.get("stop_loss"),
            "alvo_1": status.get("take_profit"),
            "alvo_2": status.get("take_profit_2"),
            "risco_retorno": status.get("risk_reward"),
        }, live_smc)
        live_confluence = build_institutional_confluence(
            smc=live_smc,
            wyckoff=live_wyckoff,
            elliott=status.get("elliott_wave", {}),
            flow=live_flow,
            mtf=live_mtf,
            technical=status.get("technical", {}),
            risk=live_risk,
        )
        live_signal = build_institutional_signal(live_confluence, {"confirmed": status.get("state") in ["BUY_CONFIRMED", "SELL_CONFIRMED", "AGGRESSIVE_ENTRY", "CONSERVATIVE_ENTRY"]}, live_risk)
        live_narrative = build_operational_narrative(live_signal, live_smc, live_flow, live_mtf, live_risk)
        status["smc_context"] = live_smc
        status["wyckoff"] = {**status.get("wyckoff", {}), **live_wyckoff}
        status["institutional_mtf"] = live_mtf
        context = live_context_engine.update(df, symbol, timeframe, status)
        operational_panel = build_operational_panel(status, context)
        smart_overlays = live_overlay_engine.build(context, status)
        narrative_feed = live_narrative_engine.update(symbol, timeframe, context, status)
        mtf_confluence = {}
        try:
            _, mtf_confluence = build_multi_timeframe(symbol)
        except Exception:
            mtf_confluence = {"strong_signal_allowed": True}
        status.update({
            "market": market_meta.get("market"),
            "market_label": market_meta.get("market_label"),
            "source": market_meta.get("source"),
            "market_data_status": market_meta.get("market_status"),
            "market_message": market_meta.get("message"),
            "streaming": market_meta.get("streaming", False),
            "market_data": build_market_data_snapshot(market_meta, ticker),
            "context": context,
            "operational_panel": operational_panel,
            "smart_overlays": smart_overlays,
            "narrative_feed": narrative_feed,
            "institutional_ai": {
                "context": context,
                "smc": live_smc,
                "wyckoff": live_wyckoff,
                "flow": live_flow,
                "multi_timeframe": live_mtf,
                "confluence": live_confluence,
                "signal": live_signal,
                "risk": live_risk,
                "narrative": live_narrative,
            },
            "websocket": build_binance_kline_stream(symbol, timeframe) if market_meta.get("streaming", False) else None,
        })
        status["signal_event"] = live_signal_manager.update_from_live_status(status, market_meta, mtf_confluence)
        status["live_signals"] = {
            "active": live_signal_manager.list_active(),
            "history": live_signal_manager.list_history(40),
            "stats": live_signal_manager.stats(),
            "source": "live_status",
        }
        live_status_cache.set(cache_key, status)
        return jsonify(sanitize_json(status))
    except Exception as error:
        fallback = {
            "success": False,
            "error": str(error),
            "symbol": symbol,
            "timeframe": timeframe,
            "state": "ANALYZING",
            "status": "ANALISANDO",
            "message": "IA recalculando. Grafico permanece ativo.",
            "messages": ["Analisando estrutura do mercado...", "Se a IA falhar, mantenha o grafico como referencia visual."],
            "confluence_score": 0,
            "confidence": 0,
            "probable_direction": "NEUTRAL",
            "trend_strength": 0,
            "volume_strength": 0,
            "risk_reward": 0,
            "entry_aggressive": None,
            "entry_conservative": None,
            "stop_loss": None,
            "take_profit": None,
            "reason": "Leitura live indisponivel no momento.",
            "invalidations": ["IA live indisponivel temporariamente."],
            "real_invalidations": [],
            "confirmation_filters": ["IA live indisponivel temporariamente."],
            "alerts": [],
            "disclaimer": "Analise educativa. Nao e recomendacao financeira. Toda operacao envolve risco.",
        }
        return jsonify(sanitize_json(fallback)), 200


@app.route("/api/execution/status")
@login_required
def api_execution_status():
    return jsonify(sanitize_json({"success": True, "status": execution_engine.status()}))


@app.route("/api/execution/config", methods=["POST"])
@login_required
def api_execution_config():
    payload = request.get_json(silent=True) or {}
    status = execution_engine.configure(enabled=payload.get("enabled"), mode=payload.get("mode"))
    return jsonify(sanitize_json({"success": True, "status": status}))


@app.route("/api/execution/kill-switch", methods=["POST"])
@login_required
def api_execution_kill_switch():
    return jsonify(sanitize_json({"success": True, "status": execution_engine.kill()}))


@app.route("/api/execution/evaluate", methods=["POST"])
@login_required
def api_execution_evaluate():
    payload = request.get_json(silent=True) or {}
    decision = execution_engine.evaluate(payload.get("live_status") or {})
    return jsonify(sanitize_json({"success": True, "decision": decision, "status": execution_engine.status()}))


@app.route("/api/execution/paper-order", methods=["POST"])
@login_required
def api_execution_paper_order():
    payload = request.get_json(silent=True) or {}
    return jsonify(sanitize_json(execution_engine.execute_paper(payload.get("live_status") or {})))


@app.route("/api/execution/confirm", methods=["POST"])
@login_required
def api_execution_confirm():
    payload = request.get_json(silent=True) or {}
    return jsonify(sanitize_json(execution_engine.confirm(payload.get("live_status") or {}, real=bool(payload.get("real")))))


@app.route("/api/execution/history")
@login_required
def api_execution_history():
    return jsonify(sanitize_json({"success": True, "orders": execution_engine.history(), "status": execution_engine.status()}))


@app.route("/api/live/signals")
@login_required
def api_live_signals():
    symbol = normalize_symbol(request.args.get("symbol", DEFAULT_SYMBOL))
    timeframe = normalize_timeframe(request.args.get("timeframe", "15m"))
    cache_key = f"live-signals:{symbol}:{timeframe}"
    cached = live_status_cache.get(cache_key)
    if cached is not None:
        return jsonify(sanitize_json(cached))
    try:
        df = load_market_data(symbol, timeframe, 260)
        ticker = get_ticker(symbol)
        status = build_live_status(df, symbol, timeframe, ticker)
        mtf_confluence = {}
        try:
            _, mtf_confluence = build_multi_timeframe(symbol)
        except Exception:
            mtf_confluence = {"strong_signal_allowed": True}
        status.update({
            "market": market.last_meta(symbol).get("market"),
            "market_label": market.last_meta(symbol).get("market_label"),
            "source": market.last_meta(symbol).get("source"),
            "market_data_status": market.last_meta(symbol).get("market_status"),
            "streaming": market.last_meta(symbol).get("streaming", False),
        })
        current_signal = live_signal_manager.update_from_live_status(status, market.last_meta(symbol), mtf_confluence)
        response = {
            "success": True,
            "signal": current_signal,
            "active": live_signal_manager.list_active(),
            "stats": live_signal_manager.stats(),
            "disclaimer": "Analise educativa. Nao constitui recomendacao financeira. Toda operacao envolve risco.",
        }
        live_status_cache.set(cache_key, response)
        return jsonify(sanitize_json(response))
    except Exception as error:
        return jsonify({"success": False, "error": str(error), "active": live_signal_manager.list_active(), "stats": live_signal_manager.stats()}), 200


@app.route("/api/live/signals/active")
@login_required
def api_live_signals_active():
    return jsonify(sanitize_json({
        "success": True,
        "active": live_signal_manager.list_active(),
        "stats": live_signal_manager.stats(),
        "disclaimer": "Analise educativa. Nao constitui recomendacao financeira. Toda operacao envolve risco.",
    }))


@app.route("/api/live/signals/history")
@login_required
def api_live_signals_history():
    limit = int(request.args.get("limit", 100))
    return jsonify(sanitize_json({
        "success": True,
        "history": live_signal_manager.list_history(limit),
        "stats": live_signal_manager.stats(),
    }))


@app.route("/api/operacional/analysis/<symbol>/<timeframe>")
@login_required
def api_operacional_analysis(symbol, timeframe):
    symbol = normalize_symbol(symbol)
    timeframe = normalize_timeframe(timeframe)
    try:
        limit = int(request.args.get("limit", 240))
        df = load_market_data(symbol, timeframe, limit)
        meta = market.last_meta(symbol)
        payload = build_operacional_reading(df, symbol, timeframe)
        payload.update({
            "source": meta.get("source"),
            "market": meta.get("market"),
            "market_label": meta.get("market_label"),
            "market_status": meta.get("market_status"),
            "market_message": meta.get("message"),
        })
        return jsonify(sanitize_json(payload))
    except Exception as error:
        return jsonify(sanitize_json({
            "success": False,
            "module": "operacional_leitura_grafica",
            "symbol": symbol,
            "timeframe": timeframe,
            "error": str(error),
            "narrative": ["Nao foi possivel gerar leitura operacional para este ativo agora."],
        })), 200


@app.route("/api/operacional/candles/<symbol>/<timeframe>")
@login_required
def api_operacional_candles(symbol, timeframe):
    symbol = normalize_symbol(symbol)
    timeframe = normalize_timeframe(timeframe)
    try:
        limit = int(request.args.get("limit", 240))
        df = load_market_data(symbol, timeframe, limit)
        meta = market.last_meta(symbol)
        payload = operacional_chart_payload(df, symbol, timeframe)
        payload.update({
            "source": meta.get("source"),
            "market": meta.get("market"),
            "market_label": meta.get("market_label"),
            "market_status": meta.get("market_status"),
            "market_message": meta.get("message"),
        })
        return jsonify(sanitize_json(payload))
    except Exception as error:
        return jsonify({"success": False, "symbol": symbol, "timeframe": timeframe, "error": str(error), "candles": [], "overlays": {}}), 200


@app.route("/api/operacional/live/<symbol>/<timeframe>")
@login_required
def api_operacional_live(symbol, timeframe):
    symbol = normalize_symbol(symbol)
    timeframe = normalize_timeframe(timeframe)
    try:
        limit = int(request.args.get("limit", 240))
        df = load_market_data(symbol, timeframe, limit)
        reading = build_operacional_reading(df, symbol, timeframe)
        signal = reading.get("operacional_signal", {})
        return jsonify(sanitize_json({
            "success": True,
            "module": "operacional_leitura_grafica",
            "isolated": True,
            "symbol": symbol,
            "timeframe": timeframe,
            "operacional_live": reading.get("operacional_live", []),
            "operacional_context": reading.get("operacional_context", {}),
            "operacional_score": reading.get("operacional_score", 0),
            "operacional_signal": signal,
            "status": signal.get("status", "analisando"),
            "direction": signal.get("direction", "NEUTRO"),
            "disclaimer": reading.get("disclaimer"),
        }))
    except Exception as error:
        return jsonify({"success": False, "symbol": symbol, "timeframe": timeframe, "error": str(error), "messages": ["Leitura operacional indisponivel."]}), 200


@app.route("/api/operacional/signals/<symbol>/<timeframe>")
@login_required
def api_operacional_signals(symbol, timeframe):
    symbol = normalize_symbol(symbol)
    timeframe = normalize_timeframe(timeframe)
    try:
        limit = int(request.args.get("limit", 240))
        df = load_market_data(symbol, timeframe, limit)
        reading = build_operacional_reading(df, symbol, timeframe)
        return jsonify(sanitize_json({
            "success": True,
            "module": "operacional_leitura_grafica",
            "isolated": True,
            "symbol": symbol,
            "timeframe": timeframe,
            "operacional_signal": reading.get("operacional_signal", {}),
            "operacional_score": reading.get("operacional_score", 0),
            "operacional_confirmations": reading.get("operacional_confirmations", []),
            "operacional_invalidations": reading.get("operacional_invalidations", []),
            "operacional_trade_plan": reading.get("operacional_trade_plan", {}),
            "disclaimer": reading.get("disclaimer"),
        }))
    except Exception as error:
        return jsonify({"success": False, "symbol": symbol, "timeframe": timeframe, "error": str(error), "signal": {"status": "analisando", "direction": "NEUTRO"}}), 200


def register_operacional_live_signal(status):
    signal = status.get("signal") or {}
    if signal.get("direction") not in ["COMPRA", "VENDA"]:
        return None
    signature = f"{signal.get('symbol')}:{signal.get('timeframe')}:{signal.get('direction')}:{signal.get('entry')}:{signal.get('stop_loss')}"
    if operacional_live_signals and operacional_live_signals[-1].get("signature") == signature:
        return operacional_live_signals[-1]
    item = dict(signal)
    item["signature"] = signature
    item["engine"] = "live_operacional_grafico"
    operacional_live_signals.append(item)
    del operacional_live_signals[:-80]
    return item


@app.route("/api/operacional-live/status/<symbol>/<timeframe>")
@login_required
def api_operacional_live_status(symbol, timeframe):
    symbol = normalize_symbol(symbol)
    timeframe = normalize_timeframe(timeframe)
    try:
        limit = int(request.args.get("limit", 240))
        df = load_market_data(symbol, timeframe, limit)
        status = build_operacional_live_status(df, symbol, timeframe)
        meta = market.last_meta(symbol)
        status.update({
            "source": meta.get("source"),
            "market": meta.get("market"),
            "market_label": meta.get("market_label"),
            "market_status_raw": meta.get("market_status"),
            "market_message": meta.get("message"),
            "streaming": meta.get("streaming", False),
        })
        current_signal = register_operacional_live_signal(status)
        status["signal_event"] = current_signal
        return jsonify(sanitize_json(status))
    except Exception as error:
        return jsonify({
            "success": False,
            "module": "live_operacional_grafico",
            "symbol": symbol,
            "timeframe": timeframe,
            "error": str(error),
            "status": "AGUARDAR CONFIRMACAO",
            "direction": "NEUTRO",
            "messages": ["Sem contexto operacional suficiente no momento."],
            "signals": [],
        }), 200


@app.route("/api/operacional-live/signals/<symbol>/<timeframe>")
@login_required
def api_operacional_live_signals(symbol, timeframe):
    symbol = normalize_symbol(symbol)
    timeframe = normalize_timeframe(timeframe)
    items = [
        item for item in operacional_live_signals
        if item.get("symbol") == symbol and item.get("timeframe") == timeframe
    ]
    return jsonify(sanitize_json({
        "success": True,
        "module": "live_operacional_grafico",
        "symbol": symbol,
        "timeframe": timeframe,
        "signals": items[-40:],
        "count": len(items),
        "disclaimer": "Sinais operacionais graficos educativos. Nao constituem recomendacao financeira.",
    }))


@app.route("/api/operacional/context/<symbol>/<timeframe>")
@login_required
def api_operacional_context(symbol, timeframe):
    symbol = normalize_symbol(symbol)
    timeframe = normalize_timeframe(timeframe)
    try:
        limit = int(request.args.get("limit", 240))
        df = load_market_data(symbol, timeframe, limit)
        return jsonify(sanitize_json(build_operacional_context(df, symbol, timeframe)))
    except Exception as error:
        return jsonify({"success": False, "symbol": symbol, "timeframe": timeframe, "error": str(error)}), 200


@app.route("/api/operacional/candle-flow/<symbol>/<timeframe>")
@login_required
def api_operacional_candle_flow(symbol, timeframe):
    symbol = normalize_symbol(symbol)
    timeframe = normalize_timeframe(timeframe)
    try:
        limit = int(request.args.get("limit", 120))
        df = load_market_data(symbol, timeframe, limit)
        return jsonify(sanitize_json(build_candle_flow(df, symbol, timeframe)))
    except Exception as error:
        return jsonify({"success": False, "symbol": symbol, "timeframe": timeframe, "error": str(error), "candle_flow": []}), 200


@app.route("/api/heatmap")
def get_heatmap():
    try:
        assets = market.get_assets()
        selected = request.args.get("symbols")
        if selected:
            requested = [normalize_symbol(item) for item in selected.split(",") if item.strip()]
            assets = [asset for asset in assets if asset["symbol"] in requested] or assets

        assets = assets[:8]
        heatmap = create_mtf_heatmap(assets, HEATMAP_TIMEFRAMES)
        return jsonify({"success": True, "source": "router", "heatmap": heatmap})
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 400


def create_mtf_heatmap(assets, timeframes):
    colors = {
        "BULLISH": "#10b981",
        "BEARISH": "#ef4444",
        "NEUTRAL": "#64748b",
    }
    heatmap = {}
    for asset in assets:
        symbol = asset["symbol"] if isinstance(asset, dict) else asset
        analysis, confluence = build_multi_timeframe(symbol, timeframes)
        heatmap[symbol] = {}
        for timeframe, item in analysis.items():
            direction = item["direction"]
            heatmap[symbol][timeframe] = {
                "trend": item["trend"],
                "signal": item["signal"],
                "technical_signal": item["technical_signal"],
                "direction": direction,
                "strength": item["strength"],
                "confidence": item["confidence"],
                "color": colors.get(direction, "#64748b"),
            }
        heatmap[symbol]["confluence"] = confluence
    return heatmap


@app.route("/api/backtest/<symbol>")
def run_backtest(symbol):
    try:
        timeframe = request.args.get("timeframe", "1h")
        df = load_market_data(symbol, timeframe, 1000)
        market_meta = market.last_meta(symbol)
        result = ProfessionalBacktest(df, initial_capital=10000, risk_per_trade=0.01).run()
        result["pattern_learning"] = PatternLearner().summarize(result)
        return jsonify({"success": True, "source": market_meta.get("source"), "market": market_meta.get("market"), "symbol": normalize_symbol(symbol), "backtest": result})
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 400


@app.route("/api/smc/<symbol>/<timeframe>")
def get_smc(symbol, timeframe):
    try:
        df = load_market_data(symbol, timeframe, 600)
        return jsonify({"success": True, "symbol": normalize_symbol(symbol), "timeframe": timeframe, "smc": analyze_smart_money(df)})
    except Exception as error:
        return jsonify({"success": False, "error": str(error)}), 400


@app.route("/api/watchlist", methods=["GET", "POST", "DELETE"])
@login_required
def api_watchlist():
    user_id = current_user_id()
    if request.method == "GET":
        symbols = get_watchlist(user_id)
        if not symbols:
            symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        return jsonify({"success": True, "watchlist": symbols})
    payload = request.get_json(silent=True) or {}
    symbol = normalize_symbol(payload.get("symbol", ""))
    if request.method == "POST":
        return jsonify({"success": True, "watchlist": add_watchlist(user_id, symbol)})
    return jsonify({"success": True, "watchlist": remove_watchlist(user_id, symbol)})


@app.route("/api/alerts", methods=["GET", "POST"])
@login_required
def api_alerts():
    user_id = current_user_id()
    if request.method == "GET":
        return jsonify({"success": True, "alerts": list_alerts(user_id)})
    payload = request.get_json(silent=True) or {}
    alert_id = create_alert(
        user_id,
        normalize_symbol(payload.get("symbol", "BTCUSDT")),
        payload.get("condition_type", "price_above"),
        float(payload.get("target", 0)),
    )
    return jsonify({"success": True, "alert_id": alert_id, "alerts": list_alerts(user_id)})


@app.route("/api/telegram/settings", methods=["POST"])
@login_required
def api_telegram_settings():
    payload = request.get_json(silent=True) or {}
    save_setting(current_user_id(), "telegram", {
        "bot_token": payload.get("bot_token", ""),
        "chat_id": payload.get("chat_id", ""),
    })
    return jsonify({"success": True})


@app.route("/api/telegram/test", methods=["POST"])
@login_required
def api_telegram_test():
    settings = get_setting(current_user_id(), "telegram", {})
    if not settings.get("bot_token") or not settings.get("chat_id"):
        return jsonify({"success": False, "error": "telegram_not_configured"}), 400
    message = (request.get_json(silent=True) or {}).get("message", "FinanceAI institucional online.")
    result = send_telegram(settings["bot_token"], settings["chat_id"], message)
    return jsonify(result)


def send_telegram(bot_token, chat_id, message):
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
            timeout=10,
        )
        return {"success": response.ok, "status_code": response.status_code, "response": response.json()}
    except Exception as error:
        return {"success": False, "error": str(error)}


@app.route("/api/assets")
def get_assets():
    market_key = request.args.get("market")
    return jsonify({
        "success": True,
        "source": "router",
        "markets": market.get_markets(),
        "assets": market.get_assets(market_key),
    })


@app.route("/api/market/tick/<symbol>")
def api_market_tick(symbol):
    requested_symbol = normalize_symbol(symbol)
    try:
        quote = market.get_realtime_quote(requested_symbol)
        return jsonify(sanitize_json({"success": True, **quote}))
    except Exception as error:
        meta = market.last_meta(requested_symbol)
        return jsonify(sanitize_json({
            "success": False,
            "symbol": requested_symbol,
            "source": meta.get("source"),
            "market": meta.get("market"),
            "market_status": meta.get("market_status", "no_data"),
            "message": meta.get("message") or "Tick indisponivel.",
            "error": str(error),
        })), 200


@app.route("/api/timeframes")
def get_timeframes():
    return jsonify({"success": True, "timeframes": SUPPORTED_TIMEFRAMES})


if __name__ == "__main__":
    app.run(debug=True)

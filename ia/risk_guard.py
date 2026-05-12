"""
Risk Guard obrigatorio para execucao automatizada.
"""

from datetime import datetime


class RiskGuard:
    DEFAULTS = {
        "risk_per_trade_pct": 0.5,
        "max_daily_loss_pct": 2.0,
        "max_trades_per_day": 3,
        "max_spread_pct": 0.08,
        "min_rr": 1.2,
        "min_ai_score": 80,
        "allowed_symbols": [],
        "allowed_hours": [0, 24],
        "fixed_quantity": 1,
    }

    def __init__(self, config=None):
        self.config = {**self.DEFAULTS, **(config or {})}

    def validate(self, signal, status):
        rejections = []
        entry = self._num(signal.get("entry"))
        stop = self._num(signal.get("stop_loss"))
        take = self._num(signal.get("take_profit"))
        score = self._num(signal.get("score"))
        rr = self._num(signal.get("risk_reward"))
        spread_pct = self._num(signal.get("spread_pct"), 0)
        symbol = signal.get("symbol")
        side = signal.get("side")
        quantity = self._num(signal.get("quantity"))

        if side not in {"buy", "sell"}:
            rejections.append("Sinal sem direcao executavel.")
        if quantity <= 0:
            rejections.append("Quantidade da ordem invalida.")
        if not entry or not stop:
            rejections.append("Stop loss obrigatorio ausente.")
        if not entry or not take:
            rejections.append("Take profit obrigatorio ausente.")
        if rr < self.config["min_rr"]:
            rejections.append(f"RR abaixo do minimo: 1:{rr:.2f}.")
        if score < self.config["min_ai_score"]:
            rejections.append(f"Score IA abaixo do minimo: {score:.0f}.")
        if spread_pct > self.config["max_spread_pct"]:
            rejections.append(f"Spread acima do permitido: {spread_pct:.3f}%.")
        if status.get("daily_loss_pct", 0) >= self.config["max_daily_loss_pct"]:
            rejections.append("Perda diaria maxima atingida.")
        if status.get("trades_today", 0) >= self.config["max_trades_per_day"]:
            rejections.append("Numero maximo de trades do dia atingido.")
        allowed = self.config.get("allowed_symbols") or []
        if allowed and symbol not in allowed:
            rejections.append("Ativo nao permitido para execucao.")
        start, end = self.config.get("allowed_hours", [0, 24])
        hour = datetime.now().hour
        if not (start <= hour < end):
            rejections.append("Horario fora da janela permitida.")

        return {
            "allowed": not rejections,
            "rejections": rejections,
            "reason": "Aprovado pelo Risk Guard." if not rejections else rejections[0],
            "config": self.config,
        }

    @staticmethod
    def _num(value, default=0):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

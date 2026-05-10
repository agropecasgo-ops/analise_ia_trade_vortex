"""
Configurações do Sistema de Análise IA
"""

# ========================================
# CONFIGURAÇÕES GERAIS
# ========================================

DEBUG = True
HOST = '0.0.0.0'
PORT = 5000
RELOAD_INTERVAL = 60  # segundos

# ========================================
# ATIVOS DISPONÍVEIS
# ========================================

ASSETS = {
    'PETR4': {'name': 'Petrobras', 'sector': 'Energia'},
    'VALE3': {'name': 'Vale', 'sector': 'Mineração'},
    'WEGE3': {'name': 'Weg', 'sector': 'Mecânica'},
    'ITUB4': {'name': 'Itaú', 'sector': 'Banco'},
    'BBDC4': {'name': 'Banco Bradesco', 'sector': 'Banco'},
    'ABEV3': {'name': 'Ambev', 'sector': 'Alimentos'},
    'JBSS3': {'name': 'JBS', 'sector': 'Alimentos'},
    'RENT3': {'name': 'Localiza', 'sector': 'Aluguel'}
}

TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d', '1w']
DEFAULT_TIMEFRAME = '1h'

# ========================================
# INDICADORES TÉCNICOS - PERÍODOS
# ========================================

INDICATORS = {
    'RSI': {
        'period': 14,
        'overbought': 70,
        'oversold': 30
    },
    'MACD': {
        'fast': 12,
        'slow': 26,
        'signal': 9
    },
    'BOLLINGER_BANDS': {
        'period': 20,
        'std_dev': 2
    },
    'ATR': {
        'period': 14
    },
    'EMA': {
        'periods': [20, 50]
    },
    'SMA': {
        'periods': [200]
    }
}

# ========================================
# SUPORTE E RESISTÊNCIA
# ========================================

SUPPORT_RESISTANCE = {
    'lookback': 20,
    'num_levels': 3
}

# ========================================
# PARÂMETROS DA IA
# ========================================

AI_SIGNAL = {
    # Pesos dos componentes
    'weights': {
        'rsi_signal': 0.20,
        'macd_signal': 0.30,
        'trend_signal': 0.35,
        'volume_signal': 0.10,
        'pattern_signal': 0.05
    },
    
    # Limites de score
    'thresholds': {
        'entrada_agressiva': 0.5,
        'entrada_conservadora': 0.3,
        'compra': 0.1,
        'neutro_positivo': 0.05,
        'neutro_negativo': -0.05,
        'venda': -0.1,
        'venda_agressiva': -0.5
    }
}

# ========================================
# RISCO/RETORNO
# ========================================

RISK_MANAGEMENT = {
    'atr_multiplier_stop': 1.5,  # Stop Loss = preço - (ATR × 1.5)
    'target_ratios': [1, 2],      # Alvo 1:1 e 1:2
    'min_risk_reward': 1.0
}

# ========================================
# SCORE OPERACIONAL
# ========================================

OPERATIONAL_SCORE = {
    'base': 50,
    'trend_bonus': 20,
    'pattern_bonus': 10,
    'rsi_extreme_bonus': 15,
    'min_score': 0,
    'max_score': 100
}

# ========================================
# BACKTEST
# ========================================

BACKTEST = {
    'initial_capital': 10000,
    'default_period': 180,  # dias
    'strategy': 'moving_average',
    'ma_fast': 20,
    'ma_slow': 50
}

# ========================================
# DADOS HISTÓRICOS
# ========================================

DATA_GENERATION = {
    'default_days': 90,
    'default_interval': '1h',
    'seed': 42  # para reprodutibilidade
}

# ========================================
# HEATMAP
# ========================================

HEATMAP = {
    'colors': {
        'entrada_agressiva': '#10b981',
        'entrada_conservadora': '#34d399',
        'compra': '#6ee7b7',
        'neutro': '#9ca3af',
        'venda': '#fca5a5',
        'venda_agressiva': '#ef4444'
    },
    'assets': list(ASSETS.keys()),
    'timeframes': ['1h', '4h', '1d']
}

# ========================================
# CACHE
# ========================================

CACHE = {
    'enabled': True,
    'ttl': 300,  # segundos
    'max_size': 100  # máximo de items
}

# ========================================
# UI/UX
# ========================================

UI = {
    'theme': 'dark',
    'colors': {
        'bg_dark': '#0a0e27',
        'bg_darker': '#050814',
        'bg_card': '#0f1428',
        'bg_hover': '#1a1f3a',
        'border': '#1e2749',
        'text_primary': '#e2e8f0',
        'text_secondary': '#a0aec0',
        'accent_blue': '#00d4ff',
        'accent_green': '#10b981',
        'accent_red': '#ef4444',
        'accent_yellow': '#f59e0b'
    },
    'chart': {
        'candlestick_up': '#26a69a',
        'candlestick_down': '#ef5350',
        'volume_color': '#26a69a'
    }
}

# ========================================
# ATUALIZAÇÕES
# ========================================

UPDATES = {
    'prices': 5,        # segundos
    'signals': 30,      # segundos
    'alerts': 10        # segundos
}

# ========================================
# ALERTAS
# ========================================

ALERTS = {
    'enabled': True,
    'price_change_percent': 2.0,  # Alerta se variar 2%
    'volume_multiplier': 1.5,      # Alerta se volume > 1.5x média
    'indicator_extreme': True       # Alerta RSI > 70 ou < 30
}

# ========================================
# LOGGING
# ========================================

LOGGING = {
    'level': 'INFO',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': 'app.log'
}

# ========================================
# FUNÇÕES AUXILIARES
# ========================================

def get_asset_name(symbol):
    """Retorna o nome completo do ativo"""
    return ASSETS.get(symbol, {}).get('name', symbol)

def get_score_quality(score):
    """Retorna qualidade baseado no score"""
    if score > 80:
        return 'Excelente'
    elif score > 60:
        return 'Boa'
    elif score > 40:
        return 'Moderada'
    else:
        return 'Fraca'

def get_signal_color(signal_type):
    """Retorna cor para o tipo de sinal"""
    colors = {
        'entrada_agressiva': HEATMAP['colors']['entrada_agressiva'],
        'entrada_conservadora': HEATMAP['colors']['entrada_conservadora'],
        'compra': HEATMAP['colors']['compra'],
        'neutro': HEATMAP['colors']['neutro'],
        'venda': HEATMAP['colors']['venda'],
        'venda_agressiva': HEATMAP['colors']['venda_agressiva']
    }
    return colors.get(signal_type, HEATMAP['colors']['neutro'])

"""
Gerador de dados históricos para teste
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def generate_sample_data(symbol='PETR4', days=90, interval='1h'):
    """
    Gera dados OHLCV de exemplo para testes
    """
    np.random.seed(42)
    
    # Gerar datas
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    if interval == '1h':
        dates = pd.date_range(start=start_date, end=end_date, freq='1h')
    elif interval == '4h':
        dates = pd.date_range(start=start_date, end=end_date, freq='4h')
    elif interval == '1d':
        dates = pd.date_range(start=start_date, end=end_date, freq='1d')
    else:
        dates = pd.date_range(start=start_date, end=end_date, freq='1h')
    
    # Gerar preços com movimento browniano geométrico
    n = len(dates)
    returns = np.random.normal(0.0001, 0.01, n)
    close_prices = 100 * np.exp(np.cumsum(returns))
    
    # Gerar OHLC
    open_prices = close_prices + np.random.normal(0, 0.5, n)
    high_prices = np.maximum(open_prices, close_prices) + np.abs(np.random.normal(0, 0.5, n))
    low_prices = np.minimum(open_prices, close_prices) - np.abs(np.random.normal(0, 0.5, n))
    
    # Volume
    volumes = np.random.uniform(1000000, 5000000, n).astype(int)
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': volumes
    })
    
    df['symbol'] = symbol
    df = df.set_index('timestamp')
    
    return df


def get_candles_for_chart(df):
    """Converte DataFrame para formato de candles para o chart"""
    candles = []
    
    for idx, row in df.iterrows():
        candle = {
            'time': int(idx.timestamp()),
            'open': float(row['open']),
            'high': float(row['high']),
            'low': float(row['low']),
            'close': float(row['close'])
        }
        candles.append(candle)
    
    return candles


def get_volumes_for_chart(df):
    """Converte volumes para formato de chart"""
    volumes = []
    
    for idx, row in df.iterrows():
        volume_color = '#26a69a' if row['close'] >= row['open'] else '#ef5350'
        volume_data = {
            'time': int(idx.timestamp()),
            'value': float(row['volume']),
            'color': volume_color
        }
        volumes.append(volume_data)
    
    return volumes


# Dados pré-configurados por ativo
SAMPLE_DATA_CONFIG = {
    'PETR4': {'base_price': 28.35, 'volatility': 0.015, 'trend': 0.0002},
    'VALE3': {'base_price': 56.78, 'volatility': 0.012, 'trend': -0.0001},
    'WEGE3': {'base_price': 42.15, 'volatility': 0.018, 'trend': 0.0003},
    'ITUB4': {'base_price': 35.45, 'volatility': 0.010, 'trend': 0.0001},
    'BBDC4': {'base_price': 18.50, 'volatility': 0.014, 'trend': 0.0002},
    'ABEV3': {'base_price': 15.20, 'volatility': 0.013, 'trend': 0.00005},
    'JBSS3': {'base_price': 34.60, 'volatility': 0.016, 'trend': 0.0002},
    'RENT3': {'base_price': 45.90, 'volatility': 0.017, 'trend': 0.0001}
}


def generate_realistic_data(symbol='PETR4', days=90, interval='1h'):
    """
    Gera dados mais realistas baseado em características do ativo
    """
    config = SAMPLE_DATA_CONFIG.get(symbol, {'base_price': 50, 'volatility': 0.015, 'trend': 0.0001})
    
    np.random.seed(hash(symbol) % 2**32)
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    if interval == '1h':
        dates = pd.date_range(start=start_date, end=end_date, freq='1h')
    elif interval == '4h':
        dates = pd.date_range(start=start_date, end=end_date, freq='4h')
    elif interval == '1d':
        dates = pd.date_range(start=start_date, end=end_date, freq='1d')
    else:
        dates = pd.date_range(start=start_date, end=end_date, freq='1h')
    
    n = len(dates)
    base_price = config['base_price']
    volatility = config['volatility']
    trend = config['trend']
    
    # Movimento browniano geométrico
    returns = np.random.normal(trend, volatility, n)
    close_prices = pd.Series(base_price * np.exp(np.cumsum(returns)), index=dates)
    
    # OHLC realista
    open_prices = close_prices.shift(1).fillna(close_prices.iloc[0])
    open_prices = open_prices + np.random.normal(0, volatility * base_price, n)
    
    high_prices = np.maximum(open_prices, close_prices) + np.abs(np.random.normal(0, volatility * base_price * 0.3, n))
    low_prices = np.minimum(open_prices, close_prices) - np.abs(np.random.normal(0, volatility * base_price * 0.3, n))
    
    # Volume realista
    base_volume = 2000000
    volumes = base_volume + np.random.normal(0, base_volume * 0.3, n)
    volumes = np.maximum(volumes, base_volume * 0.5).astype(int)
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': open_prices,
        'high': high_prices,
        'low': low_prices,
        'close': close_prices,
        'volume': volumes
    })
    
    df['symbol'] = symbol
    df = df.set_index('timestamp')
    
    return df

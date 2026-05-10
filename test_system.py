"""
Script de teste do sistema de análise de IA
Demonstra o uso de todas as funcionalidades
"""

import sys
sys.path.insert(0, '.')

from ia.analysis import (
    TechnicalAnalysis, AISignalGenerator, RiskManagement,
    BacktestEngine, OperationalScore, generate_ai_reasoning
)
from ia.data_generator import generate_realistic_data


def test_analysis():
    """Testa análise técnica completa"""
    
    print("=" * 80)
    print("TESTE DO SISTEMA DE ANÁLISE DE IA".center(80))
    print("=" * 80)
    print()
    
    # Gerar dados históricos
    print("1. Gerando dados históricos...")
    symbol = 'PETR4'
    df = generate_realistic_data(symbol, days=90, interval='1d')
    print(f"   ✓ {len(df)} candles gerados para {symbol}\n")
    
    # Análise técnica
    print("2. Executando análise técnica...")
    ta = TechnicalAnalysis(df)
    
    # Calcular indicadores
    rsi = ta.calculate_rsi(14)
    macd, signal, hist = ta.calculate_macd()
    ema20 = ta.calculate_ema(20)
    ema50 = ta.calculate_ema(50)
    sma200 = ta.calculate_sma(200)
    atr = ta.calculate_atr(14)
    
    print(f"   ✓ RSI: {rsi.iloc[-1]:.2f}")
    print(f"   ✓ MACD: {macd.iloc[-1]:.4f}")
    print(f"   ✓ ATR: {atr.iloc[-1]:.2f}")
    print(f"   ✓ EMA20: {ema20.iloc[-1]:.2f}")
    print(f"   ✓ EMA50: {ema50.iloc[-1]:.2f}")
    print(f"   ✓ SMA200: {sma200.iloc[-1]:.2f}\n")
    
    # Identificar padrões
    print("3. Identificando padrões de velas...")
    patterns = ta.identify_candle_patterns()
    if patterns:
        for pattern in patterns:
            print(f"   ✓ {pattern['name']} encontrado")
    else:
        print("   ✓ Nenhum padrão identificado")
    print()
    
    # Suporte e resistência
    print("4. Calculando suporte e resistência...")
    sr = ta.identify_support_resistance(lookback=20, num_levels=3)
    for level in sr:
        print(f"   ✓ {level['type'].upper()}: {level['price']:.2f}")
    print()
    
    # Gerar sinal da IA
    print("5. Gerando sinal da IA...")
    signal_gen = AISignalGenerator(ta)
    signal = signal_gen.generate_signal()
    
    print(f"   Sinal: {signal['signal_type']}")
    print(f"   Score: {signal['score']:.3f}")
    print(f"   Confiança: {signal['confidence']:.1f}%")
    print()
    
    # Componentes do sinal
    print("   Componentes:")
    for component, data in signal['components'].items():
        print(f"   - {component}: {data['value']} ({data['strength']:.2f})")
    print()
    
    # Cálculo de risco/retorno
    print("6. Calculando níveis de risco/retorno...")
    current_price = df['close'].iloc[-1]
    rm = RiskManagement(current_price, atr.iloc[-1])
    levels = rm.calculate_levels(signal['signal_type'])
    
    print(f"   Entrada: R$ {levels['entrada']:.2f}")
    print(f"   Stop Loss: R$ {levels['stop_loss']:.2f}")
    print(f"   Alvo 1: R$ {levels['alvo_1']:.2f}")
    print(f"   Alvo 2: R$ {levels['alvo_2']:.2f}")
    print(f"   Risco/Retorno: 1:{levels['risco_retorno']:.2f}")
    print()
    
    # Score operacional
    print("7. Calculando score operacional...")
    score = OperationalScore.calculate_score(
        signal['indicators'],
        patterns,
        signal['components']['trend_signal']['value']
    )
    print(f"   Score: {score:.1f}/100")
    print(f"   Qualidade: {'Excelente' if score > 80 else 
                         'Boa' if score > 60 else 
                         'Moderada' if score > 40 else 'Fraca'}")
    print()
    
    # Justificativa da IA
    print("8. Gerando justificativa da IA...")
    reasoning = generate_ai_reasoning(signal)
    for item in reasoning:
        print(f"   • {item}")
    print()
    
    # Backtest
    print("9. Executando backtest...")
    backtest = BacktestEngine(df, initial_capital=10000)
    result = backtest.backtest_strategy('moving_average')
    
    print(f"   Total de trades: {result['total_trades']}")
    print(f"   Vitórias: {result['wins']}")
    print(f"   Derrotas: {result['losses']}")
    print(f"   Taxa de acerto: {result['win_rate']:.1f}%")
    print(f"   Retorno total: {result['total_return']:.2f}%")
    print(f"   Capital final: R$ {result['final_capital']:.2f}")
    print()
    
    print("=" * 80)
    print("TESTE CONCLUÍDO COM SUCESSO!".center(80))
    print("=" * 80)
    
    return {
        'signal': signal,
        'levels': levels,
        'score': score,
        'reasoning': reasoning,
        'backtest': result
    }


def test_multiple_assets():
    """Testa análise de múltiplos ativos"""
    
    print("\n" + "=" * 80)
    print("TESTE MULTI-ATIVO".center(80))
    print("=" * 80)
    print()
    
    assets = ['PETR4', 'VALE3', 'WEGE3']
    results = {}
    
    for symbol in assets:
        print(f"\nAnalisando {symbol}...")
        df = generate_realistic_data(symbol, days=30, interval='1d')
        
        ta = TechnicalAnalysis(df)
        signal_gen = AISignalGenerator(ta)
        signal = signal_gen.generate_signal()
        
        results[symbol] = signal
        print(f"  Sinal: {signal['signal_type']}")
        print(f"  Confiança: {signal['confidence']:.1f}%")
    
    print("\n" + "=" * 80)
    print("Resumo")
    print("-" * 80)
    
    bullish = sum(1 for s in results.values() if 'compra' in s['signal_type'])
    bearish = sum(1 for s in results.values() if 'venda' in s['signal_type'])
    
    print(f"Compra: {bullish}/{len(assets)}")
    print(f"Venda: {bearish}/{len(assets)}")
    print(f"Sentimento: {'Bullish' if bullish > bearish else 'Bearish' if bearish > bullish else 'Neutro'}")
    print()


if __name__ == '__main__':
    try:
        result = test_analysis()
        test_multiple_assets()
    except Exception as e:
        print(f"\n❌ Erro: {e}")
        import traceback
        traceback.print_exc()

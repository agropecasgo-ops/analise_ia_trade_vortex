"""
Pacote de Análise e IA para Sistema de Trading
"""

from .analysis import (
    TechnicalAnalysis,
    AISignalGenerator,
    RiskManagement,
    BacktestEngine,
    OperationalScore,
    generate_ai_reasoning,
    create_heatmap_data
)

from .data_generator import (
    generate_sample_data,
    generate_realistic_data,
    get_candles_for_chart,
    get_volumes_for_chart
)

__all__ = [
    'TechnicalAnalysis',
    'AISignalGenerator',
    'RiskManagement',
    'BacktestEngine',
    'OperationalScore',
    'generate_ai_reasoning',
    'create_heatmap_data',
    'generate_sample_data',
    'generate_realistic_data',
    'get_candles_for_chart',
    'get_volumes_for_chart'
]

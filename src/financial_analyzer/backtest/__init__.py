"""
Backtesting module.

Ce module fournit des outils pour backtester des stratégies de trading
avec les features générées par FeaturePipeline, ainsi que des fonctions
de calcul de métriques de performance avancées et de génération de signaux.

Author: FinBot Team
Date: 2025-11-06
Version: 2.0.0
"""

from financial_analyzer.backtest.backtester import BacktestRunner, CustomStrategy
from financial_analyzer.backtest.adaptive_walk_forward import (
    AdaptiveWalkForward,
    DriftDetector,
    ModelRetrainer,
    PerformanceMetrics,
    RetrainEvent,
)
from financial_analyzer.backtest.metrics import (
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_calmar_ratio,
    calculate_max_drawdown,
    calculate_win_rate,
    calculate_profit_factor,
    calculate_avg_trade_duration,
    calculate_exposure_time,
    calculate_all_metrics,
    format_metrics_report,
    compare_strategies,
    export_metrics_json,
    export_metrics_csv
)
from financial_analyzer.backtest.signals import (
    SignalGenerator,
    sma_crossover_signal,
    rsi_threshold_signal,
    bollinger_breakout_signal,
    macd_signal,
    volume_signal,
    ml_prediction_signal,
    custom_rule_signal,
    aggregate_signals,
    smooth_signal,
    validate_signal,
    apply_signal_to_backtest,
    backtest_ready_signals
)

__all__ = [
    # Backtester
    'BacktestRunner',
    'CustomStrategy',
    # Adaptive Walk-Forward (Priority 4)
    'AdaptiveWalkForward',
    'DriftDetector',
    'ModelRetrainer',
    'PerformanceMetrics',
    'RetrainEvent',
    # Metrics
    'calculate_sharpe_ratio',
    'calculate_sortino_ratio',
    'calculate_calmar_ratio',
    'calculate_max_drawdown',
    'calculate_win_rate',
    'calculate_profit_factor',
    'calculate_avg_trade_duration',
    'calculate_exposure_time',
    'calculate_all_metrics',
    'format_metrics_report',
    'compare_strategies',
    'export_metrics_json',
    'export_metrics_csv',
    # Signals
    'SignalGenerator',
    'sma_crossover_signal',
    'rsi_threshold_signal',
    'bollinger_breakout_signal',
    'macd_signal',
    'volume_signal',
    'ml_prediction_signal',
    'custom_rule_signal',
    'aggregate_signals',
    'smooth_signal',
    'validate_signal',
    'apply_signal_to_backtest',
    'backtest_ready_signals'
]

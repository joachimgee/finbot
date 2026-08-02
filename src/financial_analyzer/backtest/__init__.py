"""
Backtesting module.

Ce module regroupe tous les outils de backtesting (fusion des anciens
packages ``backtest``, ``backtesting`` et ``backtest_advanced``) :

- Backtesting de stratégies avec les features de FeaturePipeline
  (``backtester``, ``metrics``, ``signals``)
- Stratégie FinBot complète et runner associé
  (``finbot_strategy``, ``backtest_runner``, ``walk_forward_analyzer``)
- Validation avancée : purged/combinatorial CV, meta-labeling,
  walk-forward d'optimisation (sous-package ``validation``)

Author: FinBot Team
Date: 2025-11-06
Version: 2.1.0
"""

# NOTE: finbot_strategy / backtest_runner / walk_forward_analyzer tirent la
# chaîne pipeline+strategy complète ; ils s'importent par sous-module
# (ex. `from financial_analyzer.backtest.finbot_strategy import FinBotBacktester`)
# pour garder l'import du package léger. Idem pour `backtest.validation`.
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

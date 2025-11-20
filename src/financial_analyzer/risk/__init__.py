"""
Risk Management Module.

Advanced risk measurement, stress testing, and risk budgeting.
"""

from financial_analyzer.risk.risk_metrics import (
    calculate_evar,
    calculate_rlvar,
    calculate_worst_realization,
    calculate_tail_gini,
    calculate_var_range,
    calculate_cvar_range,
    calculate_semi_variance,
    calculate_downside_deviation,
    calculate_semi_kurtosis,
    calculate_ulcer_index,
    calculate_all_advanced_risk_metrics,
    compare_risk_profiles
)

from financial_analyzer.risk.drawdown_analyzer import (
    DrawdownAnalyzer,
    compare_drawdown_profiles
)

from financial_analyzer.risk.stress_test import (
    StressTester,
    stress_test_portfolio
)

from financial_analyzer.risk.risk_budgeting import (
    RiskBudgeter,
    calculate_risk_budget
)

__all__ = [
    # Risk metrics
    'calculate_evar',
    'calculate_rlvar',
    'calculate_worst_realization',
    'calculate_tail_gini',
    'calculate_var_range',
    'calculate_cvar_range',
    'calculate_semi_variance',
    'calculate_downside_deviation',
    'calculate_semi_kurtosis',
    'calculate_ulcer_index',
    'calculate_all_advanced_risk_metrics',
    'compare_risk_profiles',
    
    # Drawdown analysis
    'DrawdownAnalyzer',
    'compare_drawdown_profiles',
    
    # Stress testing
    'StressTester',
    'stress_test_portfolio',
    
    # Risk budgeting
    'RiskBudgeter',
    'calculate_risk_budget'
]

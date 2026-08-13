"""Tearsheet de performance — surface les métriques déjà codées mais non branchées.

Le portail ne remonte que IC / Sharpe net / turnover. `backtest/metrics.py` calcule
pourtant **Sortino**, **Calmar**, **max drawdown** — jamais affichés. Ce module les
compose avec les mesures de robustesse (`robustness.py` : PSR) en un **tearsheet**
unique (façon Alphalens) à partir d'un ``SignalEvalResult``. Aucune donnée nouvelle,
aucune décision : pur *reporting* enrichi.

- **Sharpe** : rendement/vol totale (déjà là).
- **Sortino** : ne pénalise que la vol *baissière* (semi-déviation) — plus juste
  pour un edge asymétrique.
- **Calmar** : rendement annualisé / |max drawdown| — récompense la régularité.
- **max drawdown**, **PSR** (P[Sharpe vrai > 0], corrigé skew/kurtosis/T).
"""
from __future__ import annotations

import math
from typing import Any, Dict

import pandas as pd

from financial_analyzer.backtest.metrics import (
    calculate_calmar_ratio,
    calculate_max_drawdown,
    calculate_sortino_ratio,
)
from financial_analyzer.backtest.robustness import probabilistic_sharpe_ratio
from financial_analyzer.backtest.signal_evaluation import SignalEvalResult

__all__ = ["tearsheet", "format_tearsheet"]


def tearsheet(result: SignalEvalResult, periods_per_year: int = 252) -> Dict[str, Any]:
    """Compose un tearsheet complet à partir d'un ``SignalEvalResult``.

    Réutilise les métriques existantes (Sortino/Calmar/maxDD de ``metrics.py``, PSR
    de ``robustness.py``) — dérivées de la courbe d'equity **nette**. Renvoie un dict
    de métriques (``NaN`` là où l'historique est insuffisant, jamais d'exception).
    """
    eq = result.net_equity_curve
    net_rets = eq.pct_change().dropna() if eq is not None and not eq.empty else pd.Series(dtype=float)
    enough = len(net_rets) >= 2

    dd = calculate_max_drawdown(eq) if eq is not None and not eq.empty else {}
    sortino = calculate_sortino_ratio(net_rets, periods_per_year=periods_per_year) if enough else math.nan
    calmar = (
        calculate_calmar_ratio(net_rets, eq, periods_per_year=periods_per_year)
        if enough else math.nan
    )
    psr = probabilistic_sharpe_ratio(net_rets, sr_benchmark=0.0) if enough else math.nan

    return {
        "ic_mean": result.ic_mean,
        "ic_t_stat": result.ic_t_stat,
        "ic_hit_rate": result.ic_hit_rate,
        "gross_sharpe": result.gross_sharpe,
        "net_sharpe": result.net_sharpe,
        "sortino": float(sortino),
        "calmar": float(calmar),
        "max_drawdown_pct": float(dd.get("max_dd_pct", math.nan)),
        "net_ann_return": result.net_ann_return,
        "avg_turnover": result.avg_turnover,
        "psr": float(psr),
        "n_periods": result.n_periods,
    }


def format_tearsheet(result: SignalEvalResult, name: str = "signal",
                     periods_per_year: int = 252) -> str:
    """Rend le tearsheet en bloc texte aligné (pour logs / scripts)."""
    m = tearsheet(result, periods_per_year=periods_per_year)
    rows = [
        ("IC (moyen / t-stat)", f"{m['ic_mean']:+.4f} / t={m['ic_t_stat']:+.2f}"),
        ("IC hit-rate", f"{m['ic_hit_rate']:.0%}"),
        ("Sharpe brut / net", f"{m['gross_sharpe']:+.2f} / {m['net_sharpe']:+.2f}"),
        ("Sortino (net)", f"{m['sortino']:+.2f}"),
        ("Calmar (net)", f"{m['calmar']:+.2f}"),
        # max_drawdown_pct est une *fraction* (ex. -0.145) -> format % (×100).
        ("Max drawdown", f"{m['max_drawdown_pct']:+.1%}"),
        ("Rendement annualisé net", f"{m['net_ann_return']:+.1%}"),
        ("Turnover moyen / période", f"{m['avg_turnover']:.2f}"),
        ("PSR (P[Sharpe>0])", f"{m['psr']:.2f}"),
        ("Périodes", f"{m['n_periods']}"),
    ]
    width = max(len(label) for label, _ in rows)
    header = f"── Tearsheet : {name} " + "─" * max(0, 54 - len(name))
    lines = [header] + [f"  {label:<{width}} : {value}" for label, value in rows]
    return "\n".join(lines)

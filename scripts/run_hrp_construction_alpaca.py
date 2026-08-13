"""HRP vs equal-weight vs inverse-variance — *sizing* du book momentum (réel).

Idée de l'audit `AUDIT_RISKFOLIO_LIB` (López de Prado). HRP dimensionne un book de
façon **robuste au bruit de covariance** (pas d'inversion de matrice) — le point
faible de FinBot. Mais HRP **ignore le signal de rendement** : il ne fait que le
*sizing*. On isole donc son effet : le **momentum sélectionne** les gagnants
(top-quantile, long-only), et on compare trois façons de les **pondérer** :

* ``EW``  : équipondéré (baseline)
* ``IVP`` : inverse-variance (risk-based simple)
* ``HRP`` : Hierarchical Risk Parity

Métriques nettes de coûts calibrés (Sharpe, turnover, maxDD). Lecture honnête : si
HRP relève le Sharpe net / baisse le drawdown vs EW, le *sizing* robuste paie ;
sinon, l'edge du momentum est dans la *sélection*, pas la pondération.

Usage::

    python scripts/run_hrp_construction_alpaca.py
    python scripts/run_hrp_construction_alpaca.py --rebalance 10 --quantile 0.2 --lookback 252
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np
import pandas as pd

from financial_analyzer.backtest.classic_factors import (
    compute_classic_factors,
    daily_returns,
)
from financial_analyzer.backtest.signal_evaluation import CostModel
from financial_analyzer.data.alpaca_history import load_or_fetch
from financial_analyzer.portfolio.hrp import hrp_weights

DEFAULT_UNIVERSE = sorted(
    {
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "JPM", "V",
        "MA", "UNH", "JNJ", "PG", "HD", "XOM", "CVX", "KO", "PEP", "COST",
        "WMT", "BAC", "WFC", "DIS", "NFLX", "INTC", "AMD", "QCOM", "TXN", "ORCL",
        "CRM", "ADBE", "CSCO", "PFE", "MRK", "ABBV", "TMO", "ABT", "LLY", "NKE",
        "MCD", "SBUX", "LOW", "CAT", "BA", "GE", "HON", "UNP", "UPS", "GS",
        "MS", "AXP", "BLK", "C", "SCHW", "T", "VZ", "CMCSA", "PM", "MO",
        "IBM", "NOW", "INTU", "AMAT", "MU", "LRCX", "GILD", "AMGN", "BMY", "DE",
        "MMM", "LMT", "RTX", "SPGI", "ISRG", "MDT", "CVS", "TGT", "COP", "PYPL",
    }
)


def _sizing(method, names, rets_window):
    if method == "EW":
        return pd.Series(1.0 / len(names), index=names)
    if method == "IVP":
        var = rets_window[names].var(ddof=1)
        inv = 1.0 / var.replace(0.0, np.nan)
        inv = inv.dropna()
        return inv / inv.sum() if not inv.empty else pd.Series(1.0 / len(names), index=names)
    if method == "HRP":
        w = hrp_weights(rets_window[names].dropna())
        return w if not w.empty else pd.Series(1.0 / len(names), index=names)
    raise ValueError(method)


def _simulate(prices, mom, returns, cost_rate, method, reb, quantile, lookback):
    fwd = returns.shift(-1)
    dates = prices.index
    prev = pd.Series(dtype=float)
    gross_rets, net_rets, tos = [], [], []
    steps = 0
    for i, dt in enumerate(dates):
        f = fwd.loc[dt]
        if f.isna().all() or i < lookback:
            continue
        if prev.empty or steps % reb == 0:
            m = mom.loc[dt].dropna()
            m = m[m > 0]  # long-only : momentum positif
            if len(m) >= 5:
                k = max(1, int(round(len(m) * quantile)))
                names = list(m.sort_values().index[-k:])
                window = returns.iloc[i - lookback: i]
                w = _sizing(method, names, window).reindex(names).fillna(0.0)
                w = w / w.sum() if w.sum() > 0 else w
            else:
                w = pd.Series(dtype=float)
            aligned_prev = prev.reindex(w.index).fillna(0.0)
            to = float((w - aligned_prev).abs().sum()) + float(
                prev.drop(index=w.index, errors="ignore").abs().sum())
            prev = w
        else:
            to = 0.0
        g = float((prev.reindex(f.index).fillna(0.0) * f.fillna(0.0)).sum())
        gross_rets.append(g)
        net_rets.append(g - to * cost_rate)
        tos.append(to)
        steps += 1
    net = pd.Series(net_rets)
    eq = (1.0 + net).cumprod()
    sd = net.std(ddof=1)
    sharpe = float(net.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0
    dd = float(((eq / eq.cummax()) - 1.0).min() * 100.0) if len(eq) else 0.0
    return {"sharpe": sharpe, "turnover": float(np.mean(tos)) if tos else 0.0,
            "net_ann": float(net.mean() * 252 * 100.0), "maxdd": dd}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2023-08-01")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--rebalance", type=int, default=10)
    ap.add_argument("--quantile", type=float, default=0.2)
    ap.add_argument("--lookback", type=int, default=252)
    ap.add_argument("--cache", default="/tmp/alpaca_rebalance_sweep.csv")
    args = ap.parse_args()

    prices = load_or_fetch(DEFAULT_UNIVERSE, args.start, args.end, cache_path=args.cache)
    prices = prices.dropna(axis=1, thresh=int(0.8 * len(prices))).ffill()
    prices = prices.dropna(axis=1, how="any").dropna(how="all")
    print(f"Panel : {prices.shape[0]} jours × {prices.shape[1]} titres\n")

    mom = compute_classic_factors(prices)["momentum_12_1"]
    returns = daily_returns(prices)
    cost_rate = CostModel.alpaca_equities().cost_rate

    print("=" * 74)
    print(f"SIZING DU BOOK MOMENTUM (long-only, top {args.quantile:.0%}, reb={args.rebalance})")
    print("=" * 74)
    print(f"\n  {'sizing':6s} {'Sharpe net':>11} {'turnover':>9} {'rdt net an.':>12} {'maxDD':>8}")
    for method in ("EW", "IVP", "HRP"):
        m = _simulate(prices, mom, returns, cost_rate, method,
                      args.rebalance, args.quantile, args.lookback)
        print(f"  {method:6s} {m['sharpe']:>+11.2f} {m['turnover']:>9.3f} "
              f"{m['net_ann']:>+11.1f}% {m['maxdd']:>+7.1f}%")

    print("\nLecture : HRP > EW sur le Sharpe net / drawdown => le sizing robuste paie.")
    print("Sinon, l'edge est dans la SÉLECTION momentum, pas la pondération (attendu")
    print("sur ~80 large-caps homogènes). Enfichable via HRPConstruction (couche #5).")


if __name__ == "__main__":
    main()

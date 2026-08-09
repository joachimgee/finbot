"""Passe les 114 facteurs `ml_features` au crible de la validation OOS (Alpaca).

Objet : montrer, chiffres à l'appui, qu'*avoir* beaucoup de facteurs ne vaut rien
sans validation. Chaque facteur `ml_features.FeatureEngineer` est évalué
out-of-sample, coûts inclus, en walk-forward, puis filtré honnêtement.

Trois enseignements que ce script rend explicites :

1. **Le t-stat de l'IC est trompeur en cross-section large.** Avec des centaines
   de titres, un IC économiquement nul sort « significatif » (|t|>2) par simple
   effet de taille d'échantillon — la quasi-totalité des facteurs « passent ».
2. **Le vrai filtre est le Sharpe net de coûts**, pas le t(IC). Très peu de
   facteurs restent positifs après coûts.
3. **Multiple-testing** : tester N facteurs et garder les gagnants surestime
   l'edge. On vérifie donc la **stabilité par fenêtre** des survivants (un edge
   réel tient sur la majorité des fenêtres ; sinon c'est de la chance).

Usage::

    python scripts/validate_ml_features_alpaca.py --candidates 600 --start 2023-08-01 --end 2026-07-31
"""
from __future__ import annotations

import argparse
import re
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd

from financial_analyzer.backtest.signal_evaluation import (
    CostModel,
    walk_forward_evaluate,
)
from financial_analyzer.data.alpaca_history import fetch_daily_ohlcv
from financial_analyzer.ml_features.feature_engineer import FeatureEngineer
from financial_analyzer.universe.market_selector import UniverseSelector


def _clean_us_universe(cap: int) -> list[str]:
    raw = UniverseSelector().select_equities(sector=None, country="United States")
    return sorted({t for t in raw if re.fullmatch(r"[A-Z]{1,5}", t)})[:cap]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2023-08-01")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--candidates", type=int, default=600,
                    help="Nb de symboles US candidats (Alpaca filtre les liquides).")
    ap.add_argument("--splits", type=int, default=5)
    args = ap.parse_args()

    universe = _clean_us_universe(args.candidates)
    print(f"Fetch OHLCV réel Alpaca de {len(universe)} candidats {args.start}..{args.end}…")
    ohlcv = fetch_daily_ohlcv(universe, args.start, args.end, progress=True)
    print(f"{len(ohlcv)} tickers avec données.")

    per_ticker: dict[str, pd.DataFrame] = {}
    for tk, df in ohlcv.items():
        if len(df) < 300:
            continue
        d = df.rename(columns={"open": "Open", "high": "High", "low": "Low",
                               "close": "Close", "volume": "Volume"})
        try:
            fdf, _ = FeatureEngineer(d).compute_all_factors()
            per_ticker[tk] = fdf
        except Exception:  # noqa: BLE001, S112 - skip tickers the engine can't process
            continue
    print(f"Facteurs calculés pour {len(per_ticker)} tickers.")
    if len(per_ticker) < 40:
        print("Trop peu de tickers exploitables."); return

    close = pd.DataFrame({tk: ohlcv[tk]["close"] for tk in per_ticker}).sort_index()
    returns = close.pct_change()
    dates = returns.index
    factor_names = sorted(set().union(*[set(f.columns) for f in per_ticker.values()]))
    print(f"{len(factor_names)} facteurs sur {returns.shape[1]} titres, {len(dates)} jours.\n")

    cost = CostModel(commission_bps=5, slippage_bps=3)
    rows = []
    for fac in factor_names:
        panel = pd.DataFrame(
            {tk: per_ticker[tk][fac] for tk in per_ticker if fac in per_ticker[tk].columns}
        ).reindex(index=dates)
        if panel.notna().sum().sum() < 0.3 * panel.size:
            continue
        if (panel.nunique(axis=1) <= 1).mean() > 0.5:
            continue
        try:
            out = walk_forward_evaluate(panel, returns, n_splits=args.splits, cost_model=cost)
        except Exception:  # noqa: BLE001, S112 - skip factors that fail evaluation
            continue
        oos = out["oos"]
        if oos is None:
            continue
        per_win = [w.net_sharpe for w in out["per_window"]]
        rows.append((fac, oos.ic_t_stat, oos.ic_mean, oos.net_sharpe, oos.avg_turnover, per_win))

    rows.sort(key=lambda r: abs(r[1]), reverse=True)
    n = len(rows)
    sig2 = sum(1 for r in rows if abs(r[1]) > 2)
    sig3 = sum(1 for r in rows if abs(r[1]) > 3)
    survivors = [r for r in rows if abs(r[1]) > 2 and r[3] > 0]

    print("=" * 80)
    print(f"VALIDATION OOS ml_features — {n} facteurs testés, {returns.shape[1]} titres")
    print("=" * 80)
    print(f"\nTop 15 par |t(IC)| :\n  {'facteur':30s} {'t(IC)':>7} {'IC':>8} {'netSharpe':>10} {'turnover':>9}")
    for fac, t, ic, ns, tov, _ in rows[:15]:
        print(f"  {fac:30s} {t:+7.2f} {ic:+.4f} {ns:+10.2f} {tov:9.2f}{' *' if abs(t) > 2 else ''}")

    print("\n--- Lecture multiple-testing ---")
    print(f"  Facteurs testés          : {n}")
    print(f"  |t|>2 (naïf)             : {sig2}   (attendu par pur hasard ≈ {0.05 * n:.0f})")
    print(f"  |t|>3                    : {sig3}")
    print(f"  |t|>2 ET Sharpe net > 0  : {len(survivors)}  <-- candidats tradeables")

    print("\n--- Stabilité par fenêtre des survivants (Sharpe net / fenêtre OOS) ---")
    print("    Un edge crédible est positif sur la MAJORITÉ des fenêtres.")
    for fac, t, ic, ns, tov, per_win in sorted(survivors, key=lambda r: r[3], reverse=True):
        pos = sum(1 for w in per_win if w > 0)
        wins = " ".join(f"{w:+.2f}" for w in per_win)
        verdict = "STABLE" if pos >= max(3, len(per_win) - 1) else "fragile"
        print(f"  {fac:26s} netSharpe={ns:+.2f}  fenêtres[{wins}]  {pos}/{len(per_win)}+  -> {verdict}")


if __name__ == "__main__":
    main()

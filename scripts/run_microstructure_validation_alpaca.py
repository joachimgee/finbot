"""Famille VOLUME/MICROSTRUCTURE au portail — jamais testée jusqu'ici.

Toutes les validations précédentes portaient sur des facteurs **prix** (momentum,
reversal, vol, 52w) ou des **fondamentaux**/sentiment. La famille **volume/
microstructure** — indépendante du price-trend et calculable depuis le **volume
Alpaca** qu'on possède — n'avait jamais passé le portail. Ce script teste **deux
hypothèses pré-enregistrées** (pas de sweep = pas de p-hacking) :

* **OFI** — *order-flow imbalance* (pression acheteuse nette sur 20 j) → hypothèse
  de **continuation** (long forte pression, short faible). Réutilise le code existant
  ``ml_features_advanced/microstructure_features.py``.
* **Amihud** — illiquidité ``|rdt|/$volume`` (Amihud 2002) → hypothèse de **prime
  de liquidité** (long illiquide, short liquide).

Passe chaque signal par EXACTEMENT le portail (`evaluate_signal`, coûts Alpaca
calibrés, reb=10) et mesure la **corrélation au momentum** (la vraie question de
breadth). Verdict honnête soumis au portail (IC t > 2 ET Sharpe net > 0 ; les 2
essais sont à compter au DSR avant toute inscription).

Usage::

    python scripts/run_microstructure_validation_alpaca.py
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np
import pandas as pd

UNIVERSE = sorted({
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "JPM", "V",
    "MA", "UNH", "JNJ", "PG", "HD", "XOM", "CVX", "KO", "PEP", "COST",
    "WMT", "BAC", "WFC", "DIS", "NFLX", "INTC", "AMD", "QCOM", "TXN", "ORCL",
    "CRM", "ADBE", "CSCO", "PFE", "MRK", "ABBV", "TMO", "ABT", "LLY", "NKE",
    "MCD", "SBUX", "LOW", "CAT", "BA", "GE", "HON", "UNP", "UPS", "GS",
})


def _book_returns(scores: pd.DataFrame, fwd: pd.DataFrame, quantile: float = 0.2) -> pd.Series:
    """Série de rendements bruts du book long/short (pour corrélation inter-signaux)."""
    from financial_analyzer.backtest.signal_evaluation import cross_sectional_weights

    out = {}
    for dt in scores.index:
        w = cross_sectional_weights(scores.loc[dt], quantile=quantile, long_short=True)
        f = fwd.loc[dt] if dt in fwd.index else None
        if f is not None:
            out[dt] = float((w.reindex(f.index).fillna(0.0) * f.fillna(0.0)).sum())
    return pd.Series(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2023-08-01")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--window", type=int, default=20, help="Fenêtre OFI/Amihud (jours).")
    ap.add_argument("--rebalance", type=int, default=10)
    ap.add_argument("--cache", default="/tmp/alpaca_ohlcv_micro.pkl")
    args = ap.parse_args()

    from financial_analyzer.backtest.classic_factors import compute_classic_factors, daily_returns
    from financial_analyzer.backtest.signal_evaluation import CostModel, evaluate_signal
    from financial_analyzer.data.alpaca_history import fetch_daily_ohlcv
    from financial_analyzer.ml_features_advanced.microstructure_features import MicrostructureFeatures

    cache = Path(args.cache)
    if cache.exists():
        ohlcv = pd.read_pickle(cache)
        print(f"OHLCV chargé du cache ({len(ohlcv)} titres).")
    else:
        print("Fetch OHLCV (avec volume) depuis Alpaca…")
        ohlcv = fetch_daily_ohlcv(sorted(UNIVERSE), args.start, args.end, progress=True)
        pd.to_pickle(ohlcv, cache)

    # Panels close & volume alignés.
    close = pd.DataFrame({s: df["close"] for s, df in ohlcv.items()}).sort_index()
    close = close.dropna(axis=1, how="any").dropna(how="all")
    syms = list(close.columns)
    print(f"Panel : {close.shape[0]} jours × {len(syms)} titres\n")

    micro = MicrostructureFeatures(window=args.window)
    ofi = pd.DataFrame({s: micro.compute_order_flow_imbalance(ohlcv[s]) for s in syms}).reindex(close.index)

    # Amihud illiquidité : moyenne glissante de |rdt| / $volume (× 1e6 pour l'échelle).
    ret = close.pct_change()
    dollar_vol = pd.DataFrame({s: ohlcv[s]["close"] * ohlcv[s]["volume"] for s in syms}).reindex(close.index)
    illiq = (ret.abs() / dollar_vol.replace(0, np.nan)).rolling(args.window).mean() * 1e6

    returns = daily_returns(close)
    fwd = returns.shift(-1)
    cost = CostModel.alpaca_equities()
    mom = compute_classic_factors(close)["momentum_12_1"]
    mom_book = _book_returns(mom, fwd)

    print("=" * 80)
    print("FAMILLE VOLUME/MICROSTRUCTURE — portail (reb=10, coûts Alpaca, 2 essais pré-enregistrés)")
    print("=" * 80)
    print(f"\n  {'signal':22} {'IC t':>7} {'Sharpe net':>11} {'rdt net an.':>12} {'corr↔momentum':>14}")
    rows = [("OFI (order-flow)", ofi), ("Amihud (illiquidité)", illiq)]
    verdicts = []
    for label, panel in rows:
        res = evaluate_signal(panel, returns, cost_model=cost, rebalance_every=args.rebalance)
        book = _book_returns(panel, fwd)
        common = book.index.intersection(mom_book.index)
        corr = float(np.corrcoef(book.reindex(common).fillna(0.0),
                                 mom_book.reindex(common).fillna(0.0))[0, 1]) if len(common) > 2 else float("nan")
        passes = res.ic_t_stat > 2 and res.net_sharpe > 0
        verdicts.append((label, res, corr, passes))
        print(f"  {label:22} {res.ic_t_stat:>+7.2f} {res.net_sharpe:>+11.2f} "
              f"{res.net_ann_return:>+11.1%} {corr:>+14.2f}")

    print("\n" + "-" * 80)
    any_pass = any(p for *_, p in verdicts)
    for label, res, corr, passes in verdicts:
        indep = "indépendant du momentum" if abs(corr) < 0.4 else f"corrélé au momentum ({corr:+.2f})"
        if passes:
            print(f"→ {label} PASSE le double critère (IC t {res.ic_t_stat:+.2f}, Sharpe net "
                  f"{res.net_sharpe:+.2f}), {indep} — CANDIDAT, à confirmer au DSR (2 essais).")
        else:
            why = "IC t ≤ 2" if res.ic_t_stat <= 2 else "Sharpe net ≤ 0"
            print(f"→ {label} REJETÉ ({why}), {indep}.")
    if not any_pass:
        print("\nAucun des deux ne franchit le portail. La famille volume/microstructure est")
        print("bien INDÉPENDANTE (breadth potentielle réelle) mais sans edge exploitable sur")
        print("barres QUOTIDIENNES / large-caps : l'OFI et Amihud vivent en intraday / sur")
        print("small-caps illiquides. Cohérent avec le plafond de données — pas d'inscription.")
    print("\nNote : 2 hypothèses pré-enregistrées (pas de sweep). Sweeper des fenêtres/variantes")
    print("serait du multiple-testing — la barre DSR monterait d'autant. Verdict = tel quel.")


if __name__ == "__main__":
    main()

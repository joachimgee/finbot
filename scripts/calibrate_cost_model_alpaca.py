"""Calibre le modèle de coûts sur Alpaca actions US (données réelles).

Alpaca est **sans commission** sur les actions US : le coût réel dominant est
l'**écart bid-ask effectif** qu'un ordre au marché traverse. Ce script mesure cet
écart de deux façons et en tire un ``CostModel`` calibré :

1. **Cotations bid/ask réelles** (mesure PRIMAIRE) — ``(ask - bid) / mid``, écrêté
   des cotations périmées (feed IEX / hors séance), agrégé en médiane.
2. **High-low de Corwin-Schultz** sur barres quotidiennes — indicatif seulement :
   sur données quotidiennes de titres liquides il confond volatilité et spread et
   **surestime** (borne haute, à ne pas utiliser pour calibrer).

Recommandation : ``CostModel(commission_bps=0, slippage_bps≈demi-spread + impact)``.

Usage::

    python scripts/calibrate_cost_model_alpaca.py
    python scripts/calibrate_cost_model_alpaca.py --broad 500 --trim-bps 30
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import warnings
from pathlib import Path

import requests

warnings.filterwarnings("ignore")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from financial_analyzer.backtest.cost_calibration import (
    estimate_effective_spread_bps,
    summarize_quote_spreads,
)
from financial_analyzer.backtest.signal_evaluation import CostModel
from financial_analyzer.data.alpaca_history import fetch_daily_ohlcv

_QUOTES_URL = "https://data.alpaca.markets/v2/stocks/quotes/latest"

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


def _headers() -> dict[str, str]:
    key = os.environ.get("ALPACA_API_KEY") or os.environ.get("APCA_API_KEY_ID")
    sec = os.environ.get("ALPACA_SECRET_KEY") or os.environ.get("APCA_API_SECRET_KEY")
    if not key or not sec:
        raise SystemExit("Clés Alpaca absentes (ALPACA_API_KEY / ALPACA_SECRET_KEY).")
    return {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": sec}


def _fetch_latest_quotes(symbols: list[str]) -> dict[str, tuple[float, float]]:
    """Cotations bid/ask les plus récentes (feed IEX) : {ticker: (bid, ask)}."""
    quotes: dict[str, tuple[float, float]] = {}
    headers = _headers()
    for i in range(0, len(symbols), 100):  # l'API borne la taille des requêtes
        batch = symbols[i : i + 100]
        resp = requests.get(
            _QUOTES_URL, params={"symbols": ",".join(batch), "feed": "iex"},
            headers=headers, timeout=30,
        )
        if resp.status_code != 200:
            print(f"  ⚠️ quotes {resp.status_code}: {resp.text[:120]}")
            continue
        for sym, d in resp.json().get("quotes", {}).items():
            bid, ask = d.get("bp"), d.get("ap")
            if bid and ask:
                quotes[sym] = (float(bid), float(ask))
    return quotes


def _broad_universe(cap: int) -> list[str]:
    from financial_analyzer.universe.market_selector import UniverseSelector

    raw = UniverseSelector().select_equities(sector=None, country="United States")
    return sorted({t for t in raw if re.fullmatch(r"[A-Z]{1,5}", t)})[:cap]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2023-08-01")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--broad", type=int, default=0)
    ap.add_argument("--trim-bps", type=float, default=30.0,
                    help="Écrête les cotations dont l'écart dépasse ce seuil (périmées).")
    ap.add_argument("--impact-buffer", type=float, default=1.0)
    args = ap.parse_args()

    universe = _broad_universe(args.broad) if args.broad > 0 else DEFAULT_UNIVERSE
    print("=" * 76)
    print("CALIBRATION DU MODÈLE DE COÛTS — Alpaca actions US (sans commission)")
    print("=" * 76)

    # 1) Mesure PRIMAIRE : cotations bid/ask réelles.
    print(f"\n[1] Cotations bid/ask réelles ({len(universe)} titres, feed IEX)…")
    quotes = _fetch_latest_quotes(universe)
    qest = summarize_quote_spreads(
        quotes, trim_bps=args.trim_bps, impact_buffer_bps=args.impact_buffer
    )
    print(f"    {qest.summary()}")

    # 2) Borne haute indicative : Corwin-Schultz sur barres quotidiennes.
    print("\n[2] Corwin-Schultz high-low (barres quotidiennes, borne HAUTE indicative)…")
    ohlcv = fetch_daily_ohlcv(universe, args.start, args.end, progress=True)
    csest = estimate_effective_spread_bps(ohlcv, impact_buffer_bps=args.impact_buffer)
    print(f"    {csest.summary()}")
    print("    (⚠️ surestime : capte la volatilité intra-journalière, pas le vrai spread)")

    if qest.n_quotes == 0:
        print("\nAucune cotation exploitable — calibration impossible.")
        return

    # Recommandation fondée sur la mesure primaire (cotations).
    calibrated = CostModel.alpaca_equities()
    print("\n" + "-" * 76)
    print("  Modèle              commission  slippage   coût/turnover (aller simple)")
    for name, cm in [
        ("CALIBRÉ (Alpaca)", calibrated),
        ("ancien (scripts)", CostModel(commission_bps=5.0, slippage_bps=3.0)),
        ("défaut générique", CostModel()),
    ]:
        print(f"  {name:18s} {cm.commission_bps:6.2f} bps  {cm.slippage_bps:6.2f} bps   "
              f"{cm.cost_rate * 1e4:6.2f} bps")
    print(f"\n  -> CostModel.alpaca_equities() = commission 0 + slippage "
          f"{calibrated.slippage_bps} bps, ancré sur le demi-spread mesuré "
          f"({qest.median_half_spread_bps:.2f} bps) + impact.")


if __name__ == "__main__":
    main()

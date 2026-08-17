"""(c) COÛTS RÉELS small-cap — l'alpha survit-il aux frictions ?

Le modèle de coûts du repo (2.5 bps) a été calibré sur des **large-caps**. Lesmond-Schill-
Zhou (2004, *The Illusory Nature of Momentum Profits*) montrent que le momentum small-cap
est largement **mangé par les coûts**. On mesure donc les **vrais écarts bid-ask** sur le
tercile small-cap (cotations Alpaca réelles) et on calcule le **point mort** : à partir de
quel coût le rendement excédentaire du book (+4.21 %/an mesuré en (a)) disparaît.

Usage::

    python scripts/run_smallcap_cost_reality.py
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

_QUOTES_URL = "https://data.alpaca.markets/v2/stocks/quotes/latest"


def _keys() -> dict:
    k = os.environ.get("ALPACA_API_KEY") or os.environ.get("APCA_API_KEY_ID")
    s = os.environ.get("ALPACA_SECRET_KEY") or os.environ.get("APCA_API_SECRET_KEY")
    return {"APCA-API-KEY-ID": k or "", "APCA-API-SECRET-KEY": s or ""}


def fetch_quotes(symbols: list[str], chunk: int = 100, timeout: int = 30) -> dict:
    """Dernières cotations bid/ask {ticker: (bid, ask)} via Alpaca."""
    import requests

    out: dict[str, tuple[float, float]] = {}
    for i in range(0, len(symbols), chunk):
        part = symbols[i:i + chunk]
        try:
            r = requests.get(_QUOTES_URL, headers=_keys(),
                             params={"symbols": ",".join(part), "feed": "iex"}, timeout=timeout)
            if r.status_code != 200:
                continue
            for sym, q in (r.json().get("quotes") or {}).items():
                bid, ask = q.get("bp"), q.get("ap")
                if bid and ask:
                    out[sym] = (float(bid), float(ask))
        except Exception:  # noqa: BLE001
            continue
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--uni-cache", default="/tmp/alpaca_broad_universe.json")
    ap.add_argument("--px-cache", default="/tmp/yahoo_broad_prices_18y.csv")
    ap.add_argument("--excess-ann", type=float, default=0.0421,
                    help="Rendement excédentaire annualisé mesuré en (a) (défaut 4.21%%).")
    ap.add_argument("--turnover-daily", type=float, default=0.022,
                    help="Turnover quotidien moyen mesuré en (a) (défaut 0.022).")
    ap.add_argument("--trim-bps", type=float, default=1000.0,
                    help="Écrêtage des cotations aberrantes (large : les small-caps ont "
                         "de vrais spreads de plusieurs centaines de bps).")
    args = ap.parse_args()

    import pandas as pd

    from financial_analyzer.backtest.cost_calibration import summarize_quote_spreads

    px = pd.read_csv(args.px_cache, index_col=0, parse_dates=True)
    px = px.ffill().dropna(axis=1, thresh=int(0.5 * len(px))).dropna(how="all")
    universe = json.loads(Path(args.uni_cache).read_text())
    ordered = [s for s in universe if s in px.columns]
    t = len(ordered) // 3
    groups = {
        "T1 grand/liquide": ordered[:t],
        "T2 moyen": ordered[t:2 * t],
        "T3 petit (small-cap)": ordered[2 * t:],
    }

    print("=" * 80)
    print("COÛTS RÉELS PAR TAILLE — écarts bid-ask (cotations Alpaca réelles)")
    print("=" * 80)
    print(f"\n  {'groupe':24} {'#cotations':>11} {'spread médian':>14} {'demi-spread':>12}")
    spreads = {}
    for label, syms in groups.items():
        q = fetch_quotes(syms)
        if not q:
            print(f"  {label:24} {'—':>11} (cotations indisponibles)")
            continue
        est = summarize_quote_spreads(q, trim_bps=args.trim_bps)
        spreads[label] = est.median_half_spread_bps
        print(f"  {label:24} {est.n_quotes:>11} {est.median_spread_bps:>12.1f} bps "
              f"{est.median_half_spread_bps:>9.1f} bps")

    # --- Point mort : à quel coût l'excédent disparaît-il ? ---
    ann_turnover = args.turnover_daily * 252  # turnover brut annualisé
    print(f"\n  Turnover annualisé du book (mesuré) : {ann_turnover:.2f} × le capital")
    print(f"  Rendement excédentaire brut (mesuré) : {args.excess_ann:+.2%}/an")
    breakeven_bps = (args.excess_ann / ann_turnover) * 1e4 if ann_turnover > 0 else float("inf")
    print(f"\n  >>> POINT MORT : {breakeven_bps:.1f} bps de coût par unité de turnover")
    print(f"      (au-delà, l'excédent de {args.excess_ann:.2%} est entièrement mangé)")

    # Garde-fou : hors séance, le feed IEX renvoie des cotations périmées (spreads
    # aberrants). On refuse de conclure sur des mesures invalides.
    suspect = [l for l, h in spreads.items() if h > 100.0 and "grand" in l]
    if suspect or not spreads:
        print("\n  ⚠️  MESURE INVALIDE : des spreads > 100 bps sur les titres LIQUIDES "
              "trahissent des\n      cotations périmées (marché fermé / feed IEX creux). "
              "On ne conclut PAS dessus.\n      → on s'appuie sur le POINT MORT + une "
              "sensibilité ancrée sur la littérature.")

    # Sensibilité : robuste (ne dépend que du turnover et de l'excédent mesurés).
    print("\n" + "-" * 80)
    print("SENSIBILITÉ AUX COÛTS (le résultat qui ne dépend pas des cotations live)")
    print(f"\n  {'coût aller simple':>18} {'coût annuel':>12} {'excédent net':>13}   profil typique")
    levels = [
        (2.5, "large-cap liquide (calibré repo)"),
        (10.0, "mid-cap"),
        (25.0, "small-cap liquide"),
        (50.0, "small-cap"),
        (75.9, "← POINT MORT"),
        (100.0, "small-cap peu liquide"),
        (200.0, "micro-cap / penny"),
    ]
    for bps, profile in levels:
        annual_cost = ann_turnover * bps / 1e4
        net = args.excess_ann - annual_cost
        flag = "✅" if net > 0.005 else ("≈" if net > -0.005 else "❌")
        print(f"  {bps:>15.1f} bps {annual_cost:>11.2%} {net:>+12.2%} {flag}  {profile}")

    print("\nLecture : coût annuel = turnover annualisé × coût aller simple. L'excédent brut")
    print("de +4.21 %/an ne survit qu'à des coûts < ~76 bps. Les small-caps ont typiquement")
    print("50-300 bps d'écart effectif (Lesmond-Schill-Zhou 2004) → l'excédent est mangé ou")
    print("proche de zéro dans la plage réaliste. Et il n'était DÉJÀ pas significatif (t=0.52,")
    print("DSR 0.05) avant coûts : les frictions ne font qu'enfoncer un edge déjà non prouvé.")


if __name__ == "__main__":
    main()

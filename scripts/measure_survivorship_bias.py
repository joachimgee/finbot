"""Quantifie le **biais de survie** de l'univers (données Polygon point-in-time).

Compare l'univers *coté à une date historique* (ce qui était réellement
investissable alors) à l'univers *actuel*. La différence — des titres cotés
autrefois, disparus depuis (faillites, fusions, radiations) — est exactement ce
qu'un backtest sur « titres actuellement liquides » exclut silencieusement, et
donc surestime.

Usage::

    python scripts/measure_survivorship_bias.py --as-of 2020-06-30
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import pandas as pd

from financial_analyzer.data.polygon_universe import as_of_universe, list_delisted


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--as-of", default="2020-06-30", help="Date historique de référence.")
    ap.add_argument("--now", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    args = ap.parse_args()

    print("=" * 76)
    print("BIAIS DE SURVIE — univers US common stock (Polygon, point-in-time)")
    print("=" * 76)

    print(f"\nUnivers coté au {args.as_of}…")
    past = as_of_universe(args.as_of)
    print(f"  {len(past)} titres cotés (point-in-time).")

    print(f"Univers coté au {args.now} (actuel)…")
    now = as_of_universe(args.now)
    print(f"  {len(now)} titres cotés aujourd'hui.")

    gone = past - now
    still = past & now
    print("\n--- Écart de survie ---")
    if past:
        print(f"  Titres de {args.as_of} DISPARUS depuis : {len(gone)} "
              f"({len(gone) / len(past):.1%} de l'univers d'alors)")
        print(f"  Titres de {args.as_of} toujours cotés   : {len(still)} "
              f"({len(still) / len(past):.1%})")
    print("  -> Un backtest sur l'univers ACTUEL ignore ces disparus : c'est le")
    print("     biais de survie. Leurs (mauvais) rendements manquants gonflent l'edge.")

    print(f"\n--- Radiations depuis {args.as_of} (échantillon daté) ---")
    dl = list_delisted(delisted_gte=args.as_of, max_pages=6)
    if not dl.empty:
        dl["year"] = dl["delisted_utc"].dt.year
        by_year = dl.groupby("year").size()
        print(f"  {len(dl)} radiations listées (page échantillon). Par année :")
        for y, n in by_year.items():
            print(f"    {int(y)}: {n}")
    else:
        print("  (aucune radiation renvoyée sur l'échantillon)")

    print("\nConséquence pour FinBot : l'infra d'appartenance point-in-time")
    print("(`data/pit_universe.build_membership_mask`) est prête à masquer les")
    print("panels aux seules dates où chaque titre était vivant. La validation")
    print("pleinement sans biais exige EN PLUS les prix des delistés (Polygon 403")
    print("sur ce tier ; Alpaca ne les a pas) — c'est le blocage data restant.")


if __name__ == "__main__":
    main()

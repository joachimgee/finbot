"""Démo des algos d'exécution : plannings + réduction d'impact (modèle Almgren-Chriss).

Illustre TWAP / VWAP / POV / Almgren-Chriss et montre que **découper** un gros ordre
réduit le coût d'**impact temporaire** (∝ taux de participation) — le vrai bénéfice
à grande taille. À petite taille sur large-caps liquides, l'impact est négligeable :
c'est un outil pour *scaler* le capital, pas un gain immédiat.

Usage::

    python scripts/run_execution_algos_demo.py --qty 50000 --adv 1000000 --slices 10
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from financial_analyzer.trading.execution_algos import (
    almgren_chriss_schedule,
    expected_impact_cost,
    pov_schedule,
    twap_schedule,
    vwap_schedule,
)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--qty", type=int, default=50000, help="Ordre parent (actions).")
    ap.add_argument("--adv", type=float, default=1_000_000, help="Volume quotidien moyen.")
    ap.add_argument("--price", type=float, default=50.0)
    ap.add_argument("--slices", type=int, default=10)
    ap.add_argument("--participation", type=float, default=0.10)
    args = ap.parse_args()

    # Profil de volume intraday en U (ouverture/clôture plus actives).
    n = args.slices
    u = [1.6, 1.1, 0.8, 0.7, 0.6, 0.6, 0.7, 0.8, 1.1, 1.6][:n] or [1.0] * n
    interval_vol = args.adv / n

    plans = {
        "1 shot": [args.qty],
        "TWAP": twap_schedule(args.qty, n),
        "VWAP (U)": vwap_schedule(args.qty, u),
        f"POV {args.participation:.0%}": pov_schedule(args.qty, [interval_vol] * n, args.participation),
        "AC κ=0.5": almgren_chriss_schedule(args.qty, n, kappa=0.5),
        "AC κ=1.5 (urgent)": almgren_chriss_schedule(args.qty, n, kappa=1.5),
    }

    print("=" * 74)
    print(f"ALGOS D'EXÉCUTION — ordre {args.qty:,} actions, ADV {args.adv:,.0f}, "
          f"{n} tranches")
    print("=" * 74)
    print(f"\n  {'algo':20s} {'coût impact ($)':>16} {'coût risque ($)':>16} {'planning':>10}")
    for name, sched in plans.items():
        impact = expected_impact_cost(sched, args.adv, args.price,
                                      tau=1.0 / n, risk_aversion=0.0)
        risk = expected_impact_cost(sched, args.adv, args.price, eta=0.0,
                                    tau=1.0 / n, risk_aversion=1e-6)
        head = ",".join(str(x) for x in sched[:4]) + ("…" if len(sched) > 4 else "")
        print(f"  {name:20s} {impact:>16,.0f} {risk:>16,.0f}   {head}")

    print("\nLecture : découper (TWAP/VWAP/POV) écrase le coût d'IMPACT vs '1 shot'")
    print("(impact ∝ participation²). Almgren-Chriss arbitre impact↔risque via κ :")
    print("urgent (κ élevé) = front-loaded = moins de risque de timing, plus d'impact.")
    print("Enfichable via ScheduledExecution (couche #5). Bénéfice réel = à grande taille.")


if __name__ == "__main__":
    main()

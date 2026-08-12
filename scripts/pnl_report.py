"""Rapport P&L (P4) à partir des journaux d'exécution.

Lit les snapshots de compte persistés par le daemon (``logs/execution_journal_*.jsonl``
et journaux de validation paper) et affiche la courbe d'equity, le P&L, le
rendement et le drawdown maximal. Lecture seule — n'exécute aucun ordre.

Usage::

    python scripts/pnl_report.py                       # tous les journaux logs/
    python scripts/pnl_report.py logs/execution_journal_202608.jsonl
    python scripts/pnl_report.py --glob 'logs/paper_validation_*.jsonl'
"""
from __future__ import annotations

import argparse
import glob as globlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from financial_analyzer.trading.pnl import compute_pnl, load_snapshots


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("journals", nargs="*", help="Fichiers JSONL (défaut : logs/*journal*.jsonl).")
    ap.add_argument("--glob", default="logs/execution_journal_*.jsonl",
                    help="Motif si aucun fichier explicite n'est donné.")
    ap.add_argument("--curve", type=int, default=10,
                    help="Nb de points d'equity à afficher (0 = aucun).")
    args = ap.parse_args()

    paths = args.journals or sorted(globlib.glob(args.glob))
    if not paths:
        print(f"Aucun journal trouvé (motif: {args.glob}). Rien à rapporter.")
        return

    snaps = load_snapshots(paths)
    report = compute_pnl(snaps)

    print("=" * 72)
    print("RAPPORT P&L — journaux d'exécution (lecture seule)")
    print("=" * 72)
    print(f"\nSources : {len(paths)} journal(aux)")
    print(f"  {report.summary()}")
    if report.n_snapshots and report.start_ts:
        print(f"  Période : {report.start_ts[:19]} → {report.end_ts[:19]}")

    if args.curve and report.equity_curve:
        pts = report.equity_curve
        step = max(1, len(pts) // args.curve)
        print(f"\n  Courbe d'equity (1 point / {step}) :")
        for ts, eq in pts[::step]:
            print(f"    {ts[:19]}  {eq:>14,.2f}")

    if report.max_drawdown_pct < -0.01:
        print(f"\n  ⚠️ Drawdown max observé : {report.max_drawdown_pct:.2f}% "
              f"(pic {report.peak_equity:,.2f}).")


if __name__ == "__main__":
    main()

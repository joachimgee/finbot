"""Rapport de préparation au live (go/no-go) — score les 10 critères du runbook.

Lit les journaux d'exécution paper (``logs/*.jsonl``) qui s'accumulent (notamment
ceux du book planifié `run_multi_strategy_paper.py`) et **score les 10 critères
chiffrés** de `docs/RUNBOOK_PAPER_TO_LIVE.md`. Lecture seule — n'active jamais le
live (le double-verrou reste seul maître). Transforme les runs paper en une décision
**go/no-go auditable**.

Les critères *auto* sont jugés depuis les artefacts ; les critères *opérateur*
(chokepoint, kill-switch, capital) sont rappelés pour vérification manuelle.

Usage::

    python scripts/live_readiness_report.py
    python scripts/live_readiness_report.py --glob 'logs/multistrat_paper_*.jsonl'
"""
from __future__ import annotations

import argparse
import glob as globlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from financial_analyzer.trading.readiness import evaluate_readiness


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("journals", nargs="*",
                    help="Journaux JSONL explicites (défaut : motifs --glob).")
    ap.add_argument("--glob", action="append", default=None,
                    help="Motif(s) de journaux (répétable). "
                         "Défaut : execution_journal_* + multistrat_paper_* + paper_validation_*.")
    ap.add_argument("--rebalance-state", default="logs/rebalance_state.json")
    ap.add_argument("--alert-log", default="logs/alerts.jsonl")
    args = ap.parse_args()

    # Motifs par défaut : ils doivent couvrir le book qui tourne RÉELLEMENT. La liste
    # précédente nommait `multistrat_paper_*` en dur et ne voyait donc pas
    # `amihud_paper_*` — le rapport mesurait la préparation de stratégies éteintes et
    # ignorait la seule en forward-test. Le motif générique `*_paper_*` s'auto-entretient
    # : tout nouveau book paper est pris en compte sans qu'on ait à y penser.
    patterns = args.glob or [
        "logs/execution_journal_*.jsonl",
        "logs/*_paper_*.jsonl",
        "logs/paper_validation_*.jsonl",
    ]
    paths = args.journals or sorted({p for pat in patterns for p in globlib.glob(pat)})

    report = evaluate_readiness(
        paths, rebalance_state=args.rebalance_state, alert_log=args.alert_log)

    print("=" * 78)
    print("PRÉPARATION AU LIVE — critères du runbook (lecture seule, n'active rien)")
    print("=" * 78)
    print(f"\nSources : {len(paths)} journal(aux)")
    print(f"\n  {'#':>2} {'critère':52} {'seuil':28} verdict")
    print("  " + "-" * 92)
    for c in report.criteria:
        tag = "" if c.kind == "auto" else "  (opérateur)"
        print(f"  {c.id:>2} {c.title[:52]:52} {c.threshold[:28]:28} {c.icon} {c.measured}{tag}")

    print("\n" + "-" * 78)
    print(f"  {report.summary()}")
    if not report.ready:
        blockers = [f"#{c.id}" for c in report.auto if c.status != "pass"]
        print(f"  Bloquants auto : {', '.join(blockers) or 'aucun'}")
    print("\n  Rappel : « prêt côté automatique » ≠ autorisation de live. Les critères")
    print("  opérateur (chokepoint, kill-switch, capital) et la décision d'engager de")
    print("  l'argent restent humains. Le double-verrou code+jeton reste seul maître.")
    # Code de sortie : 0 si prêt (côté auto), 1 sinon — pratique en CI/cron.
    return 0 if report.ready else 1


if __name__ == "__main__":
    raise SystemExit(main())

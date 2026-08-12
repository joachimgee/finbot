"""Validation bout-en-bout du LiveTradingPipeline sur Alpaca **paper** (P0).

Dernier verrou P0 : prouver que le chemin d'exécution canonique
(fetch → signaux validés → allocation Black-Litterman → ordres → OrderGateway)
fonctionne de bout en bout contre un vrai compte, **sans risque d'argent réel**.

Par défaut, tout tourne en **dry-run** : la chaîne complète s'exécute, le gateway
applique garde de mode + risque + audit + journal, mais **aucun ordre n'est soumis
au broker**. C'est la validation sûre.

Avec ``--execute``, les ordres sont réellement placés sur le compte **paper**
(jamais live : la garde de mode l'interdit sans le jeton d'activation), puis on
réconcilie journal vs broker.

Usage::

    python scripts/validate_paper_pipeline_alpaca.py            # dry-run (sûr)
    python scripts/validate_paper_pipeline_alpaca.py --execute  # ordres paper réels
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

# Univers de validation : large-caps très liquides, historique long (>252 j pour
# activer le momentum 12-1 validé).
UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "JPM", "V",
    "KO", "PEP", "XOM", "CVX", "JNJ", "PG", "WMT", "HD",
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true",
                    help="Placer réellement les ordres sur le compte PAPER (sinon dry-run).")
    ap.add_argument("--tickers", default=",".join(UNIVERSE),
                    help="Liste de symboles séparés par des virgules.")
    args = ap.parse_args()
    tickers = [t.strip().upper() for t in args.tickers.split(",") if t.strip()]

    from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
    from financial_analyzer.trading.journal import TradingJournal
    from financial_analyzer.trading.live_trading_pipeline import LiveTradingPipeline
    from financial_analyzer.trading.reconciliation import reconcile_orders
    from financial_analyzer.trading.run_manifest import build_run_manifest

    dry_run = not args.execute
    mode_label = "DRY-RUN (aucun ordre soumis)" if dry_run else "EXÉCUTION PAPER RÉELLE"
    print("=" * 78)
    print(f"VALIDATION PIPELINE — Alpaca PAPER — {mode_label}")
    print("=" * 78)

    adapter = AlpacaAdapter.from_env(mode="paper")
    adapter.connect()
    acct = adapter.get_account()
    print(f"\nCompte paper: equity=${float(acct.get('equity', 0)):,.2f}  "
          f"cash=${float(acct.get('cash', 0)):,.2f}  mode={adapter.mode}")

    journal = TradingJournal(f"logs/paper_validation_{datetime.now().strftime('%Y%m%d_%H%M')}.jsonl")  # noqa: DTZ005
    journal.record_manifest(build_run_manifest(mode=adapter.mode))
    # Snapshot de départ : alimente le suivi P&L (scripts/pnl_report.py).
    journal.record_snapshot(
        equity=float(acct.get("equity", 0.0)), cash=float(acct.get("cash", 0.0)),
        event="run_start", mode=adapter.mode,
    )

    pipeline = LiveTradingPipeline(
        broker_adapter=adapter,
        tickers=tickers,
        strategy="factor_ensemble",
        journal=journal,
    )

    # 1) Transparence décision : signaux -> poids cibles Black-Litterman.
    print(f"\n[1] Décision (signaux validés -> allocation Black-Litterman) sur {len(tickers)} titres…")
    target_weights, _data = pipeline.compute_target_weights()
    if target_weights:
        print(f"    {len(target_weights)} positions cibles (signaux positifs) :")
        for sym, w in sorted(target_weights.items(), key=lambda kv: kv[1], reverse=True):
            print(f"      {sym:6s} {w * 100:5.1f}%")
    else:
        print("    Aucun signal positif -> abstention (aucune position). Chaîne validée quand même.")

    # 2) Chaîne complète run() : ordres -> gateway (dry-run ou réel).
    print(f"\n[2] Exécution de la chaîne complète (dry_run={dry_run})…")
    result = pipeline.run(force=True, dry_run=dry_run)
    print(f"    statut={result['status']}  ordres générés={result.get('orders_generated', 0)}  "
          f"exécutés={result.get('orders_executed', 0)}  rejetés={result.get('orders_rejected', 0)}")
    for r in result.get("execution_results", []):
        o = r["order"]
        print(f"      {r['status']:9s} {o['side']:4s} {o['qty']:>5} {o['symbol']:6s} "
              f"@ ${o['price']:.2f}" + (f"  ({r.get('reason', '')})" if r.get("reason") else ""))

    # 3) Piste d'audit : le journal a bien enregistré chaque intention d'ordre.
    orders_logged = journal.orders()
    print(f"\n[3] Journal d'audit: {len(orders_logged)} ordres enregistrés "
          f"(chaque soumission passe par l'unique OrderGateway).")

    # 4) Réconciliation (seulement pertinente si on a réellement soumis).
    if not dry_run:
        print("\n[4] Réconciliation journal vs broker…")
        broker_orders = adapter.get_orders(status="all", limit=200) or []
        recon = reconcile_orders(orders_logged, broker_orders)
        journal.record_reconciliation(recon.to_dict())
        print(f"    {'✅' if recon.ok else '🚨'} {recon.summary()}")
    else:
        print("\n[4] Réconciliation ignorée (dry-run — aucun ordre réel à réconcilier).")

    # Snapshot de fin : clôt la période pour le suivi P&L.
    acct_end = adapter.get_account()
    journal.record_snapshot(
        equity=float(acct_end.get("equity", 0.0)), cash=float(acct_end.get("cash", 0.0)),
        event="run_end", mode=adapter.mode,
    )

    adapter.disconnect()
    print(f"\n✅ Validation terminée ({mode_label}). Journal: {journal.path}")


if __name__ == "__main__":
    main()

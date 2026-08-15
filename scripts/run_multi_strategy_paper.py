"""Book combiné (momentum + PCA-résiduel + paires) en **paper trading** Alpaca.

Forward-test du multi-stratégie décorrélé sur le compte **paper** (jamais live : le
double-verrou l'interdit sans le jeton d'activation). Réutilise tout le chemin
audité — fetch → construction → ordres → OrderGateway → journal → réconciliation —
en injectant la construction multi-stratégie (couche enfichable #5).

⚠️ Discipline : sur les trois familles, **seul momentum est validé** ; PCA-résiduel
et paires sont en *forward-test* — d'où **paper uniquement**. Long/short
(market-neutral). Par défaut **dry-run** (aucun ordre soumis) ; ``--execute`` place
réellement les ordres sur le compte paper.

Usage::

    python scripts/run_multi_strategy_paper.py            # dry-run (sûr)
    python scripts/run_multi_strategy_paper.py --execute  # ordres PAPER réels
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

UNIVERSE = sorted({
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "JPM", "V",
    "MA", "UNH", "JNJ", "PG", "HD", "XOM", "CVX", "KO", "PEP", "COST",
    "WMT", "BAC", "WFC", "DIS", "NFLX", "INTC", "AMD", "QCOM", "TXN", "ORCL",
    "CRM", "ADBE", "CSCO", "PFE", "MRK", "ABBV", "TMO", "ABT", "LLY", "NKE",
    "MCD", "SBUX", "LOW", "CAT", "BA", "GE", "HON", "UNP", "UPS", "GS",
})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true",
                    help="Placer réellement les ordres sur le compte PAPER (sinon dry-run).")
    ap.add_argument("--scheduled", action="store_true",
                    help="Mode planifié : ne rien faire si le marché est fermé "
                         "(jour férié / week-end / hors séance), via l'horloge Alpaca.")
    ap.add_argument("--no-trade-band", type=float, default=0.02, metavar="FRAC",
                    help="Bande de non-transaction (poids absolu, ex. 0.02 = 2%%) : "
                         "ne rééquilibre une ligne que si son poids bouge de plus que "
                         "la bande vs le book détenu — réduit le churn quotidien. "
                         "0 = viser exactement le cible chaque jour (défaut : 0.02).")
    args = ap.parse_args()

    from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
    from financial_analyzer.trading.framework import MultiStrategyConstruction
    from financial_analyzer.trading.journal import TradingJournal
    from financial_analyzer.trading.live_trading_pipeline import LiveTradingPipeline
    from financial_analyzer.trading.reconciliation import reconcile_orders

    dry_run = not args.execute
    band = max(0.0, float(args.no_trade_band))
    label = "DRY-RUN (aucun ordre soumis)" if dry_run else "EXÉCUTION PAPER RÉELLE"
    print("=" * 78)
    print(f"MULTI-STRATÉGIE — Alpaca PAPER — {label}")
    band_txt = f"{band * 100:.1f}%" if band > 0 else "désactivée (viser le cible)"
    print(f"Bande de non-transaction : {band_txt}")
    print("=" * 78)

    adapter = AlpacaAdapter.from_env(mode="paper")
    adapter.connect()

    # Mode planifié : garde-fou « jour ouvré » via l'horloge Alpaca (connaît les
    # jours fériés du NYSE, que le cron hebdomadaire ne connaît pas). Marché fermé
    # -> run ignorée proprement (aucun ordre), sortie 0.
    if args.scheduled and not adapter.is_market_open():
        print("Marché FERMÉ (week-end / jour férié / hors séance) — run planifiée ignorée.")
        adapter.disconnect()
        return

    acct = adapter.get_account()
    print(f"\nCompte paper: equity=${float(acct.get('equity', 0)):,.2f}  "
          f"cash=${float(acct.get('cash', 0)):,.2f}  mode={adapter.mode}")

    journal = TradingJournal(
        f"logs/multistrat_paper_{datetime.now().strftime('%Y%m%d_%H%M')}.jsonl")  # noqa: DTZ005
    pipeline = LiveTradingPipeline(broker_adapter=adapter, tickers=UNIVERSE, journal=journal,
                                   no_trade_band=band)
    # Couche enfichable #5 : remplacer la construction par le book multi-stratégie.
    pipeline.construction = MultiStrategyConstruction(pipeline)

    print(f"\n[1] Book combiné multi-stratégie (long/short) sur {len(UNIVERSE)} titres…")
    target, _data = pipeline.compute_target_weights()
    if not target:
        print("    Book vide (données insuffisantes ?). Fin.")
        adapter.disconnect()
        return
    longs = {s: w for s, w in target.items() if w > 0}
    shorts = {s: w for s, w in target.items() if w < 0}
    gross = sum(abs(w) for w in target.values())
    net = sum(target.values())
    print(f"    {len(target)} positions (brut={gross:.2f}, net={net:+.2f}) : "
          f"{len(longs)} longs / {len(shorts)} shorts")
    for sym, w in sorted(target.items(), key=lambda kv: kv[1], reverse=True):
        print(f"      {sym:6s} {w * 100:+6.2f}%")

    print(f"\n[2] Chaîne complète run() via OrderGateway (dry_run={dry_run})…")
    result = pipeline.run(force=True, dry_run=dry_run)
    print(f"    statut={result['status']}  générés={result.get('orders_generated', 0)}  "
          f"exécutés={result.get('orders_executed', 0)}  rejetés={result.get('orders_rejected', 0)}")
    for r in result.get("execution_results", [])[:60]:
        o = r["order"]
        reason = f"  ({r.get('reason', '')})" if r.get("reason") else ""
        print(f"      {r['status']:9s} {o['side']:4s} {o['qty']:>5} {o['symbol']:6s} "
              f"@ ${o['price']:.2f}{reason}")

    if not dry_run:
        print("\n[3] Réconciliation journal vs broker…")
        recon = reconcile_orders(journal.orders(), adapter.get_orders(status="all", limit=300) or [])
        journal.record_reconciliation(recon.to_dict())
        print(f"    {'✅' if recon.ok else '🚨'} {recon.summary()}")

    adapter.disconnect()
    print(f"\n✅ Terminé ({label}). Journal: {journal.path}")
    print("Rappel : PAPER uniquement (PCA-résiduel & paires en forward-test, non validés).")


if __name__ == "__main__":
    main()

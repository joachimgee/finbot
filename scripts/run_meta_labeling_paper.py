"""Book momentum **méta-labelé** en **paper trading** Alpaca (forward-test).

Le momentum 12-1 (primaire) décide la direction ; un modèle secondaire (logistique)
ne garde que les paris à ``P(gain) ≥ seuil`` (couche enfichable
``framework.MetaLabelConstruction``). Réutilise tout le chemin audité — fetch →
construction → ordres → OrderGateway → journal → réconciliation.

⚠️ Discipline : le méta-labeling a passé les **contrôles d'artefact** sur 18 ans
(bat 100 % de l'aléatoire, AUC p=0.002) mais reste sous **biais de survie** et sans
DSR campagne → **paper uniquement** (le double-verrou l'interdit en live sans le
jeton). Long/short. Par défaut **dry-run** ; ``--execute`` place les ordres PAPER.

Usage::

    python scripts/run_meta_labeling_paper.py            # dry-run (sûr)
    python scripts/run_meta_labeling_paper.py --execute  # ordres PAPER réels
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


def _business_days_since_last_order(adapter, lookback: int = 100) -> int | None:
    """Jours ouvrés depuis le dernier ordre broker (= dernier rééquilibrage), ou None.

    L'historique d'ordres Alpaca est l'état persistant (survit aux sessions fraîches).
    Fail-safe : toute erreur → None (on autorise le rééquilibrage plutôt que bloquer).
    """
    try:
        import numpy as np

        orders = adapter.get_orders(status="all", limit=lookback) or []
        dates = []
        for o in orders:
            ts = o.get("submitted_at") or o.get("filled_at") or o.get("created_at")
            if ts is not None:
                dates.append(getattr(ts, "date", lambda: None)() or __import__("pandas").Timestamp(ts).date())
        if not dates:
            return None
        last = max(dates)
        from datetime import date

        return max(0, int(np.busday_count(last.isoformat(), date.today().isoformat())))  # noqa: DTZ011
    except Exception as e:  # noqa: BLE001 - une garde de cadence ne doit jamais casser le run
        print(f"    (cadence : historique d'ordres illisible — {e} ; rééquilibrage autorisé)")
        return None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true",
                    help="Placer réellement les ordres sur le compte PAPER (sinon dry-run).")
    ap.add_argument("--scheduled", action="store_true",
                    help="Mode planifié : ne rien faire si le marché est fermé (horloge Alpaca).")
    ap.add_argument("--threshold", type=float, default=0.5, help="Seuil P(gain) du méta-filtre.")
    ap.add_argument("--no-trade-band", type=float, default=0.02, metavar="FRAC",
                    help="Bande de non-transaction (défaut 0.02 ; 0 = viser le cible).")
    ap.add_argument("--rebalance-every", type=int, default=21, metavar="N",
                    help="Cadence : ne rééquilibre que tous les N jours ouvrés (défaut 21 "
                         "≈ mensuel — meilleure cadence mesurée pour ce book). Persistée.")
    ap.add_argument("--ignore-cadence", action="store_true",
                    help="Forcer le rééquilibrage même si la cadence n'est pas due.")
    args = ap.parse_args()

    from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
    from financial_analyzer.trading.framework import MetaLabelConstruction
    from financial_analyzer.trading.journal import TradingJournal
    from financial_analyzer.trading.live_trading_pipeline import LiveTradingPipeline
    from financial_analyzer.trading.reconciliation import reconcile_orders

    dry_run = not args.execute
    band = max(0.0, float(args.no_trade_band))
    label = "DRY-RUN (aucun ordre soumis)" if dry_run else "EXÉCUTION PAPER RÉELLE"
    print("=" * 78)
    print(f"MÉTA-LABELING momentum — Alpaca PAPER — {label}")
    print(f"Seuil P(gain) : {args.threshold:.2f}  |  Bande de non-transaction : "
          f"{band * 100:.1f}%" if band > 0 else f"Seuil P(gain) : {args.threshold:.2f}")
    print("=" * 78)

    adapter = AlpacaAdapter.from_env(mode="paper")
    adapter.connect()

    if args.scheduled and not adapter.is_market_open():
        print("Marché FERMÉ (week-end / jour férié / hors séance) — run planifiée ignorée.")
        adapter.disconnect()
        return

    acct = adapter.get_account()
    print(f"\nCompte paper: equity=${float(acct.get('equity', 0)):,.2f}  "
          f"cash=${float(acct.get('cash', 0)):,.2f}  mode={adapter.mode}")

    journal = TradingJournal(
        f"logs/metalabel_paper_{datetime.now().strftime('%Y%m%d_%H%M')}.jsonl")  # noqa: DTZ005
    journal.record_snapshot(
        equity=float(acct.get("equity", 0.0)), cash=float(acct.get("cash", 0.0)),
        event="run_start", mode=adapter.mode,
    )

    # Garde de cadence : le book méta est meilleur espacé (reb≈21 mensuel : Sharpe net
    # +0.92 vs +0.35 en quotidien, turnover −88 %). N'exécute un rééquilibrage réel que
    # tous les N jours ouvrés. IMPORTANT : la source d'état est l'HISTORIQUE D'ORDRES
    # ALPACA (persistant côté broker), pas un fichier local — les runs planifiés sont
    # des sessions fraîches à disque éphémère, un fichier ne survivrait pas. Le book ne
    # trade qu'aux rééquilibrages, donc « dernier ordre » = « dernier rééquilibrage ».
    # En dry-run, garde inactive (on montre toujours le book).
    gate_active = (not dry_run) and (not args.ignore_cadence)
    if gate_active:
        dsince = _business_days_since_last_order(adapter)
        if dsince is not None and dsince < args.rebalance_every:
            left = args.rebalance_every - dsince
            print(f"\nCadence : book TENU (dernier rééquilibrage il y a {dsince} j ouvrés < "
                  f"{args.rebalance_every} ; prochain dans ~{left} j). Aucun ordre.")
            journal.record_snapshot(equity=float(acct.get("equity", 0.0)),
                                    cash=float(acct.get("cash", 0.0)), event="run_end", mode=adapter.mode)
            adapter.disconnect()
            return

    pipeline = LiveTradingPipeline(broker_adapter=adapter, tickers=UNIVERSE, journal=journal,
                                   no_trade_band=band)
    # Couche enfichable #5 : construction méta-labeling.
    pipeline.construction = MetaLabelConstruction(pipeline, p_threshold=args.threshold)

    print(f"\n[1] Book momentum méta-labelé (long/short) sur {len(UNIVERSE)} titres…")
    target, _data = pipeline.compute_target_weights()
    if not target:
        print("    Book vide (données insuffisantes / aucun pari retenu). Fin.")
        acct_end = adapter.get_account()
        journal.record_snapshot(equity=float(acct_end.get("equity", 0.0)),
                                cash=float(acct_end.get("cash", 0.0)), event="run_end", mode=adapter.mode)
        adapter.disconnect()
        return
    longs = {s: w for s, w in target.items() if w > 0}
    shorts = {s: w for s, w in target.items() if w < 0}
    gross = sum(abs(w) for w in target.values())
    print(f"    {len(target)} positions (brut={gross:.2f}) : {len(longs)} longs / {len(shorts)} shorts")
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
        # Pas d'état local à persister : les ordres de ce run sont eux-mêmes la trace
        # du rééquilibrage (les prochains runs liront « 0 j depuis le dernier ordre »).

    acct_end = adapter.get_account()
    journal.record_snapshot(equity=float(acct_end.get("equity", 0.0)),
                            cash=float(acct_end.get("cash", 0.0)), event="run_end", mode=adapter.mode)
    adapter.disconnect()
    print(f"\n✅ Terminé ({label}). Journal: {journal.path}")
    print("Rappel : PAPER uniquement (méta-labeling sous biais de survie, DSR campagne à faire).")


if __name__ == "__main__":
    main()

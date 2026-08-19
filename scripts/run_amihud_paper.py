"""Book ILLIQUIDITÉ (Amihud) small-cap en **paper trading** Alpaca — forward-test.

Le facteur d'illiquidité d'Amihud a montré le meilleur profil de toute la campagne
(Sharpe L/S net +1.55, t=3.72, stable sur 3 régimes, robuste jusqu'à 300 bps de coûts).
**Mais** c'est aussi celui où le **biais de survie** frappe le plus fort : acheter les
titres les plus illiquides revient à acheter les futurs radiés, absents des panels
historiques.

Le **forward-test paper est le seul contournement rigoureux** de ce biais : il trade en
temps réel, sur l'univers tel qu'il existe aujourd'hui, radiations comprises. C'est
l'objet de ce script.

Book : long les 20 % les plus **illiquides**, short les 20 % les plus **liquides**
(dollar-volume), rééquilibré tous les 21 jours ouvrés, via le chemin audité
(OrderGateway + journal + réconciliation), **paper uniquement** (double-verrou).

⚠️ Ce que le forward-test va aussi révéler — et c'est voulu : la **faisabilité réelle**
(certains small-caps ne sont pas shortables ; les spreads réels s'appliquent). Les rejets
d'ordres sont une information, pas un bug.

Usage::

    python scripts/run_amihud_paper.py            # dry-run (sûr)
    python scripts/run_amihud_paper.py --execute  # ordres PAPER réels
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

UNIVERSE_CACHE = "/tmp/alpaca_broad_universe.json"
PRICES_CACHE = "/tmp/yahoo_broad_prices_18y.csv"
#: Fichier de halte : présent → les rééquilibrages sont bloqués (levée manuelle).
HALT_PATH = "logs/amihud_halt.json"


def _small_cap_universe(n: int) -> list[str]:
    """Les ``n`` premiers titres du tercile small-cap (par liquidité décroissante)."""
    import pandas as pd

    px = pd.read_csv(PRICES_CACHE, index_col=0, parse_dates=True)
    px = px.ffill().dropna(axis=1, thresh=int(0.5 * len(px))).dropna(how="all")
    universe = json.loads(Path(UNIVERSE_CACHE).read_text())
    ordered = [s for s in universe if s in px.columns]
    t = len(ordered) // 3
    return ordered[2 * t:][:n]


def _business_days_since_last_order(adapter, lookback: int = 200) -> int | None:
    """Jours ouvrés depuis le dernier ordre broker (état persistant côté serveur)."""
    try:
        import numpy as np
        import pandas as pd

        orders = adapter.get_orders(status="all", limit=lookback) or []
        dates = []
        for o in orders:
            ts = o.get("submitted_at") or o.get("filled_at") or o.get("created_at")
            if ts is not None:
                d = getattr(ts, "date", None)
                dates.append(d() if callable(d) else pd.Timestamp(ts).date())
        if not dates:
            return None
        return max(0, int(np.busday_count(max(dates).isoformat(), date.today().isoformat())))  # noqa: DTZ011
    except Exception as e:  # noqa: BLE001
        print(f"    (cadence : historique illisible — {e} ; rééquilibrage autorisé)")
        return None


def _peak_equity_from_journals(pattern: str = "logs/amihud_paper_*.jsonl") -> float | None:
    """Pic d'equity observé dans les journaux du book (pour le drawdown)."""
    import glob

    from financial_analyzer.trading.pnl import load_snapshots

    try:
        snaps = load_snapshots(sorted(glob.glob(pattern)))
        eqs = [float(s["equity"]) for s in snaps if isinstance(s.get("equity"), (int, float))]
        return max(eqs) if eqs else None
    except Exception:  # noqa: BLE001
        return None


def _daily_health_check(adapter, journal, equity: float, since: int, cadence: int) -> None:
    """Audit quotidien du book détenu, les jours SANS rééquilibrage."""
    from financial_analyzer.trading.book_health import check_book_health

    print(f"\nCadence : book TENU (dernier rééq. il y a {since} j < {cadence}) — "
          f"aucun ordre. AUDIT du book :")
    try:
        positions = adapter.get_positions() or []
    except Exception as e:  # noqa: BLE001
        print(f"    ⚠️ positions illisibles ({e}) — audit impossible.")
        return

    peak = _peak_equity_from_journals()
    h = check_book_health(positions, equity, peak_equity=peak)
    print(f"    {h.summary()}")
    print(f"    exposition brute {h.gross_exposure:.2f}× | nette {h.net_exposure:+.2%} "
          f"| equity {h.equity:,.0f} (pic {h.peak_equity:,.0f})")
    if h.worst:
        pires = ", ".join(f"{s} {p:+,.0f}$" for s, p in h.worst[:3])
        print(f"    pires lignes : {pires}")
    if h.alerts:
        for a in h.alerts:
            print(f"    🚨 {a}")
    else:
        print("    ✅ aucune anomalie (neutralité, levier, concentration, drawdown).")

    # Journalise l'audit + alerte via l'AlertManager si anomalie.
    try:
        journal.record_snapshot(
            equity=h.equity, cash=None, event="health_check", mode=adapter.mode,
            status=h.status, n_positions=h.n_positions, gross=h.gross_exposure,
            net=h.net_exposure, drawdown_pct=h.drawdown_pct, alerts=h.alerts,
        )
    except Exception:  # noqa: BLE001
        pass
    if h.status != "ok":
        try:
            from financial_analyzer.trading.alerts import AlertLevel, AlertManager

            mgr = AlertManager(alert_log_path="logs/alerts.jsonl", mode=adapter.mode)
            lvl = AlertLevel.ERROR if h.status == "critical" else AlertLevel.WARNING
            mgr.alert(lvl, f"Book Amihud — audit {h.status}", " ; ".join(h.alerts),
                      n_positions=h.n_positions, net=h.net_exposure,
                      drawdown_pct=h.drawdown_pct)
            print(f"    (alerte {lvl.value} émise)")
        except Exception:  # noqa: BLE001
            pass
    # Anomalie CRITIQUE (drawdown au-delà du seuil) → HALTE : on bloque les prochains
    # rééquilibrages jusqu'à revue humaine. On ne liquide PAS (un stop sur un book
    # market-neutral vend au pire moment — cf. book_health, Kaminski & Lo 2014).
    if h.status == "critical":
        from financial_analyzer.trading.book_health import raise_halt

        raise_halt(f"audit critique : {' ; '.join(h.alerts)}",
                   {"drawdown_pct": h.drawdown_pct, "equity": h.equity,
                    "peak_equity": h.peak_equity},
                   path=HALT_PATH)
        print(f"    ⛔ HALTE levée → les rééquilibrages sont BLOQUÉS jusqu'à revue.")
        print(f"       Positions conservées (pas de liquidation automatique).")
        print(f"       Pour reprendre après analyse : rm {HALT_PATH}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--execute", action="store_true", help="Ordres PAPER réels (sinon dry-run).")
    ap.add_argument("--scheduled", action="store_true", help="Ignorer si le marché est fermé.")
    ap.add_argument("--universe-size", type=int, default=200,
                    help="Nb de small-caps suivies (défaut 200 → ~40 longs / 40 shorts).")
    ap.add_argument("--window", type=int, default=60, help="Fenêtre Amihud (jours).")
    ap.add_argument("--quantile", type=float, default=0.2)
    ap.add_argument("--rebalance-every", type=int, default=21,
                    help="Cadence (jours ouvrés) — 21 = celle testée.")
    # Bande de non-transaction : DÉSACTIVÉE pour ce book. Le 0.02 hérité du book
    # méta-momentum (~10 lignes, |w| ≈ 0.10) est ici supérieur au poids d'une ligne
    # (~68 lignes, |w| ≈ 0.015) : il gèle 100 % des mouvements et écroule le Sharpe
    # 18 ans de +1.69 à +0.55 (scripts/run_amihud_module_transfer.py). Testée à
    # l'échelle du book, la bande n'apporte rien (0.01 → +1.71 vs +1.69, turnover
    # inchangé) : on ne paie pas la complexité d'un paramètre sans gain.
    ap.add_argument("--no-trade-band", type=float, default=0.0,
                    help="Bande de non-transaction (0 = désactivée, valeur testée).")
    ap.add_argument("--ignore-cadence", action="store_true")
    args = ap.parse_args()

    from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
    from financial_analyzer.trading.framework import AmihudConstruction
    from financial_analyzer.trading.journal import TradingJournal
    from financial_analyzer.trading.live_trading_pipeline import LiveTradingPipeline
    from financial_analyzer.trading.reconciliation import reconcile_orders

    universe = _small_cap_universe(args.universe_size)
    dry_run = not args.execute
    label = "DRY-RUN (aucun ordre soumis)" if dry_run else "EXÉCUTION PAPER RÉELLE"
    print("=" * 78)
    print(f"ILLIQUIDITÉ (Amihud) small-cap — Alpaca PAPER — {label}")
    print(f"Univers : {len(universe)} small-caps | fenêtre {args.window} j | "
          f"quantile {args.quantile:.0%} | cadence {args.rebalance_every} j")
    print("=" * 78)

    adapter = AlpacaAdapter.from_env(mode="paper")
    adapter.connect()

    if args.scheduled and not adapter.is_market_open():
        print("Marché FERMÉ — run planifiée ignorée.")
        adapter.disconnect()
        return

    acct = adapter.get_account()
    equity = float(acct.get("equity", 0.0))
    print(f"\nCompte paper: equity=${equity:,.2f} cash=${float(acct.get('cash', 0)):,.2f} "
          f"mode={adapter.mode}")

    journal = TradingJournal(
        f"logs/amihud_paper_{datetime.now().strftime('%Y%m%d_%H%M')}.jsonl")  # noqa: DTZ005
    # Début du run : borne la réconciliation. Sans elle, get_orders renvoie aussi les
    # ordres des stratégies précédentes du compte, tous comptés comme « ayant contourné
    # le chokepoint » -> ok=false perpétuel et critère #1 du runbook inatteignable.
    run_start = datetime.now(timezone.utc).isoformat()
    journal.record_snapshot(equity=equity, cash=float(acct.get("cash", 0.0)),
                            event="run_start", mode=adapter.mode)

    # HALTE : si une anomalie critique a été détectée précédemment, aucun nouveau
    # rééquilibrage tant qu'un humain n'a pas levé la halte. Les positions restent en
    # place (pas de liquidation automatique). L'audit continue de tourner.
    if not dry_run:
        from financial_analyzer.trading.book_health import read_halt

        halt = read_halt(HALT_PATH)
        if halt.active:
            print(f"\n⛔ HALTE ACTIVE depuis {halt.raised_at[:19]} — rééquilibrage REFUSÉ.")
            print(f"   Motif : {halt.reason}")
            print(f"   Positions conservées. Audit du book quand même :")
            _daily_health_check(adapter, journal, equity, -1, args.rebalance_every)
            print(f"\n   Pour reprendre après revue : rm {HALT_PATH}")
            journal.record_snapshot(equity=equity, cash=float(acct.get("cash", 0.0)),
                                    event="run_end", mode=adapter.mode, halted=True)
            adapter.disconnect()
            return

    gate_active = (not dry_run) and (not args.ignore_cadence)
    if gate_active:
        since = _business_days_since_last_order(adapter)
        if since is not None and since < args.rebalance_every:
            # Jour SANS rééquilibrage : on ne se contente pas de « rien à faire » — on
            # AUDITE le book détenu (dérive de neutralité/levier, concentration,
            # drawdown, positions orphelines) et on alerte si nécessaire.
            _daily_health_check(adapter, journal, equity, since, args.rebalance_every)
            journal.record_snapshot(equity=equity, cash=float(acct.get("cash", 0.0)),
                                    event="run_end", mode=adapter.mode)
            adapter.disconnect()
            return

    # Le book compte ~2×quantile×N positions : le RiskGuard par défaut (20 lignes)
    # les rejetterait. On l'ajuste à la taille réelle du book, en gardant des limites
    # de concentration serrées (chaque ligne est minuscule).
    n_pos = int(2 * args.quantile * len(universe))
    risk_config = {
        "max_position_size": max(equity * 0.05, 5000.0),
        "max_position_pct": 0.05,
        "max_total_positions": max(30, n_pos + 20),
        "max_drawdown": -0.25,
        "max_daily_loss": max(equity * 0.10, 1000.0),
        "max_leverage": 2.0,  # long/short : le brut atteint ~2× le net
        "enable_circuit_breaker": True,
    }
    pipeline = LiveTradingPipeline(broker_adapter=adapter, tickers=universe, journal=journal,
                                   no_trade_band=max(0.0, args.no_trade_band),
                                   risk_config=risk_config)
    pipeline.construction = AmihudConstruction(pipeline, window=args.window,
                                               quantile=args.quantile)

    print(f"\n[1] Book illiquidité (long illiquides / short liquides)…")
    target, _data = pipeline.compute_target_weights()
    if not target:
        print("    Book vide (données insuffisantes). Fin.")
        acct_end = adapter.get_account()
        journal.record_snapshot(equity=float(acct_end.get("equity", 0.0)),
                                cash=float(acct_end.get("cash", 0.0)),
                                event="run_end", mode=adapter.mode)
        adapter.disconnect()
        return
    longs = {s: w for s, w in target.items() if w > 0}
    shorts = {s: w for s, w in target.items() if w < 0}
    print(f"    {len(target)} positions (brut={sum(abs(w) for w in target.values()):.2f}, "
          f"net={sum(target.values()):+.2f}) : {len(longs)} longs (illiquides) / "
          f"{len(shorts)} shorts (liquides)")
    for sym, w in sorted(target.items(), key=lambda kv: kv[1], reverse=True)[:10]:
        print(f"      {sym:6s} {w * 100:+6.2f}%")
    if len(target) > 10:
        print(f"      … et {len(target) - 10} autres")

    print(f"\n[2] Chaîne complète run() via OrderGateway (dry_run={dry_run})…")
    result = pipeline.run(force=True, dry_run=dry_run)
    print(f"    statut={result['status']}  générés={result.get('orders_generated', 0)}  "
          f"exécutés={result.get('orders_executed', 0)}  rejetés={result.get('orders_rejected', 0)}")
    rejects = [r for r in result.get("execution_results", []) if r["status"] == "rejected"]
    if rejects:
        print(f"\n    ⚠️ {len(rejects)} rejets — information de FAISABILITÉ (shorts "
              f"indisponibles, liquidité) :")
        for r in rejects[:8]:
            print(f"      {r['order']['side']:4s} {r['order']['symbol']:6s} — "
                  f"{r.get('reason', '')[:70]}")

    if not dry_run:
        print("\n[3] Réconciliation journal vs broker…")
        recon = reconcile_orders(journal.orders(),
                                 adapter.get_orders(status="all", limit=400) or [],
                                 since=run_start)
        journal.record_reconciliation(recon.to_dict())
        print(f"    {'✅' if recon.ok else '🚨'} {recon.summary()}")

    acct_end = adapter.get_account()
    journal.record_snapshot(equity=float(acct_end.get("equity", 0.0)),
                            cash=float(acct_end.get("cash", 0.0)),
                            event="run_end", mode=adapter.mode)
    adapter.disconnect()
    print(f"\n✅ Terminé ({label}). Journal: {journal.path}")
    print("Rappel : PAPER uniquement. Le forward-test sert précisément à contourner le")
    print("biais de survie du backtest — il trade l'univers réel, radiations comprises.")


if __name__ == "__main__":
    main()

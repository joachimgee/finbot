"""Moniteur de décroissance du signal ILLIQUIDITÉ (Amihud) — le signal du book en cours.

Le book paper est désormais piloté par l'illiquidité d'Amihud. Comme pour momentum, il
faut détecter si l'edge se **dégrade** ou s'**inverse** (crowding, changement de régime
de liquidité) plutôt que de le découvrir dans le P&L.

Ré-évalue la santé récente du facteur sur une fenêtre glissante, avec **volumes
consolidés** (Yahoo — le feed Alpaca IEX ne rapporte que ~4 % du volume réel), et alerte
via l'``AlertManager`` si l'edge est dégradé (Sharpe L/S < 0) ou inversé (IC < 0).

Lecture seule. Codes de sortie : 0 = sain, 1 = dégradé, 2 = mort.

Usage::

    python scripts/monitor_amihud_decay.py
    python scripts/monitor_amihud_decay.py --lookback 378   # ~18 mois
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

_EXIT = {"healthy": 0, "degraded": 1, "dead": 2}
#: Référence du backtest 18 ans (2008-2026, coûts 60 bps), mesurée par le MÊME
#: chemin de code que ce moniteur (``evaluate_signal``, IC à l'horizon de détention
#: de 21 j, sans recouvrement) — sinon la base et la mesure ne sont pas comparables.
BASELINE_SHARPE = 2.12
BASELINE_IC_T = 4.37


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--universe-size", type=int, default=200)
    ap.add_argument("--lookback", type=int, default=252, help="Jours récents évalués (~1 an).")
    ap.add_argument("--window", type=int, default=60, help="Fenêtre Amihud.")
    ap.add_argument("--reb", type=int, default=21)
    ap.add_argument("--quantile", type=float, default=0.2)
    ap.add_argument("--cost-bps", type=float, default=60.0)
    ap.add_argument("--health-log", default="logs/amihud_health.jsonl")
    ap.add_argument("--no-alert", action="store_true")
    args = ap.parse_args()

    from datetime import datetime, timedelta, timezone

    import pandas as pd

    from financial_analyzer.backtest.illiquidity import amihud_illiquidity, prepare_panels
    from financial_analyzer.backtest.signal_evaluation import CostModel, evaluate_signal
    from financial_analyzer.data.yahoo_history import fetch_daily_ohlcv_yahoo

    # Univers : même tercile small-cap que le book.
    px = pd.read_csv("/tmp/yahoo_broad_prices_18y.csv", index_col=0, parse_dates=True)
    px = px.ffill().dropna(axis=1, thresh=int(0.5 * len(px))).dropna(how="all")
    universe = json.loads(Path("/tmp/alpaca_broad_universe.json").read_text())
    ordered = [s for s in universe if s in px.columns]
    t = len(ordered) // 3
    small = ordered[2 * t:][: args.universe_size]

    print("=" * 78)
    print(f"MONITEUR AMIHUD — fenêtre récente {args.lookback} j, {len(small)} small-caps")
    print("=" * 78)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=int(args.lookback * 1.6) + args.window * 2 + 60)
    o = fetch_daily_ohlcv_yahoo(small, start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
    if len(o) < 20:
        print("❌ Données insuffisantes — statut inconnu.")
        return 1
    # Définition du signal : importée, jamais recalculée (cf. backtest/illiquidity.py).
    close, vol = prepare_panels(
        pd.DataFrame({s: d["close"] for s, d in o.items()}),
        pd.DataFrame({s: d["volume"] for s, d in o.items()}),
    )
    amihud = amihud_illiquidity(close, vol, window=args.window)
    rets = close.pct_change()
    recent = amihud.index[-args.lookback:]
    amihud, rets = amihud.reindex(recent), rets.reindex(recent)

    # Évaluation par le MÊME primitif que le portail (``evaluate_signal``) plutôt que
    # par une boucle recopiée : un moniteur qui mesure autrement que le portail finit
    # par diverger de lui. C'est précisément ce qui s'était produit ici — l'IC était
    # calculé contre le rendement du LENDEMAIN alors que le book détient 21 jours.
    # Sur la fenêtre récente : t=+0.62 à 1 j contre t=+3.91 à 21 j ; et sur 18 ans
    # l'IC à 1 j est NÉGATIF (t=-1.74), donc l'alarme « edge inversé » se serait
    # déclenchée à tort sur un signal parfaitement sain. ``evaluate_signal`` mesure
    # désormais l'IC à l'horizon de détention, sans recouvrement.
    res = evaluate_signal(
        amihud, rets,
        cost_model=CostModel(commission_bps=args.cost_bps, slippage_bps=0.0),
        quantile=args.quantile, long_short=True, rebalance_every=args.reb,
    )
    if res.n_periods < 30:
        print("❌ Trop peu d'observations — statut inconnu.")
        return 1

    sharpe = res.net_sharpe
    ic_mean, ic_t = res.ic_mean, res.ic_t_stat
    n_ic = max(1, res.n_periods // args.reb)

    reasons = []
    if sharpe < 0:
        reasons.append(f"Sharpe L/S {sharpe:+.2f} < 0 (edge économique perdu)")
    if ic_mean < 0:
        reasons.append(f"IC moyen {ic_mean:+.4f} < 0 (edge inversé)")
    status = "dead" if len(reasons) == 2 else ("degraded" if reasons else "healthy")
    if status == "healthy" and sharpe < 0.5 * BASELINE_SHARPE:
        reasons.append(f"Sharpe récent {sharpe:+.2f} < 50 % de la base {BASELINE_SHARPE:+.2f} "
                       f"(fenêtre courte — informatif, non bloquant)")

    print(f"\n  [{status.upper()}] Sharpe L/S récent {sharpe:+.2f} (base {BASELINE_SHARPE:+.2f}) | "
          f"IC(h={res.ic_horizon}j) {ic_mean:+.4f} (t={ic_t:+.2f}, base t={BASELINE_IC_T:+.2f}) | "
          f"{res.n_periods} jours, ~{n_ic} rééq.")
    for r in reasons:
        print(f"    • {r}")

    try:
        p = Path(args.health_log)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(), "kind": "signal_health",
                "signal": "amihud_illiquidity", "status": status, "net_sharpe": sharpe,
                "ic_mean": ic_mean, "ic_t_stat": ic_t, "ic_horizon": res.ic_horizon,
                "n_days": res.n_periods, "reasons": reasons,
            }, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001
        print(f"  (journal non écrit : {e})")

    if status != "healthy" and not args.no_alert:
        from financial_analyzer.trading.alerts import AlertLevel, AlertManager

        mgr = AlertManager(alert_log_path="logs/alerts.jsonl", mode="paper")
        lvl = AlertLevel.ERROR if status == "dead" else AlertLevel.WARNING
        mgr.alert(lvl, f"Décroissance du signal Amihud ({status})", " ; ".join(reasons),
                  signal="amihud_illiquidity", net_sharpe=sharpe, ic_mean=ic_mean)
        print(f"\n  🚨 Alerte {lvl.value} émise.")
    elif status == "healthy":
        print("\n  ✅ Signal sain — aucune alerte.")

    print("\nRappel : fenêtre courte → Sharpe/IC bruités ; les alarmes portent sur les SIGNES")
    print("(Sharpe < 0, IC < 0), pas sur l'écart de magnitude à la base 18 ans. L'IC est")
    print(f"mesuré à l'horizon de DÉTENTION ({args.reb} j), pas au lendemain : pour un signal")
    print("d'illiquidité, l'IC à 1 jour est du bruit (négatif sur 18 ans) et ferait hurler")
    print("l'alarme sur un signal sain.")
    return _EXIT.get(status, 1)


if __name__ == "__main__":
    raise SystemExit(main())

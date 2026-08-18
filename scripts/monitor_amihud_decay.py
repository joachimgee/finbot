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
#: Référence du backtest 18 ans (2008-2026, coûts 60 bps).
BASELINE_SHARPE = 2.16
BASELINE_IC_T = 2.29


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

    import numpy as np
    import pandas as pd

    from financial_analyzer.backtest.classic_factors import daily_returns
    from financial_analyzer.backtest.signal_evaluation import cross_sectional_weights
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
    close = pd.DataFrame({s: d["close"] for s, d in o.items()}).sort_index().ffill()
    vol = pd.DataFrame({s: d["volume"] for s, d in o.items()}).sort_index()
    close = close.dropna(axis=1, thresh=int(0.6 * len(close))).dropna(how="all")
    vol = vol.reindex(columns=close.columns, index=close.index)

    rets = daily_returns(close)
    dv = (close * vol).replace(0, np.nan)
    amihud = (rets.abs() / dv).rolling(args.window).mean() * 1e9
    recent = amihud.index[-args.lookback:]
    amihud, rets = amihud.reindex(recent), rets.reindex(recent)

    cost = args.cost_bps / 1e4
    fwd = rets.shift(-1)
    reb_set = {amihud.index[i] for i in range(0, len(amihud.index), args.reb)}
    cur = prev = pd.Series(dtype=float)
    out, ics = {}, []
    for dt in amihud.index:
        to = 0.0
        row = amihud.loc[dt].dropna()
        if dt in reb_set and len(row) >= 10:
            w = cross_sectional_weights(row, quantile=args.quantile, long_short=True)
            w = w[w.abs() > 1e-12]
            idx = w.index.union(prev.index)
            to = float((w.reindex(idx).fillna(0.0) - prev.reindex(idx).fillna(0.0)).abs().sum())
            cur = prev = w
            if dt in fwd.index:
                b = fwd.loc[dt]
                m = row.notna() & b.notna()
                if m.sum() >= 10:
                    ics.append(float(row[m].corr(b[m], method="spearman")))
        if dt in fwd.index and len(cur):
            f = fwd.loc[dt]
            out[dt] = float((cur.reindex(f.index).fillna(0.0) * f.fillna(0.0)).sum()) - to * cost
    s = pd.Series(out).dropna()
    if len(s) < 30:
        print("❌ Trop peu d'observations — statut inconnu.")
        return 1

    sharpe = float(s.mean() / s.std(ddof=1) * np.sqrt(252)) if s.std(ddof=1) > 0 else 0.0
    ic = pd.Series(ics).dropna()
    ic_mean = float(ic.mean()) if len(ic) else 0.0
    ic_t = float(ic.mean() / ic.std(ddof=1) * np.sqrt(len(ic))) if len(ic) > 2 and ic.std(ddof=1) > 0 else 0.0

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
          f"IC moyen {ic_mean:+.4f} (t={ic_t:+.2f}, base t={BASELINE_IC_T:+.2f}) | "
          f"{len(s)} jours, {len(ic)} rééq.")
    for r in reasons:
        print(f"    • {r}")

    try:
        p = Path(args.health_log)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(), "kind": "signal_health",
                "signal": "amihud_illiquidity", "status": status, "net_sharpe": sharpe,
                "ic_mean": ic_mean, "ic_t_stat": ic_t, "n_days": len(s), "reasons": reasons,
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
    print("(Sharpe < 0, IC < 0), pas sur l'écart de magnitude à la base 18 ans.")
    return _EXIT.get(status, 1)


if __name__ == "__main__":
    raise SystemExit(main())

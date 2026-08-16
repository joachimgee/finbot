"""Moniteur de décroissance du signal validé (garde-fou du point de défaillance unique).

Ré-évalue la **santé récente** de `momentum_12_1` (le seul signal du registre) sur
une fenêtre glissante, avec **le portail existant** (mêmes coûts Alpaca calibrés), et
**alerte** via l'`AlertManager` si l'edge s'est dégradé (Sharpe net < 0) ou inversé
(IC moyen < 0). Sans ce garde-fou, l'unique edge pourrait cesser de marcher en
production sans que rien ne le détecte (*factor decay* / crowding).

Lecture seule : n'active jamais le live, ne modifie pas le registre. Persiste la
santé dans ``logs/signal_health.jsonl`` pour suivre la tendance. Codes de sortie :
0 = sain, 1 = dégradé, 2 = mort — pratique en cron/CI.

Usage::

    python scripts/monitor_signal_decay.py
    python scripts/monitor_signal_decay.py --lookback 189 --signal momentum_12_1
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

UNIVERSE = sorted({
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "JPM", "V",
    "MA", "UNH", "JNJ", "PG", "HD", "XOM", "CVX", "KO", "PEP", "COST",
    "WMT", "BAC", "WFC", "DIS", "NFLX", "INTC", "AMD", "QCOM", "TXN", "ORCL",
    "CRM", "ADBE", "CSCO", "PFE", "MRK", "ABBV", "TMO", "ABT", "LLY", "NKE",
    "MCD", "SBUX", "LOW", "CAT", "BA", "GE", "HON", "UNP", "UPS", "GS",
})

_EXIT = {"healthy": 0, "degraded": 1, "dead": 2}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--signal", default="momentum_12_1", help="Signal du registre à surveiller.")
    ap.add_argument("--lookback", type=int, default=252, help="Périodes récentes évaluées (~1 an).")
    ap.add_argument("--start", default="2023-08-01")
    ap.add_argument("--end", default=None,
                    help="Date de fin (défaut : aujourd'hui — indispensable pour un "
                         "suivi récurrent qui doit voir les données les plus fraîches).")
    ap.add_argument("--price-cache", default=None,
                    help="Cache prix (défaut : estampillé par la date de fin, pour "
                         "re-fetcher des données fraîches à chaque exécution récurrente).")
    ap.add_argument("--health-log", default="logs/signal_health.jsonl")
    ap.add_argument("--no-alert", action="store_true", help="Ne pas émettre d'alerte (rapport seul).")
    args = ap.parse_args()

    import json
    from datetime import datetime, timezone

    from financial_analyzer.backtest.classic_factors import compute_classic_factors, daily_returns
    from financial_analyzer.backtest.signal_monitor import evaluate_signal_health
    from financial_analyzer.data.alpaca_history import load_or_fetch

    end = args.end or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    print("=" * 78)
    print(f"MONITEUR DE DÉCROISSANCE — signal '{args.signal}' (fenêtre {args.lookback} pér.)")
    print("=" * 78)

    price_cache = args.price_cache or f"/tmp/alpaca_signal_monitor_{end}.csv"
    px = load_or_fetch(UNIVERSE, args.start, end, cache_path=price_cache)
    px = px[[c for c in UNIVERSE if c in px.columns]].ffill()
    px = px.dropna(axis=1, how="any").dropna(how="all")

    factors = compute_classic_factors(px)
    if args.signal not in factors:
        print(f"⚠️ Signal '{args.signal}' introuvable dans compute_classic_factors — abandon.")
        return 1
    scores = factors[args.signal]
    returns = daily_returns(px)

    health = evaluate_signal_health(args.signal, scores, returns, lookback=args.lookback)
    print(f"\nPanel : {px.shape[0]} jours × {px.shape[1]} titres")
    print(f"\n  {health.summary()}")

    # Persistance (best-effort) de la santé pour suivre la tendance dans le temps.
    try:
        p = Path(args.health_log)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            rec = {"ts": datetime.now(timezone.utc).isoformat(), "kind": "signal_health",
                   "signal": health.name, "status": health.status, "ic_mean": health.ic_mean,
                   "ic_t_stat": health.ic_t_stat, "net_sharpe": health.net_sharpe,
                   "n_periods": health.n_periods, "reasons": health.reasons}
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception as e:  # noqa: BLE001 - la persistance ne doit jamais casser le moniteur
        print(f"  (journal de santé non écrit : {e})")

    # Alerte si dégradé/mort (fail-safe : l'AlertManager ne lève jamais).
    if health.status != "healthy" and not args.no_alert:
        from financial_analyzer.trading.alerts import AlertLevel, AlertManager
        mgr = AlertManager(alert_log_path="logs/alerts.jsonl", mode="paper")
        level = AlertLevel.ERROR if health.status == "dead" else AlertLevel.WARNING
        mgr.alert(level, f"Décroissance du signal '{health.name}' ({health.status})",
                  health.summary(), signal=health.name, status=health.status,
                  net_sharpe=health.net_sharpe, ic_mean=health.ic_mean)
        print(f"\n  🚨 Alerte {level.value} émise (canal : log + logs/alerts.jsonl"
              f"{' + webhook' if mgr.webhook_url else ''}).")
    elif health.status == "healthy":
        print("\n  ✅ Signal sain — aucune alerte.")

    print("\nRappel : la fenêtre courte sous-estime l'IC t (t∝√n) — les alarmes portent")
    print("sur le Sharpe net < 0 et le signe de l'IC (scale-free), pas sur l'IC t.")
    return _EXIT.get(health.status, 1)


if __name__ == "__main__":
    raise SystemExit(main())

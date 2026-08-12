"""Sentiment FinBERT (texte réel) via le portail, 80 large-caps (famille décorrélée).

Le test de sentiment précédent (IC t = −0.93) notait le champ ``insight`` **brut**
de Polygon (±1/0). Ici on note le **texte** des articles (titre + description) avec
**FinBERT** (ProsusAI/finbert) — un signal bien plus fin — puis on agrège en panel
**point-in-time** (``published_utc``, aucun look-ahead) et on passe le **même
portail**. Le sentiment est une *famille de données différente* (news, pas prix) →
potentiellement **décorrélée** du momentum → vraie breadth.

Étapes :
1. articles avec texte (Polygon, caché) ; 2. score FinBERT ∈ [−1,1] ;
3. panel PIT (fenêtre courte, news décroît vite) ; 4. portail + PSR + corrélation
au momentum ; 5. inscription **seulement** si IC t > 2 ET Sharpe net > 0.

⚠️ Sentiment natif/texte Polygon dense surtout à partir de ~2024 ; échantillon court.

Usage::

    python scripts/run_finbert_sentiment_alpaca.py --fetch-only   # étape lente (5 req/min)
    python scripts/run_finbert_sentiment_alpaca.py                 # score + portail
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import numpy as np
import pandas as pd

from financial_analyzer.backtest.classic_factors import (
    compute_classic_factors,
    daily_returns,
)
from financial_analyzer.backtest.robustness import probabilistic_sharpe_ratio
from financial_analyzer.backtest.signal_evaluation import (
    CostModel,
    walk_forward_evaluate,
)
from financial_analyzer.backtest.validation_gate import evaluate_signal_gate
from financial_analyzer.data.alpaca_history import load_or_fetch
from financial_analyzer.data.polygon_news_sentiment import (
    build_sentiment_panel,
    build_sentiment_surprise_panel,
    fetch_news_articles,
)

DEFAULT_UNIVERSE = sorted(
    {
        "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "AVGO", "JPM", "V",
        "MA", "UNH", "JNJ", "PG", "HD", "XOM", "CVX", "KO", "PEP", "COST",
        "WMT", "BAC", "WFC", "DIS", "NFLX", "INTC", "AMD", "QCOM", "TXN", "ORCL",
        "CRM", "ADBE", "CSCO", "PFE", "MRK", "ABBV", "TMO", "ABT", "LLY", "NKE",
        "MCD", "SBUX", "LOW", "CAT", "BA", "GE", "HON", "UNP", "UPS", "GS",
        "MS", "AXP", "BLK", "C", "SCHW", "T", "VZ", "CMCSA", "PM", "MO",
        "IBM", "NOW", "INTU", "AMAT", "MU", "LRCX", "GILD", "AMGN", "BMY", "DE",
        "MMM", "LMT", "RTX", "SPGI", "ISRG", "MDT", "CVS", "TGT", "COP", "PYPL",
    }
)


def _load_articles(args) -> pd.DataFrame:
    """Fetch **par ticker avec checkpoint** : un aléa proxy ne perd pas tout, et un
    re-lancement reprend là où on s'était arrêté (tickers déjà en cache sautés)."""
    cache = Path(args.article_cache)
    done: pd.DataFrame = pd.read_parquet(cache) if cache.exists() else pd.DataFrame(
        columns=["ticker", "published_utc", "text"])
    have = set(done["ticker"].unique()) if not done.empty else set()
    if args.refetch:
        done, have = done.iloc[0:0], set()
    todo = [t for t in DEFAULT_UNIVERSE if t not in have]
    if not todo:
        print(f"Articles (cache complet) : {len(done)} lignes, {len(have)} tickers")
        return done
    print(f"Fetch Polygon (5 req/min) : {len(todo)} tickers restants "
          f"({len(have)} déjà en cache)…")
    parts = [done] if not done.empty else []
    for i, tk in enumerate(todo, 1):
        one = fetch_news_articles([tk], args.start, args.end,
                                  max_pages_per_ticker=args.max_pages)
        parts.append(one)
        # Checkpoint après chaque ticker : la progression survit à un crash.
        pd.concat(parts, ignore_index=True).to_parquet(cache)
        print(f"  [{i}/{len(todo)}] {tk}: +{len(one)} articles "
              f"(total {sum(len(p) for p in parts)})")
    return pd.concat(parts, ignore_index=True)


def _score_finbert(df: pd.DataFrame, batch_size: int) -> pd.DataFrame:
    from financial_analyzer.sentiment.finbert_engine import FinBERTEngine

    print(f"Scoring FinBERT de {len(df)} articles (CPU, batch={batch_size})…")
    engine = FinBERTEngine(batch_size=batch_size)
    scores = engine.batch_sentiment(df["text"].tolist())
    out = df.copy()
    out["sentiment"] = [s["score"] for s in scores]
    return out[["ticker", "published_utc", "sentiment"]]


def _oos_net(scores, returns, cost, reb, splits):
    out = walk_forward_evaluate(scores, returns, n_splits=splits, cost_model=cost,
                               rebalance_every=reb)
    oos = out["oos"]
    if oos is None or oos.net_equity_curve.empty:
        return None
    return oos.net_equity_curve.pct_change().dropna()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2023-08-01")
    ap.add_argument("--end", default="2026-07-31")
    ap.add_argument("--rebalance", type=int, default=5, help="News décroît vite -> reb court.")
    ap.add_argument("--splits", type=int, default=5)
    ap.add_argument("--window", type=int, default=7, help="Fenêtre d'agrégation (jours).")
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--max-pages", type=int, default=4)
    ap.add_argument("--price-cache", default="/tmp/alpaca_rebalance_sweep.csv")
    ap.add_argument("--article-cache", default="/tmp/polygon_articles_text.parquet")
    ap.add_argument("--scored-cache", default="/tmp/finbert_scored.parquet")
    ap.add_argument("--refetch", action="store_true")
    ap.add_argument("--fetch-only", action="store_true", help="Ne fait que l'étape fetch.")
    ap.add_argument("--signal", choices=["level", "surprise"], default="level",
                    help="'level' = sentiment moyen ; 'surprise' = innovation (récent − norme).")
    ap.add_argument("--fast", type=int, default=3, help="Fenêtre récente (surprise).")
    ap.add_argument("--slow", type=int, default=30, help="Norme glissante (surprise).")
    args = ap.parse_args()

    articles = _load_articles(args)
    if args.fetch_only:
        return
    if articles.empty:
        print("Aucun article — abandon.")
        return

    # Score FinBERT (caché : le scoring est déterministe et coûteux).
    scored_path = Path(args.scored_cache)
    if scored_path.exists() and not args.refetch:
        scored = pd.read_parquet(scored_path)
        print(f"Scores FinBERT (cache) : {len(scored)} lignes")
    else:
        scored = _score_finbert(articles, args.batch_size)
        scored.to_parquet(scored_path)
    print(f"  sentiment moyen={scored['sentiment'].mean():+.3f}, "
          f"part non-neutre={(scored['sentiment'].abs() > 0.1).mean():.0%}")

    prices = load_or_fetch(DEFAULT_UNIVERSE, args.start, args.end, cache_path=args.price_cache)
    prices = prices.dropna(axis=1, thresh=int(0.8 * len(prices))).ffill()
    prices = prices.dropna(axis=1, how="any").dropna(how="all")
    returns = daily_returns(prices)
    cost = CostModel.alpaca_equities()

    if args.signal == "surprise":
        panel = build_sentiment_surprise_panel(
            scored, prices.index, fast_days=args.fast, slow_days=args.slow)
        desc = f"SURPRISE (innovation {args.fast}j vs norme {args.slow}j)"
    else:
        panel = build_sentiment_panel(scored, prices.index, window_days=args.window)
        desc = f"NIVEAU (fenêtre {args.window}j)"
    panel = panel.reindex(columns=prices.columns)
    cov = float(panel.notna().mean().mean())
    print(f"Panel sentiment [{args.signal}] : {prices.shape[0]} jours × {panel.shape[1]} "
          f"titres, couverture non-NaN={cov:.0%}\n")

    print("=" * 74)
    print(f"SENTIMENT FinBERT {desc} — portail (reb={args.rebalance})")
    print("=" * 74)
    verdict = evaluate_signal_gate(
        f"finbert_{args.signal}", panel, returns, cost_model=cost,
        rebalance_every=args.rebalance, n_splits=args.splits,
    )
    print("\n  " + verdict.summary())

    sent_oos = _oos_net(panel, returns, cost, args.rebalance, args.splits)
    if sent_oos is not None:
        psr = probabilistic_sharpe_ratio(sent_oos, sr_benchmark=0.0)
        print(f"  PSR (P[Sharpe vrai > 0], corrigé skew/kurtosis/T) : {psr:.2f}")
        factors = compute_classic_factors(prices)
        mom_oos = _oos_net(factors["momentum_12_1"], returns, cost, args.rebalance, args.splits)
        if mom_oos is not None:
            idx = sent_oos.index.intersection(mom_oos.index)
            if len(idx) > 10:
                corr = float(np.corrcoef(sent_oos.loc[idx], mom_oos.loc[idx])[0, 1])
                print(f"  Corrélation OOS sentiment↔momentum : {corr:+.2f} "
                      f"(bas = famille décorrélée = breadth)")

    print("\n--- Décision d'inscription ---")
    if verdict.passed:
        print("  ✅ FinBERT passe le portail. Candidat à inscrire (famille news,")
        print("     à combiner par risk-weighting avec momentum si décorrélé).")
    else:
        print("  ❌ Ne passe pas le portail -> NON inscrit. Raisons ci-dessus.")


if __name__ == "__main__":
    main()

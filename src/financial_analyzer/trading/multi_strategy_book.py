"""Book cible du multi-stratégie (momentum + PCA-résiduel + paires) — pour le live.

Traduit les trois familles décorrélées (cf. `backtest/multi_strategy`) en **poids
cibles par symbole** *aujourd'hui*, prêts à exécuter. Chaque famille produit ses
positions courantes (long/short), on normalise chacune à brut = 1, puis on mélange
par les **poids de famille** (risk-weighting estimé sur l'historique) et on
re-normalise le brut du book combiné.

⚠️ Long/short (market-neutral) : PCA-résiduel et momentum sont cross-section
long/short ; les paires sont dollar-neutres. Le book combiné a des poids négatifs
(ventes à découvert) — n'exécuter qu'en **paper** tant que les familles ne sont pas
validées (seul momentum l'est ; paires/PCA sont en forward-test).

Snapshot : les positions paires utilisent la **règle d'entrée** au z-score courant
(pas d'état inter-jour) — approximation raisonnable pour un rééquilibrage périodique.
"""
from __future__ import annotations

import pandas as pd

from financial_analyzer.backtest.classic_factors import compute_classic_factors
from financial_analyzer.backtest.pairs_trading import find_cointegrated_pairs
from financial_analyzer.backtest.residual_momentum import pca_residual_momentum_score
from financial_analyzer.backtest.signal_evaluation import cross_sectional_weights

__all__ = ["combined_book"]

# Poids de famille par défaut : issus du risk-parity mesuré (run_multi_strategy_alpaca).
DEFAULT_FAMILY_WEIGHTS = {"momentum": 0.18, "pca_resid": 0.30, "pairs": 0.52}


def _norm_gross(book: dict[str, float]) -> dict[str, float]:
    gross = sum(abs(v) for v in book.values())
    return {s: v / gross for s, v in book.items()} if gross > 0 else {}


def _cross_sectional_book(score_row: pd.Series, quantile: float) -> dict[str, float]:
    w = cross_sectional_weights(score_row, quantile=quantile, long_short=True)
    return {s: float(v) for s, v in w.items() if abs(v) > 1e-9}


def _pairs_book(
    prices: pd.DataFrame, form: int, z_lookback: int, entry: float, stop: float,
    max_pairs: int, corr_min: float,
) -> dict[str, float]:
    pairs = find_cointegrated_pairs(prices.iloc[-form:], max_pairs=max_pairs,
                                    corr_min=corr_min)
    book: dict[str, float] = {}
    for p in pairs:
        a, b, beta = p["a"], p["b"], p["beta"]
        spread = prices[a] - beta * prices[b]
        tail = spread.tail(z_lookback)
        sd = tail.std(ddof=1)
        if sd == 0:
            continue
        z = (spread.iloc[-1] - tail.mean()) / sd
        pos = -1 if z > entry else (1 if z < -entry else 0)  # short/long spread
        if pos == 0 or abs(z) > stop:
            continue
        gross = 1.0 + abs(beta)
        book[a] = book.get(a, 0.0) + pos / gross
        book[b] = book.get(b, 0.0) - pos * beta / gross
    return book


def combined_book(
    prices: pd.DataFrame,
    family_weights: dict[str, float] | None = None,
    *,
    quantile: float = 0.2,
    pca_components: int = 5,
    pairs_form: int = 252,
    z_lookback: int = 21,
    entry: float = 2.0,
    stop: float = 4.0,
    max_pairs: int = 15,
    corr_min: float = 0.7,
) -> dict[str, float]:
    """Poids cibles combinés par symbole (long/short, brut ≈ 1) pour aujourd'hui.

    Args:
        prices: panel de clôtures (dates × tickers), historique suffisant (≥252 j).
        family_weights: pondération des familles (défaut = risk-parity mesuré).

    Returns:
        ``{symbole: poids net}`` (positif = long, négatif = short), brut normalisé à 1.
        Vide si données insuffisantes pour toute famille.
    """
    fw = family_weights or DEFAULT_FAMILY_WEIGHTS
    books: dict[str, dict[str, float]] = {}

    mom = compute_classic_factors(prices).get("momentum_12_1")
    if mom is not None and not mom.dropna(how="all").empty:
        books["momentum"] = _norm_gross(_cross_sectional_book(mom.iloc[-1], quantile))

    pca = pca_residual_momentum_score(prices, n_components=pca_components)
    if not pca.dropna(how="all").empty:
        books["pca_resid"] = _norm_gross(_cross_sectional_book(pca.iloc[-1], quantile))

    pb = _pairs_book(prices, pairs_form, z_lookback, entry, stop, max_pairs, corr_min)
    if pb:
        books["pairs"] = _norm_gross(pb)

    combined: dict[str, float] = {}
    for fam, book in books.items():
        w = fw.get(fam, 0.0)
        for sym, v in book.items():
            combined[sym] = combined.get(sym, 0.0) + w * v
    return _norm_gross(combined)

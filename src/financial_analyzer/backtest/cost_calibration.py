"""Calibration empirique du coût de transaction (P1) sur données réelles.

Le modèle de coûts (``CostModel``) pilote *tous* les verdicts de validation :
un coût trop haut écarte des signaux tradeables, trop bas fait passer du bruit.
Il doit donc refléter le broker réel — ici **Alpaca actions US**, qui est
**sans commission** ; le coût dominant est l'**écart bid-ask effectif** (plus un
léger impact de marché) qu'un ordre au marché traverse.

Deux mesures, avec leurs limites :

* **Cotations bid/ask réelles** (:func:`effective_spread_bps`) — la vérité
  microstructure : ``(ask - bid) / mid``. C'est la mesure *primaire*. Sur le feed
  IEX gratuit et hors séance, quelques cotations sont périmées (spreads absurdes) :
  on **écrête** (:func:`summarize_quote_spreads`) avant d'agréger en médiane.
* **High-low de Corwin & Schultz (2012)** (:func:`corwin_schultz_spread`) — déduit
  un spread des barres *quotidiennes*, sans cotations. ATTENTION : sur données
  quotidiennes de titres liquides, il **confond la volatilité intra-journalière
  avec le spread et SURESTIME massivement** (dizaines de bps là où le vrai spread
  est de quelques bps). On ne l'utilise que comme **borne haute** indicative, pas
  comme calibration.

Le **coût aller simple** = moitié de l'écart effectif (traverser le spread coûte
un demi-spread par côté) + un tampon d'impact optionnel.

Références :
    Corwin, S. A., & Schultz, P. (2012). A Simple Way to Estimate the Bid-Ask
    Spread from Daily High and Low Prices. Journal of Finance, 67(2).
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = [
    "QuoteSpreadEstimate",
    "SpreadEstimate",
    "corwin_schultz_spread",
    "effective_spread_bps",
    "estimate_effective_spread_bps",
    "summarize_quote_spreads",
]


def effective_spread_bps(bid: float, ask: float) -> float | None:
    """Écart bid-ask effectif d'une cotation, en bps : ``(ask - bid) / mid``.

    Retourne ``None`` si la cotation est invalide (prix ≤ 0, ask < bid).
    """
    if bid is None or ask is None:
        return None
    bid = float(bid)
    ask = float(ask)
    if bid <= 0 or ask <= 0 or ask < bid:
        return None
    mid = (bid + ask) / 2.0
    return (ask - bid) / mid * 1e4


@dataclass(frozen=True)
class QuoteSpreadEstimate:
    """Résumé d'une calibration à partir de cotations bid/ask réelles."""

    n_quotes: int              # cotations retenues après écrêtage
    n_dropped: int             # cotations écartées (périmées / aberrantes)
    median_spread_bps: float   # écart effectif médian (aller-retour), bps
    mean_spread_bps: float
    median_half_spread_bps: float
    recommended_slippage_bps: float
    impact_buffer_bps: float

    def summary(self) -> str:
        return (
            f"{self.n_quotes} cotations retenues ({self.n_dropped} écartées) | "
            f"écart effectif médian={self.median_spread_bps:.2f} bps "
            f"(moyen={self.mean_spread_bps:.2f}) | demi-spread médian="
            f"{self.median_half_spread_bps:.2f} bps | slippage recommandé="
            f"{self.recommended_slippage_bps:.2f} bps"
        )


def summarize_quote_spreads(
    quotes: Mapping[str, tuple[float, float]],
    *,
    trim_bps: float = 30.0,
    impact_buffer_bps: float = 1.0,
) -> QuoteSpreadEstimate:
    """Agrège des cotations {ticker: (bid, ask)} en un coût calibré, robuste.

    Les cotations invalides ou dont l'écart dépasse ``trim_bps`` (probablement
    périmées hors séance / feed IEX) sont écartées avant l'agrégation en médiane.

    Args:
        quotes: mapping ticker -> (bid, ask).
        trim_bps: seuil d'écrêtage des écarts aberrants (bps).
        impact_buffer_bps: marge d'impact ajoutée au demi-spread médian.
    """
    spreads: list[float] = []
    dropped = 0
    for bid, ask in quotes.values():
        s = effective_spread_bps(bid, ask)
        if s is None or s > trim_bps:
            dropped += 1
            continue
        spreads.append(s)
    if not spreads:
        return QuoteSpreadEstimate(0, dropped, float("nan"), float("nan"),
                                   float("nan"), float("nan"), impact_buffer_bps)
    arr = np.array(spreads)
    median_bps = float(np.median(arr))
    half = median_bps / 2.0
    return QuoteSpreadEstimate(
        n_quotes=len(arr),
        n_dropped=dropped,
        median_spread_bps=median_bps,
        mean_spread_bps=float(np.mean(arr)),
        median_half_spread_bps=half,
        recommended_slippage_bps=half + impact_buffer_bps,
        impact_buffer_bps=impact_buffer_bps,
    )

# Constante de Corwin-Schultz : 3 - 2*sqrt(2).
_K = 3.0 - 2.0 * np.sqrt(2.0)


def corwin_schultz_spread(high: pd.Series, low: pd.Series) -> pd.Series:
    """Écart bid-ask **proportionnel** quotidien (fraction) par Corwin-Schultz.

    Args:
        high, low: séries des plus hauts/plus bas quotidiens (même index), prix >0.

    Returns:
        pd.Series de l'écart proportionnel estimé par jour (aligné sur l'index à
        partir du 2e jour). Les estimations négatives — bruit d'échantillon — sont
        ramenées à 0, conformément à l'usage standard de l'estimateur.
    """
    high = high.astype(float)
    low = low.astype(float)
    # (ln(H/L))^2 par jour.
    hl = np.log(high / low) ** 2

    # beta = (ln H/L)^2 du jour t-1 + du jour t (deux jours consécutifs).
    beta = hl.shift(1) + hl
    # gamma = (ln(max(H_t,H_{t-1}) / min(L_t,L_{t-1})))^2.
    h2 = np.maximum(high, high.shift(1))
    l2 = np.minimum(low, low.shift(1))
    gamma = np.log(h2 / l2) ** 2

    alpha = (np.sqrt(2.0 * beta) - np.sqrt(beta)) / _K - np.sqrt(gamma / _K)
    spread = 2.0 * (np.exp(alpha) - 1.0) / (1.0 + np.exp(alpha))
    # Écarts négatifs = bruit -> 0 ; garder l'index temporel.
    return spread.clip(lower=0.0)


@dataclass(frozen=True)
class SpreadEstimate:
    """Résumé de la calibration d'écart sur un univers."""

    n_tickers: int
    median_spread_bps: float          # écart effectif médian (aller-retour), bps
    mean_spread_bps: float
    median_half_spread_bps: float     # coût aller simple médian (spread/2), bps
    recommended_slippage_bps: float   # half-spread médian + tampon d'impact
    impact_buffer_bps: float

    def summary(self) -> str:
        return (
            f"{self.n_tickers} titres | écart effectif médian={self.median_spread_bps:.2f} bps "
            f"(moyen={self.mean_spread_bps:.2f}) | demi-spread médian="
            f"{self.median_half_spread_bps:.2f} bps | slippage recommandé="
            f"{self.recommended_slippage_bps:.2f} bps (tampon impact "
            f"{self.impact_buffer_bps:.2f})"
        )


def estimate_effective_spread_bps(
    ohlcv_by_ticker: dict[str, pd.DataFrame],
    *,
    min_days: int = 60,
    impact_buffer_bps: float = 1.0,
    high_col: str = "high",
    low_col: str = "low",
) -> SpreadEstimate:
    """Estime l'écart effectif de l'univers et un slippage aller simple recommandé.

    Args:
        ohlcv_by_ticker: {ticker: DataFrame OHLCV} (colonnes high/low réelles).
        min_days: nombre minimal de jours exploitables par ticker.
        impact_buffer_bps: marge d'impact de marché ajoutée au demi-spread (le
            demi-spread capte le franchissement du spread ; un ordre au marché sur
            un nom moins liquide subit un léger impact supplémentaire).

    Returns:
        SpreadEstimate agrégé sur les tickers (médiane robuste aux valeurs extrêmes).
    """
    per_ticker_bps: list[float] = []
    for df in ohlcv_by_ticker.values():
        if df is None or df.empty or high_col not in df or low_col not in df:
            continue
        spread = corwin_schultz_spread(df[high_col], df[low_col]).dropna()
        spread = spread[spread > 0]
        if len(spread) < min_days:
            continue
        per_ticker_bps.append(float(spread.mean()) * 1e4)

    if not per_ticker_bps:
        # Aucun ticker exploitable : renvoyer un estimate neutre marqué (0 titre).
        return SpreadEstimate(0, float("nan"), float("nan"), float("nan"),
                              float("nan"), impact_buffer_bps)

    arr = np.array(per_ticker_bps)
    median_bps = float(np.median(arr))
    mean_bps = float(np.mean(arr))
    half = median_bps / 2.0
    return SpreadEstimate(
        n_tickers=len(arr),
        median_spread_bps=median_bps,
        mean_spread_bps=mean_bps,
        median_half_spread_bps=half,
        recommended_slippage_bps=half + impact_buffer_bps,
        impact_buffer_bps=impact_buffer_bps,
    )

"""Facteurs value/quality à partir de fondamentaux **point-in-time** + prix.

Chaque facteur est un panel cross-sectionnel (dates × titres), aligné sur les
dates de prix, où la composante fondamentale est jointe **as-of** par date de
dépôt (aucun look-ahead ; cf. :mod:`financial_analyzer.data.fundamentals_pit_loader`).

Convention : score **élevé = position longue** (cohérent avec le long-haut /
short-bas du harness de validation).

- ``earnings_yield`` (E/P) = résultat net TTM / capitalisation — *value* (cher→bas).
- ``book_to_price`` (B/P) = capitaux propres / capitalisation — *value*.
- ``roe`` = résultat net TTM / capitaux propres — *quality*.
- ``gross_profitability`` (GP/A) = marge brute TTM / actifs — *quality* (Novy-Marx).

La capitalisation = prix × actions (moyenne diluée, as-of). Les ratios à
dénominateur ≤ 0 (capitaux propres négatifs, etc.) sont mis à ``NaN`` (non
interprétables cross-section).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from financial_analyzer.data.fundamentals_pit_loader import build_asof_panel

__all__ = ["FUNDAMENTAL_FACTORS", "compute_fundamental_factors"]

FUNDAMENTAL_FACTORS = ("earnings_yield", "book_to_price", "roe", "gross_profitability")


def _positive(panel: pd.DataFrame) -> pd.DataFrame:
    """Remplace les valeurs ≤ 0 par NaN (dénominateur non interprétable)."""
    return panel.where(panel > 0)


def compute_fundamental_factors(
    prices: pd.DataFrame, fundamentals_long: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    """Calcule les facteurs value/quality, alignés sur ``prices`` (dates × titres).

    Args:
        prices: panel de clôtures (dates × titres).
        fundamentals_long: sortie de ``FundamentalsPITLoader.load`` (avec ``ttm_*``).

    Returns:
        ``{nom_facteur: DataFrame (dates × titres)}``. Panels vides si aucun
        fondamental exploitable.
    """
    dates = pd.DatetimeIndex(prices.index)
    cols = prices.columns

    def panel(field: str) -> pd.DataFrame:
        return build_asof_panel(fundamentals_long, dates, field).reindex(
            index=dates, columns=cols
        )

    shares = panel("shares")
    ttm_ni = panel("ttm_net_income")
    equity = panel("equity")
    assets = panel("assets")
    ttm_gp = panel("ttm_gross_profit")

    market_cap = _positive(prices * shares)
    equity_pos = _positive(equity)
    assets_pos = _positive(assets)

    factors = {
        "earnings_yield": ttm_ni / market_cap,
        "book_to_price": equity_pos / market_cap,
        "roe": ttm_ni / equity_pos,
        "gross_profitability": ttm_gp / assets_pos,
    }
    return {k: v.replace([np.inf, -np.inf], np.nan) for k, v in factors.items()}

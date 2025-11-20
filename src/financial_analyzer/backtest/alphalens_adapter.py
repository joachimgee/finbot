from __future__ import annotations
from typing import Dict, List, Optional, Union
import pandas as pd
import numpy as np
from pathlib import Path


def build_alphalens_inputs(
    factor_series: pd.Series,
    prices: pd.DataFrame,
    periods: Union[int, List[int]] = 1,
) -> Dict[str, Union[pd.Series, pd.DataFrame, List[int]]]:
    """
    Prépare les inputs nécessaires à Alphalens: factor (MultiIndex date,asset), prices.

    Args:
        factor_series: Série multi-actifs avec MultiIndex (date, asset) ou simplement asset si constant
        prices: DataFrame des prix (dates x actifs)
        periods: horizon(s) de rendement futur (int ou liste)

    Returns:
        Dict avec 'factor', 'prices', 'periods'
    """
    # Normaliser periods en liste
    if isinstance(periods, int):
        periods = [periods]
    
    # Valider format factor_series (doit avoir MultiIndex ou être converti)
    if not isinstance(factor_series.index, pd.MultiIndex):
        raise ValueError("factor_series must have MultiIndex (date, asset)")
    
    return {"factor": factor_series, "prices": prices, "periods": periods}


def generate_alphalens_report(
    factor_series: pd.Series,
    prices: pd.DataFrame,
    periods: Union[int, List[int]] = 1,
    outdir: Optional[str] = None,
    quantiles: int = 5,
    long_short: bool = True,
) -> None:
    """
    Génère un rapport Alphalens complet (IC, quantile analysis, turnover).

    Args:
        factor_series: Série avec MultiIndex (date, asset) des valeurs de facteur
        prices: DataFrame des prix (dates x actifs)
        periods: horizon(s) forward returns (ex: [1, 5, 10])
        outdir: Dossier de sortie pour le rapport HTML/PNG (optionnel)
        quantiles: Nombre de quantiles pour l'analyse (défaut 5)
        long_short: Inclure analyse long-short (défaut True)

    Raises:
        ImportError si alphalens n'est pas installé
    """
    try:
        import alphalens as al
    except Exception as e:
        raise ImportError(
            "alphalens n'est pas installé. Essayez: pip install alphalens-reloaded"
        ) from e

    # Préparer inputs
    data = build_alphalens_inputs(factor_series, prices, periods)
    
    # Nettoyer et calculer forward returns
    factor_data = al.utils.get_clean_factor_and_forward_returns(
        factor=data["factor"],
        prices=data["prices"],
        periods=data["periods"],
        quantiles=quantiles,
        bins=None,
        filter_zscore=20,  # Outlier filtering
    )
    
    # Générer tear sheet complet
    if outdir:
        outpath = Path(outdir)
        outpath.mkdir(parents=True, exist_ok=True)
        al.tears.create_full_tear_sheet(
            factor_data,
            long_short=long_short,
            group_neutral=False,
            by_group=False,
        )
    else:
        al.tears.create_full_tear_sheet(
            factor_data,
            long_short=long_short,
            group_neutral=False,
            by_group=False,
        )

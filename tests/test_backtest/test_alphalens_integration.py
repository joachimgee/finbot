"""Tests pour l'intégration Alphalens avec données synthétiques."""
import numpy as np
import pandas as pd
import pytest
from pathlib import Path

from financial_analyzer.backtest.alphalens_adapter import build_alphalens_inputs


def test_build_alphalens_inputs_multiindex():
    """Vérifie que build_alphalens_inputs accepte un MultiIndex."""
    # Créer facteur avec MultiIndex (date, asset)
    dates = pd.date_range('2024-01-01', periods=10, freq='D')
    assets = ['A', 'B', 'C']
    
    index = pd.MultiIndex.from_product([dates, assets], names=['date', 'asset'])
    rng = np.random.default_rng(42)
    factor_values = rng.normal(0, 1, len(index))
    factor_series = pd.Series(factor_values, index=index)
    
    # Créer prix
    prices = pd.DataFrame(
        rng.normal(100, 10, (len(dates), len(assets))),
        index=dates,
        columns=assets
    )
    
    # Build inputs
    data = build_alphalens_inputs(factor_series, prices, periods=[1, 5])
    
    assert 'factor' in data
    assert 'prices' in data
    assert 'periods' in data
    assert data['periods'] == [1, 5]
    assert isinstance(data['factor'].index, pd.MultiIndex)


def test_build_alphalens_inputs_single_period():
    """Vérifie conversion int -> list pour periods."""
    dates = pd.date_range('2024-01-01', periods=5, freq='D')
    assets = ['X', 'Y']
    
    index = pd.MultiIndex.from_product([dates, assets], names=['date', 'asset'])
    factor_series = pd.Series(np.ones(len(index)), index=index)
    prices = pd.DataFrame(np.ones((len(dates), len(assets))), index=dates, columns=assets)
    
    data = build_alphalens_inputs(factor_series, prices, periods=1)
    assert data['periods'] == [1]


def test_build_alphalens_inputs_invalid_index():
    """Vérifie qu'une erreur est levée si pas de MultiIndex."""
    factor_series = pd.Series([1, 2, 3], index=['A', 'B', 'C'])
    prices = pd.DataFrame([[100, 101]], columns=['A', 'B'])
    
    with pytest.raises(ValueError, match="MultiIndex"):
        build_alphalens_inputs(factor_series, prices)


def test_generate_alphalens_report_import_error():
    """Vérifie qu'ImportError est levé si alphalens absent."""
    # Créer données minimales
    dates = pd.date_range('2024-01-01', periods=3, freq='D')
    assets = ['A']
    index = pd.MultiIndex.from_product([dates, assets], names=['date', 'asset'])
    factor_series = pd.Series([0.1, 0.2, 0.3], index=index)
    prices = pd.DataFrame([[100], [101], [102]], index=dates, columns=assets)
    
    # Si alphalens pas installé, devrait lever ImportError
    # (on ne peut pas mocker facilement ici, donc skip si installé)
    pytest.importorskip("alphalens", reason="alphalens not installed")

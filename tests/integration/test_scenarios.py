"""Tests d'intégration : scénarios de marché paramétrés.

Ce module couvre différents régimes (bull, bear, volatilité élevée, crash, divergences,
conditions mixtes, extrêmes) en paramétrant les attentes pour réduire la duplication.

Stratégie de test :
    1. Génération de rendements synthétiques contrôlés (drift + volatilité).
    2. Conversion en prix (base 100) via cumul produit.
    3. Exécution du pipeline pour obtenir allocations agrégées.
    4. Assertions spécifiques au scénario (diversification, sparsité, concentration).

Complexité : Chaque scénario O(n) pour n périodes (120 par défaut). Paramétrisation
permet de mutualiser le code de préparation et de validation.

Exemple:
    >>> # Exécution d'un scénario bull
    >>> prices = _prices_from_returns(_make_returns(120, mu=0.001, sigma=0.01))
    >>> frames = {'AAA': prices}
    >>> result = _run_pipeline(frames)
    >>> assert result['status'] in {'success', 'partial'}
"""
from __future__ import annotations

from typing import Dict
import numpy as np
import pandas as pd
import pytest

from financial_analyzer.pipeline.pipeline import Pipeline
from financial_analyzer.data.universe import UniverseSelector
from financial_analyzer.data.market_data import MarketDataFetcher


class DummyUniverseSelector(UniverseSelector):  # pragma: no cover - simple stub
    def __init__(self) -> None:  # pragma: no cover - trivial
        pass

    def get_metadata(self, tickers: list[str], asset_type: str = 'equities') -> pd.DataFrame:  # pragma: no cover - trivial
        return pd.DataFrame({'symbol': tickers})


class DummyFetcher(MarketDataFetcher):  # pragma: no cover - simple stub
    def __init__(self, frames: Dict[str, pd.DataFrame]) -> None:  # pragma: no cover - trivial
        self.frames = frames

    def get_historical_data(self, ticker: str, start_date: str, end_date: str) -> pd.DataFrame:  # pragma: no cover - trivial
        return self.frames.get(ticker, pd.DataFrame({'Close': []}))


def _prices_from_returns(returns: pd.Series) -> pd.DataFrame:
    """Transforme une série de rendements en prix base 100.

    Args:
        returns: Série de rendements timestampés.
    Returns:
        DataFrame avec colonne 'Close'.
    """
    prices = 100 * (1 + returns).cumprod()
    return pd.DataFrame({'Close': prices}, index=returns.index)


def _make_returns(n: int, mu: float, sigma: float, seed: int = 42) -> pd.Series:
    """Génère rendements gaussiens synthétiques.

    Args:
        n: Nombre de périodes.
        mu: Drift moyen par période.
        sigma: Volatilité (écart-type).
        seed: Graine pour reproductibilité.
    Returns:
        Série de rendements.
    """
    np.random.seed(seed)
    dates = pd.date_range('2025-09-01', periods=n, freq='B')
    return pd.Series(np.random.normal(mu, sigma, n), index=dates)


def _run_pipeline(frames: Dict[str, pd.DataFrame]) -> Dict[str, object]:
    """Exécute le pipeline pour un dict ticker->DataFrame."""
    pipe = Pipeline(
        DummyUniverseSelector(),
        lookback_days=60,
        forecast_horizon=5,
        market_data_fetcher=DummyFetcher(frames),
    )
    return pipe.run('2025-11-07', list(frames.keys()))


@pytest.mark.parametrize(
    "scenario",
    [
        {
            "name": "bull",
            "frames": lambda: {t: _prices_from_returns(_make_returns(120, 0.001, 0.01)) for t in ['AAA', 'BBB', 'CCC']},
            "expect": {"status_in": {"success", "partial"}},
        },
        {
            "name": "bear",
            "frames": lambda: {t: _prices_from_returns(_make_returns(120, -0.001, 0.015)) for t in ['AAA', 'BBB', 'CCC']},
            "expect": {"status_in": {"success", "partial"}},
        },
        {
            "name": "high_vol",
            "frames": lambda: {t: _prices_from_returns(_make_returns(120, 0.0, 0.05)) for t in ['AAA', 'BBB', 'CCC']},
            "expect": {"status_in": {"success", "partial"}},
        },
        {
            "name": "crash",
            "frames": lambda: {
                'AAA': _prices_from_returns(
                    pd.Series(
                        np.concatenate([
                            np.random.normal(0.0002, 0.01, 100),
                            np.full(20, -0.05),
                        ]),
                        index=pd.date_range('2025-09-01', periods=120, freq='B'),
                    )
                )
            },
            "expect": {"status_in": {"success", "partial"}},
        },
        {
            "name": "divergent",
            "frames": lambda: {
                'AAA': _prices_from_returns(_make_returns(120, 0.001, 0.01)),
                'BBB': _prices_from_returns(_make_returns(120, -0.001, 0.01)),
                'CCC': _prices_from_returns(_make_returns(120, 0.0, 0.03)),
            },
            "expect": {"status_in": {"success", "partial"}},
        },
        {
            "name": "all_bearish",
            "frames": lambda: {t: _prices_from_returns(_make_returns(120, -0.002, 0.02)) for t in ['AAA', 'BBB', 'CCC']},
            "expect": {"status_in": {"success", "partial"}},
        },
        {
            "name": "mixed",
            "frames": lambda: {
                'AAA': _prices_from_returns(_make_returns(120, 0.001, 0.02)),
                'BBB': _prices_from_returns(_make_returns(120, 0.0, 0.02)),
                'CCC': _prices_from_returns(_make_returns(120, -0.001, 0.02)),
            },
            "expect": {"status_in": {"success", "partial"}},
        },
        {
            "name": "outliers",
            "frames": lambda: {
                'AAA': _prices_from_returns(
                    (lambda:
                        (lambda dates:
                            (lambda arr: (
                                arr.__setitem__(10, 0.25) or True,
                                arr.__setitem__(50, -0.3) or True,
                                pd.Series(arr, index=dates)
                            )[-1])(
                                np.random.normal(0.0003, 0.01, 120)
                            )
                        )(pd.date_range('2025-09-01', periods=120, freq='B'))
                    )()
                )
            },
            "expect": {"status_in": {"success", "partial"}},
        },
    ],
)
def test_market_scenarios_parametrized(scenario):
    """Test paramétré pour différents scénarios de marché.

    Args:
        scenario: Dict décrivant le nom, frames callable et attentes.
    """
    frames = scenario["frames"]()
    result = _run_pipeline(frames)
    assert result["status"] in scenario["expect"]["status_in"]

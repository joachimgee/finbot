"""Point-In-Time (PIT) Data Loader.

Charge des prix historiques **ajustés** (splits + dividendes) sans biais de
look-ahead. Deux sources :

- ``source="alpaca"`` — vraies barres OHLCV via l'API market-data Alpaca
  (``adjustment="all"``), point-in-time correct.
- ``source="synthetic"`` — random-walk déterministe, réservé aux tests et au
  développement hors-ligne.

Sûreté (dans l'esprit du garde-fou de mode) : le synthétique ne doit jamais
être pris pour du réel. Quand la source réelle est demandée mais échoue, le
repli synthétique est **bruyamment** journalisé ; et il peut être interdit
(``allow_synthetic_fallback=False``) pour qu'un chemin de production échoue
plutôt que de décider sur des données factices.

Example:
    >>> loader = PITDataLoader(source="alpaca")
    >>> data = loader.load_prices(['AAPL', 'MSFT'], '2020-01-01', '2020-06-30')
    >>> data['AAPL'].columns.tolist()
    ['open', 'high', 'low', 'close', 'volume']
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class RealDataUnavailableError(RuntimeError):
    """Levée quand des données réelles sont exigées mais indisponibles."""


@dataclass
class PITDataLoader:
    """Chargeur de prix point-in-time.

    Args:
        source: ``"alpaca"`` (vraies données ajustées) ou ``"synthetic"``
            (random-walk déterministe, tests/hors-ligne). Défaut ``"synthetic"``
            pour préserver le comportement déterministe des tests existants.
        allow_synthetic_fallback: si vrai (défaut), un échec de la source réelle
            retombe sur le synthétique avec un avertissement ; si faux, il lève
            :class:`RealDataUnavailableError` (à utiliser en production).
        feed: feed Alpaca pour la source réelle (``"iex"`` inclus au plan gratuit).
    """

    source: str = "synthetic"
    allow_synthetic_fallback: bool = True
    feed: str = "iex"

    def load_prices(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> dict[str, pd.DataFrame]:
        """Charge les prix ajustés par symbole : ``{symbole: DataFrame OHLCV}``."""
        if self.source == "alpaca":
            try:
                data = self._load_alpaca(symbols, start_date, end_date)
                if not data:
                    raise RealDataUnavailableError(
                        "Alpaca n'a renvoyé aucune barre pour les symboles/plage demandés"
                    )
                logger.info(
                    "PIT load prices: %d/%d symboles depuis Alpaca (ajusté) %s→%s",
                    len(data),
                    len(symbols),
                    start_date,
                    end_date,
                )
                return data
            except Exception as e:
                if not self.allow_synthetic_fallback:
                    raise RealDataUnavailableError(
                        f"Données réelles indisponibles et repli synthétique interdit : {e}"
                    ) from e
                logger.warning(
                    "PIT: échec de la récupération des données réelles (%s). "
                    "REPLI SUR DES DONNÉES SYNTHÉTIQUES — ne pas utiliser pour de "
                    "vraies décisions.",
                    e,
                )
        elif self.source != "synthetic":
            raise ValueError(
                f"source PIT inconnue : {self.source!r} (attendu 'alpaca' ou 'synthetic')"
            )

        return self._load_synthetic(symbols, start_date, end_date)

    def _load_alpaca(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> dict[str, pd.DataFrame]:
        from financial_analyzer.data.alpaca_history import fetch_daily_ohlcv

        return fetch_daily_ohlcv(
            list(symbols), start_date, end_date, feed=self.feed, progress=False
        )

    def _load_synthetic(
        self, symbols: list[str], start_date: str, end_date: str
    ) -> dict[str, pd.DataFrame]:
        logger.info(
            "PIT load prices (SYNTHETIC): %d symboles %s→%s",
            len(symbols),
            start_date,
            end_date,
        )
        dates = pd.date_range(start=start_date, end=end_date, freq="B")
        data: dict[str, pd.DataFrame] = {}
        for sym in symbols:
            seed = (hash(sym) + hash(start_date)) % (2**32)
            rng = np.random.default_rng(seed)
            returns = rng.normal(0.0005, 0.02, len(dates))
            prices = 100 * np.exp(np.cumsum(returns))
            df = pd.DataFrame(
                {
                    "open": prices * (1 + rng.normal(0, 0.005, len(dates))),
                    "high": prices * (1 + np.abs(rng.normal(0, 0.01, len(dates)))),
                    "low": prices * (1 - np.abs(rng.normal(0, 0.01, len(dates)))),
                    "close": prices,
                    "volume": rng.integers(1_000_000, 5_000_000, len(dates)),
                },
                index=dates,
            )
            data[sym] = df
        return data

    def load_metadata(self, symbols: list[str]) -> pd.DataFrame:
        """Charge les métadonnées statiques (secteur, devise, etc.)."""
        rows = [{"symbol": s, "sector": "TECH", "currency": "USD"} for s in symbols]
        return pd.DataFrame(rows)


__all__ = ["PITDataLoader", "RealDataUnavailableError"]

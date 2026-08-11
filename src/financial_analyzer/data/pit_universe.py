"""Appartenance **point-in-time** à l'univers (anti biais de survie).

Un titre ne doit entrer dans une évaluation qu'aux dates où il était *réellement
coté et investissable* — ni avant son introduction, ni après sa radiation. Ce
module construit ce **masque d'appartenance** (date × titre) à partir des durées
de vie cotées (``list_date`` / ``delisted_utc``) et l'applique aux panels de
facteurs/rendements.

Corrige deux fuites :

- **Pré-cotation** : un titre introduit en cours de période (ex. une IPO 2021) ne
  doit pas figurer dans la cross-section d'avant son ``list_date``.
- **Post-radiation** : un titre delisté ne doit plus figurer après son
  ``delisted_utc`` (et, avec les prix du titre delisté, sa dernière période doit
  être prise en compte — sinon on ne « voit » que les survivants).

Contrat fail-safe, comme les autres loaders : source réelle (Polygon) ou
synthétique déterministe ; l'absence de source réelle peut être interdite.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

from financial_analyzer.data.pit_loader import RealDataUnavailableError
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

__all__ = ["PITUniverseLoader", "apply_membership", "build_membership_mask"]


def build_membership_mask(
    dates: pd.DatetimeIndex, lifespans: pd.DataFrame
) -> pd.DataFrame:
    """Masque booléen (date × titre) : ``True`` là où le titre est coté et vivant.

    Args:
        dates: index des dates d'évaluation (peut être timezone-aware).
        lifespans: DataFrame ``[ticker, list_date, delisted_utc]`` (dates naïves ;
            ``NaT`` = pas de borne de ce côté).

    Returns:
        DataFrame booléen indexé par ``dates``, colonnes = tickers.
    """
    idx = pd.DatetimeIndex(dates)
    naive = (idx.tz_localize(None) if idx.tz is not None else idx).to_numpy()
    cols: dict[str, np.ndarray] = {}
    for _, row in lifespans.iterrows():
        tk = row["ticker"]
        listed = row.get("list_date")
        delist = row.get("delisted_utc")
        alive = np.ones(len(naive), dtype=bool)
        if pd.notna(listed):
            alive &= naive >= np.datetime64(pd.Timestamp(listed).tz_localize(None))
        if pd.notna(delist):
            alive &= naive < np.datetime64(pd.Timestamp(delist).tz_localize(None))
        cols[tk] = alive
    return pd.DataFrame(cols, index=idx)


def apply_membership(panel: pd.DataFrame, mask: pd.DataFrame) -> pd.DataFrame:
    """Met à ``NaN`` les cases du panel où le titre n'appartient pas à l'univers."""
    m = mask.reindex(index=panel.index, columns=panel.columns).fillna(False)
    return panel.where(m)


@dataclass
class PITUniverseLoader:
    """Charge les durées de vie cotées (point-in-time), contrat fail-safe.

    Args:
        source: ``"polygon"`` (réel) ou ``"synthetic"`` (déterministe, tests).
        allow_synthetic_fallback: si faux, un échec du réel lève
            ``RealDataUnavailableError`` au lieu de retomber sur le synthétique.
    """

    source: str = "polygon"
    allow_synthetic_fallback: bool = True

    def lifespans(self, tickers: list[str], **kwargs) -> pd.DataFrame:
        """DataFrame ``[ticker, list_date, delisted_utc, active]`` pour l'univers."""
        if self.source == "polygon":
            try:
                from financial_analyzer.data.polygon_universe import ticker_lifespans

                df = ticker_lifespans(list(tickers), **kwargs)
                if df.empty or df["list_date"].isna().all():
                    raise RealDataUnavailableError("Polygon n'a renvoyé aucune durée de vie.")
                return df
            except RealDataUnavailableError:
                if not self.allow_synthetic_fallback:
                    raise
                logger.warning("PIT universe: aucun réel — REPLI SYNTHÉTIQUE.")
            except Exception as e:
                if not self.allow_synthetic_fallback:
                    raise RealDataUnavailableError(
                        f"Durées de vie réelles indisponibles, repli interdit : {e}"
                    ) from e
                logger.warning("PIT universe: échec réel (%s) — REPLI SYNTHÉTIQUE.", e)
        elif self.source != "synthetic":
            raise ValueError(f"source inconnue : {self.source!r} (attendu 'polygon' ou 'synthetic').")

        return self._synthetic(list(tickers))

    @staticmethod
    def _synthetic(tickers: list[str]) -> pd.DataFrame:
        """Durées de vie déterministes : la plupart cotées, quelques-unes delistées."""
        recs = []
        for tk in tickers:
            seed = int(hashlib.sha256(tk.encode()).hexdigest()[:8], 16)
            rng = np.random.default_rng(seed)
            list_year = int(rng.integers(2005, 2021))
            delisted = rng.random() < 0.15  # ~15 % de radiations
            recs.append({
                "ticker": tk,
                "list_date": pd.Timestamp(f"{list_year}-01-15"),
                "delisted_utc": pd.Timestamp(f"{int(rng.integers(2022, 2026))}-06-30") if delisted else pd.NaT,
                "active": not delisted,
            })
        return pd.DataFrame(recs)

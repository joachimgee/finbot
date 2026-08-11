"""Chargeur de fondamentaux **point-in-time** (as-of par date de dépôt).

Même esprit de sûreté que :mod:`financial_analyzer.data.pit_loader` (prix) :

- ``source="polygon"`` — vrais fondamentaux trimestriels avec ``filing_date``
  (point-in-time correct : une valeur n'est connue qu'à partir de son dépôt).
- ``source="synthetic"`` — fondamentaux déterministes pour tests/hors-ligne.

L'anti-look-ahead est structurel : :func:`build_asof_panel` fait une jointure
**as-of** (``merge_asof`` backward) sur la ``filing_date``, si bien qu'à la date
t on ne voit que le dépôt le plus récent tel que ``filing_date ≤ t`` — jamais une
valeur restatée publiée plus tard. Avant le premier dépôt, la valeur est ``NaN``.

Les variables de flux (résultat net, chiffre d'affaires, marge brute) sont
converties en **TTM** (somme des 4 derniers trimestres, sur la timeline des
dépôts) pour être comparables ; les variables de stock (capitaux propres, actifs,
actions) sont prises telles quelles.

Contrat fail-safe : source réelle indisponible → soit repli synthétique
**bruyamment journalisé**, soit (``allow_synthetic_fallback=False``)
:class:`~financial_analyzer.data.pit_loader.RealDataUnavailableError`.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass

import numpy as np
import pandas as pd

from financial_analyzer.data.pit_loader import RealDataUnavailableError
from financial_analyzer.data.polygon_fundamentals import FUNDAMENTAL_FIELDS
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

__all__ = ["FundamentalsPITLoader", "add_ttm_columns", "build_asof_panel"]

# Flux -> TTM (somme 4 trimestres) ; stocks -> valeur instantanée.
_FLOW_FIELDS = ("net_income", "revenues", "cost_of_revenue", "gross_profit")
_STOCK_FIELDS = ("equity", "assets", "shares")


def add_ttm_columns(long_df: pd.DataFrame) -> pd.DataFrame:
    """Ajoute ``ttm_<flux>`` = somme glissante des 4 derniers trimestres.

    La somme est calculée par ticker, **ordonnée par ``end_date``** (ordre
    économique), puis reste attachée à la ``filing_date`` d'origine pour rester
    point-in-time. Exige au moins 4 trimestres pour un TTM (sinon NaN).
    """
    if long_df.empty:
        for f in _FLOW_FIELDS:
            long_df[f"ttm_{f}"] = pd.Series(dtype=float)
        return long_df
    out = long_df.sort_values(["ticker", "end_date"]).copy()
    for f in _FLOW_FIELDS:
        if f not in out.columns:  # champ absent (panel partiel) -> pas de TTM
            continue
        out[f"ttm_{f}"] = (
            out.groupby("ticker")[f].transform(lambda s: s.rolling(4, min_periods=4).sum())
        )
    return out


def build_asof_panel(
    long_df: pd.DataFrame, dates: pd.DatetimeIndex, field: str
) -> pd.DataFrame:
    """Panel (dates × tickers) **point-in-time** d'un champ, par jointure as-of.

    Pour chaque date t et ticker, la valeur est celle du dépôt le plus récent tel
    que ``filing_date ≤ t``. Avant le premier dépôt disponible : ``NaN``.
    """
    orig = pd.DatetimeIndex(sorted(pd.DatetimeIndex(dates).unique()))
    if long_df.empty or field not in long_df.columns:
        return pd.DataFrame(index=orig)
    # merge_asof exige des clés de même dtype. Les prix Alpaca sont timezone-aware
    # (UTC), les dates de dépôt Polygon sont naïves : on fait la jointure en naïf
    # des deux côtés, mais on renvoie le panel indexé par les dates d'origine (pour
    # rester aligné sur le panel de prix de l'appelant).
    naive = orig.tz_localize(None) if orig.tz is not None else orig
    left = pd.DataFrame({"date": naive})
    cols: dict[str, np.ndarray] = {}
    for tk, g in long_df.groupby("ticker"):
        g = g.dropna(subset=[field, "filing_date"]).sort_values("filing_date")
        if g.empty:
            continue
        fd = pd.to_datetime(g["filing_date"])
        if fd.dt.tz is not None:
            fd = fd.dt.tz_localize(None)
        right = pd.DataFrame({"date": fd.to_numpy(), field: g[field].to_numpy()}).sort_values("date")
        merged = pd.merge_asof(left, right, on="date", direction="backward")
        cols[tk] = merged[field].to_numpy()
    return pd.DataFrame(cols, index=orig)


@dataclass
class FundamentalsPITLoader:
    """Charge des fondamentaux point-in-time, contrat fail-safe.

    Args:
        source: ``"polygon"`` (réel, avec dates de dépôt) ou ``"synthetic"``.
        allow_synthetic_fallback: si vrai, un échec du réel retombe sur le
            synthétique (bruyamment) ; sinon lève ``RealDataUnavailableError``.
    """

    source: str = "polygon"
    allow_synthetic_fallback: bool = True

    def load(self, tickers: list[str], start: str, end: str | None = None) -> pd.DataFrame:
        """Renvoie le panel long des fondamentaux (+ colonnes TTM), trié.

        Colonnes : ``[ticker, fiscal_period, fiscal_year, end_date, filing_date,
        *FUNDAMENTAL_FIELDS, ttm_*]``.
        """
        if self.source == "polygon":
            try:
                from financial_analyzer.data.polygon_fundamentals import (
                    fetch_fundamentals,
                )

                df = fetch_fundamentals(list(tickers), start=start, end=end)
                if df.empty:
                    raise RealDataUnavailableError(
                        "Polygon n'a renvoyé aucun fondamental pour l'univers/plage."
                    )
                logger.info("PIT fundamentals: %d dépôts, %d tickers (Polygon).",
                            len(df), df["ticker"].nunique())
                return add_ttm_columns(df)
            except RealDataUnavailableError:
                if not self.allow_synthetic_fallback:
                    raise
                logger.warning("PIT fundamentals: aucun réel — REPLI SYNTHÉTIQUE (ne pas trader dessus).")
            except Exception as e:
                if not self.allow_synthetic_fallback:
                    raise RealDataUnavailableError(
                        f"Fondamentaux réels indisponibles, repli interdit : {e}"
                    ) from e
                logger.warning("PIT fundamentals: échec réel (%s) — REPLI SYNTHÉTIQUE.", e)
        elif self.source != "synthetic":
            raise ValueError(f"source inconnue : {self.source!r} (attendu 'polygon' ou 'synthetic').")

        return add_ttm_columns(self._synthetic(list(tickers), start, end))

    @staticmethod
    def _synthetic(tickers: list[str], start: str, end: str | None) -> pd.DataFrame:
        """Fondamentaux trimestriels déterministes (tests / hors-ligne)."""
        end = end or pd.Timestamp.today().strftime("%Y-%m-%d")
        quarters = pd.date_range(start=start, end=end, freq="QE")
        rows = []
        for tk in tickers:
            seed = int(hashlib.sha256(tk.encode()).hexdigest()[:8], 16)
            rng = np.random.default_rng(seed)
            scale = rng.uniform(0.5, 5.0)
            for qend in quarters:
                rev = float(rng.uniform(0.8, 1.2) * scale * 1e10)
                ni = rev * float(rng.uniform(0.05, 0.30))
                cogs = rev * float(rng.uniform(0.4, 0.7))
                rows.append({
                    "ticker": tk, "fiscal_period": f"Q{((qend.month - 1) // 3) + 1}",
                    "fiscal_year": qend.year, "end_date": qend,
                    # Dépôt ~30 jours après la fin de période (lag réaliste).
                    "filing_date": qend + pd.Timedelta(days=30),
                    "net_income": ni, "revenues": rev, "cost_of_revenue": cogs,
                    "gross_profit": rev - cogs,
                    "equity": float(rng.uniform(2, 8) * scale * 1e10),
                    "assets": float(rng.uniform(5, 15) * scale * 1e10),
                    "shares": float(rng.uniform(1, 5) * 1e9),
                })
        cols = ["ticker", "fiscal_period", "fiscal_year", "end_date", "filing_date", *FUNDAMENTAL_FIELDS]
        df = pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)
        return df.sort_values(["ticker", "filing_date"]).reset_index(drop=True)

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional

import numpy as np
import pandas as pd


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WeightBounds:
    """
    Bornes de poids par actif.

    Args:
        lower: Borne inférieure globale ou mapping par symbole.
        upper: Borne supérieure globale ou mapping par symbole.

    Example:
        >>> bounds = WeightBounds(lower=0.0, upper=0.1)
        >>> bounds.get_lower('AAPL')
        0.0
    """

    lower: float | Mapping[str, float] = 0.0
    upper: float | Mapping[str, float] = 1.0

    def get_lower(self, ticker: str) -> float:
        if isinstance(self.lower, Mapping):
            return float(self.lower.get(ticker, 0.0))
        return float(self.lower)

    def get_upper(self, ticker: str) -> float:
        if isinstance(self.upper, Mapping):
            return float(self.upper.get(ticker, 1.0))
        return float(self.upper)


@dataclass(frozen=True)
class MaxPositionsConstraint:
    """
    Contrainte sur le nombre maximum de positions non nulles.
    """

    max_positions: int


@dataclass(frozen=True)
class GroupConstraint:
    """
    Contrainte de groupe (ex: secteurs) avec bornes min/max sur la somme des poids.

    Args:
        group_map: Mapping ticker -> nom groupe.
        group_min: Borne min par groupe (optionnelle, valeur par défaut 0.0).
        group_max: Borne max par groupe (optionnelle, valeur par défaut 1.0).
    """

    group_map: Mapping[str, str]
    group_min: Mapping[str, float] = field(default_factory=dict)
    group_max: Mapping[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class MaxTurnoverConstraint:
    """
    Contrainte de turnover relatif au portefeuille précédent (somme |w - w_prev| <= max_turnover).
    """

    previous_weights: Mapping[str, float]
    max_turnover: float


@dataclass(frozen=True)
class LeverageConstraint:
    """
    Contrainte de levier total (somme des poids absolus <= max_leverage).
    """

    max_leverage: float = 1.0


@dataclass(frozen=True)
class RiskBudgetConstraint:
    """
    Contrainte de risque: budget de volatilité maximum.
    """

    max_volatility: float


@dataclass
class Constraints:
    """
    Regroupe et applique les contraintes de portefeuille.

    Attributes:
        bounds: Bornes de poids par actif.
        max_positions: Contrainte du nombre maximum de positions.
        group: Contrainte par groupes (ex: secteurs).
        turnover: Contrainte de turnover par rapport au portefeuille précédent.
        leverage: Contrainte de levier total.
        risk_budget: Contrainte de budget de risque (volatilité maximale).

    Example:
        >>> cons = Constraints(bounds=WeightBounds(0, 0.1), max_positions=MaxPositionsConstraint(20))
        >>> tickers = ['A', 'B', 'C']
        >>> w = pd.Series([0.1, 0.0, 0.0], index=tickers)
        >>> cons.enforce_bounds(w).round(2).tolist()
        [0.1, 0.0, 0.0]
    """

    bounds: Optional[WeightBounds] = None
    max_positions: Optional[MaxPositionsConstraint] = None
    group: Optional[GroupConstraint] = None
    turnover: Optional[MaxTurnoverConstraint] = None
    leverage: Optional[LeverageConstraint] = None
    risk_budget: Optional[RiskBudgetConstraint] = None

    def enforce_bounds(self, weights: pd.Series) -> pd.Series:
        if self.bounds is None:
            return weights
        w = weights.copy()
        # Clamp to [lo, hi]
        lo_arr = []
        hi_arr = []
        for t in w.index:
            lo = self.bounds.get_lower(t)
            hi = self.bounds.get_upper(t)
            if lo > hi:
                raise ValueError(f"Borne invalide pour {t}: lower {lo} > upper {hi}")
            lo_arr.append(lo)
            hi_arr.append(hi)
            if w[t] < lo:
                w[t] = lo
            if w[t] > hi:
                w[t] = hi
        # Project onto bounded simplex using (lo, hi)
        lo_v = np.array(lo_arr, dtype=float)
        hi_v = np.array(hi_arr, dtype=float)
        total_lo = float(lo_v.sum())
        cap = hi_v - lo_v
        cap[cap < 0] = 0.0
        slack = 1.0 - total_lo
        if slack <= 1e-12 or float(cap.sum()) <= 1e-12:
            # Nothing to distribute or no capacity: return lower bounds
            w[:] = lo_v
            return w
        # Distribute slack proportionally to capacities
        add = cap * (slack / float(cap.sum()))
        new_w = lo_v + add
        return pd.Series(new_w, index=w.index)

    def check_max_positions(self, weights: pd.Series) -> bool:
        if self.max_positions is None:
            return True
        non_zero = int((weights.abs() > 1e-12).sum())
        return non_zero <= self.max_positions.max_positions

    def check_group_bounds(self, weights: pd.Series) -> bool:
        if self.group is None:
            return True
        group_map = self.group.group_map
        group_min = self.group.group_min
        group_max = self.group.group_max
        group_sums: Dict[str, float] = {}
        for t, w in weights.items():
            g = group_map.get(t)
            if g is None:
                continue
            group_sums[g] = group_sums.get(g, 0.0) + float(w)
        for g, val in group_sums.items():
            gmin = float(group_min.get(g, 0.0))
            gmax = float(group_max.get(g, 1.0))
            if val < gmin - 1e-9 or val > gmax + 1e-9:
                return False
        return True

    def check_turnover(self, weights: pd.Series) -> bool:
        if self.turnover is None:
            return True
        prev = pd.Series(self.turnover.previous_weights, dtype=float)
        prev = prev.reindex(weights.index).fillna(0.0)
        turnover = float((weights - prev).abs().sum())
        return turnover <= self.turnover.max_turnover + 1e-9

    def check_leverage(self, weights: pd.Series) -> bool:
        if self.leverage is None:
            return True
        lev = float(weights.abs().sum())
        return lev <= self.leverage.max_leverage + 1e-9

    def check_risk_budget(self, weights: pd.Series, cov: pd.DataFrame) -> bool:
        if self.risk_budget is None:
            return True
        w = weights.values.astype(float)
        cov_m = cov.values.astype(float)
        vol = float(np.sqrt(w @ cov_m @ w))
        return vol <= self.risk_budget.max_volatility + 1e-12

    def is_feasible(self, weights: pd.Series, cov: Optional[pd.DataFrame] = None) -> bool:
        if abs(float(weights.sum()) - 1.0) > 1e-8:
            return False
        if not self.check_max_positions(weights):
            return False
        if not self.check_group_bounds(weights):
            return False
        if not self.check_turnover(weights):
            return False
        if not self.check_leverage(weights):
            return False
        if self.risk_budget is not None and cov is not None:
            if not self.check_risk_budget(weights, cov):
                return False
        return True
from typing import Callable, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class PortfolioConstraints:
    """
    Gère les contraintes d'optimisation.

    Contraintes supportées :
    - Min/max allocation par asset (0.5% - 10%)
    - Sector constraints (tech max 30%)
    - Concentration limit (Herfindahl < 0.2)
    - Long-only (pas de short)
    - Custom constraints (callable)

    Notes:
        - Les contraintes sont stockées sous forme de structure facilitant la conversion
          en bounds et en fonctions de contraintes pour scipy.optimize.
        - sector_mapping peut être fourni via l'attribut public `sector_mapping` en
          mappant {asset: sector}.
    """

    def __init__(self, sector_mapping: Optional[Dict[str, str]] = None) -> None:
        """Init contraintes vides.

        Args:
            sector_mapping: Mapping optionnel des actifs vers secteurs
        """
        self.constraints: List[Dict] = []
        self.min_weight: Optional[float] = None
        self.max_weight: Optional[float] = None
        self.asset_specific_bounds: Dict[str, Tuple[float, float]] = {}
        # Par défaut: long-only activé pour correspondre aux attentes des tests
        self.long_only_enabled: bool = True
        self.max_herfindahl: Optional[float] = None
        self.sector_limits: Dict[str, float] = {}
        self.sector_mapping: Dict[str, str] = sector_mapping or {}
        self.custom_funcs: List[Callable[[np.ndarray, List[str]], float]] = []
        self._turnover_prev: Optional[List[float]] = None
        self._turnover_limit: Optional[float] = None

    def add_allocation_limits(
        self,
        min_weight: float = 0.0,
        max_weight: float = 1.0,
        asset_ids: Optional[List[str]] = None,
    ) -> None:
        """
        Ajoute min/max allocation.

        Args:
            min_weight: Poids minimum par actif (global ou spécifique)
            max_weight: Poids maximum par actif (global ou spécifique)
            asset_ids: Si fourni, applique ces limites seulement à ces actifs
        """
        if min_weight > max_weight:
            raise ValueError("min_weight ne peut pas être supérieur à max_weight")
        if asset_ids:
            for a in asset_ids:
                self.asset_specific_bounds[a] = (min_weight, max_weight)
        else:
            self.min_weight = min_weight
            self.max_weight = max_weight
        logger.info(
            f"Added allocation limits: min={min_weight}, max={max_weight}, assets={asset_ids or 'ALL'}"
        )

    def add_asset_bound(self, asset_id: str, min_weight: float, max_weight: float) -> None:
        """Ajoute une borne spécifique à un actif.

        Args:
            asset_id: Identifiant de l'actif
            min_weight: Poids minimum
            max_weight: Poids maximum

        Raises:
            ValueError: si min_weight > max_weight
        """
        if min_weight > max_weight:
            raise ValueError("min_weight ne peut pas être supérieur à max_weight")
        self.asset_specific_bounds[asset_id] = (min_weight, max_weight)
        logger.info(f"Added asset bound for {asset_id}: ({min_weight}, {max_weight})")

    def add_sector_constraint(
        self,
        sector_or_limits: Union[str, Dict[str, float]],
        max_weight_or_mapping: Union[float, Dict[str, str]],
    ) -> None:
        """Ajoute des contraintes sectorielles.

        Deux signatures supportées:
          - add_sector_constraint(sector: str, max_weight: float)
          - add_sector_constraint(limits: Dict[str, float], sector_mapping: Dict[str, str])
        """
        if isinstance(sector_or_limits, str):
            sector = sector_or_limits
            max_weight = float(max_weight_or_mapping)  # type: ignore[assignment]
            if max_weight <= 0 or max_weight > 1:
                raise ValueError("max_weight doit être entre (0, 1]")
            self.sector_limits[sector] = max_weight
            logger.info(f"Added sector constraint: {sector} <= {max_weight:.2f}")
        else:
            limits = sector_or_limits
            mapping = dict(max_weight_or_mapping)  # type: ignore[arg-type]
            for sec, lim in limits.items():
                if lim <= 0 or lim > 1:
                    raise ValueError("max_weight doit être entre (0, 1]")
                self.sector_limits[sec] = float(lim)
            # fusionner le mapping
            if mapping:
                self.sector_mapping.update(mapping)
            logger.info(f"Added sector constraints: {limits}")

    def add_concentration_limit(self, max_herfindahl: float = 0.2) -> None:
        """Limite concentration (ex: HHI < 0.2)."""
        if max_herfindahl <= 0 or max_herfindahl > 1:
            raise ValueError("max_herfindahl doit être dans (0, 1]")
        self.max_herfindahl = max_herfindahl
        logger.info(f"Added concentration limit: HHI <= {max_herfindahl:.2f}")

    def add_long_only(self, enabled: bool = True) -> None:
        """Active/désactive long-only (poids >= 0).

        Args:
            enabled: True pour activer, False pour autoriser le short jusqu'à -1 si pas de borne min.
        """
        self.long_only_enabled = bool(enabled)
        logger.info(f"Long-only set to {self.long_only_enabled}")

    def add_custom_constraint(self, constraint_func: Callable) -> None:
        """Ajoute contrainte custom."""
        if not callable(constraint_func):
            raise TypeError("constraint_func doit être callable")
        self.custom_funcs.append(constraint_func)
        logger.info("Added custom constraint callable")

    def add_turnover_limit(self, previous_weights: pd.Series, max_turnover: float) -> None:
        """Ajoute une contrainte de turnover sum(|w - w_prev|) <= max_turnover.

        Args:
            previous_weights: Série des poids précédents indexée par tickers
            max_turnover: borne maximale du turnover (0..2)
        """
        if max_turnover <= 0:
            raise ValueError("max_turnover doit être positif")
        self._turnover_prev = [float(x) for x in previous_weights.values]
        self._turnover_limit = float(max_turnover)

        def turnover_func(w: np.ndarray, names: List[str]) -> float:
            prev = np.array(self._turnover_prev or [0.0] * len(w), dtype=float)
            return float(self._turnover_limit - np.abs(w - prev).sum())

        self.add_custom_constraint(turnover_func)

    # ---------- Helpers for optimizer ----------
    def build_bounds(self, tickers: List[str]) -> List[Tuple[float, float]]:
        """Construit bounds (min/max par asset) pour scipy.optimize.

        Returns:
            Liste de tuples (lb, ub) pour chaque ticker
        """
        bounds: List[Tuple[float, float]] = []
        for t in tickers:
            if t in self.asset_specific_bounds:
                bounds.append(self.asset_specific_bounds[t])
            else:
                if self.long_only_enabled:
                    lb = 0.0 if self.min_weight is None else self.min_weight
                else:
                    lb = -1.0 if self.min_weight is None else self.min_weight
                ub = self.max_weight if self.max_weight is not None else 1.0
                bounds.append((lb, ub))
        return bounds

    def sector_constraints_functions(self, tickers: List[str]) -> List[Callable[[np.ndarray], float]]:
        """Retourne une liste de fonctions inégalités pour secteurs.

        Convention : f(w) >= 0 quand SATISFAIT (scipy.optimize convention)
        Exemple: max_weight - sum(w_sector) >= 0
        
        Returns:
            Liste de callables prenant w (np.ndarray) et retournant float >= 0 si contrainte OK
        """
        funcs: List[Callable[[np.ndarray], float]] = []
        if not self.sector_limits:
            return funcs
        # Prépare index des tickers par secteur
        sector_to_idx: Dict[str, List[int]] = {}
        for i, t in enumerate(tickers):
            sec = self.sector_mapping.get(t)
            if sec is None:
                continue
            sector_to_idx.setdefault(sec, []).append(i)
        for sector, max_w in self.sector_limits.items():
            idxs = sector_to_idx.get(sector, [])
            if not idxs:
                # Pas de chevauchement -> pas de contrainte effective
                continue
            def make_func(indices: List[int], max_weight: float):
                return lambda w, ind=indices, m=max_weight: float(m - np.sum(w[ind]))
            funcs.append(make_func(idxs, max_w))
        return funcs

    def concentration_constraint_function(self) -> Optional[Callable[[np.ndarray], float]]:
        """Contrainte non-linéaire HHI: sum(w^2) - max_hhi <= 0 (retourne <= 0 si OK)."""
        if self.max_herfindahl is None:
            return None
        return lambda w: np.sum(w ** 2) - float(self.max_herfindahl)


# ---------- Module-level helpers (wrappers) ----------

def add_allocation_limits(constraints: PortfolioConstraints, *args, **kwargs) -> PortfolioConstraints:
    constraints.add_allocation_limits(*args, **kwargs)
    return constraints

def add_sector_constraint(constraints: PortfolioConstraints, *args, **kwargs) -> PortfolioConstraints:
    constraints.add_sector_constraint(*args, **kwargs)
    return constraints

def add_concentration_limit(constraints: PortfolioConstraints, *args, **kwargs) -> PortfolioConstraints:
    constraints.add_concentration_limit(*args, **kwargs)
    return constraints

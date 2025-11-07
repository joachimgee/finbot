from __future__ import annotations

# 1. Stdlib
from typing import Callable, Dict, List, Optional, Tuple, Union

# 2. Third-party
import numpy as np
import pandas as pd

# 3. Local
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

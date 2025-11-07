"""Factor selection using Information Coefficient (IC) analysis."""
from __future__ import annotations

from typing import Dict
import numpy as np
import pandas as pd
from scipy.stats import spearmanr, pearsonr


class FactorAnalyzer:
    """Analyze factor quality using Information Coefficient (IC).

    The IC measures correlation between factor values and forward returns.
    Higher absolute IC implies stronger predictive relationship.

    Example:
        >>> fa = FactorAnalyzer(factors_df, forward_returns)
        >>> ic_map = fa.information_coefficient()
        >>> ranked = fa.rank_factors(top_n=10)
    """

    def __init__(self, factors_df: pd.DataFrame, returns: pd.Series) -> None:
        """Initialize analyzer.

        Args:
            factors_df: DataFrame of factor columns
            returns: Forward returns series aligned by date
        """
        if factors_df is None or factors_df.empty:
            raise ValueError("factors_df must be non-empty")
        if returns is None or returns.empty:
            raise ValueError("returns must be non-empty")

        self.factors = factors_df
        self.returns = returns

    def information_coefficient(self, method: str = "spearman") -> Dict[str, float]:
        """Calculate IC for each factor vs forward returns.

        Args:
            method: 'spearman' (default) or 'pearson'

        Returns:
            Mapping factor_name -> IC value (float)
        """
        if method not in {"spearman", "pearson"}:
            raise ValueError("method must be 'spearman' or 'pearson'")

        ics: Dict[str, float] = {}
        for factor_name in self.factors.columns:
            vals = self.factors[factor_name]
            valid_idx = vals.notna() & self.returns.notna()
            if valid_idx.sum() < 30:  # Need enough data points
                continue
            try:
                if method == "spearman":
                    ic, _ = spearmanr(vals[valid_idx], self.returns[valid_idx])
                else:
                    ic, _ = pearsonr(vals[valid_idx], self.returns[valid_idx])
            except Exception:
                continue
            if np.isfinite(ic):
                ics[factor_name] = float(ic)
        return ics

    def rank_factors(self, top_n: int = 20) -> pd.DataFrame:
        """Rank factors by absolute IC magnitude.

        Args:
            top_n: Number of top factors to return
        """
        ics = self.information_coefficient()
        if not ics:
            return pd.DataFrame(columns=["Factor", "IC"])  # empty result
        ranked = (
            pd.DataFrame({"Factor": list(ics.keys()), "IC": list(ics.values())})
            .assign(absIC=lambda d: d["IC"].abs())
            .sort_values("absIC", ascending=False)
            .drop(columns="absIC")
        )
        return ranked.head(top_n)

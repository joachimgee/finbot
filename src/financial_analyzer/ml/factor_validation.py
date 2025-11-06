"""Factor validation utilities (Phase 5.2 - PLACEHOLDER).

This module will provide tools for validating factor quality:
- Data quality checks (missing data ratio)
- Outlier detection (z-score, IQR)
- Stationarity tests (ADF, KPSS)

To be implemented in Phase 5.2: Extended Factor Library.
"""
from __future__ import annotations

from typing import Dict, Optional

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import adfuller


class FactorValidator:
    """Validate factor quality and statistical properties.
    
    Placeholder for Phase 5.2 implementation.
    
    Example:
        >>> validator = FactorValidator(factors_df)
        >>> quality = validator.check_data_quality()
        >>> stationarity = validator.test_stationarity()
    """
    
    def __init__(self, factors: pd.DataFrame) -> None:
        """Initialize validator with factor DataFrame.
        
        Args:
            factors: DataFrame with factors (dates x factor_names)
        """
        self.factors = factors
    
    def check_data_quality(self) -> pd.Series:
        """Check data quality (missing data ratio).
        
        Returns:
            Series with missing_data_ratio for each factor
        """
        missing_ratio = self.factors.isna().sum() / len(self.factors)
        return missing_ratio
    
    def test_stationarity(self, factor_name: str) -> Dict[str, float]:
        """Test factor stationarity using Augmented Dickey-Fuller test.
        
        Args:
            factor_name: Name of factor to test
            
        Returns:
            Dict with ADF test results (test_statistic, p_value, critical_values)
            
        Raises:
            ValueError: If factor_name not found or insufficient data
        """
        if factor_name not in self.factors.columns:
            raise ValueError(f"Factor {factor_name} not found")
        
        series = self.factors[factor_name].dropna()
        if len(series) < 10:
            raise ValueError(f"Insufficient data for ADF test (need 10+, got {len(series)})")
        
        adf_result = adfuller(series, autolag='AIC')
        return {
            'test_statistic': float(adf_result[0]),
            'p_value': float(adf_result[1]),
            'critical_value_1pct': float(adf_result[4]['1%']),
            'critical_value_5pct': float(adf_result[4]['5%']),
            'critical_value_10pct': float(adf_result[4]['10%']),
        }
    
    def detect_outliers_zscore(
        self,
        factor_name: str,
        threshold: float = 3.0
    ) -> pd.Series:
        """Detect outliers using z-score method.
        
        Args:
            factor_name: Name of factor to check
            threshold: Z-score threshold (default: 3.0)
            
        Returns:
            Boolean Series indicating outliers (True = outlier)
        """
        if factor_name not in self.factors.columns:
            raise ValueError(f"Factor {factor_name} not found")
        
        series = self.factors[factor_name]
        mean = series.mean()
        std = series.std()
        
        if std == 0:
            return pd.Series(False, index=series.index)
        
        z_scores = np.abs((series - mean) / std)
        return z_scores > threshold

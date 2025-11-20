"""
Autocorrelation Features Module.

Module pour extraire features temporelles basées sur autocorrélation :
- ACF (Autocorrelation Function) : Corrélation avec lags
- PACF (Partial Autocorrelation Function) : Corrélation après enlever effets intermédiaires
- Hurst Exponent : Mesure de la mémoire long terme (mean-reversion vs trending)
- Seasonality Detection : Détection de patterns saisonniers

Applications :
- Feature engineering pour ML
- Détection de mean-reversion vs momentum
- Sélection de lags optimaux pour modèles AR/ARMA
- Détection de cycles de marché

Based on : Box & Jenkins (1976), Hurst (1951), Prado (2018).
"""

from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.tsa.stattools import acf, pacf
from statsmodels.tsa.seasonal import seasonal_decompose

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class AutocorrelationFeatures:
    """
    Générateur de features basées sur autocorrélation.
    
    Attributes:
        max_lags: Nombre max de lags à calculer
        alpha: Niveau de confiance pour tests significativité
    
    Example:
        >>> acf_features = AutocorrelationFeatures(max_lags=20)
        >>> features = acf_features.compute_all(returns)
        >>> print(features['hurst_exponent'])  # 0.5 = random walk, >0.5 = trending, <0.5 = mean-reverting
    """
    
    def __init__(
        self,
        max_lags: int = 20,
        alpha: float = 0.05
    ):
        """
        Initialise AutocorrelationFeatures.
        
        Args:
            max_lags: Nombre max de lags pour ACF/PACF
            alpha: Niveau de confiance pour significativité (0.05 = 95%)
        """
        if max_lags < 1:
            raise ValueError("max_lags doit être >= 1")
        if not 0 < alpha < 1:
            raise ValueError("alpha doit être dans (0, 1)")
        
        self.max_lags = max_lags
        self.alpha = alpha
        
        logger.debug(f"AutocorrelationFeatures initialized: max_lags={max_lags}, alpha={alpha}")
    
    def compute_acf(
        self,
        series: pd.Series,
        nlags: Optional[int] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calcule ACF (Autocorrelation Function).
        
        Args:
            series: Série temporelle
            nlags: Nombre de lags (si None, utilise self.max_lags)
        
        Returns:
            Tuple (acf_values, confidence_intervals)
        
        Example:
            >>> acf_vals, conf_int = acf_features.compute_acf(returns)
        """
        nlags = nlags or self.max_lags
        nlags = min(nlags, len(series) // 2 - 1)
        
        if nlags < 1:
            raise ValueError("Series trop courte pour ACF")
        
        acf_values = acf(series.dropna(), nlags=nlags, alpha=self.alpha, fft=False)
        
        # Confidence intervals (±1.96/sqrt(n) pour 95% sous H0: no autocorr)
        n = len(series.dropna())
        conf_int = 1.96 / np.sqrt(n)
        
        return acf_values, conf_int
    
    def compute_pacf(
        self,
        series: pd.Series,
        nlags: Optional[int] = None
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Calcule PACF (Partial Autocorrelation Function).
        
        Args:
            series: Série temporelle
            nlags: Nombre de lags
        
        Returns:
            Tuple (pacf_values, confidence_intervals)
        
        Example:
            >>> pacf_vals, conf_int = acf_features.compute_pacf(returns)
        """
        nlags = nlags or self.max_lags
        nlags = min(nlags, len(series) // 2 - 1)
        
        if nlags < 1:
            raise ValueError("Series trop courte pour PACF")
        
        pacf_values = pacf(series.dropna(), nlags=nlags, alpha=self.alpha, method='ywm')
        
        n = len(series.dropna())
        conf_int = 1.96 / np.sqrt(n)
        
        return pacf_values, conf_int
    
    def compute_hurst_exponent(
        self,
        series: pd.Series,
        lags_range: Tuple[int, int] = (2, 20)
    ) -> float:
        """
        Calcule Hurst Exponent (H).
        
        Interprétation :
        - H = 0.5 : Random walk (Brownian motion)
        - H > 0.5 : Trending behavior (momentum)
        - H < 0.5 : Mean-reverting behavior
        
        Méthode : R/S analysis (Rescaled Range)
        
        Args:
            series: Série temporelle
            lags_range: (min_lag, max_lag) pour estimation
        
        Returns:
            Hurst exponent
        
        Example:
            >>> hurst = acf_features.compute_hurst_exponent(prices)
            >>> if hurst < 0.5:
            ...     print("Mean-reverting series")
        """
        series_clean = series.dropna().values
        
        if len(series_clean) < lags_range[1]:
            raise ValueError("Series trop courte pour Hurst exponent")
        
        lags = range(lags_range[0], min(lags_range[1], len(series_clean) // 2))
        
        # R/S analysis
        tau = []
        rs_values = []
        
        for lag in lags:
            # Diviser série en chunks de taille lag
            n_chunks = len(series_clean) // lag
            
            if n_chunks == 0:
                continue
            
            rs_chunk = []
            
            for i in range(n_chunks):
                chunk = series_clean[i * lag:(i + 1) * lag]
                
                # Mean-centered cumulative sum
                mean = np.mean(chunk)
                cumsum = np.cumsum(chunk - mean)
                
                # Range
                R = np.max(cumsum) - np.min(cumsum)
                
                # Std
                S = np.std(chunk, ddof=1)
                
                if S > 0:
                    rs_chunk.append(R / S)
            
            if rs_chunk:
                tau.append(lag)
                rs_values.append(np.mean(rs_chunk))
        
        # Linear regression : log(R/S) = H * log(lag) + const
        if len(tau) < 2:
            logger.warning("Pas assez de lags pour Hurst exponent, retourne 0.5")
            return 0.5
        
        log_tau = np.log(tau)
        log_rs = np.log(rs_values)
        
        # Regression
        slope, intercept, r_value, p_value, std_err = stats.linregress(log_tau, log_rs)
        
        hurst = slope
        
        # Clamp to [0, 1]
        hurst = np.clip(hurst, 0.0, 1.0)
        
        logger.debug(f"Hurst exponent computed: H={hurst:.3f} (R²={r_value**2:.3f})")
        
        return hurst
    
    def detect_seasonality(
        self,
        series: pd.Series,
        period: Optional[int] = None,
        model: str = 'additive'
    ) -> Dict[str, Union[pd.Series, float]]:
        """
        Détecte seasonality dans série temporelle.
        
        Args:
            series: Série temporelle
            period: Période saisonnière (si None, détection auto)
            model: 'additive' ou 'multiplicative'
        
        Returns:
            Dict avec trend, seasonal, residual, seasonality_strength
        
        Example:
            >>> decomp = acf_features.detect_seasonality(prices, period=252)
            >>> print(decomp['seasonality_strength'])  # 0 à 1
        """
        series_clean = series.dropna()
        
        if period is None:
            # Auto-detect period via ACF peaks
            acf_vals, _ = self.compute_acf(series_clean, nlags=min(100, len(series_clean) // 2))
            
            # Trouver premier pic significatif
            peaks = []
            for i in range(2, len(acf_vals) - 1):
                if acf_vals[i] > acf_vals[i-1] and acf_vals[i] > acf_vals[i+1]:
                    peaks.append((i, acf_vals[i]))
            
            if peaks:
                period = max(peaks, key=lambda x: x[1])[0]
            else:
                period = 7  # Default
        
        # Seasonal decomposition
        if len(series_clean) < 2 * period:
            logger.warning("Series trop courte pour decomposition saisonnière")
            return {
                'trend': pd.Series(dtype=float),
                'seasonal': pd.Series(dtype=float),
                'residual': pd.Series(dtype=float),
                'seasonality_strength': 0.0
            }
        
        decomposition = seasonal_decompose(
            series_clean,
            model=model,
            period=period,
            extrapolate_trend='freq'
        )
        
        # Seasonality strength : 1 - Var(residual) / Var(seasonal + residual)
        var_resid = np.var(decomposition.resid.dropna())
        var_detrend = np.var((series_clean - decomposition.trend).dropna())
        
        if var_detrend > 0:
            seasonality_strength = max(0, 1 - var_resid / var_detrend)
        else:
            seasonality_strength = 0.0
        
        return {
            'trend': decomposition.trend,
            'seasonal': decomposition.seasonal,
            'residual': decomposition.resid,
            'seasonality_strength': seasonality_strength
        }
    
    def select_optimal_lags(
        self,
        series: pd.Series,
        method: str = 'pacf',
        threshold: Optional[float] = None
    ) -> List[int]:
        """
        Sélectionne lags significatifs pour modèles AR.
        
        Args:
            series: Série temporelle
            method: 'pacf' ou 'acf'
            threshold: Seuil de significativité (si None, utilise confidence interval)
        
        Returns:
            Liste de lags significatifs
        
        Example:
            >>> lags = acf_features.select_optimal_lags(returns, method='pacf')
            >>> print(f"Lags significatifs: {lags}")
        """
        if method == 'pacf':
            values, conf_int = self.compute_pacf(series)
        else:
            values, conf_int = self.compute_acf(series)
        
        threshold = threshold or conf_int
        
        # Sélectionner lags où |value| > threshold
        significant_lags = []
        
        for i, val in enumerate(values[1:], start=1):  # Skip lag 0
            if abs(val) > threshold:
                significant_lags.append(i)
        
        logger.debug(f"Lags significatifs ({method}): {significant_lags}")
        
        return significant_lags
    
    def compute_all(
        self,
        series: pd.Series,
        include_seasonality: bool = False
    ) -> Dict[str, Union[float, List[int], np.ndarray]]:
        """
        Calcule toutes les features d'autocorrélation.
        
        Args:
            series: Série temporelle
            include_seasonality: Inclure décomposition saisonnière
        
        Returns:
            Dict avec toutes les features
        
        Example:
            >>> features = acf_features.compute_all(returns)
            >>> print(features['hurst_exponent'])
            >>> print(features['significant_lags_pacf'])
        """
        features = {}
        
        # ACF/PACF
        acf_vals, acf_conf = self.compute_acf(series)
        pacf_vals, pacf_conf = self.compute_pacf(series)
        
        features['acf_values'] = acf_vals
        features['pacf_values'] = pacf_vals
        features['acf_confidence'] = acf_conf
        features['pacf_confidence'] = pacf_conf
        
        # Hurst
        try:
            features['hurst_exponent'] = self.compute_hurst_exponent(series)
        except Exception as e:
            logger.warning(f"Hurst exponent failed: {e}")
            features['hurst_exponent'] = 0.5
        
        # Lags significatifs
        features['significant_lags_acf'] = self.select_optimal_lags(series, method='acf')
        features['significant_lags_pacf'] = self.select_optimal_lags(series, method='pacf')
        
        # Seasonality (optionnel, coûteux)
        if include_seasonality:
            try:
                decomp = self.detect_seasonality(series)
                features['seasonality_strength'] = decomp['seasonality_strength']
            except Exception as e:
                logger.warning(f"Seasonality detection failed: {e}")
                features['seasonality_strength'] = 0.0
        
        logger.info(f"Computed all autocorrelation features: Hurst={features['hurst_exponent']:.3f}")
        
        return features


def compute_hurst(series: pd.Series, lags_range: Tuple[int, int] = (2, 20)) -> float:
    """
    Fonction convenience pour Hurst exponent.
    
    Args:
        series: Série temporelle
        lags_range: (min, max) lags
    
    Returns:
        Hurst exponent
    
    Example:
        >>> h = compute_hurst(prices)
        >>> regime = 'trending' if h > 0.5 else 'mean-reverting'
    """
    acf_features = AutocorrelationFeatures()
    return acf_features.compute_hurst_exponent(series, lags_range)

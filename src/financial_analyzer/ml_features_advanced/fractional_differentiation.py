"""
Fractional Differentiation Module.

La différenciation fractionnaire permet de rendre une série temporelle stationnaire
tout en préservant la mémoire (autocorrélation).

Problème : 
- Intégration d'ordre 1 (I(1)) → non-stationnaire
- Différenciation standard (d=1) → perte de mémoire

Solution : Différenciation fractionnaire (0 < d < 1)
- Préserve stationnarité ET mémoire
- Optimal pour ML features

Based on: Prado, M. L. de. (2018). Advances in Financial Machine Learning, Chapter 5.
"""

from typing import Dict, Optional, Tuple
import numpy as np
import pandas as pd
from scipy.stats import norm
from statsmodels.tsa.stattools import adfuller

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class FractionalDifferentiator:
    """
    Différenciateur fractionnel pour séries temporelles financières.
    
    La différenciation fractionnaire d'ordre d est définie par :
    X_t^d = Σ(k=0 to ∞) w_k * X_{t-k}
    
    où les poids w_k sont calculés via la formule des coefficients binomiaux :
    w_k = (-1)^k * d! / (k! * (d-k)!)
    
    Attributes:
        d: Ordre de différenciation (0 < d < 1)
        threshold: Seuil pour tronquer les poids
        min_weight: Poids min pour arrêter expansion
    
    Example:
        >>> fd = FractionalDifferentiator()
        >>> optimal_d = fd.get_optimal_d(prices)
        >>> stationary_series = fd.transform(prices, d=optimal_d)
        >>> original = fd.inverse_transform(stationary_series)
    """
    
    def __init__(
        self,
        threshold: float = 1e-5,
        min_weight: float = 1e-5
    ):
        """
        Initialise FractionalDifferentiator.
        
        Args:
            threshold: Seuil ADF p-value pour stationnarité
            min_weight: Poids min pour tronquer expansion
        """
        self.threshold = threshold
        self.min_weight = min_weight
        self.weights_cache_ = {}
        
        logger.debug(f"FractionalDifferentiator initialized: threshold={threshold}")
    
    def _get_weights(self, d: float, size: int) -> np.ndarray:
        """
        Calcule les poids w_k pour différenciation fractionnaire.
        
        Formula: w_k = -w_{k-1} * (d - k + 1) / k
        
        Args:
            d: Ordre différenciation
            size: Nombre de poids à calculer
        
        Returns:
            Array de poids [w_0, w_1, ..., w_{size-1}]
        """
        # Cache lookup
        cache_key = (d, size)
        if cache_key in self.weights_cache_:
            return self.weights_cache_[cache_key]
        
        # Initialisation
        weights = np.zeros(size)
        weights[0] = 1.0
        
        # Récurrence : w_k = -w_{k-1} * (d - k + 1) / k
        for k in range(1, size):
            weights[k] = -weights[k-1] * (d - k + 1) / k
            
            # Tronquer si poids devient négligeable
            if abs(weights[k]) < self.min_weight:
                weights = weights[:k]
                break
        
        # Cache
        self.weights_cache_[cache_key] = weights
        
        logger.debug(f"Computed {len(weights)} weights for d={d:.3f}")
        return weights
    
    def _get_weights_ffd(self, d: float, threshold: float, size: int) -> pd.Series:
        """
        Fixed-Width Window Differentiation (FFD).
        
        Variante optimisée : fixe une fenêtre pour calculer les poids.
        Plus rapide et évite expansion infinie.
        
        Args:
            d: Ordre
            threshold: Seuil pour tronquer
            size: Taille max
        
        Returns:
            Series de poids
        """
        w = [1.0]
        k = 1
        
        while k < size:
            w_k = -w[-1] * (d - k + 1) / k
            
            if abs(w_k) < threshold:
                break
            
            w.append(w_k)
            k += 1
        
        w = np.array(w[::-1])  # Reverse pour convolution
        return pd.Series(w)
    
    def transform(
        self,
        series: pd.Series,
        d: float,
        use_ffd: bool = True
    ) -> pd.Series:
        """
        Applique différenciation fractionnaire.
        
        Args:
            series: Série temporelle (ex: log prices)
            d: Ordre de différenciation (0 < d < 1)
            use_ffd: Utiliser Fixed-Width Window (plus rapide)
        
        Returns:
            Série différenciée d'ordre d
        
        Raises:
            ValueError: Si d hors bornes
        
        Example:
            >>> stationary = fd.transform(log_prices, d=0.4)
        """
        if not (0 <= d <= 1):
            raise ValueError(f"d must be in [0, 1], got {d}")
        
        if d == 0:
            return series.copy()
        
        # Calculer poids
        if use_ffd:
            weights = self._get_weights_ffd(d, self.min_weight, len(series))
        else:
            weights = self._get_weights(d, len(series))
        
        # Convolution : X_t^d = Σ w_k * X_{t-k}
        result = []
        
        for i in range(len(weights) - 1, len(series)):
            window = series.iloc[i - len(weights) + 1 : i + 1].values
            value = np.dot(weights, window)
            result.append(value)
        
        # Créer série avec index aligné
        transformed = pd.Series(
            result,
            index=series.index[len(weights) - 1:],
            name=f"{series.name}_d{d:.2f}"
        )
        
        logger.info(f"Transformed series with d={d:.3f}, retained {len(transformed)}/{len(series)} obs")
        
        return transformed
    
    def inverse_transform(
        self,
        series_diff: pd.Series,
        d: float,
        initial_values: Optional[pd.Series] = None
    ) -> pd.Series:
        """
        Inverse la différenciation fractionnaire (reconstruction).
        
        Approximation : X_t ≈ Σ(k=0 to t) (-w_k) * X_{t-k}^d
        
        Args:
            series_diff: Série différenciée
            d: Ordre utilisé pour transformation
            initial_values: Valeurs initiales (optionnel, sinon zéro)
        
        Returns:
            Série reconstruite (approximation)
        
        Example:
            >>> reconstructed = fd.inverse_transform(stationary, d=0.4)
        """
        if d == 0:
            return series_diff.copy()
        
        # Poids inversés (approximation)
        weights = self._get_weights(-d, len(series_diff))
        
        result = []
        
        for i in range(len(series_diff)):
            if i < len(weights):
                # Utiliser initial_values si disponible
                window = series_diff.iloc[:i+1].values
                w = weights[:i+1][::-1]
            else:
                window = series_diff.iloc[i - len(weights) + 1 : i + 1].values
                w = weights
            
            value = np.dot(w, window)
            result.append(value)
        
        reconstructed = pd.Series(
            result,
            index=series_diff.index,
            name=f"{series_diff.name}_invd{d:.2f}"
        )
        
        return reconstructed
    
    def get_optimal_d(
        self,
        series: pd.Series,
        d_range: Tuple[float, float] = (0.0, 1.0),
        step: float = 0.05,
        adf_pvalue_threshold: float = 0.05
    ) -> Dict[str, float]:
        """
        Trouve le d optimal : minimum pour avoir stationnarité.
        
        Stratégie :
        1. Tester d de 0.0 à 1.0 par pas de step
        2. Pour chaque d, calculer ADF test
        3. Retourner le plus petit d avec p-value < threshold
        
        Args:
            series: Série temporelle
            d_range: Range de d à tester (min, max)
            step: Pas pour recherche
            adf_pvalue_threshold: Seuil p-value ADF
        
        Returns:
            Dict avec 'optimal_d', 'adf_pvalue', 'adf_statistic'
        
        Example:
            >>> result = fd.get_optimal_d(log_prices)
            >>> print(f"Optimal d: {result['optimal_d']:.3f}")
        """
        logger.info(f"Finding optimal d in range {d_range} with step={step}")
        
        d_values = np.arange(d_range[0], d_range[1] + step, step)
        
        best_d = None
        best_result = None
        
        for d in d_values:
            # Transformer
            try:
                transformed = self.transform(series, d=d)
                
                # ADF test
                adf_result = adfuller(transformed.dropna(), maxlag=1, regression='c', autolag=None)
                adf_stat = adf_result[0]
                adf_pval = adf_result[1]
                
                logger.debug(f"d={d:.2f} → ADF p-value={adf_pval:.4f}")
                
                # Premier d qui donne stationnarité
                if adf_pval < adf_pvalue_threshold:
                    best_d = d
                    best_result = {
                        'optimal_d': d,
                        'adf_pvalue': adf_pval,
                        'adf_statistic': adf_stat,
                        'is_stationary': True
                    }
                    break
            
            except Exception as e:
                logger.warning(f"Failed to test d={d:.2f}: {e}")
                continue
        
        # Si aucun d ne donne stationnarité, retourner d=1.0
        if best_d is None:
            logger.warning("No d found for stationarity, using d=1.0")
            transformed = self.transform(series, d=1.0)
            adf_result = adfuller(transformed.dropna(), maxlag=1, regression='c', autolag=None)
            best_result = {
                'optimal_d': 1.0,
                'adf_pvalue': adf_result[1],
                'adf_statistic': adf_result[0],
                'is_stationary': False
            }
        
        logger.info(f"Optimal d={best_result['optimal_d']:.3f} (p-value={best_result['adf_pvalue']:.4f})")
        
        return best_result
    
    def plot_weights(self, d: float, size: int = 50) -> pd.DataFrame:
        """
        Génère poids pour visualisation.
        
        Args:
            d: Ordre
            size: Nombre de poids
        
        Returns:
            DataFrame avec k et w_k
        """
        weights = self._get_weights(d, size)
        
        df = pd.DataFrame({
            'lag': np.arange(len(weights)),
            'weight': weights,
            'd': d
        })
        
        return df
    
    def analyze_memory_preservation(
        self,
        series: pd.Series,
        d: float,
        max_lag: int = 20
    ) -> Dict[str, np.ndarray]:
        """
        Analyse la préservation de mémoire (autocorrélation).
        
        Compare ACF de série originale vs différenciée.
        
        Args:
            series: Série originale
            d: Ordre différenciation
            max_lag: Nombre de lags
        
        Returns:
            Dict avec 'acf_original', 'acf_diff', 'memory_preserved'
        """
        from statsmodels.tsa.stattools import acf
        
        # ACF original
        acf_orig = acf(series.dropna(), nlags=max_lag, fft=False)
        
        # Transformer et ACF
        transformed = self.transform(series, d=d)
        acf_diff = acf(transformed.dropna(), nlags=max_lag, fft=False)
        
        # Ratio de préservation
        memory_preserved = np.abs(acf_diff[1:]) / (np.abs(acf_orig[1:]) + 1e-8)
        
        result = {
            'acf_original': acf_orig,
            'acf_diff': acf_diff,
            'memory_preserved': memory_preserved,
            'd': d
        }
        
        logger.info(f"Memory preservation: mean ratio={memory_preserved.mean():.3f}")
        
        return result


def frac_diff(
    series: pd.Series,
    d: float = 0.5,
    threshold: float = 1e-5
) -> pd.Series:
    """
    Fonction convenience pour différenciation fractionnaire.
    
    Args:
        series: Série temporelle
        d: Ordre (auto si None)
        threshold: Seuil poids
    
    Returns:
        Série différenciée
    
    Example:
        >>> stationary = frac_diff(log_prices, d=0.4)
    """
    fd = FractionalDifferentiator(min_weight=threshold)
    return fd.transform(series, d=d)


def get_optimal_d(
    series: pd.Series,
    step: float = 0.05
) -> float:
    """
    Trouve d optimal (convenience).
    
    Args:
        series: Série
        step: Pas recherche
    
    Returns:
        d optimal
    
    Example:
        >>> d_opt = get_optimal_d(log_prices)
    """
    fd = FractionalDifferentiator()
    result = fd.get_optimal_d(series, step=step)
    return result['optimal_d']

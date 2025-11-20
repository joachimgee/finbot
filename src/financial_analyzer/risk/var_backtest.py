"""
Backtesting VaR (Value at Risk) selon méthodologie Basel.

Implémente les tests de validation réglementaires:
- Unconditional coverage test (Kupiec)
- Conditional coverage test (Christoffersen)
- Traffic light approach (Basel Committee)

Références:
- Basel Committee on Banking Supervision (1996, 2019)
- Kupiec, P. (1995): "Techniques for Verifying the Accuracy of Risk Measurement Models"
- Christoffersen, P. (1998): "Evaluating Interval Forecasts"
"""

import pandas as pd
import numpy as np
from typing import Dict, Tuple, Optional
from scipy import stats
from datetime import datetime

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class VaRBacktester:
    """
    Backtester VaR conforme Basel.
    
    Attributes:
        returns: Series de rendements observés
        var_forecasts: Series de VaR forecasts (valeurs positives)
        confidence_level: Niveau de confiance (défaut 0.95)
    
    Example:
        >>> backtester = VaRBacktester(returns, var_forecasts)
        >>> results = backtester.run_all_tests()
        >>> print(results['traffic_light'])
        'green'
    """
    
    def __init__(
        self,
        returns: pd.Series,
        var_forecasts: pd.Series,
        confidence_level: float = 0.95
    ):
        """
        Initialise le backtester.
        
        Args:
            returns: Rendements observés (négatif = perte)
            var_forecasts: VaR forecasts (positif = perte prévue)
            confidence_level: Niveau de confiance (ex: 0.95 pour 95%)
        
        Raises:
            ValueError: Si données incompatibles
        """
        if len(returns) != len(var_forecasts):
            raise ValueError(f"Length mismatch: returns={len(returns)}, forecasts={len(var_forecasts)}")
        
        self.returns = returns.copy()
        self.var_forecasts = var_forecasts.copy()
        self.confidence_level = confidence_level
        self.alpha = 1.0 - confidence_level
        
        # Calculer violations (exceptions)
        self.losses = -returns  # Pertes positives
        self.violations = (self.losses > var_forecasts).astype(int)
        self.n_violations = self.violations.sum()
        self.n_obs = len(returns)
        
        logger.info(f"VaRBacktester initialized: {self.n_obs} obs, {self.n_violations} violations")
    
    def kupiec_test(self) -> Dict:
        """
        Test de Kupiec (Unconditional Coverage).
        
        H0: Taux de violation = α (niveau de confiance correct)
        
        Returns:
            Dict avec:
            - statistic: LR test statistic
            - p_value: P-value
            - reject_h0: True si on rejette H0 (mauvais modèle)
            - violation_rate: Taux observé
        
        Reference:
            Kupiec (1995): POF test (Proportion of Failures)
        """
        observed_rate = self.n_violations / self.n_obs
        expected_rate = self.alpha
        
        # Likelihood ratio test
        if self.n_violations == 0:
            lr_stat = 0.0
        elif self.n_violations == self.n_obs:
            lr_stat = np.inf
        else:
            lr_stat = -2 * (
                self.n_violations * np.log(expected_rate) +
                (self.n_obs - self.n_violations) * np.log(1 - expected_rate) -
                self.n_violations * np.log(observed_rate) -
                (self.n_obs - self.n_violations) * np.log(1 - observed_rate)
            )
        
        # Chi-square distribution (df=1)
        p_value = 1 - stats.chi2.cdf(lr_stat, df=1)
        reject_h0 = p_value < 0.05
        
        result = {
            'test': 'Kupiec (Unconditional Coverage)',
            'statistic': float(lr_stat),
            'p_value': float(p_value),
            'reject_h0': reject_h0,
            'violation_rate': float(observed_rate),
            'expected_rate': float(expected_rate),
            'interpretation': 'FAIL' if reject_h0 else 'PASS'
        }
        
        logger.info(f"Kupiec test: LR={lr_stat:.2f}, p={p_value:.4f}, {result['interpretation']}")
        
        return result
    
    def christoffersen_test(self) -> Dict:
        """
        Test de Christoffersen (Conditional Coverage).
        
        H0: Violations indépendantes ET taux correct
        
        Returns:
            Dict avec test statistics et résultat
        
        Reference:
            Christoffersen (1998): Tests violations clustering
        """
        # Test d'indépendance (Markov chain)
        n00 = n01 = n10 = n11 = 0
        
        for i in range(len(self.violations) - 1):
            if self.violations.iloc[i] == 0 and self.violations.iloc[i+1] == 0:
                n00 += 1
            elif self.violations.iloc[i] == 0 and self.violations.iloc[i+1] == 1:
                n01 += 1
            elif self.violations.iloc[i] == 1 and self.violations.iloc[i+1] == 0:
                n10 += 1
            elif self.violations.iloc[i] == 1 and self.violations.iloc[i+1] == 1:
                n11 += 1
        
        # Probabilités de transition
        pi_0 = n01 / (n00 + n01) if (n00 + n01) > 0 else 0
        pi_1 = n11 / (n10 + n11) if (n10 + n11) > 0 else 0
        pi = (n01 + n11) / (n00 + n01 + n10 + n11)
        
        # LR test d'indépendance
        if pi_0 == 0 or pi_1 == 0 or pi == 0 or pi == 1:
            lr_ind = 0.0
        else:
            lr_ind = -2 * (
                (n00 + n01) * np.log(1 - pi) + (n01 + n11) * np.log(pi) -
                n00 * np.log(1 - pi_0) - n01 * np.log(pi_0) -
                n10 * np.log(1 - pi_1) - n11 * np.log(pi_1)
            )
        
        p_value_ind = 1 - stats.chi2.cdf(lr_ind, df=1)
        
        # Test conditionnel = Kupiec + indépendance
        kupiec = self.kupiec_test()
        lr_cc = kupiec['statistic'] + lr_ind
        p_value_cc = 1 - stats.chi2.cdf(lr_cc, df=2)
        reject_h0 = p_value_cc < 0.05
        
        result = {
            'test': 'Christoffersen (Conditional Coverage)',
            'statistic': float(lr_cc),
            'p_value': float(p_value_cc),
            'independence_stat': float(lr_ind),
            'independence_pvalue': float(p_value_ind),
            'reject_h0': reject_h0,
            'interpretation': 'FAIL' if reject_h0 else 'PASS'
        }
        
        logger.info(f"Christoffersen test: LR_CC={lr_cc:.2f}, p={p_value_cc:.4f}, {result['interpretation']}")
        
        return result
    
    def traffic_light_test(self) -> Dict:
        """
        Test Traffic Light (Basel Committee).
        
        Zones:
        - Green: 0-4 violations sur 250 jours (modèle acceptable)
        - Yellow: 5-9 violations (zone d'alerte)
        - Red: 10+ violations (modèle rejeté)
        
        Returns:
            Dict avec zone et recommandation
        
        Reference:
            Basel Committee (1996, 2019): Supervisory framework for VaR
        """
        # Normaliser à 250 jours (1 an trading)
        days_factor = 250 / self.n_obs
        violations_250 = int(self.n_violations * days_factor)
        
        if violations_250 <= 4:
            zone = 'green'
            multiplier = 3.0  # Multiplicateur capital Basel
            interpretation = 'PASS - Model acceptable'
        elif violations_250 <= 9:
            zone = 'yellow'
            multiplier = 3.4 + 0.2 * (violations_250 - 4)
            interpretation = 'WARNING - Model in alert zone'
        else:
            zone = 'red'
            multiplier = 4.0
            interpretation = 'FAIL - Model rejected'
        
        result = {
            'test': 'Basel Traffic Light',
            'zone': zone,
            'violations_observed': self.n_violations,
            'violations_250d': violations_250,
            'capital_multiplier': float(multiplier),
            'interpretation': interpretation
        }
        
        logger.info(f"Traffic Light: {zone.upper()} zone, {violations_250} violations/250d")
        
        return result
    
    def expected_shortfall_backtest(self) -> Dict:
        """
        Backtest Expected Shortfall (CVaR).
        
        Vérifie que les pertes au-delà de VaR ont la moyenne attendue.
        
        Returns:
            Dict avec résultats ES backtest
        """
        # Pertes dépassant VaR
        tail_losses = self.losses[self.losses > self.var_forecasts]
        
        if len(tail_losses) == 0:
            return {
                'test': 'Expected Shortfall Backtest',
                'n_tail_losses': 0,
                'avg_tail_loss': 0.0,
                'interpretation': 'No violations to assess'
            }
        
        avg_tail_loss = float(tail_losses.mean())
        avg_var = float(self.var_forecasts[self.losses > self.var_forecasts].mean())
        
        # ES devrait être > VaR
        es_ratio = avg_tail_loss / avg_var if avg_var > 0 else 0
        
        result = {
            'test': 'Expected Shortfall Backtest',
            'n_tail_losses': len(tail_losses),
            'avg_tail_loss': avg_tail_loss,
            'avg_var_at_violation': avg_var,
            'es_var_ratio': float(es_ratio),
            'interpretation': 'PASS' if es_ratio >= 1.0 else 'FAIL - Underestimated tail'
        }
        
        logger.info(f"ES Backtest: avg tail loss={avg_tail_loss:.2%}, ratio={es_ratio:.2f}")
        
        return result
    
    def run_all_tests(self) -> Dict:
        """
        Exécute tous les tests de validation.
        
        Returns:
            Dict avec résultats de tous les tests
        
        Example:
            >>> results = backtester.run_all_tests()
            >>> print(f"Overall: {results['overall_assessment']}")
        """
        logger.info("Running all VaR backtests...")
        
        kupiec = self.kupiec_test()
        christoffersen = self.christoffersen_test()
        traffic_light = self.traffic_light_test()
        es_backtest = self.expected_shortfall_backtest()
        
        # Assessment global
        all_pass = (
            not kupiec['reject_h0'] and
            not christoffersen['reject_h0'] and
            traffic_light['zone'] == 'green'
        )
        
        results = {
            'kupiec': kupiec,
            'christoffersen': christoffersen,
            'traffic_light': traffic_light,
            'expected_shortfall': es_backtest,
            'overall_assessment': 'PASS' if all_pass else 'FAIL',
            'n_observations': self.n_obs,
            'n_violations': self.n_violations,
            'violation_rate': float(self.n_violations / self.n_obs)
        }
        
        logger.info(f"Backtest complete: {results['overall_assessment']}")
        
        return results


def _cornish_fisher_adjusted_z(z: float, skew: float, kurt_excess: float) -> float:
    """Calcule le quantile ajusté Cornish-Fisher.

    Args:
        z: Quantile normal standard (ex: stats.norm.ppf(confidence))
        skew: Skewness (3rd moment normalisé)
        kurt_excess: Kurtosis - 3 (excess)

    Returns:
        Quantile ajusté prenant en compte skew et kurtosis.
    """
    term1 = z
    term2 = (1/6) * (z**2 - 1) * skew
    term3 = (1/24) * (z**3 - 3*z) * kurt_excess
    term4 = (1/36) * (2*z**3 - 5*z) * (skew**2)
    return term1 + term2 + term3 - term4


def _compute_var(train_window: pd.Series, confidence: float, method: str) -> float:
    """Calcule la VaR selon méthode spécifiée.

    Méthodes supportées:
        - historical
        - parametric
        - ewma
        - cornish_fisher (parametric ajusté pour skew/kurtosis)
        - garch (si librairie arch disponible)
    """
    losses = -train_window  # pertes positives
    if method == 'historical':
        return float(np.percentile(losses, confidence * 100))
    mean = train_window.mean()
    std = train_window.std()
    if method == 'parametric':
        z = stats.norm.ppf(confidence)
        return float(-mean + z * std)
    if method == 'ewma':
        # EWMA variance
        lam = 0.94
        ewma_var = 0.0
        for r in train_window[::-1]:
            ewma_var = lam * ewma_var + (1-lam) * r**2
        return float(stats.norm.ppf(confidence) * np.sqrt(ewma_var))
    if method == 'cornish_fisher':
        skew = train_window.skew()
        kurt_excess = train_window.kurtosis() - 3
        z = stats.norm.ppf(confidence)
        z_cf = _cornish_fisher_adjusted_z(z, skew, kurt_excess)
        return float(-mean + z_cf * std)
    if method == 'garch':
        try:
            from arch import arch_model  # type: ignore
            am = arch_model(train_window * 100, vol='Garch', p=1, q=1, dist='normal')
            res = am.fit(disp='off')
            forecast = res.forecast(horizon=1)
            sigma = float(forecast.variance.iloc[-1,0]) ** 0.5 / 100.0
            z = stats.norm.ppf(confidence)
            return float(-mean + z * sigma)
        except Exception as e:
            logger.warning(f"GARCH failed ({e}), fallback EWMA")
            return _compute_var(train_window, confidence, 'ewma')
    raise ValueError(f"Unknown VaR method: {method}")


def backtest_multi_methods(
    returns: pd.Series,
    methods: Optional[list] = None,
    window: int = 250,
    confidence: float = 0.95
) -> Dict[str, Dict]:
    """Backtest simultané multi-méthodes pour comparaison.

    Args:
        returns: Série de rendements
        methods: Liste méthodes (défaut toutes)
        window: Fenêtre estimation
        confidence: Niveau de confiance

    Returns:
        Dict mapping méthode -> résultats (incluant violation_rate)
    """
    if methods is None:
        methods = ['historical', 'parametric', 'ewma', 'cornish_fisher', 'garch']
    results = {}
    for method in methods:
        var_forecasts = []
        test_returns = []
        for i in range(window, len(returns)):
            train = returns.iloc[i-window:i]
            var_val = _compute_var(train, confidence, method)
            var_forecasts.append(var_val)
            test_returns.append(returns.iloc[i])
        var_series = pd.Series(var_forecasts, index=returns.index[window:])
        test_series = pd.Series(test_returns, index=var_series.index)
        backtester = VaRBacktester(test_series, var_series, confidence)
        res = backtester.run_all_tests()
        res['method'] = method
        res['forecasts'] = var_series
        results[method] = res
    return results


def backtest_rolling_var(
    returns: pd.Series,
    window: int = 250,
    horizon: int = 1,
    confidence: float = 0.95,
    method: str = 'historical'
) -> Dict:
    """
    Backtest VaR avec rolling window (out-of-sample).
    
    Args:
        returns: Series de rendements
        window: Taille fenêtre d'estimation (jours)
        horizon: Horizon forecast (jours)
        confidence: Niveau de confiance
        method: 'historical', 'parametric', 'ewma'
    
    Returns:
        Dict avec forecasts et résultats backtests
    
    Example:
        >>> results = backtest_rolling_var(returns, window=250)
        >>> print(results['backtester'].traffic_light_test())
    """
    logger.info(f"Running rolling VaR backtest: window={window}, method={method}")
    
    var_forecasts = []
    test_returns = []
    
    for i in range(window, len(returns) - horizon + 1):
        train_window = returns.iloc[i-window:i]
        
        # Calculer VaR selon méthode
        if method == 'historical':
            var = float(np.percentile(-train_window, confidence * 100))
        elif method == 'parametric':
            mean = train_window.mean()
            std = train_window.std()
            var = float(-mean + stats.norm.ppf(confidence) * std)
        elif method == 'ewma':
            # EWMA volatility (RiskMetrics lambda=0.94)
            ewma_var = train_window.ewm(span=75, adjust=False).var().iloc[-1]
            var = float(stats.norm.ppf(confidence) * np.sqrt(ewma_var))
        else:
            raise ValueError(f"Unknown method: {method}")
        
        var_forecasts.append(var)
        test_returns.append(returns.iloc[i])
    
    var_forecasts = pd.Series(var_forecasts, index=returns.index[window:len(returns)-horizon+1])
    test_returns = pd.Series(test_returns, index=var_forecasts.index)
    
    # Run backtests
    backtester = VaRBacktester(test_returns, var_forecasts, confidence)
    results = backtester.run_all_tests()
    
    results['forecasts'] = var_forecasts
    results['test_returns'] = test_returns
    results['backtester'] = backtester
    
    return results

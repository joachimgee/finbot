"""
Advanced Risk Metrics Module.

Fournit des mesures de risque avancées pour portfolio analysis, au-delà des
métriques basiques (VaR, CVaR) déjà présentes dans portfolio/metrics.py.

Basé sur Riskfolio-Lib et recherches académiques (AFML, Modern Portfolio Theory).

Fonctionnalités :
- Entropic Value at Risk (EVaR)
- Relativistic Value at Risk (RLVaR)
- Worst Realization (Minimax)
- Tail Gini (TG)
- Range-based measures (VaR Range, CVaR Range)
- Downside measures (Semi-variance, Semi-kurtosis)
- Risk decomposition (marginal contribution)

Note : Ce module complète (ne duplique pas) portfolio/metrics.py qui contient VaR, CVaR basiques.
"""

from typing import Dict, Optional, Union
import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import minimize_scalar

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


def calculate_evar(
    returns: pd.Series,
    confidence: float = 0.95,
    z: float = None
) -> float:
    """
    Entropic Value at Risk (EVaR).
    
    EVaR est une mesure de risque cohérente qui généralise CVaR. Plus sensible
    aux pertes extrêmes que CVaR grâce à une pondération exponentielle.
    
    Formule (Ahmadi-Javid 2012):
        EVaR_α(X) = inf_z { z + (1/α) * ln(E[exp((X-z)/α)]) }
    
    Args:
        returns: Série de rendements (négatif = perte)
        confidence: Niveau de confiance (0.95 = 95%)
        z: Paramètre d'aversion au risque (si None, optimisé automatiquement)
    
    Returns:
        EVaR (valeur positive représentant perte potentielle)
    
    Example:
        >>> returns = pd.Series([-0.02, 0.01, -0.05, 0.03, -0.01])
        >>> evar_95 = calculate_evar(returns, confidence=0.95)
        >>> print(f"EVaR 95%: {evar_95:.4f}")
    """
    if returns.empty:
        logger.warning("Empty returns, returning 0.0")
        return 0.0
    
    alpha = 1 - confidence
    losses = -returns.values  # Convertir en pertes positives
    
    # Si z non fourni, optimiser
    if z is None:
        z = np.std(losses)  # Heuristique initiale
    
    def evar_objective(z_param):
        """Fonction à minimiser pour EVaR."""
        # EVaR_z = z + (1/alpha) * ln(E[exp((L - z)/alpha)])
        scaled_losses = (losses - z_param) / alpha
        # Clip pour stabilité numérique
        scaled_losses = np.clip(scaled_losses, -20, 20)
        exp_term = np.mean(np.exp(scaled_losses))
        return z_param + alpha * np.log(max(exp_term, 1e-10))
    
    # Optimisation
    result = minimize_scalar(
        evar_objective,
        bounds=(losses.min(), losses.max()),
        method='bounded'
    )
    
    evar_value = result.fun if result.success else losses.mean()
    
    logger.debug(f"EVaR {confidence*100:.0f}% calculated: {evar_value:.6f}")
    return float(max(0.0, evar_value))


def calculate_rlvar(
    returns: pd.Series,
    confidence: float = 0.95,
    kappa: float = 0.3
) -> float:
    """
    Relativistic Value at Risk (RLVaR).
    
    RLVaR utilise une transformation hyperbolique (cosh) pour capturer le risque
    extrême tout en restant computationnellement tractable.
    
    Formule (Huang et al. 2021):
        RLVaR_α,κ = inf_θ { θ + κ * ln((1/α) * E[cosh((L - θ)/κ)]) }
    
    Args:
        returns: Série de rendements
        confidence: Niveau de confiance
        kappa: Paramètre d'aversion au risque (contrôle sensibilité)
    
    Returns:
        RLVaR (valeur positive)
    
    Example:
        >>> rlvar = calculate_rlvar(returns, confidence=0.95, kappa=0.3)
    """
    if returns.empty:
        return 0.0
    
    alpha = 1 - confidence
    losses = -returns.values
    
    def rlvar_objective(theta):
        """Fonction à minimiser pour RLVaR."""
        scaled = (losses - theta) / kappa
        # Clip pour stabilité numérique
        scaled = np.clip(scaled, -20, 20)
        cosh_term = np.mean(np.cosh(scaled))
        return theta + kappa * np.log(max(cosh_term / alpha, 1e-10))
    
    result = minimize_scalar(
        rlvar_objective,
        bounds=(losses.min(), losses.max()),
        method='bounded'
    )
    
    rlvar_value = result.fun if result.success else losses.mean()
    
    logger.debug(f"RLVaR {confidence*100:.0f}% calculated: {rlvar_value:.6f}")
    return float(max(0.0, rlvar_value))


def calculate_worst_realization(
    returns: pd.Series,
) -> float:
    """
    Worst Realization (WR) - Minimax criterion.
    
    Mesure de risque la plus conservative : la pire perte observée.
    Équivalent à VaR avec confidence=1.0.
    
    Args:
        returns: Série de rendements
    
    Returns:
        Pire perte observée (valeur positive)
    
    Example:
        >>> wr = calculate_worst_realization(returns)
        >>> print(f"Worst case loss: {wr:.2%}")
    """
    if returns.empty:
        return 0.0
    
    worst_loss = float(-returns.min())  # Plus grosse perte (négatif → positif)
    
    logger.debug(f"Worst Realization: {worst_loss:.6f}")
    return max(0.0, worst_loss)


def calculate_tail_gini(
    returns: pd.Series,
    confidence: float = 0.95
) -> float:
    """
    Tail Gini (TG) - Mesure de dispersion dans la queue de distribution.
    
    Tail Gini évalue l'inégalité des pertes dans la queue (au-delà du VaR).
    Un TG élevé indique des pertes très dispersées dans la queue.
    
    Formule:
        TG_α = E[|L_i - L_j|] pour L_i, L_j > VaR_α
    
    Args:
        returns: Série de rendements
        confidence: Niveau de confiance pour définir la queue
    
    Returns:
        Tail Gini coefficient (valeur positive)
    
    Example:
        >>> tg = calculate_tail_gini(returns, confidence=0.95)
    """
    if returns.empty or len(returns) < 2:
        return 0.0
    
    alpha = 1 - confidence
    losses = -returns.values
    
    # VaR threshold
    var_threshold = np.percentile(losses, confidence * 100)
    
    # Pertes dans la queue
    tail_losses = losses[losses >= var_threshold]
    
    if len(tail_losses) < 2:
        return 0.0
    
    # Calcul Gini : moyenne des différences absolues
    n = len(tail_losses)
    gini_sum = 0.0
    for i in range(n):
        for j in range(i+1, n):
            gini_sum += abs(tail_losses[i] - tail_losses[j])
    
    # Normaliser
    tail_gini = gini_sum / (n * (n - 1) / 2) if n > 1 else 0.0
    
    logger.debug(f"Tail Gini {confidence*100:.0f}% calculated: {tail_gini:.6f}")
    return float(tail_gini)


def calculate_var_range(
    returns: pd.Series,
    confidence_low: float = 0.90,
    confidence_high: float = 0.99
) -> float:
    """
    VaR Range - Écart entre deux niveaux de VaR.
    
    Mesure la sensibilité du risque aux variations de confiance.
    Un range élevé indique une queue de distribution épaisse (fat tail).
    
    Args:
        returns: Série de rendements
        confidence_low: Niveau bas (ex: 90%)
        confidence_high: Niveau haut (ex: 99%)
    
    Returns:
        VaR range (différence entre VaR_high et VaR_low)
    
    Example:
        >>> var_range = calculate_var_range(returns, 0.90, 0.99)
        >>> print(f"VaR sensitivity: {var_range:.4f}")
    """
    if returns.empty:
        return 0.0
    
    losses = -returns.values
    
    var_low = np.percentile(losses, confidence_low * 100)
    var_high = np.percentile(losses, confidence_high * 100)
    
    var_range = var_high - var_low
    
    logger.debug(f"VaR Range [{confidence_low*100:.0f}%-{confidence_high*100:.0f}%]: {var_range:.6f}")
    return float(max(0.0, var_range))


def calculate_cvar_range(
    returns: pd.Series,
    confidence_low: float = 0.90,
    confidence_high: float = 0.99
) -> float:
    """
    CVaR Range - Écart entre deux niveaux de CVaR.
    
    Similaire à VaR Range mais pour CVaR (Expected Shortfall).
    Mesure la sensibilité du risque de queue moyen.
    
    Args:
        returns: Série de rendements
        confidence_low: Niveau bas
        confidence_high: Niveau haut
    
    Returns:
        CVaR range
    
    Example:
        >>> cvar_range = calculate_cvar_range(returns, 0.90, 0.99)
    """
    if returns.empty:
        return 0.0
    
    losses = -returns.values
    
    # CVaR low
    var_low = np.percentile(losses, confidence_low * 100)
    tail_low = losses[losses >= var_low]
    cvar_low = tail_low.mean() if len(tail_low) > 0 else var_low
    
    # CVaR high
    var_high = np.percentile(losses, confidence_high * 100)
    tail_high = losses[losses >= var_high]
    cvar_high = tail_high.mean() if len(tail_high) > 0 else var_high
    
    cvar_range = cvar_high - cvar_low
    
    logger.debug(f"CVaR Range [{confidence_low*100:.0f}%-{confidence_high*100:.0f}%]: {cvar_range:.6f}")
    return float(max(0.0, cvar_range))


def calculate_semi_variance(
    returns: pd.Series,
    target_return: float = 0.0
) -> float:
    """
    Semi-Variance (Downside Variance) - Variance des rendements négatifs.
    
    Mesure uniquement la variabilité des pertes (downside), ignorant les gains.
    Utilisé dans le Sortino Ratio.
    
    Args:
        returns: Série de rendements
        target_return: Seuil de rendement minimum acceptable (MAR)
    
    Returns:
        Semi-variance (carré de downside deviation)
    
    Example:
        >>> semi_var = calculate_semi_variance(returns, target_return=0.0)
    """
    if returns.empty:
        return 0.0
    
    downside_returns = returns[returns < target_return] - target_return
    
    if len(downside_returns) == 0:
        return 0.0
    
    semi_var = float((downside_returns ** 2).mean())
    
    logger.debug(f"Semi-Variance (target={target_return}): {semi_var:.6f}")
    return semi_var


def calculate_downside_deviation(
    returns: pd.Series,
    target_return: float = 0.0
) -> float:
    """
    Downside Deviation - Racine carrée de la semi-variance.
    
    Args:
        returns: Série de rendements
        target_return: Seuil MAR
    
    Returns:
        Downside deviation
    
    Example:
        >>> dd = calculate_downside_deviation(returns)
    """
    semi_var = calculate_semi_variance(returns, target_return)
    return float(np.sqrt(semi_var))


def calculate_semi_kurtosis(
    returns: pd.Series,
    target_return: float = 0.0
) -> float:
    """
    Semi-Kurtosis - Kurtosis des rendements négatifs.
    
    Mesure l'épaisseur de la queue de la distribution downside.
    Un SKT élevé indique un risque de pertes extrêmes.
    
    Args:
        returns: Série de rendements
        target_return: Seuil MAR
    
    Returns:
        Semi-kurtosis (> 0 = queue épaisse)
    
    Example:
        >>> skt = calculate_semi_kurtosis(returns)
        >>> print(f"Downside tail thickness: {skt:.2f}")
    """
    if returns.empty:
        return 0.0
    
    downside_returns = returns[returns < target_return]
    
    if len(downside_returns) < 4:
        return 0.0
    
    # Kurtosis de Fisher (excess kurtosis, normal = 0)
    kurt = float(stats.kurtosis(downside_returns, fisher=True))
    
    logger.debug(f"Semi-Kurtosis: {kurt:.6f}")
    return kurt


def calculate_ulcer_index(
    equity_curve: pd.Series,
) -> float:
    """
    Ulcer Index - Mesure de profondeur et durée des drawdowns.
    
    UI pénalise à la fois la profondeur et la durée des drawdowns.
    Plus élevé = plus de "douleur" pour l'investisseur.
    
    Formule (Peter Martin 1987):
        UI = sqrt(mean(DD²)) où DD = drawdown %
    
    Args:
        equity_curve: Série de valeurs d'equity
    
    Returns:
        Ulcer Index (%)
    
    Example:
        >>> ui = calculate_ulcer_index(equity_curve)
        >>> print(f"Ulcer Index: {ui:.2%}")
    """
    if equity_curve.empty or len(equity_curve) < 2:
        return 0.0
    
    # Calcul running maximum
    running_max = equity_curve.expanding().max()
    
    # Drawdown en % depuis peak
    drawdown_pct = (equity_curve - running_max) / running_max
    
    # Ulcer Index = RMS des drawdowns
    ulcer = float(np.sqrt((drawdown_pct ** 2).mean()))
    
    logger.debug(f"Ulcer Index calculated: {ulcer:.6f}")
    return abs(ulcer)


def calculate_all_advanced_risk_metrics(
    returns: pd.Series,
    equity_curve: Optional[pd.Series] = None,
    confidence: float = 0.95
) -> Dict[str, float]:
    """
    Calcule toutes les métriques de risque avancées en un seul appel.
    
    Args:
        returns: Série de rendements quotidiens
        equity_curve: Série d'equity (optionnel, pour Ulcer Index)
        confidence: Niveau de confiance (défaut 95%)
    
    Returns:
        Dict avec toutes les métriques calculées
    
    Example:
        >>> metrics = calculate_all_advanced_risk_metrics(returns, equity_curve)
        >>> print(f"EVaR: {metrics['evar']:.4f}")
        >>> print(f"Worst Case: {metrics['worst_realization']:.4f}")
    """
    metrics = {}
    
    try:
        # Entropic & Relativistic VaR
        metrics['evar'] = calculate_evar(returns, confidence)
        metrics['rlvar'] = calculate_rlvar(returns, confidence)
        
        # Worst case & Tail measures
        metrics['worst_realization'] = calculate_worst_realization(returns)
        metrics['tail_gini'] = calculate_tail_gini(returns, confidence)
        
        # Range measures
        metrics['var_range'] = calculate_var_range(returns, 0.90, 0.99)
        metrics['cvar_range'] = calculate_cvar_range(returns, 0.90, 0.99)
        
        # Downside measures
        metrics['semi_variance'] = calculate_semi_variance(returns)
        metrics['downside_deviation'] = calculate_downside_deviation(returns)
        metrics['semi_kurtosis'] = calculate_semi_kurtosis(returns)
        
        # Ulcer Index (si equity_curve fourni)
        if equity_curve is not None and not equity_curve.empty:
            metrics['ulcer_index'] = calculate_ulcer_index(equity_curve)
        else:
            metrics['ulcer_index'] = 0.0
        
        logger.info(f"Calculated {len(metrics)} advanced risk metrics")
        
    except Exception as e:
        logger.error(f"Error calculating advanced risk metrics: {e}")
        # Retourner dict avec valeurs 0.0 en cas d'erreur
        metrics = {k: 0.0 for k in [
            'evar', 'rlvar', 'worst_realization', 'tail_gini',
            'var_range', 'cvar_range', 'semi_variance',
            'downside_deviation', 'semi_kurtosis', 'ulcer_index'
        ]}
    
    return metrics


def compare_risk_profiles(
    returns_a: pd.Series,
    returns_b: pd.Series,
    equity_a: Optional[pd.Series] = None,
    equity_b: Optional[pd.Series] = None,
    labels: tuple = ('Strategy A', 'Strategy B')
) -> pd.DataFrame:
    """
    Compare les profils de risque de deux stratégies.
    
    Args:
        returns_a: Returns stratégie A
        returns_b: Returns stratégie B
        equity_a: Equity curve A (optionnel)
        equity_b: Equity curve B (optionnel)
        labels: Noms des stratégies
    
    Returns:
        DataFrame comparatif avec toutes les métriques
    
    Example:
        >>> comparison = compare_risk_profiles(returns_strat1, returns_strat2)
        >>> print(comparison)
    """
    metrics_a = calculate_all_advanced_risk_metrics(returns_a, equity_a)
    metrics_b = calculate_all_advanced_risk_metrics(returns_b, equity_b)
    
    df = pd.DataFrame({
        labels[0]: metrics_a,
        labels[1]: metrics_b
    })
    
    # Ajouter colonne différence
    df['Difference'] = df[labels[1]] - df[labels[0]]
    df['Difference %'] = (df['Difference'] / df[labels[0]].replace(0, np.nan)) * 100
    
    logger.info(f"Risk profile comparison completed for {labels[0]} vs {labels[1]}")
    
    return df

"""
Module de calcul de métriques avancées de performance pour backtesting.

Ce module fournit des fonctions pour calculer les métriques clés de performance
de stratégies de trading (Sharpe, Sortino, Calmar, Max Drawdown, Win Rate, etc.)
et générer des rapports formatés pour analyse comparative.

Classes:
    Aucune

Functions:
    calculate_sharpe_ratio: Calcule le Sharpe Ratio annualisé
    calculate_sortino_ratio: Calcule le Sortino Ratio (downside deviation)
    calculate_calmar_ratio: Calcule le Calmar Ratio (return/max_dd)
    calculate_max_drawdown: Calcule le max drawdown % et durée
    calculate_win_rate: Calcule le % de trades gagnants
    calculate_profit_factor: Calcule le Profit Factor
    calculate_avg_trade_duration: Calcule la durée moyenne des trades
    calculate_exposure_time: Calcule le % temps en position
    calculate_all_metrics: Calcule toutes les métriques en 1 appel
    format_metrics_report: Formate les métriques en DataFrame
    compare_strategies: Compare plusieurs stratégies côte à côte
    export_metrics_json: Export métriques en JSON
    export_metrics_csv: Export DataFrame métriques en CSV

Typical usage example:
    >>> returns = pd.Series([0.01, -0.02, 0.03, ...])
    >>> equity = pd.Series([100000, 101000, 98980, ...])
    >>> trades = pd.DataFrame({'PnL': [100, -50, 200], ...})
    >>> metrics = calculate_all_metrics(returns, equity, trades)
    >>> report = format_metrics_report(metrics, "MyStrategy")
"""

from typing import Dict, Any, Optional
import numpy as np
import pandas as pd
import json
from pathlib import Path

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


def calculate_sharpe_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252
) -> float:
    """
    Calcule le Sharpe Ratio annualisé.
    
    Le Sharpe Ratio mesure le rendement excédentaire par unité de risque total.
    Un ratio > 1 est considéré bon, > 2 excellent, > 3 exceptionnel.
    
    Args:
        returns: Series de returns quotidiens (fractionnels, ex: 0.01 = 1%)
        risk_free_rate: Taux sans risque annuel (default 0.0)
        periods_per_year: Nombre de périodes par an (252=daily, 52=weekly, 12=monthly)
    
    Returns:
        Sharpe ratio annualisé (float). NaN si volatilité nulle.
    
    Raises:
        ValueError: Si returns est vide ou periods_per_year invalide
    """
    if returns.empty:
        raise ValueError("Returns series cannot be empty")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")
    
    # Convertir risk_free_rate annuel en rate par période
    rf_per_period = risk_free_rate / periods_per_year
    
    # Calcul excess returns
    excess_returns = returns - rf_per_period
    
    # Calcul mean et std
    mean_excess = excess_returns.mean()
    std_excess = excess_returns.std(ddof=1)
    
    # Check pour volatilité nulle (avec tolérance numérique)
    if np.isclose(std_excess, 0.0) or np.isnan(std_excess):
        logger.warning("Zero volatility detected, returning NaN for Sharpe Ratio")
        return np.nan
    
    # Annualiser
    sharpe = (mean_excess / std_excess) * np.sqrt(periods_per_year)
    
    logger.debug(f"Sharpe Ratio calculated: {sharpe:.4f}")
    return float(sharpe)


def calculate_sortino_ratio(
    returns: pd.Series,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252
) -> float:
    """
    Calcule le Sortino Ratio (pénalise seulement la volatilité négative).
    
    Le Sortino Ratio est similaire au Sharpe Ratio mais utilise la downside
    deviation au lieu de la volatilité totale, ce qui pénalise uniquement
    les pertes et non la volatilité haussière.
    
    Args:
        returns: Series de returns quotidiens (fractionnels)
        risk_free_rate: Taux sans risque annuel (default 0.0)
        periods_per_year: Nombre de périodes par an (252=daily, 52=weekly, 12=monthly)
    
    Returns:
        Sortino ratio annualisé (float). NaN si downside deviation nulle.
    
    Raises:
        ValueError: Si returns est vide ou periods_per_year invalide
    """
    if returns.empty:
        raise ValueError("Returns series cannot be empty")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")
    
    # Convertir risk_free_rate annuel en rate par période
    rf_per_period = risk_free_rate / periods_per_year
    
    # Calcul excess returns
    excess_returns = returns - rf_per_period
    mean_excess = excess_returns.mean()
    
    # Calcul downside deviation (seulement returns négatifs)
    downside_dev = _calculate_downside_deviation(excess_returns, target_return=0.0)
    
    # Check pour downside deviation nulle (avec tolérance numérique)
    if np.isclose(downside_dev, 0.0) or np.isnan(downside_dev):
        logger.warning("Zero downside deviation, returning NaN for Sortino Ratio")
        return np.nan
    
    # Annualiser
    sortino = (mean_excess / downside_dev) * np.sqrt(periods_per_year)
    
    logger.debug(f"Sortino Ratio calculated: {sortino:.4f}")
    return float(sortino)


def calculate_calmar_ratio(
    returns: pd.Series,
    equity_curve: pd.Series,
    periods_per_year: int = 252
) -> float:
    """
    Calcule le Calmar Ratio (return annuel / max drawdown absolu).
    
    Le Calmar Ratio mesure le rendement par unité de risque de drawdown.
    Plus le ratio est élevé, meilleure est la stratégie.
    
    Args:
        returns: Series de returns quotidiens (fractionnels)
        equity_curve: Series equity au cours du temps
        periods_per_year: Nombre de périodes par an (252=daily, 52=weekly, 12=monthly)
    
    Returns:
        Calmar ratio (float). NaN si max_dd est nul.
    
    Raises:
        ValueError: Si returns ou equity_curve est vide
    """
    if returns.empty or equity_curve.empty:
        raise ValueError("Returns and equity_curve cannot be empty")
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")
    
    # Calcul return annuel
    total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1
    num_periods = len(returns)
    annual_return = _annualize_return(total_return, num_periods, periods_per_year)
    
    # Calcul max drawdown
    max_dd_info = calculate_max_drawdown(equity_curve)
    max_dd_pct = abs(max_dd_info['max_dd_pct'])
    
    # Check pour max drawdown nul (avec tolérance numérique)
    if np.isclose(max_dd_pct, 0.0) or np.isnan(max_dd_pct):
        logger.warning("Zero max drawdown, returning NaN for Calmar Ratio")
        return np.nan
    
    calmar = annual_return / max_dd_pct
    
    logger.debug(f"Calmar Ratio calculated: {calmar:.4f}")
    return float(calmar)


def calculate_max_drawdown(equity_curve: pd.Series) -> Dict[str, Any]:
    """
    Calcule le max drawdown % et durée (peak-to-trough).
    
    Le max drawdown est la plus grande perte depuis un pic d'equity jusqu'au
    creux suivant, exprimée en pourcentage du pic.
    
    Args:
        equity_curve: Series equity au cours du temps (index = dates)
    
    Returns:
        Dict avec clés:
            - max_dd_pct (float): Max drawdown en % (négatif)
            - max_dd_duration_days (int): Durée du drawdown en jours
            - peak_date (pd.Timestamp or None): Date du pic
            - trough_date (pd.Timestamp or None): Date du creux
    
    Raises:
        ValueError: Si equity_curve est vide
    """
    if equity_curve.empty:
        raise ValueError("Equity curve cannot be empty")
    
    # Calcul running maximum (pic historique)
    running_max = equity_curve.expanding().max()
    
    # Calcul drawdown à chaque point
    drawdown = (equity_curve - running_max) / running_max
    
    # Trouver max drawdown
    max_dd_pct = drawdown.min()
    
    if pd.isna(max_dd_pct) or max_dd_pct == 0:
        logger.info("No drawdown detected (equity curve monotonic)")
        return {
            'max_dd_pct': 0.0,
            'max_dd_duration_days': 0,
            'peak_date': None,
            'trough_date': None
        }
    
    # Trouver le creux (trough)
    trough_idx = drawdown.idxmin()
    
    # Trouver le pic correspondant (dernier max avant le creux)
    peak_idx = running_max[:trough_idx].idxmax()
    
    # Calcul durée
    if isinstance(equity_curve.index, pd.DatetimeIndex):
        duration_days = (trough_idx - peak_idx).days
    else:
        # Si index n'est pas DatetimeIndex, compter les périodes
        duration_days = int(equity_curve.index.get_loc(trough_idx) - 
                           equity_curve.index.get_loc(peak_idx))
    
    result = {
        'max_dd_pct': float(max_dd_pct),
        'max_dd_duration_days': int(duration_days),
        'peak_date': peak_idx,
        'trough_date': trough_idx
    }
    
    logger.debug(f"Max Drawdown: {max_dd_pct*100:.2f}% over {duration_days} days")
    return result


def calculate_win_rate(trades_df: pd.DataFrame) -> float:
    """
    Calcule le % de trades gagnants.
    
    Args:
        trades_df: DataFrame trades avec colonne 'PnL'
    
    Returns:
        Win rate (0-100)
    
    Raises:
        ValueError: Si trades_df est vide ou manque colonne 'PnL'
    """
    if trades_df.empty:
        raise ValueError("Trades DataFrame cannot be empty")
    if 'PnL' not in trades_df.columns:
        raise ValueError("Trades DataFrame must have 'PnL' column")
    
    winning_trades = (trades_df['PnL'] > 0).sum()
    total_trades = len(trades_df)
    
    if total_trades == 0:
        return 0.0
    
    win_rate = (winning_trades / total_trades) * 100
    
    logger.debug(f"Win Rate: {win_rate:.2f}% ({winning_trades}/{total_trades})")
    return float(win_rate)


def calculate_profit_factor(trades_df: pd.DataFrame) -> float:
    """
    Calcule le Profit Factor (total profit / total loss).
    
    Un Profit Factor > 1 indique une stratégie profitable.
    PF = 2 signifie 2x plus de profits que de pertes.
    
    Args:
        trades_df: DataFrame trades avec colonne 'PnL'
    
    Returns:
        Profit factor (float). Inf si aucune perte, 0 si aucun profit.
    
    Raises:
        ValueError: Si trades_df est vide ou manque colonne 'PnL'
    """
    if trades_df.empty:
        raise ValueError("Trades DataFrame cannot be empty")
    if 'PnL' not in trades_df.columns:
        raise ValueError("Trades DataFrame must have 'PnL' column")
    
    total_profit = trades_df[trades_df['PnL'] > 0]['PnL'].sum()
    total_loss = abs(trades_df[trades_df['PnL'] < 0]['PnL'].sum())
    
    if total_loss == 0:
        if total_profit > 0:
            logger.warning("No losses detected, returning Inf for Profit Factor")
            return float('inf')
        else:
            return 0.0
    
    profit_factor = total_profit / total_loss
    
    logger.debug(f"Profit Factor: {profit_factor:.2f}")
    return float(profit_factor)


def calculate_avg_trade_duration(trades_df: pd.DataFrame) -> float:
    """
    Calcule la durée moyenne des trades en jours.
    
    Args:
        trades_df: DataFrame trades avec colonnes 'EntryTime' et 'ExitTime'
    
    Returns:
        Durée moyenne en jours (float)
    
    Raises:
        ValueError: Si trades_df est vide ou manque colonnes requises
    """
    if trades_df.empty:
        raise ValueError("Trades DataFrame cannot be empty")
    if 'EntryTime' not in trades_df.columns or 'ExitTime' not in trades_df.columns:
        raise ValueError("Trades DataFrame must have 'EntryTime' and 'ExitTime' columns")
    
    # Calcul durée pour chaque trade
    durations = (pd.to_datetime(trades_df['ExitTime']) - 
                 pd.to_datetime(trades_df['EntryTime']))
    
    # Convertir en jours
    avg_duration_days = durations.dt.total_seconds().mean() / (24 * 3600)
    
    logger.debug(f"Average Trade Duration: {avg_duration_days:.2f} days")
    return float(avg_duration_days)


def calculate_exposure_time(
    equity_curve: pd.Series,
    trades_df: pd.DataFrame
) -> float:
    """
    Calcule le % temps en position (exposure).
    
    L'exposure time est le pourcentage du temps total où la stratégie
    avait une position ouverte (long ou short).
    
    Args:
        equity_curve: Series equity au cours du temps (index = dates)
        trades_df: DataFrame trades avec colonnes 'EntryTime' et 'ExitTime'
    
    Returns:
        Exposure time en % (0-100)
    
    Raises:
        ValueError: Si equity_curve ou trades_df est vide
    """
    if equity_curve.empty:
        raise ValueError("Equity curve cannot be empty")
    if trades_df.empty:
        logger.warning("No trades, exposure time is 0%")
        return 0.0
    if 'EntryTime' not in trades_df.columns or 'ExitTime' not in trades_df.columns:
        raise ValueError("Trades DataFrame must have 'EntryTime' and 'ExitTime' columns")
    
    # Période totale
    total_time = equity_curve.index[-1] - equity_curve.index[0]
    
    # Calculer temps en position (somme des durées de trades)
    durations = (pd.to_datetime(trades_df['ExitTime']) - 
                 pd.to_datetime(trades_df['EntryTime']))
    total_exposure = durations.sum()
    
    # Convertir en pourcentage
    if isinstance(total_time, pd.Timedelta):
        exposure_pct = (total_exposure.total_seconds() / total_time.total_seconds()) * 100
    else:
        # Si index n'est pas DatetimeIndex, utiliser nombre de périodes
        total_periods = len(equity_curve)
        exposure_periods = len(trades_df)  # Approximation simplifiée
        exposure_pct = (exposure_periods / total_periods) * 100
    
    # Limiter à 100% max
    exposure_pct = min(exposure_pct, 100.0)
    
    logger.debug(f"Exposure Time: {exposure_pct:.2f}%")
    return float(exposure_pct)


def calculate_all_metrics(
    returns: pd.Series,
    equity_curve: pd.Series,
    trades_df: pd.DataFrame,
    risk_free_rate: float = 0.0,
    periods_per_year: int = 252
) -> Dict[str, float]:
    """
    Calcule TOUTES les métriques en 1 appel.
    
    Cette fonction centralise le calcul de toutes les métriques de performance
    pour éviter la duplication de code et garantir la cohérence.
    
    Args:
        returns: Series de returns quotidiens (fractionnels)
        equity_curve: Series equity au cours du temps
        trades_df: DataFrame trades avec colonnes 'PnL', 'EntryTime', 'ExitTime'
        risk_free_rate: Taux sans risque annuel (default 0.0)
        periods_per_year: Nombre de périodes par an (default 252)
    
    Returns:
        Dict contenant toutes les métriques:
            - sharpe_ratio
            - sortino_ratio
            - calmar_ratio
            - max_drawdown_pct
            - max_drawdown_duration_days
            - win_rate_pct
            - profit_factor
            - avg_trade_duration_days
            - exposure_time_pct
            - total_return_pct
            - annual_return_pct
            - total_trades
    
    Raises:
        ValueError: Si inputs invalides
    """
    logger.info("Calculating all performance metrics...")
    
    metrics = {}
    
    # Métriques basées sur returns
    try:
        metrics['sharpe_ratio'] = calculate_sharpe_ratio(
            returns, risk_free_rate, periods_per_year
        )
    except Exception as e:
        logger.error(f"Error calculating Sharpe Ratio: {e}")
        metrics['sharpe_ratio'] = np.nan
    
    try:
        metrics['sortino_ratio'] = calculate_sortino_ratio(
            returns, risk_free_rate, periods_per_year
        )
    except Exception as e:
        logger.error(f"Error calculating Sortino Ratio: {e}")
        metrics['sortino_ratio'] = np.nan
    
    try:
        metrics['calmar_ratio'] = calculate_calmar_ratio(
            returns, equity_curve, periods_per_year
        )
    except Exception as e:
        logger.error(f"Error calculating Calmar Ratio: {e}")
        metrics['calmar_ratio'] = np.nan
    
    # Max Drawdown
    try:
        max_dd_info = calculate_max_drawdown(equity_curve)
        metrics['max_drawdown_pct'] = max_dd_info['max_dd_pct'] * 100  # Convert to %
        metrics['max_drawdown_duration_days'] = max_dd_info['max_dd_duration_days']
    except Exception as e:
        logger.error(f"Error calculating Max Drawdown: {e}")
        metrics['max_drawdown_pct'] = np.nan
        metrics['max_drawdown_duration_days'] = np.nan
    
    # Métriques basées sur trades
    try:
        metrics['win_rate_pct'] = calculate_win_rate(trades_df)
    except Exception as e:
        logger.error(f"Error calculating Win Rate: {e}")
        metrics['win_rate_pct'] = np.nan
    
    try:
        metrics['profit_factor'] = calculate_profit_factor(trades_df)
    except Exception as e:
        logger.error(f"Error calculating Profit Factor: {e}")
        metrics['profit_factor'] = np.nan
    
    try:
        metrics['avg_trade_duration_days'] = calculate_avg_trade_duration(trades_df)
    except Exception as e:
        logger.error(f"Error calculating Avg Trade Duration: {e}")
        metrics['avg_trade_duration_days'] = np.nan
    
    try:
        metrics['exposure_time_pct'] = calculate_exposure_time(equity_curve, trades_df)
    except Exception as e:
        logger.error(f"Error calculating Exposure Time: {e}")
        metrics['exposure_time_pct'] = np.nan
    
    # Returns totaux et annualisés
    try:
        total_return = (equity_curve.iloc[-1] / equity_curve.iloc[0]) - 1
        metrics['total_return_pct'] = total_return * 100
        
        num_periods = len(returns)
        annual_return = _annualize_return(total_return, num_periods, periods_per_year)
        metrics['annual_return_pct'] = annual_return * 100
    except Exception as e:
        logger.error(f"Error calculating returns: {e}")
        metrics['total_return_pct'] = np.nan
        metrics['annual_return_pct'] = np.nan
    
    # Nombre de trades
    metrics['total_trades'] = len(trades_df)
    
    logger.info(f"All metrics calculated successfully: {len(metrics)} metrics")
    return metrics


def format_metrics_report(
    metrics: Dict[str, float],
    strategy_name: str = "Strategy"
) -> pd.DataFrame:
    """
    Formate les métriques en DataFrame lisible pour affichage.
    
    Args:
        metrics: Dict contenant les métriques
        strategy_name: Nom de la stratégie (default "Strategy")
    
    Returns:
        DataFrame avec colonnes 'Metric' et 'Value'
    """
    # Créer DataFrame avec noms formatés
    formatted_metrics = {
        'sharpe_ratio': 'Sharpe Ratio',
        'sortino_ratio': 'Sortino Ratio',
        'calmar_ratio': 'Calmar Ratio',
        'max_drawdown_pct': 'Max Drawdown (%)',
        'max_drawdown_duration_days': 'Max DD Duration (days)',
        'win_rate_pct': 'Win Rate (%)',
        'profit_factor': 'Profit Factor',
        'avg_trade_duration_days': 'Avg Trade Duration (days)',
        'exposure_time_pct': 'Exposure Time (%)',
        'total_return_pct': 'Total Return (%)',
        'annual_return_pct': 'Annual Return (%)',
        'total_trades': 'Total Trades'
    }
    
    data = []
    for key, label in formatted_metrics.items():
        if key in metrics:
            value = metrics[key]
            # Formatage selon le type de métrique
            if key in ['total_trades', 'max_drawdown_duration_days']:
                formatted_value = f"{int(value)}" if not np.isnan(value) else "N/A"
            elif key == 'profit_factor':
                if np.isinf(value):
                    formatted_value = "∞"
                elif np.isnan(value):
                    formatted_value = "N/A"
                else:
                    formatted_value = f"{value:.2f}"
            else:
                formatted_value = f"{value:.2f}" if not np.isnan(value) else "N/A"
            
            data.append({'Metric': label, 'Value': formatted_value})
    
    df = pd.DataFrame(data)
    
    logger.info(f"Formatted metrics report for strategy: {strategy_name}")
    return df


def compare_strategies(strategies_results: Dict[str, Dict]) -> pd.DataFrame:
    """
    Compare plusieurs stratégies côte à côte.
    
    Args:
        strategies_results: Dict avec structure:
            {'Strategy1': metrics_dict, 'Strategy2': metrics_dict, ...}
    
    Returns:
        DataFrame comparative (metrics en lignes, strategies en colonnes)
    
    Raises:
        ValueError: Si strategies_results est vide
    """
    if not strategies_results:
        raise ValueError("strategies_results cannot be empty")
    
    # Créer DataFrame avec stratégies en colonnes
    comparison_df = pd.DataFrame(strategies_results).T
    
    # Ordonner colonnes dans un ordre logique
    column_order = [
        'total_return_pct', 'annual_return_pct', 'sharpe_ratio', 'sortino_ratio',
        'calmar_ratio', 'max_drawdown_pct', 'max_drawdown_duration_days',
        'win_rate_pct', 'profit_factor', 'avg_trade_duration_days',
        'exposure_time_pct', 'total_trades'
    ]
    
    # Réordonner colonnes (garder seulement celles qui existent)
    existing_cols = [col for col in column_order if col in comparison_df.columns]
    comparison_df = comparison_df[existing_cols]
    
    logger.info(f"Compared {len(strategies_results)} strategies")
    return comparison_df


def export_metrics_json(metrics: Dict, filepath: str) -> None:
    """
    Export métriques en JSON avec gestion de la sérialisation pandas.
    
    Args:
        metrics: Dict contenant les métriques
        filepath: Chemin du fichier JSON de sortie
    
    Raises:
        IOError: Si échec écriture fichier
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    # Convertir types numpy/pandas en types Python natifs
    serializable_metrics = {}
    for key, value in metrics.items():
        if isinstance(value, (np.integer, np.floating)):
            serializable_metrics[key] = float(value) if not np.isnan(value) else None
        elif isinstance(value, pd.Timestamp):
            serializable_metrics[key] = value.isoformat()
        elif pd.isna(value):
            serializable_metrics[key] = None
        elif np.isinf(value):
            serializable_metrics[key] = "Infinity" if value > 0 else "-Infinity"
        else:
            serializable_metrics[key] = value
    
    try:
        with open(filepath, 'w') as f:
            json.dump(serializable_metrics, f, indent=2)
        logger.info(f"Metrics exported to JSON: {filepath}")
    except Exception as e:
        logger.error(f"Failed to export metrics to JSON: {e}")
        raise IOError(f"Could not write to {filepath}: {e}")


def export_metrics_csv(metrics_df: pd.DataFrame, filepath: str) -> None:
    """
    Export DataFrame métriques en CSV.
    
    Args:
        metrics_df: DataFrame contenant les métriques
        filepath: Chemin du fichier CSV de sortie
    
    Raises:
        IOError: Si échec écriture fichier
    """
    filepath = Path(filepath)
    filepath.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        metrics_df.to_csv(filepath, index=True)
        logger.info(f"Metrics exported to CSV: {filepath}")
    except Exception as e:
        logger.error(f"Failed to export metrics to CSV: {e}")
        raise IOError(f"Could not write to {filepath}: {e}")


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _calculate_returns(equity_curve: pd.Series) -> pd.Series:
    """
    Calcule les returns à partir de l'equity curve.
    
    Args:
        equity_curve: Series equity au cours du temps
    
    Returns:
        Series de returns (pct_change)
    """
    returns = equity_curve.pct_change().fillna(0)
    return returns


def _annualize_return(
    total_return: float,
    num_periods: int,
    periods_per_year: int
) -> float:
    """
    Annualise un return total.
    
    Args:
        total_return: Return total sur la période (fractionnaire)
        num_periods: Nombre de périodes dans la série
        periods_per_year: Nombre de périodes par an (252, 52, 12, etc.)
    
    Returns:
        Return annualisé (fractionnaire)
    """
    if num_periods == 0:
        return 0.0
    
    years = num_periods / periods_per_year
    if years == 0:
        return 0.0
    
    # Formule: (1 + total_return)^(1/years) - 1
    annual_return = ((1 + total_return) ** (1 / years)) - 1
    return annual_return


def _calculate_downside_deviation(
    returns: pd.Series,
    target_return: float = 0.0
) -> float:
    """
    Calcule la downside deviation (volatilité des returns négatifs).
    
    La downside deviation mesure la volatilité seulement des returns
    inférieurs au target_return (généralement 0).
    
    Args:
        returns: Series de returns
        target_return: Return cible (default 0.0)
    
    Returns:
        Downside deviation (float)
    """
    # Filtrer seulement les returns < target
    downside_returns = returns[returns < target_return]
    
    if len(downside_returns) == 0:
        return 0.0
    
    # Calcul écart-type des returns négatifs
    downside_dev = downside_returns.std(ddof=1)
    
    return float(downside_dev)

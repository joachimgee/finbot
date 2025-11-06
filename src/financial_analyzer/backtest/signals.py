"""
Génération de signaux de trading pour le backtesting.

Ce module fournit des fonctions pour créer différents types de signaux
(crossover, threshold, ML predictions, etc.) et les combiner/valider
avant utilisation en backtesting.

Classes:
    SignalGenerator: Helper pour générer et stocker signaux

Functions:
    sma_crossover_signal: Signaux croisement SMA fast/slow
    rsi_threshold_signal: Signaux RSI oversold/overbought
    bollinger_breakout_signal: Signaux Bollinger Band breakout
    macd_signal: Signaux MACD crossover
    volume_signal: Signaux basés volume (momentum)
    ml_prediction_signal: Signaux de prédictions ML
    custom_rule_signal: Signaux règles custom (callable)
    aggregate_signals: Combine plusieurs signaux (AND/OR/VOTE)
    smooth_signal: Lisse les signaux (reduce noise)
    validate_signal: Valide format signal (index, values)
    apply_signal_to_backtest: Ajoute signal aux features pour backtest
    backtest_ready_signals: Prépare tous les signaux pour backtesting

Typical usage example:
    >>> from financial_analyzer.backtest.signals import SignalGenerator
    >>> gen = SignalGenerator(features_df)
    >>> rsi_sig = gen.generate_rsi_signal(lower=30, upper=70)
    >>> sma_sig = gen.generate_sma_crossover(fast=50, slow=200)
    >>> combined = gen.combine_signals({'RSI': rsi_sig, 'SMA': sma_sig}, method='vote')
"""

from typing import Dict, Callable, Optional, Union
import numpy as np
import pandas as pd
from functools import reduce

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class SignalGenerator:
    """
    Helper pour générer et stocker signaux de trading.
    
    Cette classe facilite la génération de multiples signaux à partir d'un
    DataFrame features et conserve un historique des signaux créés.
    
    Attributes:
        features: DataFrame features (OHLCV + indicators)
        signals: Dict stockant tous les signaux générés
    """
    
    def __init__(self, features: pd.DataFrame):
        """
        Initialise le générateur de signaux.
        
        Args:
            features: DataFrame features (output FeaturePipeline)
        
        Raises:
            ValueError: Si features est vide ou invalide
        """
        if features.empty:
            raise ValueError("Features DataFrame cannot be empty")
        if not isinstance(features.index, pd.DatetimeIndex):
            raise ValueError("Features must have DatetimeIndex")
        
        self.features = features
        self.signals: Dict[str, pd.Series] = {}
        
        logger.info(f"SignalGenerator initialized with {len(features)} rows")
    
    def generate_sma_crossover(
        self,
        fast: int = 50,
        slow: int = 200,
        name: str = 'SMA_Crossover'
    ) -> pd.Series:
        """
        Génère signaux croisement SMA fast/slow.
        
        Args:
            fast: Période SMA rapide
            slow: Période SMA lente
            name: Nom du signal
        
        Returns:
            Series signaux (1, 0, -1)
        """
        signal = sma_crossover_signal(self.features, fast, slow, name)
        self.signals[name] = signal
        logger.debug(f"Generated {name} signal")
        return signal
    
    def generate_rsi_signal(
        self,
        rsi_col: str = 'RSI_14',
        lower: float = 30,
        upper: float = 70,
        name: str = 'RSI_Signal'
    ) -> pd.Series:
        """
        Génère signaux RSI oversold/overbought.
        
        Args:
            rsi_col: Nom colonne RSI dans features
            lower: Seuil oversold (buy signal)
            upper: Seuil overbought (sell signal)
            name: Nom du signal
        
        Returns:
            Series signaux (1, 0, -1)
        """
        signal = rsi_threshold_signal(self.features, rsi_col, lower, upper, name)
        self.signals[name] = signal
        logger.debug(f"Generated {name} signal")
        return signal
    
    def generate_bollinger_signal(
        self,
        bb_upper_col: str = 'BB_Upper',
        bb_lower_col: str = 'BB_Lower',
        close_col: str = 'Close',
        name: str = 'BB_Signal'
    ) -> pd.Series:
        """
        Génère signaux Bollinger Band breakout.
        
        Args:
            bb_upper_col: Nom colonne BB upper
            bb_lower_col: Nom colonne BB lower
            close_col: Nom colonne Close
            name: Nom du signal
        
        Returns:
            Series signaux (1, 0, -1)
        """
        signal = bollinger_breakout_signal(
            self.features, bb_upper_col, bb_lower_col, close_col, name
        )
        self.signals[name] = signal
        logger.debug(f"Generated {name} signal")
        return signal
    
    def generate_macd_signal(
        self,
        macd_col: str = 'MACD',
        signal_col: str = 'MACD_Signal',
        name: str = 'MACD_Signal'
    ) -> pd.Series:
        """
        Génère signaux MACD crossover.
        
        Args:
            macd_col: Nom colonne MACD
            signal_col: Nom colonne Signal line
            name: Nom du signal
        
        Returns:
            Series signaux (1, 0, -1)
        """
        signal = macd_signal(self.features, macd_col, signal_col, name)
        self.signals[name] = signal
        logger.debug(f"Generated {name} signal")
        return signal
    
    def combine_signals(
        self,
        signals_dict: Dict[str, pd.Series],
        method: str = 'vote',
        weights: Optional[Dict[str, float]] = None
    ) -> pd.Series:
        """
        Combine plusieurs signaux en un seul.
        
        Args:
            signals_dict: Dict de signaux à combiner
            method: Méthode combinaison ('vote', 'and', 'or', 'weighted')
            weights: Poids pour method='weighted'
        
        Returns:
            Series signal combiné (1, 0, -1)
        """
        combined = aggregate_signals(signals_dict, method, weights)
        logger.info(f"Combined {len(signals_dict)} signals using {method} method")
        return combined
    
    def smooth_signals(
        self,
        signal: pd.Series,
        window: int = 3,
        method: str = 'majority'
    ) -> pd.Series:
        """
        Lisse un signal pour réduire noise.
        
        Args:
            signal: Series signal à lisser
            window: Taille fenêtre
            method: Méthode lissage ('majority', 'median', 'mean')
        
        Returns:
            Series signal lissé
        """
        smoothed = smooth_signal(signal, window, method)
        logger.debug(f"Smoothed signal with window={window}, method={method}")
        return smoothed
    
    def get_all_signals(self) -> Dict[str, pd.Series]:
        """
        Retourne tous les signaux générés.
        
        Returns:
            Dict avec tous les signaux
        """
        return self.signals.copy()


# ============================================================================
# SIGNAL GENERATION FUNCTIONS
# ============================================================================

def sma_crossover_signal(
    features: pd.DataFrame,
    fast_period: int = 50,
    slow_period: int = 200,
    name: str = 'SMA_Crossover'
) -> pd.Series:
    """
    Génère signaux croisement SMA fast/slow.
    
    Signal = 1 quand fast > slow (bullish)
    Signal = -1 quand fast < slow (bearish)
    Signal = 0 ailleurs
    
    Args:
        features: DataFrame features avec colonnes OHLCV
        fast_period: Période SMA rapide
        slow_period: Période SMA lente
        name: Nom du signal
    
    Returns:
        Series signaux (1, 0, -1) avec même index que features
    
    Raises:
        ValueError: Si features invalide ou colonnes manquantes
    """
    if features.empty:
        raise ValueError("Features DataFrame cannot be empty")
    if 'Close' not in features.columns:
        raise ValueError("Features must have 'Close' column")
    
    # Calculer SMAs si pas présentes
    sma_fast_col = f'SMA_{fast_period}'
    sma_slow_col = f'SMA_{slow_period}'
    
    if sma_fast_col not in features.columns:
        sma_fast = features['Close'].rolling(window=fast_period).mean()
    else:
        sma_fast = features[sma_fast_col]
    
    if sma_slow_col not in features.columns:
        sma_slow = features['Close'].rolling(window=slow_period).mean()
    else:
        sma_slow = features[sma_slow_col]
    
    # Générer signaux
    signal = pd.Series(0, index=features.index, dtype=int)
    signal[sma_fast > sma_slow] = 1
    signal[sma_fast < sma_slow] = -1
    
    signal.name = name
    
    logger.info(f"Generated {name}: {(signal == 1).sum()} buy, {(signal == -1).sum()} sell")
    return signal


def rsi_threshold_signal(
    features: pd.DataFrame,
    rsi_col: str = 'RSI_14',
    lower: float = 30,
    upper: float = 70,
    name: str = 'RSI_Signal'
) -> pd.Series:
    """
    Génère signaux RSI oversold/overbought.
    
    Signal = 1 quand RSI < lower (oversold, buy)
    Signal = -1 quand RSI > upper (overbought, sell)
    Signal = 0 ailleurs
    
    Args:
        features: DataFrame features avec colonne RSI
        rsi_col: Nom colonne RSI
        lower: Seuil oversold (default 30)
        upper: Seuil overbought (default 70)
        name: Nom du signal
    
    Returns:
        Series signaux (1, 0, -1)
    
    Raises:
        ValueError: Si colonne RSI manquante ou thresholds invalides
    """
    if features.empty:
        raise ValueError("Features DataFrame cannot be empty")
    if rsi_col not in features.columns:
        raise ValueError(f"Features must have '{rsi_col}' column")
    if lower >= upper:
        raise ValueError("Lower threshold must be < upper threshold")
    
    rsi = features[rsi_col]
    
    # Générer signaux
    signal = pd.Series(0, index=features.index, dtype=int)
    signal[rsi < lower] = 1   # Oversold -> Buy
    signal[rsi > upper] = -1  # Overbought -> Sell
    
    signal.name = name
    
    logger.info(f"Generated {name}: {(signal == 1).sum()} buy, {(signal == -1).sum()} sell")
    return signal


def bollinger_breakout_signal(
    features: pd.DataFrame,
    bb_upper_col: str = 'BB_Upper',
    bb_lower_col: str = 'BB_Lower',
    close_col: str = 'Close',
    name: str = 'BB_Signal'
) -> pd.Series:
    """
    Génère signaux Bollinger Band breakout.
    
    Signal = 1 quand Close > BB_Upper (breakout haut)
    Signal = -1 quand Close < BB_Lower (breakout bas)
    Signal = 0 ailleurs
    
    Args:
        features: DataFrame features avec BB bands
        bb_upper_col: Nom colonne BB upper
        bb_lower_col: Nom colonne BB lower
        close_col: Nom colonne Close
        name: Nom du signal
    
    Returns:
        Series signaux (1, 0, -1)
    
    Raises:
        ValueError: Si colonnes manquantes
    """
    if features.empty:
        raise ValueError("Features DataFrame cannot be empty")
    
    required_cols = [bb_upper_col, bb_lower_col, close_col]
    missing = [col for col in required_cols if col not in features.columns]
    if missing:
        raise ValueError(f"Features missing columns: {missing}")
    
    close = features[close_col]
    bb_upper = features[bb_upper_col]
    bb_lower = features[bb_lower_col]
    
    # Générer signaux
    signal = pd.Series(0, index=features.index, dtype=int)
    signal[close > bb_upper] = 1   # Breakout haut
    signal[close < bb_lower] = -1  # Breakout bas
    
    signal.name = name
    
    logger.info(f"Generated {name}: {(signal == 1).sum()} buy, {(signal == -1).sum()} sell")
    return signal


def macd_signal(
    features: pd.DataFrame,
    macd_col: str = 'MACD',
    signal_col: str = 'MACD_Signal',
    name: str = 'MACD_Signal'
) -> pd.Series:
    """
    Génère signaux MACD crossover.
    
    Signal = 1 quand MACD > Signal line
    Signal = -1 quand MACD < Signal line
    Signal = 0 ailleurs
    
    Args:
        features: DataFrame features avec MACD
        macd_col: Nom colonne MACD
        signal_col: Nom colonne Signal line
        name: Nom du signal
    
    Returns:
        Series signaux (1, 0, -1)
    
    Raises:
        ValueError: Si colonnes manquantes
    """
    if features.empty:
        raise ValueError("Features DataFrame cannot be empty")
    
    required_cols = [macd_col, signal_col]
    missing = [col for col in required_cols if col not in features.columns]
    if missing:
        raise ValueError(f"Features missing columns: {missing}")
    
    macd = features[macd_col]
    signal_line = features[signal_col]
    
    # Générer signaux
    signal = pd.Series(0, index=features.index, dtype=int)
    signal[macd > signal_line] = 1
    signal[macd < signal_line] = -1
    
    signal.name = name
    
    logger.info(f"Generated {name}: {(signal == 1).sum()} buy, {(signal == -1).sum()} sell")
    return signal


def volume_signal(
    features: pd.DataFrame,
    volume_col: str = 'Volume',
    volume_ma_col: str = 'Volume_SMA',
    threshold: float = 1.5,
    name: str = 'Volume_Signal'
) -> pd.Series:
    """
    Génère signaux volume (momentum).
    
    Signal = 1 quand Volume > threshold × Volume_MA (forte hausse volume)
    Signal = -1 quand Volume < (1/threshold) × Volume_MA (faible volume)
    Signal = 0 ailleurs
    
    Args:
        features: DataFrame features avec Volume
        volume_col: Nom colonne Volume
        volume_ma_col: Nom colonne Volume MA
        threshold: Multiplicateur threshold (default 1.5)
        name: Nom du signal
    
    Returns:
        Series signaux (1, 0, -1)
    
    Raises:
        ValueError: Si colonnes manquantes
    """
    if features.empty:
        raise ValueError("Features DataFrame cannot be empty")
    if volume_col not in features.columns:
        raise ValueError(f"Features must have '{volume_col}' column")
    
    volume = features[volume_col]
    
    # Calculer Volume MA si pas présente
    if volume_ma_col not in features.columns:
        volume_ma = volume.rolling(window=20).mean()
        logger.debug("Calculated Volume_SMA on-the-fly")
    else:
        volume_ma = features[volume_ma_col]
    
    # Générer signaux
    signal = pd.Series(0, index=features.index, dtype=int)
    signal[volume > threshold * volume_ma] = 1
    signal[volume < (1 / threshold) * volume_ma] = -1
    
    signal.name = name
    
    logger.info(f"Generated {name}: {(signal == 1).sum()} high vol, {(signal == -1).sum()} low vol")
    return signal


def ml_prediction_signal(
    predictions: pd.Series,
    threshold: float = 0.5,
    name: str = 'ML_Signal'
) -> pd.Series:
    """
    Convertit prédictions ML en signaux de trading.
    
    Signal = 1 si predictions >= threshold (bullish)
    Signal = -1 si predictions <= (1-threshold) (bearish)
    Signal = 0 ailleurs (incertitude)
    
    Args:
        predictions: Series avec probabilités (0-1) ou scores
        threshold: Seuil décision (default 0.5)
        name: Nom du signal
    
    Returns:
        Series signaux (1, 0, -1)
    
    Raises:
        ValueError: Si predictions invalide
    """
    if predictions.empty:
        raise ValueError("Predictions series cannot be empty")
    if threshold <= 0 or threshold >= 1:
        raise ValueError("Threshold must be in range (0, 1)")
    
    # Normaliser si range différent de [0, 1]
    if predictions.min() < 0 or predictions.max() > 1:
        logger.warning("Predictions outside [0,1] range, normalizing...")
        predictions = (predictions - predictions.min()) / (predictions.max() - predictions.min())
    
    # Générer signaux
    signal = pd.Series(0, index=predictions.index, dtype=int)
    signal[predictions >= threshold] = 1
    signal[predictions <= (1 - threshold)] = -1
    
    signal.name = name
    
    logger.info(f"Generated {name}: {(signal == 1).sum()} buy, {(signal == -1).sum()} sell")
    return signal


def custom_rule_signal(
    features: pd.DataFrame,
    rule_func: Callable[[pd.Series], int],
    name: str = 'Custom_Signal'
) -> pd.Series:
    """
    Applique une règle custom pour générer signaux.
    
    La fonction rule_func est appliquée à chaque ligne du DataFrame.
    
    Args:
        features: DataFrame features
        rule_func: Fonction(row: pd.Series) -> int (1, 0, -1)
        name: Nom du signal
    
    Returns:
        Series signaux (1, 0, -1)
    
    Raises:
        ValueError: Si rule_func invalide ou retourne valeurs incorrectes
    
    Example:
        >>> def my_rule(row):
        ...     if row['Close'] > row['SMA_20'] and row['RSI_14'] < 70:
        ...         return 1
        ...     return 0
        >>> signal = custom_rule_signal(features, my_rule)
    """
    if features.empty:
        raise ValueError("Features DataFrame cannot be empty")
    if not callable(rule_func):
        raise ValueError("rule_func must be callable")
    
    try:
        # Appliquer règle à chaque ligne
        signal = features.apply(rule_func, axis=1)
        
        # Valider que les valeurs sont {-1, 0, 1}
        unique_vals = signal.unique()
        if not all(val in [-1, 0, 1] for val in unique_vals):
            raise ValueError("rule_func must return only -1, 0, or 1")
        
        signal = signal.astype(int)
        signal.name = name
        
        logger.info(f"Generated {name}: {(signal == 1).sum()} buy, {(signal == -1).sum()} sell")
        return signal
        
    except Exception as e:
        logger.error(f"Error applying custom rule: {e}")
        raise ValueError(f"Failed to apply rule_func: {e}")


# ============================================================================
# SIGNAL AGGREGATION & MANIPULATION
# ============================================================================

def aggregate_signals(
    signals_dict: Dict[str, pd.Series],
    method: str = 'vote',
    weights: Optional[Dict[str, float]] = None
) -> pd.Series:
    """
    Combine plusieurs signaux en un seul.
    
    Args:
        signals_dict: {'Signal1': Series, 'Signal2': Series, ...}
        method: 'vote' (majority voting), 'and' (tous doivent être 1/-1),
                'or' (au moins 1), 'weighted' (moyenne pondérée)
        weights: {'Signal1': 0.5, 'Signal2': 0.5, ...} pour method='weighted'
    
    Returns:
        Series signal combiné (1, 0, -1)
    
    Raises:
        ValueError: Si signals_dict vide ou method invalide
    """
    if not signals_dict:
        raise ValueError("signals_dict cannot be empty")
    
    valid_methods = ['vote', 'and', 'or', 'weighted']
    if method not in valid_methods:
        raise ValueError(f"method must be one of {valid_methods}")
    
    # Aligner tous les signaux sur le même index
    signals_df = pd.DataFrame(signals_dict)
    
    if method == 'vote':
        # Majority voting: sum et sign
        combined = signals_df.sum(axis=1)
        signal = pd.Series(0, index=combined.index, dtype=int)
        signal[combined > 0] = 1
        signal[combined < 0] = -1
        
    elif method == 'and':
        # Tous doivent être 1 pour buy, tous -1 pour sell
        signal = pd.Series(0, index=signals_df.index, dtype=int)
        signal[(signals_df == 1).all(axis=1)] = 1
        signal[(signals_df == -1).all(axis=1)] = -1
        
    elif method == 'or':
        # Au moins un signal 1 pour buy, au moins un -1 pour sell
        signal = pd.Series(0, index=signals_df.index, dtype=int)
        signal[(signals_df == 1).any(axis=1)] = 1
        signal[(signals_df == -1).any(axis=1)] = -1
        
    elif method == 'weighted':
        if weights is None:
            raise ValueError("weights must be provided for method='weighted'")
        
        # Vérifier que tous les signaux ont un poids
        missing_weights = set(signals_dict.keys()) - set(weights.keys())
        if missing_weights:
            raise ValueError(f"Missing weights for signals: {missing_weights}")
        
        # Moyenne pondérée
        weighted_sum = sum(signals_df[sig] * weights[sig] for sig in signals_dict.keys())
        signal = pd.Series(0, index=weighted_sum.index, dtype=int)
        signal[weighted_sum > 0] = 1
        signal[weighted_sum < 0] = -1
    
    signal.name = 'Aggregated_Signal'
    
    logger.info(f"Aggregated {len(signals_dict)} signals using {method} method: "
                f"{(signal == 1).sum()} buy, {(signal == -1).sum()} sell")
    return signal


def smooth_signal(
    signal: pd.Series,
    window: int = 3,
    method: str = 'majority'
) -> pd.Series:
    """
    Lisse signaux pour réduire noise (faux signaux court-terme).
    
    Args:
        signal: Series signaux (1, 0, -1)
        window: Taille fenêtre lissage
        method: 'majority' (vote majoritaire), 'median', 'mean'
    
    Returns:
        Series signal lissé
    
    Raises:
        ValueError: Si window invalide ou method inconnu
    """
    if signal.empty:
        raise ValueError("Signal series cannot be empty")
    if window < 1:
        raise ValueError("Window must be >= 1")
    if window == 1:
        return signal.copy()
    
    valid_methods = ['majority', 'median', 'mean']
    if method not in valid_methods:
        raise ValueError(f"method must be one of {valid_methods}")
    
    if method == 'majority':
        # Vote majoritaire sur fenêtre glissante
        smoothed = signal.rolling(window=window, center=True, min_periods=1).apply(
            lambda x: pd.Series(x).mode()[0] if len(pd.Series(x).mode()) > 0 else 0,
            raw=True
        )
        
    elif method == 'median':
        smoothed = signal.rolling(window=window, center=True, min_periods=1).median()
        
    elif method == 'mean':
        # Mean puis arrondir et sign
        smoothed = signal.rolling(window=window, center=True, min_periods=1).mean()
        smoothed = smoothed.apply(lambda x: 1 if x > 0.33 else (-1 if x < -0.33 else 0))
    
    smoothed = smoothed.astype(int)
    smoothed.name = signal.name
    
    logger.debug(f"Smoothed signal with window={window}, method={method}")
    return smoothed


# ============================================================================
# SIGNAL VALIDATION & APPLICATION
# ============================================================================

def validate_signal(signal: pd.Series, features: pd.DataFrame) -> bool:
    """
    Valide qu'un signal est au format correct pour backtesting.
    
    Vérifie:
    - Index DatetimeIndex
    - Values en {-1, 0, 1}
    - Longueur = longueur features
    - Pas de NaN
    
    Args:
        signal: Series signal à valider
        features: DataFrame features de référence
    
    Returns:
        True si valide
    
    Raises:
        ValueError: Si validation échoue avec détails
    """
    # Check index DatetimeIndex
    if not isinstance(signal.index, pd.DatetimeIndex):
        raise ValueError("Signal index must be DatetimeIndex")
    
    # Check longueur
    if len(signal) != len(features):
        raise ValueError(f"Signal length ({len(signal)}) must match features length ({len(features)})")
    
    # Check NaN
    if signal.isna().any():
        raise ValueError("Signal cannot contain NaN values")
    
    # Check valeurs {-1, 0, 1}
    unique_vals = signal.unique()
    if not all(val in [-1, 0, 1] for val in unique_vals):
        raise ValueError(f"Signal values must be in {{-1, 0, 1}}, found: {unique_vals}")
    
    logger.debug("Signal validation passed")
    return True


def apply_signal_to_backtest(
    features: pd.DataFrame,
    signal: pd.Series,
    signal_name: str = 'Signal'
) -> pd.DataFrame:
    """
    Ajoute signal au DataFrame features pour backtesting.
    
    Args:
        features: DataFrame features FeaturePipeline
        signal: Series signal
        signal_name: Nom colonne signal
    
    Returns:
        DataFrame features + colonne signal
    
    Raises:
        ValueError: Si signal invalide
    """
    # Valider signal
    validate_signal(signal, features)
    
    # Copier features et ajouter signal
    features_with_signal = features.copy()
    features_with_signal[signal_name] = signal.values
    
    logger.info(f"Added signal '{signal_name}' to features DataFrame")
    return features_with_signal


def backtest_ready_signals(
    features: pd.DataFrame,
    signals_dict: Dict[str, pd.Series]
) -> pd.DataFrame:
    """
    Prépare tous les signaux pour backtesting (validation + ajout).
    
    Valide chaque signal et les ajoute tous au DataFrame features.
    
    Args:
        features: DataFrame features
        signals_dict: {'Signal1': Series, 'Signal2': Series, ...}
    
    Returns:
        DataFrame features + colonnes signaux
    
    Raises:
        ValueError: Si au moins un signal invalide
    """
    if not signals_dict:
        raise ValueError("signals_dict cannot be empty")
    
    features_with_signals = features.copy()
    
    for signal_name, signal in signals_dict.items():
        try:
            validate_signal(signal, features)
            features_with_signals[signal_name] = signal.values
            logger.debug(f"Added signal '{signal_name}'")
        except ValueError as e:
            logger.error(f"Validation failed for signal '{signal_name}': {e}")
            raise ValueError(f"Signal '{signal_name}' is invalid: {e}")
    
    logger.info(f"Prepared {len(signals_dict)} signals for backtesting")
    return features_with_signals

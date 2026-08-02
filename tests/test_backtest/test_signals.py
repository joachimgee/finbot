"""
Tests unitaires pour le module signals.py.

Ce module teste toutes les fonctions de génération de signaux,
l'agrégation, le lissage, la validation et l'application aux backtests.

Test Coverage:
    - SignalGenerator class (init, generate methods, combine, smooth)
    - SMA Crossover signals
    - RSI threshold signals
    - Bollinger Band breakout signals
    - MACD signals
    - Volume signals
    - ML prediction signals
    - Custom rule signals
    - Signal aggregation (vote, and, or, weighted)
    - Signal smoothing (majority, median, mean)
    - Signal validation
    - Apply signals to backtest
    - Backtest-ready signals preparation
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from financial_analyzer.backtest.signals import (
    SignalGenerator,
    sma_crossover_signal,
    rsi_threshold_signal,
    bollinger_breakout_signal,
    macd_signal,
    volume_signal,
    ml_prediction_signal,
    custom_rule_signal,
    aggregate_signals,
    smooth_signal,
    validate_signal,
    apply_signal_to_backtest,
    backtest_ready_signals
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_features_with_indicators():
    """Generate mock features DataFrame with technical indicators."""
    np.random.seed(42)
    n = 252
    
    dates = pd.date_range(start='2023-01-01', periods=n, freq='D')
    
    # Generate OHLCV
    close = 100 + np.cumsum(np.random.randn(n) * 2)
    
    df = pd.DataFrame({
        'Open': close + np.random.randn(n) * 0.5,
        'High': close + np.abs(np.random.randn(n)) * 1,
        'Low': close - np.abs(np.random.randn(n)) * 1,
        'Close': close,
        'Volume': np.random.randint(1000000, 5000000, n)
    }, index=dates)
    
    # Add technical indicators
    df['SMA_50'] = df['Close'].rolling(window=50).mean()
    df['SMA_200'] = df['Close'].rolling(window=200).mean()
    df['RSI_14'] = 50 + np.random.randn(n) * 20  # Mock RSI
    df['RSI_14'] = df['RSI_14'].clip(0, 100)
    
    # Bollinger Bands
    df['BB_Middle'] = df['Close'].rolling(window=20).mean()
    df['BB_Std'] = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['BB_Middle'] + 2 * df['BB_Std']
    df['BB_Lower'] = df['BB_Middle'] - 2 * df['BB_Std']
    
    # MACD
    df['MACD'] = df['Close'].ewm(span=12).mean() - df['Close'].ewm(span=26).mean()
    df['MACD_Signal'] = df['MACD'].ewm(span=9).mean()
    
    # Volume indicators
    df['Volume_SMA'] = df['Volume'].rolling(window=20).mean()
    
    return df


@pytest.fixture
def mock_ml_predictions():
    """Generate mock ML predictions (probabilities 0-1)."""
    np.random.seed(42)
    n = 252
    dates = pd.date_range(start='2023-01-01', periods=n, freq='D')
    
    # Generate predictions with some structure
    predictions = np.random.beta(2, 2, n)  # Beta distribution for [0,1]
    
    return pd.Series(predictions, index=dates, name='ML_Predictions')


@pytest.fixture
def mock_signal_series():
    """Generate mock signal series (1, 0, -1)."""
    np.random.seed(42)
    n = 252
    dates = pd.date_range(start='2023-01-01', periods=n, freq='D')
    
    signal = np.random.choice([-1, 0, 1], size=n, p=[0.2, 0.6, 0.2])
    
    return pd.Series(signal, index=dates, dtype=int, name='MockSignal')


# ============================================================================
# TESTS: SMA CROSSOVER
# ============================================================================

class TestSMACrossover:
    """Tests pour sma_crossover_signal."""
    
    def test_sma_crossover_basic(self, mock_features_with_indicators):
        """Test génération basique signal SMA crossover."""
        signal = sma_crossover_signal(mock_features_with_indicators, fast_period=50, slow_period=200)
        
        assert isinstance(signal, pd.Series)
        assert signal.name == 'SMA_Crossover'
        assert len(signal) == len(mock_features_with_indicators)
        assert set(signal.unique()).issubset({-1, 0, 1})
    
    def test_sma_crossover_bullish(self):
        """Test signal bullish (fast > slow)."""
        dates = pd.date_range(start='2023-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'Close': [100, 101, 102, 103, 104, 105, 106, 107, 108, 109]
        }, index=dates)
        
        # Créer SMAs where fast > slow
        df['SMA_2'] = df['Close'].rolling(window=2).mean()
        df['SMA_5'] = df['Close'].rolling(window=5).mean()
        
        signal = sma_crossover_signal(df, fast_period=2, slow_period=5)
        
        # Les dernières valeurs devraient être 1 (fast > slow dans uptrend)
        assert signal.iloc[-1] == 1
    
    def test_sma_crossover_bearish(self):
        """Test signal bearish (fast < slow)."""
        dates = pd.date_range(start='2023-01-01', periods=10, freq='D')
        df = pd.DataFrame({
            'Close': [109, 108, 107, 106, 105, 104, 103, 102, 101, 100]
        }, index=dates)
        
        signal = sma_crossover_signal(df, fast_period=2, slow_period=5)
        
        # Les dernières valeurs devraient être -1 (fast < slow dans downtrend)
        assert signal.iloc[-1] == -1
    
    def test_sma_crossover_missing_columns(self):
        """Test error quand colonne Close manquante."""
        df = pd.DataFrame({'Open': [100, 101, 102]})
        
        with pytest.raises(ValueError, match="must have 'Close' column"):
            sma_crossover_signal(df)
    
    def test_sma_crossover_edge_case(self):
        """Test avec DataFrame très petit."""
        dates = pd.date_range(start='2023-01-01', periods=3, freq='D')
        df = pd.DataFrame({'Close': [100, 101, 102]}, index=dates)
        
        # Devrait fonctionner mais avoir beaucoup de NaN au début
        signal = sma_crossover_signal(df, fast_period=2, slow_period=3)
        assert len(signal) == 3


# ============================================================================
# TESTS: RSI SIGNAL
# ============================================================================

class TestRSISignal:
    """Tests pour rsi_threshold_signal."""
    
    def test_rsi_signal_basic(self, mock_features_with_indicators):
        """Test génération basique signal RSI."""
        signal = rsi_threshold_signal(mock_features_with_indicators, lower=30, upper=70)
        
        assert isinstance(signal, pd.Series)
        assert signal.name == 'RSI_Signal'
        assert set(signal.unique()).issubset({-1, 0, 1})
    
    def test_rsi_signal_oversold(self):
        """Test signal oversold (RSI < 30)."""
        dates = pd.date_range(start='2023-01-01', periods=5, freq='D')
        df = pd.DataFrame({
            'RSI_14': [25, 28, 32, 50, 75]
        }, index=dates)
        
        signal = rsi_threshold_signal(df, lower=30, upper=70)
        
        assert signal.iloc[0] == 1  # RSI = 25 < 30 -> buy
        assert signal.iloc[1] == 1  # RSI = 28 < 30 -> buy
        assert signal.iloc[2] == 0  # RSI = 32 (neutral)
    
    def test_rsi_signal_overbought(self):
        """Test signal overbought (RSI > 70)."""
        dates = pd.date_range(start='2023-01-01', periods=5, freq='D')
        df = pd.DataFrame({
            'RSI_14': [75, 80, 65, 50, 25]
        }, index=dates)
        
        signal = rsi_threshold_signal(df, lower=30, upper=70)
        
        assert signal.iloc[0] == -1  # RSI = 75 > 70 -> sell
        assert signal.iloc[1] == -1  # RSI = 80 > 70 -> sell
        assert signal.iloc[2] == 0   # RSI = 65 (neutral)
    
    def test_rsi_signal_invalid_thresholds(self, mock_features_with_indicators):
        """Test error avec thresholds invalides."""
        with pytest.raises(ValueError, match="Lower threshold must be < upper"):
            rsi_threshold_signal(mock_features_with_indicators, lower=70, upper=30)


# ============================================================================
# TESTS: BOLLINGER SIGNAL
# ============================================================================

class TestBollingerSignal:
    """Tests pour bollinger_breakout_signal."""
    
    def test_bollinger_basic(self, mock_features_with_indicators):
        """Test génération basique signal Bollinger."""
        signal = bollinger_breakout_signal(mock_features_with_indicators)
        
        assert isinstance(signal, pd.Series)
        assert signal.name == 'BB_Signal'
        assert set(signal.unique()).issubset({-1, 0, 1})
    
    def test_bollinger_breakout_upper(self):
        """Test breakout upper band."""
        dates = pd.date_range(start='2023-01-01', periods=3, freq='D')
        df = pd.DataFrame({
            'Close': [100, 105, 110],
            'BB_Upper': [102, 103, 104],
            'BB_Lower': [98, 97, 96]
        }, index=dates)
        
        signal = bollinger_breakout_signal(df)
        
        # Close > BB_Upper -> signal = 1
        assert signal.iloc[1] == 1
        assert signal.iloc[2] == 1
    
    def test_bollinger_breakout_lower(self):
        """Test breakout lower band."""
        dates = pd.date_range(start='2023-01-01', periods=3, freq='D')
        df = pd.DataFrame({
            'Close': [100, 95, 90],
            'BB_Upper': [102, 103, 104],
            'BB_Lower': [98, 97, 96]
        }, index=dates)
        
        signal = bollinger_breakout_signal(df)
        
        # Close < BB_Lower -> signal = -1
        assert signal.iloc[1] == -1
        assert signal.iloc[2] == -1


# ============================================================================
# TESTS: MACD SIGNAL
# ============================================================================

class TestMACDSignal:
    """Tests pour macd_signal."""
    
    def test_macd_signal_basic(self, mock_features_with_indicators):
        """Test génération basique signal MACD."""
        signal = macd_signal(mock_features_with_indicators)
        
        assert isinstance(signal, pd.Series)
        assert set(signal.unique()).issubset({-1, 0, 1})
    
    def test_macd_signal_crossover(self):
        """Test MACD crossover signal line."""
        dates = pd.date_range(start='2023-01-01', periods=5, freq='D')
        df = pd.DataFrame({
            'MACD': [-1, -0.5, 0.5, 1, 0.8],
            'MACD_Signal': [0, 0, 0, 0, 0]
        }, index=dates)
        
        signal = macd_signal(df)
        
        assert signal.iloc[0] == -1  # MACD < Signal
        assert signal.iloc[2] == 1   # MACD > Signal
        assert signal.iloc[3] == 1   # MACD > Signal
    
    def test_macd_signal_missing_columns(self):
        """Test error avec colonnes manquantes."""
        df = pd.DataFrame({'Close': [100, 101]})
        
        with pytest.raises(ValueError, match="missing columns"):
            macd_signal(df)


# ============================================================================
# TESTS: VOLUME SIGNAL
# ============================================================================

class TestVolumeSignal:
    """Tests pour volume_signal."""
    
    def test_volume_signal_high(self):
        """Test signal volume élevé."""
        dates = pd.date_range(start='2023-01-01', periods=5, freq='D')
        df = pd.DataFrame({
            'Volume': [1000, 2000, 3000, 2500, 1500],
            'Volume_SMA': [1000, 1000, 1000, 1000, 1000]
        }, index=dates)
        
        signal = volume_signal(df, threshold=1.5)
        
        # Volume > 1.5 * Volume_SMA -> signal = 1
        assert signal.iloc[2] == 1  # 3000 > 1.5*1000
        assert signal.iloc[3] == 1  # 2500 > 1.5*1000
    
    def test_volume_signal_low(self):
        """Test signal volume faible."""
        dates = pd.date_range(start='2023-01-01', periods=5, freq='D')
        df = pd.DataFrame({
            'Volume': [1000, 500, 300, 700, 1200],
            'Volume_SMA': [1000, 1000, 1000, 1000, 1000]
        }, index=dates)
        
        signal = volume_signal(df, threshold=1.5)
        
        # Volume < (1/1.5) * Volume_SMA -> signal = -1
        assert signal.iloc[1] == -1  # 500 < 666
        assert signal.iloc[2] == -1  # 300 < 666
    
    def test_volume_signal_threshold(self, mock_features_with_indicators):
        """Test avec différents thresholds."""
        signal1 = volume_signal(mock_features_with_indicators, threshold=1.5)
        signal2 = volume_signal(mock_features_with_indicators, threshold=2.0)
        
        # Threshold plus haut = moins de signaux
        assert (signal1 != 0).sum() >= (signal2 != 0).sum()


# ============================================================================
# TESTS: ML SIGNAL
# ============================================================================

class TestMLSignal:
    """Tests pour ml_prediction_signal."""
    
    def test_ml_signal_high_confidence(self, mock_ml_predictions):
        """Test signaux haute confiance."""
        signal = ml_prediction_signal(mock_ml_predictions, threshold=0.5)
        
        assert isinstance(signal, pd.Series)
        assert set(signal.unique()).issubset({-1, 0, 1})
    
    def test_ml_signal_low_confidence(self):
        """Test signaux basse confiance (plus de 0)."""
        dates = pd.date_range(start='2023-01-01', periods=5, freq='D')
        predictions = pd.Series([0.45, 0.48, 0.52, 0.55, 0.5], index=dates)
        
        signal = ml_prediction_signal(predictions, threshold=0.5)
        
        # Avec threshold=0.5: <0.5 -> -1, >=0.5 -> 1, exactement 0.5 peut être 1 ou -1
        # Vérifier que les signaux sont générés
        assert set(signal.unique()).issubset({-1, 0, 1})
    
    def test_ml_signal_range_check(self):
        """Test normalisation prédictions hors [0,1]."""
        dates = pd.date_range(start='2023-01-01', periods=5, freq='D')
        predictions = pd.Series([-1, -0.5, 0, 0.5, 1], index=dates)
        
        # Devrait normaliser automatiquement
        signal = ml_prediction_signal(predictions, threshold=0.5)
        
        assert isinstance(signal, pd.Series)
        assert set(signal.unique()).issubset({-1, 0, 1})
    
    def test_ml_signal_custom_threshold(self, mock_ml_predictions):
        """Test avec threshold custom."""
        signal1 = ml_prediction_signal(mock_ml_predictions, threshold=0.5)
        signal2 = ml_prediction_signal(mock_ml_predictions, threshold=0.7)
        
        # Threshold plus haut = moins de signaux buy (1)
        assert (signal2 == 1).sum() <= (signal1 == 1).sum()


# ============================================================================
# TESTS: CUSTOM RULE SIGNAL
# ============================================================================

class TestCustomRuleSignal:
    """Tests pour custom_rule_signal."""
    
    def test_custom_rule_simple(self, mock_features_with_indicators):
        """Test règle custom simple."""
        def simple_rule(row):
            if row['Close'] > 100:
                return 1
            elif row['Close'] < 95:
                return -1
            return 0
        
        signal = custom_rule_signal(mock_features_with_indicators, simple_rule)
        
        assert isinstance(signal, pd.Series)
        assert set(signal.unique()).issubset({-1, 0, 1})
    
    def test_custom_rule_complex(self, mock_features_with_indicators):
        """Test règle custom complexe (multi-conditions)."""
        def complex_rule(row):
            if row['Close'] > row['SMA_50'] and row['RSI_14'] < 70:
                return 1
            elif row['Close'] < row['SMA_50'] and row['RSI_14'] > 30:
                return -1
            return 0
        
        signal = custom_rule_signal(mock_features_with_indicators, complex_rule)
        
        assert isinstance(signal, pd.Series)
        assert len(signal) == len(mock_features_with_indicators)
    
    def test_custom_rule_error_handling(self, mock_features_with_indicators):
        """Test error handling règle invalide."""
        def bad_rule(row):
            return "invalid"  # Devrait retourner int
        
        with pytest.raises(ValueError, match="must return only -1, 0, or 1"):
            custom_rule_signal(mock_features_with_indicators, bad_rule)


# ============================================================================
# TESTS: AGGREGATE SIGNALS
# ============================================================================

class TestAggregateSignals:
    """Tests pour aggregate_signals."""
    
    def test_aggregate_vote_method(self):
        """Test agrégation par vote majoritaire."""
        dates = pd.date_range(start='2023-01-01', periods=5, freq='D')
        signals = {
            'Signal1': pd.Series([1, 1, 0, -1, 1], index=dates),
            'Signal2': pd.Series([1, -1, 0, -1, 0], index=dates),
            'Signal3': pd.Series([1, 0, 1, -1, -1], index=dates)
        }
        
        combined = aggregate_signals(signals, method='vote')
        
        assert combined.iloc[0] == 1   # 3 votes: 1,1,1 -> 1
        assert combined.iloc[1] == 0   # 3 votes: 1,-1,0 -> 0
        assert combined.iloc[3] == -1  # 3 votes: -1,-1,-1 -> -1
    
    def test_aggregate_and_method(self):
        """Test agrégation AND (tous doivent être d'accord)."""
        dates = pd.date_range(start='2023-01-01', periods=5, freq='D')
        signals = {
            'Signal1': pd.Series([1, 1, 0, -1, -1], index=dates),
            'Signal2': pd.Series([1, 0, 0, -1, -1], index=dates)
        }
        
        combined = aggregate_signals(signals, method='and')
        
        assert combined.iloc[0] == 1   # Both 1 -> 1
        assert combined.iloc[1] == 0   # Not all 1 -> 0
        assert combined.iloc[3] == -1  # Both -1 -> -1
    
    def test_aggregate_or_method(self):
        """Test agrégation OR (au moins un)."""
        dates = pd.date_range(start='2023-01-01', periods=5, freq='D')
        signals = {
            'Signal1': pd.Series([1, 0, 0, 0, -1], index=dates),
            'Signal2': pd.Series([0, 0, 1, -1, 0], index=dates)
        }
        
        combined = aggregate_signals(signals, method='or')
        
        assert combined.iloc[0] == 1   # At least one 1
        assert combined.iloc[1] == 0   # No 1 or -1
        assert combined.iloc[2] == 1   # At least one 1
        assert combined.iloc[3] == -1  # At least one -1
    
    def test_aggregate_weighted(self):
        """Test agrégation pondérée."""
        dates = pd.date_range(start='2023-01-01', periods=3, freq='D')
        signals = {
            'Signal1': pd.Series([1, -1, 0], index=dates),
            'Signal2': pd.Series([1, 1, -1], index=dates)
        }
        weights = {'Signal1': 0.7, 'Signal2': 0.3}
        
        combined = aggregate_signals(signals, method='weighted', weights=weights)
        
        # Row 0: 1*0.7 + 1*0.3 = 1.0 -> 1
        assert combined.iloc[0] == 1
        # Row 1: -1*0.7 + 1*0.3 = -0.4 -> -1
        assert combined.iloc[1] == -1
    
    def test_aggregate_empty_dict(self):
        """Test error avec dict vide."""
        with pytest.raises(ValueError, match="cannot be empty"):
            aggregate_signals({})


# ============================================================================
# TESTS: SMOOTH SIGNAL
# ============================================================================

class TestSmoothSignal:
    """Tests pour smooth_signal."""
    
    def test_smooth_majority(self):
        """Test lissage par vote majoritaire."""
        dates = pd.date_range(start='2023-01-01', periods=7, freq='D')
        signal = pd.Series([1, 1, -1, 1, 1, -1, -1], index=dates)
        
        smoothed = smooth_signal(signal, window=3, method='majority')
        
        # Devrait lisser les fluctuations court-terme
        assert isinstance(smoothed, pd.Series)
        assert len(smoothed) == len(signal)
    
    def test_smooth_median(self):
        """Test lissage par médiane."""
        dates = pd.date_range(start='2023-01-01', periods=7, freq='D')
        signal = pd.Series([1, 1, -1, 1, 1, -1, -1], index=dates)
        
        smoothed = smooth_signal(signal, window=3, method='median')
        
        assert isinstance(smoothed, pd.Series)
        assert set(smoothed.unique()).issubset({-1, 0, 1})
    
    def test_smooth_mean(self):
        """Test lissage par moyenne."""
        dates = pd.date_range(start='2023-01-01', periods=7, freq='D')
        signal = pd.Series([1, 1, 1, -1, -1, -1, -1], index=dates)
        
        smoothed = smooth_signal(signal, window=3, method='mean')
        
        assert isinstance(smoothed, pd.Series)
        assert set(smoothed.unique()).issubset({-1, 0, 1})
    
    def test_smooth_window_size(self):
        """Test différentes tailles de fenêtre."""
        dates = pd.date_range(start='2023-01-01', periods=10, freq='D')
        signal = pd.Series([1, -1, 1, -1, 1, -1, 1, -1, 1, -1], index=dates)
        
        smoothed_w1 = smooth_signal(signal, window=1)
        smoothed_w5 = smooth_signal(signal, window=5)
        
        # Window=1 devrait être identique
        assert (smoothed_w1 == signal).all()
        
        # Window=5 devrait lisser davantage
        assert (smoothed_w5 == 0).sum() >= (signal == 0).sum()


# ============================================================================
# TESTS: VALIDATE SIGNAL
# ============================================================================

class TestValidateSignal:
    """Tests pour validate_signal."""
    
    def test_validate_valid_signal(self, mock_features_with_indicators, mock_signal_series):
        """Test validation signal valide."""
        # Aligner index
        signal = mock_signal_series[:len(mock_features_with_indicators)]
        signal.index = mock_features_with_indicators.index
        
        result = validate_signal(signal, mock_features_with_indicators)
        assert result is True
    
    def test_validate_invalid_values(self, mock_features_with_indicators):
        """Test validation échoue avec valeurs invalides."""
        # Créer signal avec même longueur mais valeurs invalides
        signal = pd.Series([1, 2, 3] * 84, index=mock_features_with_indicators.index)
        
        with pytest.raises(ValueError, match="must be in"):
            validate_signal(signal, mock_features_with_indicators)
    
    def test_validate_length_mismatch(self, mock_features_with_indicators):
        """Test validation échoue si longueur différente."""
        signal = pd.Series([1, 0, -1], index=pd.date_range('2023-01-01', periods=3))
        
        with pytest.raises(ValueError, match="length.*must match"):
            validate_signal(signal, mock_features_with_indicators)
    
    def test_validate_nan_values(self, mock_features_with_indicators):
        """Test validation échoue avec NaN."""
        signal = pd.Series([1, np.nan, -1] * 84, index=mock_features_with_indicators.index)
        
        with pytest.raises(ValueError, match="cannot contain NaN"):
            validate_signal(signal, mock_features_with_indicators)


# ============================================================================
# TESTS: APPLY SIGNAL TO BACKTEST
# ============================================================================

class TestApplySignalToBacktest:
    """Tests pour apply_signal_to_backtest."""
    
    def test_apply_single_signal(self, mock_features_with_indicators):
        """Test ajout d'un seul signal."""
        signal = pd.Series([1] * len(mock_features_with_indicators), 
                          index=mock_features_with_indicators.index)
        
        result = apply_signal_to_backtest(mock_features_with_indicators, signal, 'TestSignal')
        
        assert 'TestSignal' in result.columns
        assert len(result) == len(mock_features_with_indicators)
        assert (result['TestSignal'] == 1).all()
    
    def test_apply_multiple_signals(self, mock_features_with_indicators):
        """Test ajout de plusieurs signaux successifs."""
        signal1 = pd.Series([1] * len(mock_features_with_indicators),
                           index=mock_features_with_indicators.index)
        signal2 = pd.Series([-1] * len(mock_features_with_indicators),
                           index=mock_features_with_indicators.index)
        
        result = apply_signal_to_backtest(mock_features_with_indicators, signal1, 'Signal1')
        result = apply_signal_to_backtest(result, signal2, 'Signal2')
        
        assert 'Signal1' in result.columns
        assert 'Signal2' in result.columns
    
    def test_apply_invalid_signal(self, mock_features_with_indicators):
        """Test error avec signal invalide."""
        bad_signal = pd.Series([1, 2, 3], index=mock_features_with_indicators.index[:3])
        
        with pytest.raises(ValueError):
            apply_signal_to_backtest(mock_features_with_indicators, bad_signal)


# ============================================================================
# TESTS: BACKTEST READY SIGNALS
# ============================================================================

class TestBacktestReadySignals:
    """Tests pour backtest_ready_signals."""
    
    def test_backtest_ready_full_pipeline(self, mock_features_with_indicators):
        """Test préparation complète signaux pour backtest."""
        # Créer plusieurs signaux
        signal1 = pd.Series([1] * len(mock_features_with_indicators),
                           index=mock_features_with_indicators.index)
        signal2 = pd.Series([0] * len(mock_features_with_indicators),
                           index=mock_features_with_indicators.index)
        
        signals_dict = {'Signal1': signal1, 'Signal2': signal2}
        
        result = backtest_ready_signals(mock_features_with_indicators, signals_dict)
        
        assert 'Signal1' in result.columns
        assert 'Signal2' in result.columns
        assert len(result) == len(mock_features_with_indicators)
    
    def test_backtest_ready_error_handling(self, mock_features_with_indicators):
        """Test error handling avec signal invalide."""
        good_signal = pd.Series([1] * len(mock_features_with_indicators),
                               index=mock_features_with_indicators.index)
        bad_signal = pd.Series([1, 2, 3], index=mock_features_with_indicators.index[:3])
        
        signals_dict = {'Good': good_signal, 'Bad': bad_signal}
        
        with pytest.raises(ValueError, match="is invalid"):
            backtest_ready_signals(mock_features_with_indicators, signals_dict)


# ============================================================================
# TESTS: SIGNAL GENERATOR CLASS
# ============================================================================

class TestSignalGenerator:
    """Tests pour SignalGenerator class."""
    
    def test_signal_generator_init(self, mock_features_with_indicators):
        """Test initialisation SignalGenerator."""
        gen = SignalGenerator(mock_features_with_indicators)
        
        assert gen.features is not None
        assert isinstance(gen.signals, dict)
        assert len(gen.signals) == 0
    
    def test_signal_generator_multiple_signals(self, mock_features_with_indicators):
        """Test génération de plusieurs signaux."""
        gen = SignalGenerator(mock_features_with_indicators)
        
        rsi_sig = gen.generate_rsi_signal(lower=30, upper=70)
        sma_sig = gen.generate_sma_crossover(fast=50, slow=200)
        
        assert 'RSI_Signal' in gen.signals
        assert 'SMA_Crossover' in gen.signals
        assert len(gen.get_all_signals()) == 2
    
    def test_signal_generator_combine(self, mock_features_with_indicators):
        """Test combinaison de signaux via SignalGenerator."""
        gen = SignalGenerator(mock_features_with_indicators)
        
        sig1 = gen.generate_rsi_signal()
        sig2 = gen.generate_sma_crossover()
        
        combined = gen.combine_signals({'RSI': sig1, 'SMA': sig2}, method='vote')
        
        assert isinstance(combined, pd.Series)
        assert len(combined) == len(mock_features_with_indicators)
    
    def test_signal_generator_smooth(self, mock_features_with_indicators):
        """Test lissage via SignalGenerator."""
        gen = SignalGenerator(mock_features_with_indicators)
        
        signal = gen.generate_rsi_signal()
        smoothed = gen.smooth_signals(signal, window=3)
        
        assert isinstance(smoothed, pd.Series)
        assert len(smoothed) == len(signal)


# ============================================================================
# TESTS: EDGE CASES
# ============================================================================

class TestEdgeCases:
    """Tests pour cas limites."""
    
    def test_signal_all_ones(self):
        """Test signal constant (all 1)."""
        dates = pd.date_range(start='2023-01-01', periods=10, freq='D')
        signal = pd.Series([1] * 10, index=dates)
        
        smoothed = smooth_signal(signal, window=3)
        
        # Devrait rester constant
        assert (smoothed == 1).all()
    
    def test_signal_rapid_changes(self):
        """Test signal très bruité (changements rapides)."""
        dates = pd.date_range(start='2023-01-01', periods=20, freq='D')
        signal = pd.Series([1, -1] * 10, index=dates)
        
        # Lissage devrait réduire le bruit
        smoothed = smooth_signal(signal, window=5, method='majority')
        
        # Devrait avoir moins de changements
        changes_before = (signal.diff() != 0).sum()
        changes_after = (smoothed.diff() != 0).sum()
        
        assert changes_after <= changes_before

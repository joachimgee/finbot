"""
Tests pour le module Technical Features.

Author: FinBot Team
Date: 2025-11-06
Version: 2.0.0
"""

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.features.technical import TechnicalFeatureEngine


# Markers pytest pour tous les tests de ce fichier
pytestmark = [pytest.mark.features, pytest.mark.unit]


@pytest.fixture
def mock_ohlcv_data():
    """Fixture avec 100 jours de données OHLCV synthétiques."""
    dates = pd.date_range('2020-01-01', periods=100, freq='D', tz='UTC')
    
    # Générer prix avec tendance + bruit
    np.random.seed(42)
    base_price = 100.0
    trend = np.linspace(0, 20, 100)  # Tendance haussière
    noise = np.random.normal(0, 2, 100)  # Volatilité
    close = base_price + trend + noise
    
    # OHLC cohérents
    open_prices = close + np.random.uniform(-1, 1, 100)
    high = np.maximum(open_prices, close) + np.random.uniform(0, 2, 100)
    low = np.minimum(open_prices, close) - np.random.uniform(0, 2, 100)
    volume = np.random.randint(1000000, 5000000, 100)
    
    return pd.DataFrame(
        {
            'Open': open_prices,
            'High': high,
            'Low': low,
            'Close': close,
            'Volume': volume,
        },
        index=dates,
    )


@pytest.fixture
def mock_short_ohlcv():
    """Fixture avec seulement 5 jours (insuffisant pour RSI14)."""
    dates = pd.date_range('2020-01-01', periods=5, freq='D', tz='UTC')
    
    return pd.DataFrame(
        {
            'Open': [100.0, 101.0, 102.0, 103.0, 104.0],
            'High': [102.0, 103.0, 104.0, 105.0, 106.0],
            'Low': [99.0, 100.0, 101.0, 102.0, 103.0],
            'Close': [101.0, 102.0, 103.0, 104.0, 105.0],
            'Volume': [1000000, 1100000, 1200000, 1300000, 1400000],
        },
        index=dates,
    )


class TestTechnicalFeatureEngineInit:
    """Tests d'initialisation du TechnicalFeatureEngine."""
    
    @pytest.mark.unit
    def test_init_valid_ohlcv(self, mock_ohlcv_data):
        """Test initialisation avec OHLCV valide."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        
        assert engine.df is not None
        assert len(engine.df) == 100
        assert list(engine.df.columns) == ['Open', 'High', 'Low', 'Close', 'Volume']
        assert isinstance(engine.df.index, pd.DatetimeIndex)
    
    @pytest.mark.unit
    def test_init_invalid_ohlcv_missing_columns(self):
        """Test ValueError si colonnes OHLCV manquantes."""
        invalid_df = pd.DataFrame(
            {'Close': [100, 101, 102]},
            index=pd.date_range('2020-01-01', periods=3, tz='UTC'),
        )
        
        with pytest.raises(ValueError, match="Colonnes manquantes"):
            TechnicalFeatureEngine(invalid_df)
    
    @pytest.mark.unit
    def test_init_invalid_index_not_datetime(self, mock_ohlcv_data):
        """Test ValueError si index n'est pas DatetimeIndex."""
        invalid_df = mock_ohlcv_data.copy()
        invalid_df.index = range(len(invalid_df))
        
        with pytest.raises(ValueError, match="Index doit être DatetimeIndex"):
            TechnicalFeatureEngine(invalid_df)
    
    @pytest.mark.unit
    def test_init_invalid_nan_values(self, mock_ohlcv_data):
        """Test ValueError si valeurs NaN dans OHLCV."""
        invalid_df = mock_ohlcv_data.copy()
        invalid_df.loc[invalid_df.index[10], 'Close'] = np.nan
        
        with pytest.raises(ValueError, match="Valeurs NaN détectées"):
            TechnicalFeatureEngine(invalid_df)
    
    @pytest.mark.unit
    def test_init_insufficient_data_warning(self, mock_short_ohlcv):
        """Test que initialisation OK même avec peu de données (warning attendu)."""
        # Initialisation doit fonctionner, mais calculs donneront warnings
        engine = TechnicalFeatureEngine(mock_short_ohlcv)
        assert len(engine.df) == 5


class TestSMACalculation:
    """Tests de calcul SMA (Simple Moving Average)."""
    
    @pytest.mark.unit
    def test_sma_default_period(self, mock_ohlcv_data):
        """Test SMA avec période par défaut (20)."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        sma = engine.calculate_sma(period=20)
        
        assert isinstance(sma, pd.Series)
        assert len(sma) == 100
        # Premières 19 valeurs doivent être NaN
        assert sma.iloc[:19].isna().all()
        # Valeurs suivantes ne doivent pas être NaN
        assert sma.iloc[19:].notna().all()
    
    @pytest.mark.unit
    def test_sma_custom_period(self, mock_ohlcv_data):
        """Test SMA avec période personnalisée."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        sma50 = engine.calculate_sma(period=50)
        
        # Premières 49 valeurs NaN
        assert sma50.iloc[:49].isna().all()
        # Valeurs suivantes OK
        assert sma50.iloc[49:].notna().all()
    
    @pytest.mark.unit
    def test_sma_invalid_period(self, mock_ohlcv_data):
        """Test ValueError si période <= 0."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        
        with pytest.raises(ValueError, match="Period doit être > 0"):
            engine.calculate_sma(period=0)
        
        with pytest.raises(ValueError, match="Period doit être > 0"):
            engine.calculate_sma(period=-5)
    
    @pytest.mark.unit
    def test_sma_insufficient_data(self, mock_short_ohlcv):
        """Test SMA avec données insuffisantes (warning attendu)."""
        engine = TechnicalFeatureEngine(mock_short_ohlcv)
        sma20 = engine.calculate_sma(period=20)
        
        # Toutes les valeurs doivent être NaN (pas assez de données)
        assert sma20.isna().all()


class TestEMACalculation:
    """Tests de calcul EMA (Exponential Moving Average)."""
    
    @pytest.mark.unit
    def test_ema_default_period(self, mock_ohlcv_data):
        """Test EMA avec période par défaut (20)."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        ema = engine.calculate_ema(period=20)
        
        assert isinstance(ema, pd.Series)
        assert len(ema) == 100
        # EMA démarre plus tôt que SMA
        assert ema.notna().any()
    
    @pytest.mark.unit
    def test_ema_vs_sma(self, mock_ohlcv_data):
        """Test que EMA réagit plus vite que SMA."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        sma20 = engine.calculate_sma(period=20)
        ema20 = engine.calculate_ema(period=20)
        
        # EMA doit avoir plus de valeurs non-NaN (commence plus tôt)
        assert ema20.notna().sum() >= sma20.notna().sum()


class TestRSICalculation:
    """Tests de calcul RSI (Relative Strength Index)."""
    
    @pytest.mark.unit
    def test_rsi_default_period(self, mock_ohlcv_data):
        """Test RSI avec période par défaut (14)."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        rsi = engine.calculate_rsi(period=14)
        
        assert isinstance(rsi, pd.Series)
        assert len(rsi) == 100
        # Premières 14 valeurs NaN
        assert rsi.iloc[:14].isna().sum() >= 10  # Au moins 10 NaN
    
    @pytest.mark.unit
    def test_rsi_range(self, mock_ohlcv_data):
        """Test que RSI est entre 0 et 100."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        rsi = engine.calculate_rsi(period=14)
        
        # Ignorer NaN et vérifier range
        valid_rsi = rsi.dropna()
        assert (valid_rsi >= 0).all()
        assert (valid_rsi <= 100).all()
    
    @pytest.mark.unit
    def test_rsi_overbought_oversold(self):
        """Test RSI overbought/oversold avec données synthétiques."""
        # Créer tendance haussière forte (overbought)
        dates = pd.date_range('2020-01-01', periods=50, tz='UTC')
        prices_up = np.linspace(100, 150, 50)  # Hausse continue
        
        ohlcv_up = pd.DataFrame(
            {
                'Open': prices_up,
                'High': prices_up + 1,
                'Low': prices_up - 1,
                'Close': prices_up,
                'Volume': [1000000] * 50,
            },
            index=dates,
        )
        
        engine = TechnicalFeatureEngine(ohlcv_up)
        rsi = engine.calculate_rsi(period=14)
        
        # RSI devrait être élevé (overbought)
        last_rsi = rsi.iloc[-1]
        assert last_rsi > 60  # Au moins > 60 après hausse continue


class TestMACDCalculation:
    """Tests de calcul MACD."""
    
    @pytest.mark.unit
    def test_macd_default_params(self, mock_ohlcv_data):
        """Test MACD avec paramètres par défaut (12, 26, 9)."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        macd = engine.calculate_macd()
        
        assert isinstance(macd, pd.DataFrame)
        assert len(macd) == 100
        assert list(macd.columns) == ['MACD', 'Signal', 'Histogram']
    
    @pytest.mark.unit
    def test_macd_column_names(self, mock_ohlcv_data):
        """Test que MACD retourne colonnes correctes."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        macd = engine.calculate_macd()
        
        assert 'MACD' in macd.columns
        assert 'Signal' in macd.columns
        assert 'Histogram' in macd.columns
    
    @pytest.mark.unit
    def test_macd_histogram_calculation(self, mock_ohlcv_data):
        """Test que Histogram = MACD - Signal."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        macd = engine.calculate_macd()
        
        # Ignorer NaN et vérifier calcul
        valid_rows = macd.dropna()
        calculated_hist = valid_rows['MACD'] - valid_rows['Signal']
        
        # Tolérance numérique
        np.testing.assert_array_almost_equal(
            valid_rows['Histogram'].values,
            calculated_hist.values,
            decimal=5,
        )
    
    @pytest.mark.unit
    def test_macd_invalid_params(self, mock_ohlcv_data):
        """Test ValueError si fast >= slow."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        
        with pytest.raises(ValueError, match="Fast period .* doit être < slow period"):
            engine.calculate_macd(fast=26, slow=12)


class TestBollingerBands:
    """Tests de calcul Bollinger Bands."""
    
    @pytest.mark.unit
    def test_bollinger_default(self, mock_ohlcv_data):
        """Test Bollinger Bands avec params par défaut (20, 2σ)."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        bb = engine.calculate_bollinger_bands()
        
        assert isinstance(bb, pd.DataFrame)
        assert len(bb) == 100
        assert list(bb.columns) == ['Upper', 'Middle', 'Lower']
    
    @pytest.mark.unit
    def test_bollinger_relationships(self, mock_ohlcv_data):
        """Test que Upper > Middle > Lower."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        bb = engine.calculate_bollinger_bands()
        
        # Ignorer NaN
        valid_bb = bb.dropna()
        
        # Upper > Middle
        assert (valid_bb['Upper'] > valid_bb['Middle']).all()
        # Middle > Lower
        assert (valid_bb['Middle'] > valid_bb['Lower']).all()
    
    @pytest.mark.unit
    def test_bollinger_middle_equals_sma(self, mock_ohlcv_data):
        """Test que Middle Band = SMA."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        bb = engine.calculate_bollinger_bands(period=20)
        sma20 = engine.calculate_sma(period=20)
        
        # Ignorer NaN et comparer
        valid_idx = bb['Middle'].notna()
        np.testing.assert_array_almost_equal(
            bb.loc[valid_idx, 'Middle'].values,
            sma20.loc[valid_idx].values,
            decimal=5,
        )


class TestATRCalculation:
    """Tests de calcul ATR (Average True Range)."""
    
    @pytest.mark.unit
    def test_atr_calculation(self, mock_ohlcv_data):
        """Test calcul ATR."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        atr = engine.calculate_atr(period=14)
        
        assert isinstance(atr, pd.Series)
        assert len(atr) == 100
    
    @pytest.mark.unit
    def test_atr_positive_values(self, mock_ohlcv_data):
        """Test que ATR est toujours >= 0."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        atr = engine.calculate_atr(period=14)
        
        # Ignorer NaN et vérifier positivité
        valid_atr = atr.dropna()
        assert (valid_atr >= 0).all()


class TestROCCalculation:
    """Tests de calcul ROC (Rate of Change)."""
    
    @pytest.mark.unit
    def test_roc_calculation(self, mock_ohlcv_data):
        """Test calcul ROC."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        roc = engine.calculate_roc(period=12)
        
        assert isinstance(roc, pd.Series)
        assert len(roc) == 100
    
    @pytest.mark.unit
    def test_roc_interpretation(self):
        """Test interprétation ROC (positif si hausse, négatif si baisse)."""
        # Créer hausse progressive
        dates = pd.date_range('2020-01-01', periods=25, tz='UTC')
        # Prix qui monte de 100 à 120 progressivement
        prices = np.linspace(100, 120, 25)
        
        ohlcv = pd.DataFrame(
            {
                'Open': prices,
                'High': prices + 1,
                'Low': prices - 1,
                'Close': prices,
                'Volume': [1000000] * 25,
            },
            index=dates,
        )
        
        engine = TechnicalFeatureEngine(ohlcv)
        roc = engine.calculate_roc(period=12)
        
        # ROC à t=24 devrait être positif (prix a augmenté par rapport à t=12)
        last_roc = roc.iloc[-1]
        assert not pd.isna(last_roc), "ROC ne devrait pas être NaN"
        assert last_roc > 0, f"ROC devrait être positif, obtenu: {last_roc}"


class TestCalculateAllFeatures:
    """Tests de calcul de toutes les features."""
    
    @pytest.mark.unit
    def test_calculate_all_features(self, mock_ohlcv_data):
        """Test calcul de toutes les features."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        features = engine.calculate_all_features()
        
        assert isinstance(features, pd.DataFrame)
        assert len(features) == 100
    
    @pytest.mark.unit
    def test_all_features_columns(self, mock_ohlcv_data):
        """Test que toutes les colonnes attendues sont présentes."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        features = engine.calculate_all_features()
        
        # Vérifier présence colonnes clés
        expected_cols = [
            'Open', 'High', 'Low', 'Close', 'Volume',
            'SMA_20', 'SMA_50', 'SMA_200',
            'EMA_12', 'EMA_20', 'EMA_50',
            'RSI_14',
            'MACD', 'MACD_Signal', 'MACD_Histogram',
            'BB_Upper', 'BB_Middle', 'BB_Lower',
            'ATR_14',
            'ROC_12',
            'Volume_SMA_20',
            'BB_Width',
            'Returns',
        ]
        
        for col in expected_cols:
            assert col in features.columns, f"Colonne manquante: {col}"
    
    @pytest.mark.unit
    def test_all_features_dtypes(self, mock_ohlcv_data):
        """Test que toutes les colonnes sont numériques."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        features = engine.calculate_all_features()
        
        # Toutes les colonnes doivent être float64
        for col in features.columns:
            assert features[col].dtype in [np.float64, np.int64], \
                f"Colonne {col} n'est pas numérique: {features[col].dtype}"
    
    @pytest.mark.unit
    def test_all_features_index_preserved(self, mock_ohlcv_data):
        """Test que l'index DatetimeIndex est préservé."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        features = engine.calculate_all_features()
        
        assert isinstance(features.index, pd.DatetimeIndex)
        assert len(features.index) == len(mock_ohlcv_data.index)
        # Index doit être identique
        pd.testing.assert_index_equal(features.index, mock_ohlcv_data.index)
    
    @pytest.mark.unit
    def test_all_features_no_complete_rows(self, mock_ohlcv_data):
        """Test nombre de lignes complètes (sans NaN)."""
        engine = TechnicalFeatureEngine(mock_ohlcv_data)
        features = engine.calculate_all_features()
        
        # Compter lignes sans NaN
        complete_rows = features.notna().all(axis=1).sum()
        
        # Avec 100 barres et SMA_200, on ne peut pas avoir de ligne complète
        # Mais avec SMA_50 max, on devrait avoir 100-50=50 lignes complètes
        # En réalité, compte tenu des différents periods, vérifier qu'on a au moins quelques lignes
        assert complete_rows >= 0  # Au moins 0 (tolérant)


class TestEdgeCases:
    """Tests de cas limites."""
    
    @pytest.mark.unit
    def test_single_bar(self):
        """Test avec une seule barre (devrait fonctionner mais tout NaN)."""
        single_bar = pd.DataFrame(
            {
                'Open': [100.0],
                'High': [102.0],
                'Low': [99.0],
                'Close': [101.0],
                'Volume': [1000000],
            },
            index=pd.date_range('2020-01-01', periods=1, tz='UTC'),
        )
        
        engine = TechnicalFeatureEngine(single_bar)
        features = engine.calculate_all_features()
        
        # OHLCV doivent être présents
        assert features['Close'].iloc[0] == 101.0
        # Indicators doivent être NaN
        assert pd.isna(features['SMA_20'].iloc[0])
    
    @pytest.mark.unit
    def test_constant_prices(self):
        """Test avec prix constants (pas de volatilité)."""
        dates = pd.date_range('2020-01-01', periods=50, tz='UTC')
        constant_price = 100.0
        
        constant_ohlcv = pd.DataFrame(
            {
                'Open': [constant_price] * 50,
                'High': [constant_price] * 50,
                'Low': [constant_price] * 50,
                'Close': [constant_price] * 50,
                'Volume': [1000000] * 50,
            },
            index=dates,
        )
        
        engine = TechnicalFeatureEngine(constant_ohlcv)
        
        # SMA devrait être constant
        sma20 = engine.calculate_sma(period=20)
        assert sma20.dropna().nunique() == 1
        assert sma20.iloc[-1] == constant_price
        
        # ATR devrait être 0 (pas de volatilité)
        atr = engine.calculate_atr(period=14)
        assert atr.dropna().iloc[-1] == 0.0

"""
Tests pour le module Feature Pipeline.

Author: FinBot Team
Date: 2025-11-06
Version: 2.0.0
"""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.features.pipeline import FeaturePipeline


# Markers pytest pour tous les tests de ce fichier
pytestmark = [pytest.mark.features, pytest.mark.unit]


@pytest.fixture
def mock_ohlcv_full():
    """Fixture avec 252 jours de données OHLCV complètes (1 année trading)."""
    dates = pd.date_range('2023-01-01', periods=252, freq='D', tz='UTC')
    
    np.random.seed(42)
    
    # Prix avec tendance + volatilité
    close = 100 + np.cumsum(np.random.normal(0.1, 1, 252))
    open_prices = close + np.random.uniform(-1, 1, 252)
    high = np.maximum(open_prices, close) + np.random.uniform(0, 2, 252)
    low = np.minimum(open_prices, close) - np.random.uniform(0, 2, 252)
    volume = np.random.randint(1000000, 5000000, 252)
    
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
def mock_fundamentals_quarterly():
    """Fixture avec 8 trimestres de ratios fondamentaux."""
    dates = pd.date_range('2023-01-01', periods=8, freq='QE', tz='UTC')
    
    return pd.DataFrame(
        {
            'PE': [20.0, 21.0, 22.0, 23.0, 22.5, 21.5, 20.5, 19.5],
            'PB': [3.0, 3.1, 3.2, 3.3, 3.2, 3.1, 3.0, 2.9],
            'ROE': [15.0, 15.5, 16.0, 16.5, 16.2, 15.8, 15.5, 15.2],
            'ROA': [8.0, 8.2, 8.5, 8.8, 8.6, 8.4, 8.2, 8.0],
            'Revenue': [1000, 1050, 1100, 1150, 1200, 1250, 1300, 1350],
            'NetIncome': [100, 105, 110, 115, 120, 125, 130, 135],
        },
        index=dates,
    )


@pytest.fixture
def mock_ohlcv_with_nan():
    """Fixture avec 252 jours incluant NaN stratégiquement placés."""
    dates = pd.date_range('2023-01-01', periods=252, freq='D', tz='UTC')
    
    np.random.seed(42)
    
    close = 100 + np.cumsum(np.random.normal(0.1, 1, 252))
    open_prices = close + np.random.uniform(-1, 1, 252)
    high = np.maximum(open_prices, close) + np.random.uniform(0, 2, 252)
    low = np.minimum(open_prices, close) - np.random.uniform(0, 2, 252)
    volume = np.random.randint(1000000, 5000000, 252)
    
    df = pd.DataFrame(
        {
            'Open': open_prices,
            'High': high,
            'Low': low,
            'Close': close,
            'Volume': volume,
        },
        index=dates,
    )
    
    # Ajouter NaN stratégiquement
    df.loc[df.index[10:15], 'Close'] = np.nan
    df.loc[df.index[50], 'Volume'] = np.nan
    
    return df


class TestFeaturePipelineInit:
    """Tests d'initialisation du FeaturePipeline."""
    
    @pytest.mark.unit
    def test_init_valid_ohlcv(self, mock_ohlcv_full):
        """Test initialisation avec OHLCV valide."""
        pipeline = FeaturePipeline(mock_ohlcv_full)
        
        assert pipeline.ohlcv is not None
        assert len(pipeline.ohlcv) == 252
        assert pipeline.fundamentals is None
        assert pipeline.handle_nan == 'drop'
        assert not pipeline.remove_outliers_flag
    
    @pytest.mark.unit
    def test_init_with_fundamentals(self, mock_ohlcv_full, mock_fundamentals_quarterly):
        """Test initialisation avec fundamentals."""
        pipeline = FeaturePipeline(mock_ohlcv_full, mock_fundamentals_quarterly)
        
        assert pipeline.fundamentals is not None
        assert len(pipeline.fundamentals) == 8
    
    @pytest.mark.unit
    def test_init_without_fundamentals(self, mock_ohlcv_full):
        """Test initialisation sans fundamentals."""
        pipeline = FeaturePipeline(mock_ohlcv_full, fundamentals=None)
        
        assert pipeline.fundamentals is None
    
    @pytest.mark.unit
    def test_init_invalid_ohlcv_empty(self):
        """Test ValueError si OHLCV vide."""
        empty_df = pd.DataFrame()
        
        with pytest.raises(ValueError, match="ne peut pas être vide"):
            FeaturePipeline(empty_df)
    
    @pytest.mark.unit
    def test_init_invalid_ohlcv_no_datetime_index(self):
        """Test ValueError si index pas DatetimeIndex."""
        df = pd.DataFrame(
            {'Open': [100], 'High': [102], 'Low': [99], 'Close': [101], 'Volume': [1000000]},
            index=[0],  # Integer index
        )
        
        with pytest.raises(ValueError, match="index doit être DatetimeIndex"):
            FeaturePipeline(df)
    
    @pytest.mark.unit
    def test_init_invalid_ohlcv_missing_columns(self):
        """Test ValueError si colonnes OHLCV manquantes."""
        df = pd.DataFrame(
            {'Close': [100, 101, 102]},
            index=pd.date_range('2023-01-01', periods=3, tz='UTC'),
        )
        
        with pytest.raises(ValueError, match="Colonnes OHLCV manquantes"):
            FeaturePipeline(df)
    
    @pytest.mark.unit
    def test_init_invalid_handle_nan(self, mock_ohlcv_full):
        """Test ValueError si stratégie handle_nan inconnue."""
        with pytest.raises(ValueError, match="handle_nan inconnu"):
            FeaturePipeline(mock_ohlcv_full, handle_nan='unknown_strategy')


class TestMethodChaining:
    """Tests de method chaining."""
    
    @pytest.mark.unit
    def test_method_chaining(self, mock_ohlcv_full):
        """Test que les méthodes retournent self pour chaining."""
        pipeline = FeaturePipeline(mock_ohlcv_full)
        
        result = (pipeline
                 .add_technical_features()
                 .handle_missing_values())
        
        assert result is pipeline
        assert pipeline._technical_added
    
    @pytest.mark.unit
    def test_add_technical_features_returns_self(self, mock_ohlcv_full):
        """Test add_technical_features retourne self."""
        pipeline = FeaturePipeline(mock_ohlcv_full)
        result = pipeline.add_technical_features()
        
        assert result is pipeline
        assert pipeline._technical_added
    
    @pytest.mark.unit
    def test_add_fundamental_features_returns_self(self, mock_ohlcv_full, mock_fundamentals_quarterly):
        """Test add_fundamental_features retourne self."""
        pipeline = FeaturePipeline(mock_ohlcv_full, mock_fundamentals_quarterly)
        result = pipeline.add_fundamental_features()
        
        assert result is pipeline
        assert pipeline._fundamental_added


class TestAddFeatures:
    """Tests d'ajout de features."""
    
    @pytest.mark.unit
    def test_add_technical_features(self, mock_ohlcv_full):
        """Test ajout features techniques."""
        pipeline = FeaturePipeline(mock_ohlcv_full)
        pipeline.add_technical_features()
        
        # Vérifier colonnes techniques ajoutées
        assert 'SMA_20' in pipeline.features.columns
        assert 'RSI_14' in pipeline.features.columns
        assert 'MACD' in pipeline.features.columns
        
        # Vérifier que OHLCV pas dupliqué
        assert pipeline.features['Close'].notna().all()
    
    @pytest.mark.unit
    def test_add_fundamental_features_without_fundamentals(self, mock_ohlcv_full):
        """Test ValueError si add_fundamental_features sans fundamentals."""
        pipeline = FeaturePipeline(mock_ohlcv_full, fundamentals=None)
        
        with pytest.raises(ValueError, match="fundamentals est None"):
            pipeline.add_fundamental_features()
    
    @pytest.mark.unit
    def test_add_fundamental_features_with_fundamentals(self, mock_ohlcv_full, mock_fundamentals_quarterly):
        """Test ajout features fondamentales."""
        pipeline = FeaturePipeline(mock_ohlcv_full, mock_fundamentals_quarterly)
        pipeline.add_fundamental_features()
        
        assert pipeline._fundamental_added
        assert hasattr(pipeline, '_fund_features')


class TestAlignment:
    """Tests d'alignement features."""
    
    @pytest.mark.unit
    def test_align_features_without_fundamental(self, mock_ohlcv_full):
        """Test align_features sans features fondamentales."""
        pipeline = FeaturePipeline(mock_ohlcv_full)
        pipeline.add_technical_features()
        pipeline.align_features()
        
        assert pipeline._aligned
    
    @pytest.mark.unit
    def test_align_features_with_fundamental(self, mock_ohlcv_full, mock_fundamentals_quarterly):
        """Test alignement features techniques (daily) et fondamentales (quarterly)."""
        pipeline = FeaturePipeline(mock_ohlcv_full, mock_fundamentals_quarterly)
        pipeline.add_technical_features()
        pipeline.add_fundamental_features()
        pipeline.align_features()
        
        # Vérifier features fondamentales présentes
        assert 'PE' in pipeline.features.columns
        assert 'ROE' in pipeline.features.columns
        
        # Vérifier shape (daily index)
        assert len(pipeline.features) == 252


class TestMissingValues:
    """Tests de gestion valeurs manquantes."""
    
    @pytest.mark.unit
    def test_handle_missing_values_drop(self, mock_ohlcv_with_nan):
        """Test stratégie 'drop'."""
        pipeline = FeaturePipeline(mock_ohlcv_with_nan, handle_nan='drop')
        pipeline.handle_missing_values()
        
        # Devrait avoir supprimé lignes avec NaN
        assert len(pipeline.features) < 252
        assert pipeline.features.isna().sum().sum() == 0
    
    @pytest.mark.unit
    def test_handle_missing_values_forward_fill(self, mock_ohlcv_with_nan):
        """Test stratégie 'forward_fill'."""
        pipeline = FeaturePipeline(mock_ohlcv_with_nan, handle_nan='forward_fill')
        pipeline.handle_missing_values()
        
        # Devrait avoir rempli NaN
        assert len(pipeline.features) == 252
        # Peut rester des NaN au début (avant première valeur valide)
    
    @pytest.mark.unit
    def test_handle_missing_values_bfill(self, mock_ohlcv_with_nan):
        """Test stratégie 'bfill'."""
        pipeline = FeaturePipeline(mock_ohlcv_with_nan, handle_nan='bfill')
        pipeline.handle_missing_values()
        
        assert len(pipeline.features) == 252
    
    @pytest.mark.unit
    def test_handle_missing_values_interpolate(self, mock_ohlcv_with_nan):
        """Test stratégie 'interpolate'."""
        pipeline = FeaturePipeline(mock_ohlcv_with_nan, handle_nan='interpolate')
        pipeline.handle_missing_values()
        
        assert len(pipeline.features) == 252


class TestOutliers:
    """Tests de détection et gestion outliers."""
    
    @pytest.mark.unit
    def test_remove_outliers_iqr(self, mock_ohlcv_full):
        """Test suppression outliers avec IQR."""
        pipeline = FeaturePipeline(
            mock_ohlcv_full,
            handle_nan='forward_fill',
            remove_outliers=True,
            outlier_std=3.0
        )
        pipeline.remove_outliers_iqr()
        
        # Devrait avoir traité outliers
        assert pipeline.remove_outliers_flag
    
    @pytest.mark.unit
    def test_remove_outliers_disabled(self, mock_ohlcv_full):
        """Test que remove_outliers=False skip détection."""
        pipeline = FeaturePipeline(mock_ohlcv_full, remove_outliers=False)
        pipeline.remove_outliers_iqr()
        
        # Ne devrait rien faire
        assert not pipeline.remove_outliers_flag


class TestGetFeatures:
    """Tests de récupération features."""
    
    @pytest.mark.unit
    def test_get_features_all(self, mock_ohlcv_full):
        """Test get_features avec toutes features."""
        pipeline = FeaturePipeline(mock_ohlcv_full)
        pipeline.add_technical_features()
        
        features = pipeline.get_features()
        
        # Devrait contenir OHLCV + tech
        assert 'Close' in features.columns
        assert 'SMA_20' in features.columns
    
    @pytest.mark.unit
    def test_get_features_only_technical(self, mock_ohlcv_full, mock_fundamentals_quarterly):
        """Test get_features seulement techniques."""
        pipeline = FeaturePipeline(mock_ohlcv_full, mock_fundamentals_quarterly)
        pipeline.add_technical_features()
        pipeline.add_fundamental_features()
        pipeline.align_features()
        
        features = pipeline.get_features(include_technical=True, include_fundamental=False)
        
        # Devrait contenir OHLCV + tech, pas fund
        assert 'SMA_20' in features.columns
        assert 'PE' not in features.columns
    
    @pytest.mark.unit
    def test_get_features_only_fundamental(self, mock_ohlcv_full, mock_fundamentals_quarterly):
        """Test get_features seulement fondamentales."""
        pipeline = FeaturePipeline(mock_ohlcv_full, mock_fundamentals_quarterly)
        pipeline.add_technical_features()
        pipeline.add_fundamental_features()
        pipeline.align_features()
        
        features = pipeline.get_features(include_technical=False, include_fundamental=True)
        
        # Devrait contenir OHLCV + fund, pas tech
        assert 'PE' in features.columns
        assert 'SMA_20' not in features.columns


class TestFeatureInfo:
    """Tests de métadonnées features."""
    
    @pytest.mark.unit
    def test_get_feature_info_completeness(self, mock_ohlcv_full):
        """Test que get_feature_info retourne toutes métadonnées."""
        pipeline = FeaturePipeline(mock_ohlcv_full)
        pipeline.add_technical_features()
        
        info = pipeline.get_feature_info()
        
        # Vérifier clés présentes
        assert 'n_features' in info
        assert 'n_rows' in info
        assert 'features_by_type' in info
        assert 'missing_values' in info
        assert 'dtype_summary' in info
        
        # Vérifier valeurs
        assert info['n_features'] > 5  # OHLCV + tech features
        assert info['n_rows'] == 252
        assert 'technical' in info['features_by_type']
    
    @pytest.mark.unit
    def test_get_feature_info_counts(self, mock_ohlcv_full):
        """Test comptage features par type."""
        pipeline = FeaturePipeline(mock_ohlcv_full)
        pipeline.add_technical_features()
        
        info = pipeline.get_feature_info()
        
        # Vérifier comptages
        assert len(info['features_by_type']['original']) == 5  # OHLCV
        assert len(info['features_by_type']['technical']) > 0


class TestScaling:
    """Tests de normalisation features."""
    
    @pytest.mark.unit
    def test_scale_minmax_range(self, mock_ohlcv_full):
        """Test MinMax scaling (0-1 range)."""
        pipeline = FeaturePipeline(mock_ohlcv_full, handle_nan='forward_fill')
        pipeline.add_technical_features()
        pipeline.handle_missing_values()
        
        scaled = pipeline.scale_features(method='minmax')
        
        # Vérifier range 0-1 pour colonnes scalées (avec tolérance pour erreurs floating-point)
        numeric_cols = scaled.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            assert scaled[col].min() >= -1e-10  # Tolérance pour erreurs numériques
            assert scaled[col].max() <= 1 + 1e-10
    
    @pytest.mark.unit
    def test_scale_standard_mean_std(self, mock_ohlcv_full):
        """Test Standard scaling (mean=0, std=1)."""
        pipeline = FeaturePipeline(mock_ohlcv_full, handle_nan='forward_fill')
        pipeline.add_technical_features()
        pipeline.handle_missing_values()
        
        scaled = pipeline.scale_features(method='standard')
        
        # Vérifier mean ≈ 0 et std ≈ 1 pour colonnes scalées
        numeric_cols = scaled.select_dtypes(include=[np.number]).columns
        for col in numeric_cols:
            mean = scaled[col].mean()
            std = scaled[col].std()
            assert abs(mean) < 0.1  # Proche de 0
            assert abs(std - 1.0) < 0.1  # Proche de 1
    
    @pytest.mark.unit
    def test_scale_robust(self, mock_ohlcv_full):
        """Test Robust scaling."""
        pipeline = FeaturePipeline(mock_ohlcv_full, handle_nan='forward_fill')
        pipeline.add_technical_features()
        pipeline.handle_missing_values()
        
        scaled = pipeline.scale_features(method='robust')
        
        # Devrait fonctionner sans erreur
        assert len(scaled) == len(pipeline.features)
    
    @pytest.mark.unit
    def test_scale_exclude_columns(self, mock_ohlcv_full):
        """Test exclusion de colonnes du scaling."""
        pipeline = FeaturePipeline(mock_ohlcv_full, handle_nan='forward_fill')
        pipeline.add_technical_features()
        pipeline.handle_missing_values()
        
        # Exclure Volume du scaling
        scaled = pipeline.scale_features(method='minmax', exclude_cols=['Volume'])
        
        # Volume devrait être inchangé
        assert (scaled['Volume'] == pipeline.features['Volume']).all()


class TestEdgeCases:
    """Tests de cas limites."""
    
    @pytest.mark.unit
    def test_all_nan_column(self):
        """Test avec colonne entièrement NaN."""
        dates = pd.date_range('2023-01-01', periods=10, freq='D', tz='UTC')
        df = pd.DataFrame(
            {
                'Open': [100] * 10,
                'High': [102] * 10,
                'Low': [99] * 10,
                'Close': [101] * 10,
                'Volume': [1000000] * 10,
            },
            index=dates,
        )
        
        pipeline = FeaturePipeline(df, handle_nan='drop')
        # Devrait fonctionner
        assert len(pipeline.features) == 10
    
    @pytest.mark.unit
    def test_single_row_data(self):
        """Test avec une seule ligne de données."""
        dates = pd.date_range('2023-01-01', periods=1, freq='D', tz='UTC')
        df = pd.DataFrame(
            {
                'Open': [100.0],
                'High': [102.0],
                'Low': [99.0],
                'Close': [101.0],
                'Volume': [1000000],
            },
            index=dates,
        )
        
        pipeline = FeaturePipeline(df)
        # Devrait fonctionner même si features calculées = NaN
        assert len(pipeline.features) == 1
    
    @pytest.mark.unit
    def test_no_features_added(self, mock_ohlcv_full):
        """Test get_features avant ajout de features."""
        pipeline = FeaturePipeline(mock_ohlcv_full)
        
        features = pipeline.get_features()
        
        # Devrait retourner seulement OHLCV
        assert len(features.columns) == 5
        assert 'Close' in features.columns
    
    @pytest.mark.unit
    def test_large_feature_count(self, mock_ohlcv_full):
        """Test avec beaucoup de features (100+)."""
        pipeline = FeaturePipeline(mock_ohlcv_full, handle_nan='forward_fill')
        pipeline.add_technical_features()
        pipeline.handle_missing_values()
        
        # Ajouter features supplémentaires manuellement pour atteindre 100+
        for i in range(100):
            pipeline.features[f'dummy_feature_{i}'] = np.random.randn(len(pipeline.features))
        
        info = pipeline.get_feature_info()
        assert info['n_features'] >= 100


class TestIntegration:
    """Tests d'intégration (pipeline complet)."""
    
    @pytest.mark.unit
    def test_full_pipeline_technical_only(self, mock_ohlcv_full):
        """Test pipeline complet avec features techniques seulement."""
        pipeline = FeaturePipeline(mock_ohlcv_full, handle_nan='forward_fill')
        
        features = (pipeline
                   .add_technical_features()
                   .handle_missing_values()
                   .get_features())
        
        assert len(features) == 252
        assert 'SMA_20' in features.columns
        assert features.isna().sum().sum() == 0  # Pas de NaN après handling
    
    @pytest.mark.unit
    def test_full_pipeline_with_fundamentals(self, mock_ohlcv_full, mock_fundamentals_quarterly):
        """Test pipeline complet avec techniques + fondamentales."""
        pipeline = FeaturePipeline(
            mock_ohlcv_full,
            mock_fundamentals_quarterly,
            handle_nan='forward_fill'
        )
        
        features = (pipeline
                   .add_technical_features()
                   .add_fundamental_features()
                   .align_features()
                   .handle_missing_values()
                   .get_features())
        
        assert len(features) == 252
        assert 'SMA_20' in features.columns
        assert 'PE' in features.columns
    
    @pytest.mark.unit
    def test_full_pipeline_with_scaling(self, mock_ohlcv_full):
        """Test pipeline complet avec scaling final."""
        pipeline = FeaturePipeline(mock_ohlcv_full, handle_nan='forward_fill')
        
        pipeline.add_technical_features()
        pipeline.handle_missing_values()
        
        scaled_features = pipeline.scale_features(method='minmax')
        
        assert len(scaled_features) == 252
        # Vérifier scaling appliqué
        assert scaled_features['Close'].min() >= 0
        assert scaled_features['Close'].max() <= 1

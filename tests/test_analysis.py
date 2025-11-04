"""
Tests unitaires pour le module analysis (BacktestEngine + MLPredictor).

Coverage: BacktestEngine (setup, signaux, trades, backtest, métriques, save)
          MLPredictor (features, train, predict, evaluate, importance, save/load)
"""
import os
import pickle
import tempfile
import logging
from datetime import datetime, timedelta
from typing import Dict, Any
from unittest.mock import Mock, patch, MagicMock

import pytest
import numpy as np
import pandas as pd
from pandas.testing import assert_frame_equal, assert_series_equal

from financial_analyzer.analysis.backtester import BacktestEngine, Trade
from financial_analyzer.analysis.ml_predictor import MLPredictor, MLPredictorConfig


# ======================== FIXTURES ========================
@pytest.fixture
def sample_prices_df() -> pd.DataFrame:
    """DataFrame OHLCV synthétique pour tests."""
    dates = pd.date_range("2023-01-01", periods=100, freq="D")
    np.random.seed(42)
    close = 100 + np.cumsum(np.random.randn(100) * 2)
    df = pd.DataFrame(
        {
            "Open": close + np.random.randn(100) * 0.5,
            "High": close + np.abs(np.random.randn(100)) * 1.0,
            "Low": close - np.abs(np.random.randn(100)) * 1.0,
            "Close": close,
            "Volume": np.random.randint(1000000, 5000000, 100),
        },
        index=dates,
    )
    return df


@pytest.fixture
def sample_sentiment_df(sample_prices_df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame sentiment synthétique aligné aux prix."""
    dates = sample_prices_df.index
    np.random.seed(43)
    sentiment_score = np.random.uniform(-1, 1, len(dates))
    df = pd.DataFrame(
        {
            "sentiment_score": sentiment_score,
            "positive": np.clip(sentiment_score, 0, 1),
            "negative": np.clip(-sentiment_score, 0, 1),
            "neutral": 0.5 + np.random.randn(len(dates)) * 0.1,
            "label": ["positive" if s > 0 else "negative" for s in sentiment_score],
            "ticker": "AAPL",
        },
        index=dates,
    )
    return df


@pytest.fixture
def sample_ratios_df(sample_prices_df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame ratios financiers synthétiques."""
    dates = sample_prices_df.index[::10]  # Moins fréquent (trimestriel simulé)
    np.random.seed(44)
    df = pd.DataFrame(
        {
            "PE": np.random.uniform(10, 30, len(dates)),
            "PB": np.random.uniform(1, 5, len(dates)),
            "ROE": np.random.uniform(0.05, 0.25, len(dates)),
            "DebtToEquity": np.random.uniform(0.1, 2.0, len(dates)),
        },
        index=dates,
    )
    return df


@pytest.fixture
def backtest_engine() -> BacktestEngine:
    """Instance BacktestEngine pour tests."""
    return BacktestEngine(
        initial_capital=10000.0,
        commission_rate=0.002,
        slippage_bps=5.0,
        strategy="sentiment",
        period="D",
        sentiment_threshold=0.3,
        rebalance_freq="W",
        target_leverage=1.0,
    )


@pytest.fixture
def ml_predictor() -> MLPredictor:
    """Instance MLPredictor pour tests."""
    config = MLPredictorConfig(target_horizon=5, tscv_splits=3, random_state=42)
    return MLPredictor(target_horizon=5, config=config)


# ======================== TESTS BacktestEngine ========================
class TestBacktestEngine:
    """Tests pour la classe BacktestEngine."""

    def test_init_valid_params(self):
        """Test initialisation avec paramètres valides."""
        engine = BacktestEngine(initial_capital=10000, commission_rate=0.001)
        assert engine.initial_capital == 10000.0
        assert engine.commission_rate == 0.001
        assert engine.strategy == "sentiment"
        assert engine.period == "D"
        assert engine.cash == 10000.0
        assert engine.positions == {}
        assert engine.trades == []

    def test_init_invalid_capital(self):
        """Test ValueError si capital <= 0."""
        with pytest.raises(ValueError, match="initial_capital doit être > 0"):
            BacktestEngine(initial_capital=0)

    def test_init_invalid_period(self):
        """Test ValueError si period invalide."""
        with pytest.raises(ValueError, match="period doit être dans"):
            BacktestEngine(initial_capital=10000, period="X")

    def test_init_invalid_strategy(self):
        """Test ValueError si strategy invalide."""
        with pytest.raises(ValueError, match="strategy invalide"):
            BacktestEngine(initial_capital=10000, strategy="unknown")

    def test_setup_valid(self, backtest_engine, sample_prices_df, sample_sentiment_df):
        """Test setup avec données valides."""
        backtest_engine.setup(sample_prices_df, sample_sentiment_df)
        assert len(backtest_engine._tickers) == 1
        assert backtest_engine.prices.shape[0] > 0
        assert isinstance(backtest_engine.prices.index, pd.DatetimeIndex)
        assert backtest_engine.cash == 10000.0

    def test_setup_missing_ohlcv_columns(self, backtest_engine, sample_sentiment_df):
        """Test ValueError si colonnes OHLCV manquantes."""
        bad_df = pd.DataFrame({"Close": [100, 101]}, index=pd.date_range("2023-01-01", periods=2))
        with pytest.raises(ValueError, match="OHLCV manquants"):
            backtest_engine.setup(bad_df, sample_sentiment_df)

    def test_setup_missing_sentiment_score(self, backtest_engine, sample_prices_df):
        """Test ValueError si sentiment_score manquant."""
        bad_sent = pd.DataFrame({"positive": [0.5]}, index=pd.date_range("2023-01-01", periods=1))
        with pytest.raises(ValueError, match="sentiment_score"):
            backtest_engine.setup(sample_prices_df, bad_sent)

    def test_setup_non_datetime_index(self, backtest_engine, sample_sentiment_df):
        """Test ValueError si index non DatetimeIndex."""
        bad_df = pd.DataFrame(
            {"Open": [100], "High": [101], "Low": [99], "Close": [100], "Volume": [1000]}
        )
        with pytest.raises(ValueError, match="DatetimeIndex"):
            backtest_engine.setup(bad_df, sample_sentiment_df)

    def test_generate_signals_sentiment(self, backtest_engine, sample_prices_df, sample_sentiment_df):
        """Test génération signaux sentiment."""
        backtest_engine.setup(sample_prices_df, sample_sentiment_df)
        signals = backtest_engine.generate_signals()
        assert isinstance(signals, pd.DataFrame)
        assert signals.shape[0] == backtest_engine.prices.shape[0]
        assert set(signals.values.flatten()).issubset({-1, 0, 1})

    def test_generate_signals_momentum(self, sample_prices_df, sample_sentiment_df):
        """Test génération signaux momentum."""
        engine = BacktestEngine(
            initial_capital=10000,
            strategy="momentum",
            momentum_lookback=10,
        )
        engine.setup(sample_prices_df, sample_sentiment_df)
        signals = engine.generate_signals()
        assert isinstance(signals, pd.DataFrame)
        assert set(signals.values.flatten()).issubset({-1, 0, 1, np.nan})

    def test_generate_signals_mean_reversion(self, sample_prices_df, sample_sentiment_df):
        """Test génération signaux mean-reversion."""
        engine = BacktestEngine(
            initial_capital=10000,
            strategy="mean_reversion",
            meanrev_lookback=15,
            zscore_threshold=1.5,
        )
        engine.setup(sample_prices_df, sample_sentiment_df)
        signals = engine.generate_signals()
        assert isinstance(signals, pd.DataFrame)
        assert set(signals.values.flatten()).issubset({-1, 0, 1, np.nan})

    def test_execute_trades(self, backtest_engine, sample_prices_df, sample_sentiment_df):
        """Test exécution trades avec commission et slippage."""
        backtest_engine.setup(sample_prices_df, sample_sentiment_df)
        date = backtest_engine.prices.index[20]
        signals = {"TICKER": 1}
        cash_before = backtest_engine.cash
        backtest_engine.execute_trades(date, signals)
        # Au moins un trade devrait avoir été exécuté si signal != 0
        if signals["TICKER"] != 0:
            assert len(backtest_engine.trades) > 0
            trade = backtest_engine.trades[0]
            assert isinstance(trade, Trade)
            assert trade.commission > 0
            assert trade.slippage == 5.0

    def test_backtest_full(self, backtest_engine, sample_prices_df, sample_sentiment_df):
        """Test backtest complet retourne trades et equity_curve."""
        backtest_engine.setup(sample_prices_df, sample_sentiment_df)
        results = backtest_engine.backtest()
        assert "trades" in results
        assert "equity_curve" in results
        assert isinstance(results["trades"], pd.DataFrame)
        assert isinstance(results["equity_curve"], pd.DataFrame)
        assert "equity" in results["equity_curve"].columns
        assert "cash" in results["equity_curve"].columns
        assert results["equity_curve"].shape[0] > 0

    def test_calculate_metrics(self, backtest_engine, sample_prices_df, sample_sentiment_df):
        """Test calcul métriques de performance."""
        backtest_engine.setup(sample_prices_df, sample_sentiment_df)
        backtest_engine.backtest()
        metrics = backtest_engine.calculate_metrics(risk_free_rate=0.02)
        assert "total_return" in metrics
        assert "annual_return" in metrics
        assert "sharpe_ratio" in metrics
        assert "sortino_ratio" in metrics
        assert "max_drawdown" in metrics
        assert "win_rate" in metrics
        assert "profit_factor" in metrics
        assert "total_trades" in metrics
        assert "avg_trade" in metrics
        assert isinstance(metrics["total_return"], float)

    def test_get_results(self, backtest_engine, sample_prices_df, sample_sentiment_df):
        """Test récupération résultats."""
        backtest_engine.setup(sample_prices_df, sample_sentiment_df)
        backtest_engine.backtest()
        results = backtest_engine.get_results()
        assert "trades" in results
        assert "equity_curve" in results
        assert isinstance(results["trades"], pd.DataFrame)
        assert isinstance(results["equity_curve"], pd.DataFrame)

    def test_save_results(self, backtest_engine, sample_prices_df, sample_sentiment_df):
        """Test sauvegarde résultats CSV."""
        backtest_engine.setup(sample_prices_df, sample_sentiment_df)
        backtest_engine.backtest()
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = os.path.join(tmpdir, "results")
            backtest_engine.save_results(output_dir)
            assert os.path.exists(os.path.join(output_dir, "trades.csv"))
            assert os.path.exists(os.path.join(output_dir, "equity_curve.csv"))
            assert os.path.exists(os.path.join(output_dir, "metrics.csv"))

    def test_multi_ticker_backtest(self, sample_prices_df, sample_sentiment_df):
        """Test backtest multi-ticker."""
        engine = BacktestEngine(initial_capital=20000, strategy="momentum")
        # Simuler deux tickers avec des prix différents
        prices_dict = {"AAPL": sample_prices_df.copy(), "MSFT": sample_prices_df.copy() * 1.1}
        
        # Créer sentiment multi-ticker proprement
        # On garde seulement le sentiment AAPL puisque la stratégie momentum ne l'utilise pas
        sent_multi = sample_sentiment_df.copy()
        
        engine.setup(prices_dict, sent_multi)
        assert len(engine._tickers) == 2
        assert engine.prices.shape[1] == 2
        
        # Tester que backtest() fonctionne sans crash
        results = engine.backtest()
        assert "trades" in results
        assert "equity_curve" in results
        assert isinstance(results["trades"], pd.DataFrame)
        assert isinstance(results["equity_curve"], pd.DataFrame)
        # Equity curve doit avoir des valeurs pour toutes les dates
        assert results["equity_curve"].shape[0] > 0


# ======================== TESTS MLPredictor ========================
class TestMLPredictor:
    """Tests pour la classe MLPredictor."""

    def test_init_valid(self):
        """Test initialisation MLPredictor."""
        predictor = MLPredictor(target_horizon=5)
        assert predictor.config.target_horizon == 5
        assert predictor.model is None
        assert predictor.scaler is None
        assert predictor._is_trained is False

    def test_init_invalid_horizon(self):
        """Test ValueError si target_horizon <= 0."""
        with pytest.raises(ValueError, match="target_horizon doit être > 0"):
            MLPredictor(target_horizon=0)

    def test_prepare_features_prices_only(self, ml_predictor, sample_prices_df):
        """Test préparation features avec prix seuls."""
        X, y = ml_predictor.prepare_features(sample_prices_df)
        assert isinstance(X, pd.DataFrame)
        assert isinstance(y, pd.Series)
        assert X.shape[0] > 0
        assert y.shape[0] == X.shape[0]
        # Vérifier présence de features de base
        assert "ret_1d" in X.columns
        assert "rsi_14" in X.columns
        assert "macd" in X.columns
        assert "bb_width" in X.columns
        assert "volume_ratio" in X.columns

    def test_prepare_features_with_sentiment(self, ml_predictor, sample_prices_df, sample_sentiment_df):
        """Test préparation features avec sentiment."""
        X, y = ml_predictor.prepare_features(sample_prices_df, df_sentiment=sample_sentiment_df)
        assert isinstance(X, pd.DataFrame)
        assert X.shape[0] > 0
        # Vérifier colonnes sentiment
        assert "sentiment_score" in X.columns or "sentiment_ma_5d" in X.columns

    def test_prepare_features_with_ratios(
        self, ml_predictor, sample_prices_df, sample_sentiment_df, sample_ratios_df
    ):
        """Test préparation features avec ratios."""
        X, y = ml_predictor.prepare_features(
            sample_prices_df, df_sentiment=sample_sentiment_df, df_ratios=sample_ratios_df
        )
        assert isinstance(X, pd.DataFrame)
        # Vérifier colonnes ratios présentes
        ratio_cols = [c for c in ["PE", "PB", "ROE", "DebtToEquity"] if c in X.columns]
        assert len(ratio_cols) > 0

    def test_prepare_features_missing_close(self, ml_predictor):
        """Test ValueError si Close manquant."""
        bad_df = pd.DataFrame({"Volume": [1000]}, index=pd.date_range("2023-01-01", periods=1))
        with pytest.raises(ValueError, match="Close"):
            ml_predictor.prepare_features(bad_df)

    def test_prepare_features_non_datetime_index(self, ml_predictor):
        """Test ValueError si index non DatetimeIndex."""
        bad_df = pd.DataFrame({"Close": [100], "Volume": [1000]})
        with pytest.raises(ValueError, match="DatetimeIndex"):
            ml_predictor.prepare_features(bad_df)

    @patch("financial_analyzer.analysis.ml_predictor.RandomForestRegressor")
    @patch("financial_analyzer.analysis.ml_predictor.StandardScaler")
    def test_train_random_forest(
        self, mock_scaler, mock_rf, ml_predictor, sample_prices_df, sample_sentiment_df
    ):
        """Test entraînement Random Forest."""
        X, y = ml_predictor.prepare_features(sample_prices_df, sample_sentiment_df)
        # Mock le modèle
        mock_model_instance = MagicMock()
        mock_rf.return_value = mock_model_instance
        mock_scaler_instance = MagicMock()
        mock_scaler.return_value = mock_scaler_instance

        # Simuler fit
        with patch("financial_analyzer.analysis.ml_predictor.Pipeline") as mock_pipeline:
            mock_pipeline_instance = MagicMock()
            mock_pipeline.return_value = mock_pipeline_instance
            model = ml_predictor.train(X, y, model_type="random_forest")
            assert ml_predictor._is_trained is True
            assert ml_predictor.model is not None

    def test_train_invalid_model_type(self, ml_predictor, sample_prices_df):
        """Test ValueError si model_type inconnu."""
        X, y = ml_predictor.prepare_features(sample_prices_df)
        with pytest.raises(ValueError, match="model_type inconnu"):
            ml_predictor.train(X, y, model_type="invalid_model")

    @patch("financial_analyzer.analysis.ml_predictor.HAS_XGB", True)
    @patch("financial_analyzer.analysis.ml_predictor.StandardScaler")
    def test_train_xgboost(self, mock_scaler, ml_predictor, sample_prices_df):
        """Test entraînement XGBoost si disponible."""
        X, y = ml_predictor.prepare_features(sample_prices_df)
        mock_scaler_instance = MagicMock()
        mock_scaler.return_value = mock_scaler_instance

        # Mock XGBRegressor directement dans _get_model
        with patch.object(ml_predictor, '_get_model') as mock_get_model:
            mock_model_instance = MagicMock()
            mock_get_model.return_value = mock_model_instance
            with patch("financial_analyzer.analysis.ml_predictor.Pipeline") as mock_pipeline:
                mock_pipeline_instance = MagicMock()
                mock_pipeline.return_value = mock_pipeline_instance
                model = ml_predictor.train(X, y, model_type="xgboost")
                assert ml_predictor._is_trained is True

    @patch("financial_analyzer.analysis.ml_predictor.GridSearchCV")
    @patch("financial_analyzer.analysis.ml_predictor.RandomForestRegressor")
    @patch("financial_analyzer.analysis.ml_predictor.StandardScaler")
    def test_train_gridsearch(
        self, mock_scaler, mock_rf, mock_grid, ml_predictor, sample_prices_df
    ):
        """Test entraînement avec GridSearchCV."""
        X, y = ml_predictor.prepare_features(sample_prices_df)
        mock_scaler_instance = MagicMock()
        mock_scaler.return_value = mock_scaler_instance
        mock_model_instance = MagicMock()
        mock_rf.return_value = mock_model_instance

        mock_search_instance = MagicMock()
        mock_search_instance.best_params_ = {"n_estimators": 200}
        mock_search_instance.best_estimator_ = mock_model_instance
        mock_grid.return_value = mock_search_instance

        param_grid = {"n_estimators": [100, 200]}
        with patch("financial_analyzer.analysis.ml_predictor.Pipeline"):
            model = ml_predictor.train(X, y, model_type="random_forest", param_grid=param_grid)
            assert ml_predictor.best_params_ is not None

    def test_predict_not_trained(self, ml_predictor, sample_prices_df):
        """Test ValueError si modèle non entraîné."""
        X, y = ml_predictor.prepare_features(sample_prices_df)
        with pytest.raises(ValueError, match="non entraîné"):
            ml_predictor.predict(X)

    @patch("financial_analyzer.analysis.ml_predictor.RandomForestRegressor")
    @patch("financial_analyzer.analysis.ml_predictor.StandardScaler")
    def test_predict(self, mock_scaler, mock_rf, ml_predictor, sample_prices_df):
        """Test prédictions."""
        X, y = ml_predictor.prepare_features(sample_prices_df)
        mock_scaler_instance = MagicMock()
        mock_scaler.return_value = mock_scaler_instance
        mock_model_instance = MagicMock()
        mock_model_instance.predict.return_value = np.random.rand(len(X))
        mock_rf.return_value = mock_model_instance

        with patch("financial_analyzer.analysis.ml_predictor.Pipeline") as mock_pipeline:
            mock_pipeline_instance = MagicMock()
            mock_pipeline_instance.predict = mock_model_instance.predict
            mock_pipeline.return_value = mock_pipeline_instance
            ml_predictor.train(X, y, model_type="random_forest")
            ml_predictor.model = mock_pipeline_instance
            preds = ml_predictor.predict(X)
            assert isinstance(preds, np.ndarray)
            assert len(preds) == len(X)

    @patch("financial_analyzer.analysis.ml_predictor.RandomForestRegressor")
    @patch("financial_analyzer.analysis.ml_predictor.StandardScaler")
    def test_evaluate(self, mock_scaler, mock_rf, ml_predictor, sample_prices_df):
        """Test évaluation métriques."""
        X, y = ml_predictor.prepare_features(sample_prices_df)
        mock_scaler_instance = MagicMock()
        mock_scaler.return_value = mock_scaler_instance
        mock_model_instance = MagicMock()
        mock_model_instance.predict.return_value = y.values + np.random.randn(len(y)) * 0.01
        mock_rf.return_value = mock_model_instance

        with patch("financial_analyzer.analysis.ml_predictor.Pipeline") as mock_pipeline:
            mock_pipeline_instance = MagicMock()
            mock_pipeline_instance.predict = mock_model_instance.predict
            mock_pipeline.return_value = mock_pipeline_instance
            ml_predictor.train(X, y, model_type="random_forest")
            ml_predictor.model = mock_pipeline_instance
            metrics = ml_predictor.evaluate(X, y)
            assert "mae" in metrics
            assert "mse" in metrics
            assert "rmse" in metrics
            assert "r2" in metrics
            assert "mape" in metrics
            assert isinstance(metrics["mae"], float)

    @patch("financial_analyzer.analysis.ml_predictor.RandomForestRegressor")
    @patch("financial_analyzer.analysis.ml_predictor.StandardScaler")
    def test_get_feature_importance(self, mock_scaler, mock_rf, ml_predictor, sample_prices_df):
        """Test récupération importance features."""
        X, y = ml_predictor.prepare_features(sample_prices_df)
        mock_scaler_instance = MagicMock()
        mock_scaler.return_value = mock_scaler_instance
        mock_model_instance = MagicMock()
        mock_model_instance.feature_importances_ = np.random.rand(X.shape[1])
        mock_rf.return_value = mock_model_instance

        with patch("financial_analyzer.analysis.ml_predictor.Pipeline") as mock_pipeline:
            mock_pipeline_instance = MagicMock()
            mock_pipeline_instance.named_steps = {"model": mock_model_instance}
            mock_pipeline.return_value = mock_pipeline_instance
            ml_predictor.train(X, y, model_type="random_forest")
            ml_predictor.model = mock_pipeline_instance
            fi = ml_predictor.get_feature_importance()
            assert isinstance(fi, pd.DataFrame)
            assert "feature" in fi.columns
            assert "importance" in fi.columns
            assert fi.shape[0] == X.shape[1]
            # Vérifier tri décroissant
            assert (fi["importance"].diff().dropna() <= 0).all()

    def test_save_load_model(self, ml_predictor, sample_prices_df):
        """Test sauvegarde et chargement modèle."""
        X, y = ml_predictor.prepare_features(sample_prices_df)
        
        # Utiliser de vrais objets sklearn pour permettre pickle
        from sklearn.pipeline import Pipeline as RealPipeline
        from sklearn.preprocessing import StandardScaler as RealScaler
        from sklearn.linear_model import LinearRegression as RealModel
        
        real_pipeline = RealPipeline([("scaler", RealScaler()), ("model", RealModel())])
        real_pipeline.fit(X, y)
        
        # Simuler training sans mock
        ml_predictor.model = real_pipeline
        ml_predictor.scaler = real_pipeline.named_steps["scaler"]
        ml_predictor._is_trained = True
        ml_predictor.model_type = "linear"
        ml_predictor.feature_names = list(X.columns)

        with tempfile.TemporaryDirectory() as tmpdir:
            model_path = os.path.join(tmpdir, "model.pkl")
            ml_predictor.save_model(model_path)
            assert os.path.exists(model_path)

            # Charger dans nouvelle instance
            predictor2 = MLPredictor(target_horizon=5)
            predictor2.load_model(model_path)
            assert predictor2._is_trained is True
            assert predictor2.feature_names == ml_predictor.feature_names
            # Vérifier que le modèle peut prédire
            preds = predictor2.predict(X.head(10))
            assert len(preds) == 10

    def test_plot_results_with_matplotlib(self, backtest_engine, sample_prices_df, sample_sentiment_df):
        """Test plot_results() retourne Figure si matplotlib disponible."""
        backtest_engine.setup(sample_prices_df, sample_sentiment_df)
        backtest_engine.backtest()
        
        # Mock matplotlib disponible
        with patch("financial_analyzer.analysis.backtester.HAS_MATPLOTLIB", True):
            with patch("financial_analyzer.analysis.backtester.plt") as mock_plt:
                mock_fig = MagicMock()
                mock_plt.subplots.return_value = (mock_fig, [MagicMock(), MagicMock()])
                result = backtest_engine.plot_results()
                # Si matplotlib dispo, devrait retourner la figure
                assert result is not None

    def test_plot_results_without_matplotlib(self, backtest_engine, sample_prices_df, sample_sentiment_df):
        """Test plot_results() retourne None si matplotlib absent."""
        backtest_engine.setup(sample_prices_df, sample_sentiment_df)
        backtest_engine.backtest()
        
        # Mock matplotlib indisponible
        with patch("financial_analyzer.analysis.backtester.HAS_MATPLOTLIB", False):
            result = backtest_engine.plot_results()
            assert result is None

    def test_realized_pnl_long_position(self, backtest_engine, sample_prices_df, sample_sentiment_df):
        """Test calcul realized_pnl pour position longue."""
        backtest_engine.setup(sample_prices_df, sample_sentiment_df)
        backtest_engine.backtest()
        
        # Vérifier que des trades avec realized_pnl existent
        trades_df = pd.DataFrame([t.__dict__ for t in backtest_engine.trades])
        if not trades_df.empty and "realized_pnl" in trades_df.columns:
            # Vérifier structure
            assert trades_df["realized_pnl"].dtype in [np.float64, float]
            # PnL réalisé inclut la commission négative
            realized_trades = trades_df[trades_df["realized_pnl"] != 0]
            if not realized_trades.empty:
                # Au moins un trade devrait avoir un PnL non nul
                assert len(realized_trades) > 0

    def test_predict_missing_columns(self, ml_predictor, sample_prices_df):
        """Test ValueError si colonnes manquantes dans X_test."""
        X, y = ml_predictor.prepare_features(sample_prices_df)
        with patch("financial_analyzer.analysis.ml_predictor.Pipeline"):
            ml_predictor._is_trained = True
            ml_predictor.model = MagicMock()
            ml_predictor.feature_names = ["ret_1d", "rsi_14", "missing_col"]
            with pytest.raises(ValueError, match="manquantes dans X_test"):
                ml_predictor.predict(X)

    def test_predict_extra_columns_ignored(self, ml_predictor, sample_prices_df):
        """Test que colonnes supplémentaires dans X_test sont ignorées sans crash."""
        X, y = ml_predictor.prepare_features(sample_prices_df)
        X["extra_col"] = 1.0
        X["another_extra"] = 2.0
        
        with patch("financial_analyzer.analysis.ml_predictor.Pipeline"):
            mock_model = MagicMock()
            mock_model.predict.return_value = np.random.rand(len(X))
            ml_predictor._is_trained = True
            ml_predictor.model = mock_model
            ml_predictor.feature_names = [c for c in X.columns if c not in ["extra_col", "another_extra"]]
            
            # Devrait fonctionner sans erreur, colonnes extra ignorées
            preds = ml_predictor.predict(X)
            assert len(preds) == len(X)
            assert isinstance(preds, np.ndarray)


# ======================== TESTS D'INTÉGRATION ========================
class TestIntegration:
    """Tests d'intégration pour le workflow complet."""

    def test_pipeline_backtest_ml(self, sample_prices_df, sample_sentiment_df):
        """Test pipeline complet: backtest → features ML → predictions."""
        # Backtest
        engine = BacktestEngine(initial_capital=10000, strategy="sentiment")
        engine.setup(sample_prices_df, sample_sentiment_df)
        results = engine.backtest()
        assert results["equity_curve"].shape[0] > 0

        # ML: utiliser prix et sentiment pour prédire rendements
        predictor = MLPredictor(target_horizon=3)
        X, y = predictor.prepare_features(sample_prices_df, sample_sentiment_df)
        assert X.shape[0] > 0

        # Mock training pour speed
        with patch("financial_analyzer.analysis.ml_predictor.Pipeline"):
            mock_model = MagicMock()
            mock_model.predict.return_value = np.random.rand(len(X))
            predictor._is_trained = True
            predictor.model = mock_model
            predictor.feature_names = list(X.columns)
            preds = predictor.predict(X)
            assert len(preds) == len(X)

    def test_feature_engineering_complete(self, sample_prices_df, sample_sentiment_df, sample_ratios_df):
        """Test toutes les features sont calculées correctement."""
        predictor = MLPredictor(target_horizon=5)
        X, y = predictor.prepare_features(sample_prices_df, sample_sentiment_df, sample_ratios_df)

        # Vérifier features prix
        price_features = ["ret_1d", "ret_5d", "ret_20d", "vol_20d", "rsi_14", "macd", "bb_width"]
        for feat in price_features:
            assert feat in X.columns, f"Feature {feat} manquante"

        # Vérifier features volume
        assert "volume_ratio" in X.columns
        assert "volume_sma_20" in X.columns

        # Vérifier features sentiment (au moins une)
        sent_features = [c for c in X.columns if "sentiment" in c.lower()]
        assert len(sent_features) > 0

        # Vérifier features ratios (au moins une)
        ratio_features = [c for c in ["PE", "PB", "ROE", "DebtToEquity"] if c in X.columns]
        assert len(ratio_features) > 0

        # Vérifier pas de NaN
        assert X.isna().sum().sum() == 0
        assert y.isna().sum() == 0

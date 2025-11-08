"""Tests for LSTMPredictor."""

from unittest.mock import MagicMock, patch, Mock
import sys
import numpy as np
import pandas as pd
import pytest

# Mock TensorFlow before importing predictor
sys.modules['tensorflow'] = MagicMock()
sys.modules['tensorflow.keras'] = MagicMock()
sys.modules['tensorflow.keras.layers'] = MagicMock()
sys.modules['tensorflow.keras.models'] = MagicMock()
sys.modules['tensorflow.keras.callbacks'] = MagicMock()

from financial_analyzer.deep_learning import LSTMPredictor


@pytest.fixture
def returns_df():
    np.random.seed(42)
    data = np.random.randn(200, 3) / 100.0
    return pd.DataFrame(data, columns=["A", "B", "C"])


def test_init_default():
    pred = LSTMPredictor()
    assert pred.lookback_window == 60
    assert pred.forecast_horizon == 5
    assert pred.lstm_units == 64
    assert pred.bidirectional is True
    assert pred.use_gru is False


def test_init_gru_mode():
    pred = LSTMPredictor(use_gru=True)
    assert pred.use_gru is True


def test_init_bidirectional_false():
    pred = LSTMPredictor(bidirectional=False)
    assert pred.bidirectional is False


def test_init_invalid_lookback():
    with pytest.raises(ValueError):
        LSTMPredictor(lookback_window=0)


def test_init_invalid_dropout():
    with pytest.raises(ValueError):
        LSTMPredictor(dropout=1.5)


@patch("financial_analyzer.deep_learning.lstm_predictor.layers")
@patch("financial_analyzer.deep_learning.lstm_predictor.models")
def test_build_model_lstm(mock_models, mock_layers, returns_df):
    pred = LSTMPredictor(use_gru=False, bidirectional=False, use_attention=False)
    mock_model = MagicMock()
    mock_models.Model.return_value = mock_model
    model = pred.build_model(n_assets=3)
    assert model is not None


@patch("financial_analyzer.deep_learning.lstm_predictor.layers")
@patch("financial_analyzer.deep_learning.lstm_predictor.models")
def test_build_model_gru(mock_models, mock_layers):
    pred = LSTMPredictor(use_gru=True)
    mock_model = MagicMock()
    mock_models.Model.return_value = mock_model
    model = pred.build_model(n_assets=4)
    assert model is not None


def test_create_sequences(returns_df):
    pred = LSTMPredictor(lookback_window=20, forecast_horizon=5)
    data = returns_df.values
    X, y = pred.create_sequences(data)
    assert X.shape[1] == 20
    assert X.shape[2] == 3
    assert y.shape[1] == 3
    assert len(X) == len(y)


@patch("financial_analyzer.deep_learning.lstm_predictor.MinMaxScaler")
def test_prepare_data(mock_scaler, returns_df):
    mock_scaler.return_value = MagicMock()
    mock_scaler.return_value.fit.return_value = None
    mock_scaler.return_value.transform.return_value = returns_df.values
    pred = LSTMPredictor(lookback_window=20, forecast_horizon=5)
    splits = pred.prepare_data(returns_df, train_size=0.6, val_size=0.2)
    assert 'X_train' in splits
    assert 'y_train' in splits
    assert 'X_val' in splits
    assert 'y_val' in splits
    assert 'X_test' in splits
    assert 'y_test' in splits
    assert splits['X_train'].shape[1] == 20


@patch("financial_analyzer.deep_learning.lstm_predictor.MinMaxScaler")
@patch("financial_analyzer.deep_learning.lstm_predictor.layers")
@patch("financial_analyzer.deep_learning.lstm_predictor.models")
@patch("financial_analyzer.deep_learning.lstm_predictor.keras")
def test_fit_basic(mock_keras, mock_models, mock_layers, mock_scaler, returns_df):
    mock_scaler.return_value = MagicMock()
    mock_scaler.return_value.fit.return_value = None
    mock_scaler.return_value.transform.return_value = returns_df.values
    pred = LSTMPredictor(lookback_window=20, forecast_horizon=5)
    mock_model = MagicMock()
    mock_models.Model.return_value = mock_model
    mock_model.fit.return_value = MagicMock(history={'loss': [0.1, 0.08]})
    pred.build_model(n_assets=3)

    splits = pred.prepare_data(returns_df, train_size=0.7, val_size=0.15)
    history = pred.fit(splits['X_train'], splits['y_train'], epochs=2)
    assert 'loss' in history


@patch("financial_analyzer.deep_learning.lstm_predictor.MinMaxScaler")
@patch("financial_analyzer.deep_learning.lstm_predictor.layers")
@patch("financial_analyzer.deep_learning.lstm_predictor.models")
@patch("financial_analyzer.deep_learning.lstm_predictor.keras")
def test_predict(mock_keras, mock_models, mock_layers, mock_scaler, returns_df):
    mock_scaler_instance = MagicMock()
    mock_scaler.return_value = mock_scaler_instance
    mock_scaler_instance.fit.return_value = None
    mock_scaler_instance.transform.return_value = returns_df.values
    
    pred = LSTMPredictor(lookback_window=20, forecast_horizon=5)
    mock_model = MagicMock()
    mock_models.Model.return_value = mock_model
    
    splits = pred.prepare_data(returns_df, train_size=0.7, val_size=0.15)
    n_test_samples = splits['X_test'].shape[0]
    
    # Mock prediction to return correct shape
    mock_model.predict.return_value = np.random.randn(n_test_samples, 3)
    mock_scaler_instance.inverse_transform.return_value = np.random.randn(n_test_samples, 3)
    
    pred.build_model(n_assets=3)
    predictions = pred.predict(splits['X_test'])
    assert predictions.shape[0] == n_test_samples


def test_attention_layer_flag():
    pred = LSTMPredictor(use_attention=True)
    assert pred.use_attention is True

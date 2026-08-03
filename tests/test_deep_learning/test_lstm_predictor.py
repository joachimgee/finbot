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

# Retire les stubs de sys.modules : le module predictor garde ses references
# aux MagicMock lies a l'import ci-dessus, mais un faux tensorflow laisse dans
# sys.modules (sans __spec__) casse la collection des autres modules de tests
# (transformers appelle find_spec('tensorflow')).
for _m in [m for m in sys.modules if m == 'tensorflow' or m.startswith('tensorflow.')]:
    del sys.modules[_m]


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
    mock_model.fit.return_value = MagicMock(history={'loss': [0.1, 0.08], 'mae': [0.05, 0.04]})
    pred.build_model(n_assets=3)

    splits = pred.prepare_data(returns_df, train_size=0.7, val_size=0.15)
    history = pred.fit(splits['X_train'], splits['y_train'], epochs=2)
    assert 'train_loss' in history
    assert 'train_mae' in history
    assert 'epochs_trained' in history


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


# -------------------- Polish Tests -------------------- #

@patch("financial_analyzer.deep_learning.lstm_predictor.MinMaxScaler")
@patch("financial_analyzer.deep_learning.lstm_predictor.layers")
@patch("financial_analyzer.deep_learning.lstm_predictor.models")
@patch("financial_analyzer.deep_learning.lstm_predictor.keras")
def test_enhanced_history_format(mock_keras, mock_models, mock_layers, mock_scaler, returns_df):
    """Test that fit returns enhanced history with train_loss, val_loss, epochs_trained, best_epoch."""
    mock_scaler_instance = MagicMock()
    mock_scaler.return_value = mock_scaler_instance
    mock_scaler_instance.fit.return_value = None
    mock_scaler_instance.transform.return_value = returns_df.values
    
    pred = LSTMPredictor(lookback_window=20, forecast_horizon=5)
    mock_model = MagicMock()
    mock_models.Model.return_value = mock_model
    mock_model.fit.return_value = MagicMock(history={
        'loss': [0.1, 0.08, 0.07],
        'mae': [0.05, 0.04, 0.03],
        'val_loss': [0.12, 0.09, 0.10],
        'val_mae': [0.06, 0.045, 0.05]
    })
    pred.build_model(n_assets=3)
    splits = pred.prepare_data(returns_df, train_size=0.7, val_size=0.15)
    
    history = pred.fit(splits['X_train'], splits['y_train'], splits['X_val'], splits['y_val'], epochs=3)
    
    # Check enhanced format
    assert 'train_loss' in history
    assert 'train_mae' in history
    assert 'val_loss' in history
    assert 'val_mae' in history
    assert 'epochs_trained' in history
    assert 'best_epoch' in history
    assert history['epochs_trained'] == 3
    assert history['best_epoch'] == 2  # Index 1 has lowest val_loss (0.09)


def test_model_summary_logging(caplog):
    """Test that build_model logs model summary."""
    import logging
    caplog.set_level(logging.DEBUG)
    
    pred = LSTMPredictor(lookback_window=20, forecast_horizon=5)
    pred.build_model(n_assets=3)
    
    # Check that either model summary or fallback info was logged
    logs = [record.message for record in caplog.records]
    assert any(('Model architecture' in log) or ('SimpleModel fallback' in log) for log in logs)


@patch("financial_analyzer.deep_learning.lstm_predictor.MinMaxScaler")
@patch("financial_analyzer.deep_learning.lstm_predictor.layers")
@patch("financial_analyzer.deep_learning.lstm_predictor.models")
@patch("financial_analyzer.deep_learning.lstm_predictor.keras")
def test_inverse_scale_predictions(mock_keras, mock_models, mock_layers, mock_scaler, returns_df):
    """Test inverse_scale_predictions helper method."""
    mock_scaler_instance = MagicMock()
    mock_scaler.return_value = mock_scaler_instance
    mock_scaler_instance.fit.return_value = None
    mock_scaler_instance.transform.return_value = returns_df.values
    
    pred = LSTMPredictor(lookback_window=20, forecast_horizon=5)
    mock_model = MagicMock()
    mock_models.Model.return_value = mock_model
    pred.build_model(n_assets=3)
    
    splits = pred.prepare_data(returns_df, train_size=0.7, val_size=0.15)
    
    # Mock predictions
    scaled_preds = np.array([[0.1, 0.2, -0.1], [0.05, 0.15, -0.05]])
    real_preds = np.array([[0.01, 0.02, -0.01], [0.005, 0.015, -0.005]])
    mock_scaler_instance.inverse_transform.return_value = real_preds
    
    result = pred.inverse_scale_predictions(scaled_preds)
    
    mock_scaler_instance.inverse_transform.assert_called_once()
    np.testing.assert_array_equal(result, real_preds)


def test_inverse_scale_predictions_without_scaler():
    """Test that inverse_scale_predictions raises error if scaler not fitted."""
    pred = LSTMPredictor(lookback_window=20, forecast_horizon=5)
    pred.build_model(n_assets=3)
    
    with pytest.raises(ValueError, match="Scaler not fitted"):
        pred.inverse_scale_predictions(np.array([[0.1, 0.2, -0.1]]))


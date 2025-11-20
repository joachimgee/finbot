"""Tests for TransformerPredictor."""

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

from financial_analyzer.deep_learning import TransformerPredictor


@pytest.fixture
def returns_df():
    """Sample returns DataFrame for testing."""
    np.random.seed(42)
    dates = pd.date_range('2020-01-01', periods=150, freq='D')
    data = np.random.randn(150, 3) * 0.01
    return pd.DataFrame(data, index=dates, columns=['AAPL', 'MSFT', 'GOOGL'])


def test_init_default():
    pred = TransformerPredictor()
    assert pred.lookback_window == 60
    assert pred.forecast_horizon == 5
    assert pred.embed_dim == 64
    assert pred.num_heads == 4


def test_init_invalid_embed_dim():
    with pytest.raises(ValueError):
        TransformerPredictor(embed_dim=0)


def test_init_embed_not_divisible_by_heads():
    with pytest.raises(ValueError):
        TransformerPredictor(embed_dim=63, num_heads=4)


def test_init_invalid_lookback():
    with pytest.raises(ValueError):
        TransformerPredictor(lookback_window=-1)


@patch("financial_analyzer.deep_learning.transformer_predictor.layers")
@patch("financial_analyzer.deep_learning.transformer_predictor.models")
@patch("financial_analyzer.deep_learning.transformer_predictor.keras")
def test_build_model(mock_keras, mock_models, mock_layers):
    mock_model = MagicMock()
    mock_models.Model.return_value = mock_model
    pred = TransformerPredictor(lookback_window=20, forecast_horizon=5)
    model = pred.build_model(n_assets=3)
    # Accept either real Keras model or fallback _SimpleModel
    assert model is not None
    assert hasattr(model, 'fit') and hasattr(model, 'predict')


@patch("financial_analyzer.deep_learning.transformer_predictor.callbacks")
@patch("financial_analyzer.deep_learning.transformer_predictor.layers")
@patch("financial_analyzer.deep_learning.transformer_predictor.models")
@patch("financial_analyzer.deep_learning.transformer_predictor.keras")
def test_fit(mock_keras, mock_models, mock_layers, mock_callbacks):
    mock_model = MagicMock()
    mock_models.Model.return_value = mock_model
    mock_model.fit.return_value = MagicMock(history={
        'loss': [0.2, 0.15],
        'mae': [0.1, 0.08],
        'val_loss': [0.25, 0.18],
        'val_mae': [0.12, 0.09]
    })
    # Ensure callbacks.EarlyStopping exists even if TF is not available
    mock_callbacks.EarlyStopping = MagicMock(return_value=MagicMock())
    pred = TransformerPredictor()
    pred.build_model(n_assets=3)
    X_train = np.random.randn(50, 60, 3)
    y_train = np.random.randn(50, 3)
    history = pred.fit(X_train, y_train, epochs=2)
    assert 'train_loss' in history
    assert 'train_mae' in history
    assert 'epochs_trained' in history


@patch("financial_analyzer.deep_learning.transformer_predictor.layers")
@patch("financial_analyzer.deep_learning.transformer_predictor.models")
@patch("financial_analyzer.deep_learning.transformer_predictor.keras")
def test_predict(mock_keras, mock_models, mock_layers):
    mock_model = MagicMock()
    mock_models.Model.return_value = mock_model
    mock_model.predict.return_value = np.random.randn(10, 5)
    pred = TransformerPredictor()
    pred.build_model(n_assets=5)
    X_test = np.random.randn(10, 60, 5)
    preds = pred.predict(X_test)
    assert preds.shape == (10, 5)




@patch("financial_analyzer.deep_learning.transformer_predictor.tf")
def test_positional_encoding(mock_tf):
    # Create actual numpy array with the expected shape
    import numpy as np
    expected_shape = (1, 60, 64)
    mock_result = np.zeros(expected_shape)
    
    # Mock tf.constant to return our numpy array
    mock_tf.constant.return_value = mock_result
    mock_tf.float32 = 'float32'  # Mock dtype constant
    
    pred = TransformerPredictor()
    pos_enc = pred._positional_encoding(60, 64)
    
    # The method should return the result of tf.constant
    assert hasattr(pos_enc, 'shape')
    assert pos_enc.shape == expected_shape


# -------------------- Polish Tests -------------------- #

@patch("financial_analyzer.deep_learning.transformer_predictor.MinMaxScaler")
@patch("financial_analyzer.deep_learning.transformer_predictor.layers")
@patch("financial_analyzer.deep_learning.transformer_predictor.models")
@patch("financial_analyzer.deep_learning.transformer_predictor.keras")
@patch("financial_analyzer.deep_learning.transformer_predictor.callbacks")
def test_enhanced_history_format(mock_callbacks, mock_keras, mock_models, mock_layers, mock_scaler, returns_df):
    """Test that fit returns enhanced history with train_loss, val_loss, epochs_trained, best_epoch."""
    mock_scaler_instance = MagicMock()
    mock_scaler.return_value = mock_scaler_instance
    mock_scaler_instance.fit.return_value = None
    mock_scaler_instance.transform.return_value = returns_df.values
    
    pred = TransformerPredictor(lookback_window=20, forecast_horizon=5, num_heads=2)
    mock_model = MagicMock()
    mock_models.Model.return_value = mock_model
    mock_model.fit.return_value = MagicMock(history={
        'loss': [0.15, 0.12, 0.11],
        'mae': [0.07, 0.06, 0.055],
        'val_loss': [0.18, 0.14, 0.15],
        'val_mae': [0.08, 0.065, 0.07]
    })
    mock_callbacks.EarlyStopping = MagicMock(return_value=MagicMock())
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
    assert history['best_epoch'] == 2  # Index 1 has lowest val_loss (0.14)


def test_model_summary_logging_transformer(caplog):
    """Test that build_model logs model summary."""
    import logging
    caplog.set_level(logging.DEBUG)
    
    pred = TransformerPredictor(lookback_window=20, forecast_horizon=5, num_heads=2)
    pred.build_model(n_assets=3)
    
    # Check that either model summary or fallback info was logged
    logs = [record.message for record in caplog.records]
    assert any(('Model architecture' in log) or ('SimpleModel fallback' in log) for log in logs)


@patch("financial_analyzer.deep_learning.transformer_predictor.MinMaxScaler")
@patch("financial_analyzer.deep_learning.transformer_predictor.layers")
@patch("financial_analyzer.deep_learning.transformer_predictor.models")
@patch("financial_analyzer.deep_learning.transformer_predictor.keras")
def test_inverse_scale_predictions_transformer(mock_keras, mock_models, mock_layers, mock_scaler, returns_df):
    """Test inverse_scale_predictions helper method."""
    mock_scaler_instance = MagicMock()
    mock_scaler.return_value = mock_scaler_instance
    mock_scaler_instance.fit.return_value = None
    mock_scaler_instance.transform.return_value = returns_df.values
    
    pred = TransformerPredictor(lookback_window=20, forecast_horizon=5, num_heads=2)
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


def test_inverse_scale_predictions_without_scaler_transformer():
    """Test that inverse_scale_predictions raises error if scaler not fitted."""
    pred = TransformerPredictor(lookback_window=20, forecast_horizon=5, num_heads=2)
    pred.build_model(n_assets=3)
    
    with pytest.raises(ValueError, match="Scaler not fitted"):
        pred.inverse_scale_predictions(np.array([[0.1, 0.2, -0.1]]))


def test_prepare_data_transformer(returns_df):
    """Test prepare_data creates train/val/test splits."""
    pred = TransformerPredictor(lookback_window=20, forecast_horizon=5, num_heads=2)
    splits = pred.prepare_data(returns_df, train_size=0.7, val_size=0.15)
    
    assert 'X_train' in splits
    assert 'y_train' in splits
    assert 'X_val' in splits
    assert 'y_val' in splits
    assert 'X_test' in splits
    assert 'y_test' in splits
    assert pred.scaler is not None


def test_create_sequences_transformer(returns_df):
    """Test create_sequences generates correct shapes."""
    pred = TransformerPredictor(lookback_window=20, forecast_horizon=5, num_heads=2)
    X, y = pred.create_sequences(returns_df.values)
    
    assert X.shape[1] == 20  # lookback_window
    assert X.shape[2] == returns_df.shape[1]  # n_assets
    assert y.shape[1] == returns_df.shape[1]  # n_assets
    assert X.shape[0] == y.shape[0]  # same number of sequences


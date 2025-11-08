"""Tests for TransformerPredictor."""

from unittest.mock import MagicMock, patch, Mock
import sys
import numpy as np
import pytest

# Mock TensorFlow before importing predictor
sys.modules['tensorflow'] = MagicMock()
sys.modules['tensorflow.keras'] = MagicMock()
sys.modules['tensorflow.keras.layers'] = MagicMock()
sys.modules['tensorflow.keras.models'] = MagicMock()
sys.modules['tensorflow.keras.callbacks'] = MagicMock()

from financial_analyzer.deep_learning import TransformerPredictor


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
    assert model is mock_model


@patch("financial_analyzer.deep_learning.transformer_predictor.layers")
@patch("financial_analyzer.deep_learning.transformer_predictor.models")
@patch("financial_analyzer.deep_learning.transformer_predictor.keras")
def test_fit(mock_keras, mock_models, mock_layers):
    mock_model = MagicMock()
    mock_models.Model.return_value = mock_model
    mock_model.fit.return_value = MagicMock(history={'loss': [0.2, 0.15]})
    pred = TransformerPredictor()
    pred.build_model(n_assets=3)
    X_train = np.random.randn(50, 60, 3)
    y_train = np.random.randn(50, 3)
    history = pred.fit(X_train, y_train, epochs=2)
    assert 'loss' in history


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

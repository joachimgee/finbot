"""
Transformer-based time series predictor for financial returns.

This module provides a Transformer encoder architecture with multi-head
self-attention and positional encoding for multi-step-ahead forecasting.

Features
--------
- Multi-head self-attention over lookback window
- Sinusoidal positional encoding
- Transformer encoder blocks (attention + FFN)
- Parallel processing (non-sequential unlike LSTM)
- Sequence-to-scalar prediction (many-to-one)

Example
-------
>>> from financial_analyzer.deep_learning import TransformerPredictor
>>> predictor = TransformerPredictor(lookback_window=60, forecast_horizon=5)
>>> predictor.build_model(n_assets=10)
>>> history = predictor.fit(X_train, y_train, epochs=50)
>>> predictions = predictor.predict(X_test)
"""

from __future__ import annotations

from typing import Dict, Optional
import numpy as np

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers, models, callbacks
except ImportError as e:  # pragma: no cover
    logger.warning(f"TensorFlow not available: {e}")
    tf = None  # type: ignore
    keras = None  # type: ignore
    layers = None  # type: ignore
    models = None  # type: ignore
    callbacks = None  # type: ignore


class TransformerPredictor:
    """Transformer encoder for financial time series forecasting.

    Parameters
    ----------
    lookback_window : int, default 60
        Number of historical timesteps as input.
    forecast_horizon : int, default 5
        Future timesteps to predict (aggregated).
    embed_dim : int, default 64
        Embedding dimension (must be divisible by num_heads).
    num_heads : int, default 4
        Number of attention heads.
    num_layers : int, default 2
        Number of Transformer encoder blocks.
    dropout : float, default 0.1
        Dropout rate.
    feed_forward_dim : int, default 128
        Hidden units in FFN.
    """

    def __init__(
        self,
        lookback_window: int = 60,
        forecast_horizon: int = 5,
        embed_dim: int = 64,
        num_heads: int = 4,
        num_layers: int = 2,
        dropout: float = 0.1,
        feed_forward_dim: int = 128,
    ) -> None:
        if lookback_window <= 0:
            raise ValueError("lookback_window must be > 0")
        if forecast_horizon <= 0:
            raise ValueError("forecast_horizon must be > 0")
        if embed_dim <= 0:
            raise ValueError("embed_dim must be > 0")
        if embed_dim % num_heads != 0:
            raise ValueError("embed_dim must be divisible by num_heads")
        if num_heads <= 0:
            raise ValueError("num_heads must be > 0")
        if num_layers <= 0:
            raise ValueError("num_layers must be > 0")
        if not (0.0 <= dropout < 1.0):
            raise ValueError("dropout must be in [0,1)")

        self.lookback_window = lookback_window
        self.forecast_horizon = forecast_horizon
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.num_layers = num_layers
        self.dropout = dropout
        self.feed_forward_dim = feed_forward_dim

        self.model: Optional[keras.Model] = None
        self.n_assets: Optional[int] = None

        logger.info(
            f"TransformerPredictor initialized: lookback={lookback_window}, "
            f"horizon={forecast_horizon}, embed={embed_dim}, heads={num_heads}, layers={num_layers}"
        )

    def build_model(self, n_assets: int) -> keras.Model:
        """Build Transformer encoder architecture.

        Parameters
        ----------
        n_assets : int
            Number of input features (assets).

        Returns
        -------
        keras.Model
            Compiled Transformer model.
        """
        if n_assets <= 0:
            raise ValueError("n_assets must be > 0")

        self.n_assets = n_assets
        inp = layers.Input(shape=(self.lookback_window, n_assets))

        # Project input to embed_dim
        x = layers.Dense(self.embed_dim)(inp)

        # Add positional encoding
        pos_enc = self._positional_encoding(self.lookback_window, self.embed_dim)
        x = x + pos_enc

        # Transformer encoder blocks
        for _ in range(self.num_layers):
            x = self._transformer_encoder_block(x)

        # Global average pooling over time
        x = layers.GlobalAveragePooling1D()(x)
        x = layers.Dropout(self.dropout)(x)

        # Output
        x = layers.Dense(n_assets, activation='linear')(x)
        self.model = models.Model(inputs=inp, outputs=x)
        self.model.compile(optimizer='adam', loss='mse', metrics=['mae'])

        logger.info(f"Transformer model built: {self.model.count_params()} params")
        return self.model

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        epochs: int = 50,
        batch_size: int = 32,
        validation_split: float = 0.1,
    ) -> Dict:
        """Train the Transformer model.

        Parameters
        ----------
        X_train : np.ndarray
            Training sequences (n_samples, lookback_window, n_assets).
        y_train : np.ndarray
            Training targets (n_samples, n_assets).
        X_val : np.ndarray, optional
            Validation sequences.
        y_val : np.ndarray, optional
            Validation targets.
        epochs : int, default 50
            Maximum epochs.
        batch_size : int, default 32
            Batch size.
        validation_split : float, default 0.1
            Fraction of train to use as validation if X_val not provided.

        Returns
        -------
        dict
            Training history.
        """
        if self.model is None:
            raise ValueError("Model not built; call build_model() first")

        cbs = [
            callbacks.EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True),
        ]

        val_data = (X_val, y_val) if X_val is not None and y_val is not None else None

        logger.info(f"Training Transformer for up to {epochs} epochs")
        history = self.model.fit(
            X_train,
            y_train,
            validation_data=val_data,
            validation_split=validation_split if val_data is None else 0.0,
            epochs=epochs,
            batch_size=batch_size,
            callbacks=cbs,
            verbose=0,
        )
        logger.info(f"Training complete: final loss={history.history['loss'][-1]:.4f}")
        return history.history

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Generate predictions.

        Parameters
        ----------
        X : np.ndarray
            Input sequences (n_samples, lookback_window, n_assets).

        Returns
        -------
        np.ndarray
            Predictions (n_samples, n_assets).
        """
        if self.model is None:
            raise ValueError("Model not built")
        preds = self.model.predict(X, verbose=0)
        return preds

    # -------------------- Internals -------------------- #

    def _transformer_encoder_block(self, x: tf.Tensor) -> tf.Tensor:
        """Single Transformer encoder block with attention + FFN."""
        # Multi-head self-attention
        attn_out = layers.MultiHeadAttention(
            num_heads=self.num_heads, key_dim=self.embed_dim // self.num_heads
        )(x, x)
        attn_out = layers.Dropout(self.dropout)(attn_out)
        x = layers.Add()([x, attn_out])
        x = layers.LayerNormalization(epsilon=1e-6)(x)

        # Feed-forward network
        ffn_out = layers.Dense(self.feed_forward_dim, activation='relu')(x)
        ffn_out = layers.Dropout(self.dropout)(ffn_out)
        ffn_out = layers.Dense(self.embed_dim)(ffn_out)
        ffn_out = layers.Dropout(self.dropout)(ffn_out)
        x = layers.Add()([x, ffn_out])
        x = layers.LayerNormalization(epsilon=1e-6)(x)

        return x

    def _positional_encoding(self, seq_len: int, embed_dim: int) -> tf.Tensor:
        """Sinusoidal positional encoding."""
        positions = np.arange(seq_len)[:, np.newaxis]
        dims = np.arange(embed_dim)[np.newaxis, :]
        angles = positions / np.power(10000, (2 * (dims // 2)) / embed_dim)
        pos_enc = np.zeros((seq_len, embed_dim))
        pos_enc[:, 0::2] = np.sin(angles[:, 0::2])
        pos_enc[:, 1::2] = np.cos(angles[:, 1::2])
        pos_enc = tf.constant(pos_enc[np.newaxis, :, :], dtype=tf.float32)
        return pos_enc


__all__ = ["TransformerPredictor"]

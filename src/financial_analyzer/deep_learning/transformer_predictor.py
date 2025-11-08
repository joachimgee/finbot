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
import pandas as pd
from sklearn.preprocessing import MinMaxScaler

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
        self.scaler: Optional[MinMaxScaler] = None

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

        param_count = self.model.count_params()
        logger.info(f"Transformer model built: {param_count} params")
        
        # Log model summary
        summary_lines = []
        self.model.summary(print_fn=lambda x: summary_lines.append(x))
        logger.debug("Model architecture:\n" + "\n".join(summary_lines[:10]))  # First 10 lines
        
        return self.model

    def create_sequences(self, data: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Create sequences from time series data.

        Parameters
        ----------
        data : np.ndarray
            Time series array (rows=timesteps, cols=assets).

        Returns
        -------
        X : np.ndarray
            Sequences (n_sequences, lookback_window, n_assets).
        y : np.ndarray
            Targets (n_sequences, n_assets) - sum of forecast_horizon returns.
        """
        if data.shape[0] < self.lookback_window + self.forecast_horizon:
            logger.warning("Insufficient data for sequence creation")
            return np.empty((0, self.lookback_window, data.shape[1])), np.empty((0, data.shape[1]))

        X_list, y_list = [], []
        for i in range(len(data) - self.lookback_window - self.forecast_horizon + 1):
            X_list.append(data[i : i + self.lookback_window])
            # Target: sum of next forecast_horizon returns
            y_list.append(data[i + self.lookback_window : i + self.lookback_window + self.forecast_horizon].sum(axis=0))
        X = np.array(X_list)
        y = np.array(y_list)
        return X, y

    def prepare_data(
        self, returns: pd.DataFrame, train_size: float = 0.7, val_size: float = 0.15
    ) -> Dict[str, np.ndarray]:
        """Prepare train/val/test splits with scaling.

        Parameters
        ----------
        returns : pd.DataFrame
            Time series returns (rows=dates, cols=assets).
        train_size : float, default 0.7
            Fraction of data for training.
        val_size : float, default 0.15
            Fraction for validation (remaining is test).

        Returns
        -------
        dict
            Keys: 'X_train', 'y_train', 'X_val', 'y_val', 'X_test', 'y_test'.
        """
        data = returns.values
        n = len(data)
        train_end = int(n * train_size)
        val_end = int(n * (train_size + val_size))

        # Fit scaler on train
        self.scaler = MinMaxScaler(feature_range=(-1, 1))
        self.scaler.fit(data[:train_end])

        # Scale all
        data_scaled = self.scaler.transform(data)

        # Create sequences
        X, y = self.create_sequences(data_scaled)
        if len(X) == 0:
            logger.error("No sequences created; returning empty arrays")
            return {
                'X_train': np.empty((0, self.lookback_window, data.shape[1])),
                'y_train': np.empty((0, data.shape[1])),
                'X_val': np.empty((0, self.lookback_window, data.shape[1])),
                'y_val': np.empty((0, data.shape[1])),
                'X_test': np.empty((0, self.lookback_window, data.shape[1])),
                'y_test': np.empty((0, data.shape[1])),
            }

        # Sequence indices aligned with original splits
        seq_train_end = max(0, train_end - self.lookback_window - self.forecast_horizon + 1)
        seq_val_end = max(0, val_end - self.lookback_window - self.forecast_horizon + 1)

        return {
            'X_train': X[:seq_train_end],
            'y_train': y[:seq_train_end],
            'X_val': X[seq_train_end:seq_val_end],
            'y_val': y[seq_train_end:seq_val_end],
            'X_test': X[seq_val_end:],
            'y_test': y[seq_val_end:],
        }

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
            Training history with structured format:
            {
                'train_loss': list[float],
                'train_mae': list[float],
                'val_loss': list[float] (if validation provided),
                'val_mae': list[float] (if validation provided),
                'epochs_trained': int,
                'best_epoch': int (epoch with lowest val_loss)
            }
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
        
        # Enhanced history format
        monitor_metric = 'val_loss'
        best_epoch = int(np.argmin(history.history[monitor_metric])) + 1
        
        enhanced_history = {
            'train_loss': history.history['loss'],
            'train_mae': history.history.get('mae', history.history.get('mean_absolute_error', [])),
            'epochs_trained': len(history.history['loss']),
            'best_epoch': best_epoch,
        }
        
        if 'val_loss' in history.history:
            enhanced_history['val_loss'] = history.history['val_loss']
            enhanced_history['val_mae'] = history.history.get('val_mae', history.history.get('val_mean_absolute_error', []))
        
        logger.info(f"Best epoch: {best_epoch}, best {monitor_metric}: {history.history[monitor_metric][best_epoch-1]:.4f}")
        
        return enhanced_history

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Generate predictions.

        Parameters
        ----------
        X : np.ndarray
            Input sequences (n_samples, lookback_window, n_assets).

        Returns
        -------
        np.ndarray
            Predictions (n_samples, n_assets) in scaled space.
            Use inverse_scale_predictions() to convert back to original scale.
        """
        if self.model is None:
            raise ValueError("Model not built")
        preds = self.model.predict(X, verbose=0)
        return preds

    def inverse_scale_predictions(self, predictions: np.ndarray) -> np.ndarray:
        """Convert scaled predictions back to original return scale.

        Parameters
        ----------
        predictions : np.ndarray
            Scaled predictions from predict() (n_samples, n_assets).

        Returns
        -------
        np.ndarray
            Predictions in original return scale.

        Raises
        ------
        ValueError
            If scaler not fitted (call prepare_data first).

        Example
        -------
        >>> splits = predictor.prepare_data(returns)
        >>> predictor.fit(splits['X_train'], splits['y_train'])
        >>> scaled_preds = predictor.predict(splits['X_test'])
        >>> real_preds = predictor.inverse_scale_predictions(scaled_preds)
        """
        if self.scaler is None:
            raise ValueError("Scaler not fitted; call prepare_data() before inverse scaling")
        return self.scaler.inverse_transform(predictions)

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

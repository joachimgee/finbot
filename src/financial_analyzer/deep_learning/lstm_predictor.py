"""
LSTM/GRU-based time series predictor for financial returns.

This module provides a configurable recurrent neural network architecture
supporting LSTM, GRU, bidirectional processing, and optional attention
mechanisms for multi-step-ahead forecasting.

Features
--------
- Sequence-to-scalar (many-to-one) prediction
- Bidirectional LSTM/GRU layers
- Optional attention mechanism
- Per-asset MinMax scaling
- Early stopping and model checkpointing
- Forward returns as targets (sum of next N days)

Example
-------
>>> from financial_analyzer.deep_learning import LSTMPredictor
>>> predictor = LSTMPredictor(lookback_window=60, forecast_horizon=5)
>>> predictor.build_model(n_assets=10)
>>> history = predictor.fit(X_train, y_train, epochs=50)
>>> predictions = predictor.predict(X_test)
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple
import numpy as np
import pandas as pd

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers, models, callbacks
    from sklearn.preprocessing import MinMaxScaler
except ImportError as e:  # pragma: no cover
    logger.warning(f"TensorFlow or sklearn not available: {e}")
    tf = None  # type: ignore
    keras = None  # type: ignore
    layers = None  # type: ignore
    models = None  # type: ignore
    callbacks = None  # type: ignore
    MinMaxScaler = None  # type: ignore


class LSTMPredictor:
    """LSTM/GRU predictor for financial time series.

    Parameters
    ----------
    lookback_window : int, default 60
        Number of historical timesteps to use as input.
    forecast_horizon : int, default 5
        Number of future timesteps to predict (aggregated as sum).
    lstm_units : int, default 64
        Number of units per LSTM/GRU layer.
    lstm_layers : int, default 2
        Number of stacked recurrent layers.
    dropout : float, default 0.2
        Dropout rate for regularization.
    bidirectional : bool, default True
        Use bidirectional wrapping of recurrent layers.
    use_attention : bool, default False
        Add an attention mechanism after recurrent layers.
    use_gru : bool, default False
        Use GRU cells instead of LSTM.
    """

    def __init__(
        self,
        lookback_window: int = 60,
        forecast_horizon: int = 5,
        lstm_units: int = 64,
        lstm_layers: int = 2,
        dropout: float = 0.2,
        bidirectional: bool = True,
        use_attention: bool = False,
        use_gru: bool = False,
    ) -> None:
        if lookback_window <= 0:
            raise ValueError("lookback_window must be > 0")
        if forecast_horizon <= 0:
            raise ValueError("forecast_horizon must be > 0")
        if lstm_units <= 0:
            raise ValueError("lstm_units must be > 0")
        if lstm_layers <= 0:
            raise ValueError("lstm_layers must be > 0")
        if not (0.0 <= dropout < 1.0):
            raise ValueError("dropout must be in [0, 1)")

        self.lookback_window = lookback_window
        self.forecast_horizon = forecast_horizon
        self.lstm_units = lstm_units
        self.lstm_layers = lstm_layers
        self.dropout = dropout
        self.bidirectional = bidirectional
        self.use_attention = use_attention
        self.use_gru = use_gru

        self.model: Optional[keras.Model] = None
        self.scaler: Optional[MinMaxScaler] = None
        self.n_assets: Optional[int] = None

        logger.info(
            f"LSTMPredictor initialized: lookback={lookback_window}, "
            f"horizon={forecast_horizon}, units={lstm_units}, layers={lstm_layers}, "
            f"bi={bidirectional}, attn={use_attention}, gru={use_gru}"
        )

    def build_model(self, n_assets: int) -> keras.Model:
        """Build LSTM/GRU model architecture.

        Parameters
        ----------
        n_assets : int
            Number of assets (input features).

        Returns
        -------
        keras.Model
            Compiled model ready for training.
        """
        if n_assets <= 0:
            raise ValueError("n_assets must be > 0")

        self.n_assets = n_assets
        inp = layers.Input(shape=(self.lookback_window, n_assets))
        x = inp

        # Recurrent layers
        cell = layers.GRU if self.use_gru else layers.LSTM
        for i in range(self.lstm_layers):
            return_sequences = (i < self.lstm_layers - 1) or self.use_attention
            rnn_layer = cell(self.lstm_units, return_sequences=return_sequences)
            if self.bidirectional:
                x = layers.Bidirectional(rnn_layer)(x)
            else:
                x = rnn_layer(x)
            x = layers.Dropout(self.dropout)(x)

        # Optional attention
        if self.use_attention:
            # Simple attention: dense over time axis
            attn = layers.Dense(1, activation='tanh')(x)
            attn = layers.Flatten()(attn)
            attn = layers.Activation('softmax')(attn)
            attn = layers.RepeatVector(self.lstm_units * (2 if self.bidirectional else 1))(attn)
            attn = layers.Permute([2, 1])(attn)
            x = layers.Multiply()([x, attn])
            x = layers.Lambda(lambda z: tf.reduce_sum(z, axis=1))(x)

        # Output
        x = layers.Dense(n_assets, activation='linear')(x)
        self.model = models.Model(inputs=inp, outputs=x)
        self.model.compile(optimizer='adam', loss='mse', metrics=['mae'])

        param_count = self.model.count_params()
        logger.info(f"LSTM model built: {param_count} params")
        
        # Log model summary
        summary_lines = []
        self.model.summary(print_fn=lambda x: summary_lines.append(x))
        logger.debug("Model architecture:\n" + "\n".join(summary_lines[:10]))  # First 10 lines
        
        return self.model

    def create_sequences(self, data: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Create lookback sequences and targets from time series.

        Parameters
        ----------
        data : np.ndarray
            Shape (timesteps, n_assets).

        Returns
        -------
        X : np.ndarray
            Shape (n_sequences, lookback_window, n_assets).
        y : np.ndarray
            Shape (n_sequences, n_assets) — forward returns summed.
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

        # Split into train/val/test
        train_seq_end = max(1, int(len(X) * train_size))
        val_seq_end = max(train_seq_end + 1, int(len(X) * (train_size + val_size)))

        X_train, y_train = X[:train_seq_end], y[:train_seq_end]
        X_val, y_val = X[train_seq_end:val_seq_end], y[train_seq_end:val_seq_end]
        X_test, y_test = X[val_seq_end:], y[val_seq_end:]

        logger.info(
            f"Data prepared: train={len(X_train)}, val={len(X_val)}, test={len(X_test)}"
        )

        return {
            'X_train': X_train,
            'y_train': y_train,
            'X_val': X_val,
            'y_val': y_val,
            'X_test': X_test,
            'y_test': y_test,
        }

    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        epochs: int = 50,
        batch_size: int = 32,
        learning_rate: float = 0.001,
    ) -> Dict:
        """Train the LSTM/GRU model with early stopping.

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
            Maximum training epochs.
        batch_size : int, default 32
            Batch size.
        learning_rate : float, default 0.001
            Optimizer learning rate.

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
                'best_epoch': int (epoch with lowest val_loss or loss)
            }
        """
        if self.model is None:
            raise ValueError("Model not built; call build_model() first")

        # Set LR
        keras.backend.set_value(self.model.optimizer.learning_rate, learning_rate)

        # Callbacks
        cbs = [
            callbacks.EarlyStopping(monitor='val_loss' if X_val is not None else 'loss', patience=10, restore_best_weights=True),
        ]

        val_data = (X_val, y_val) if X_val is not None and y_val is not None else None

        logger.info(f"Training for up to {epochs} epochs, batch_size={batch_size}")
        history = self.model.fit(
            X_train,
            y_train,
            validation_data=val_data,
            epochs=epochs,
            batch_size=batch_size,
            callbacks=cbs,
            verbose=0,
        )
        logger.info(f"Training complete: final loss={history.history['loss'][-1]:.4f}")
        
        # Enhanced history format
        monitor_metric = 'val_loss' if X_val is not None else 'loss'
        best_epoch = int(np.argmin(history.history[monitor_metric])) + 1
        
        enhanced_history = {
            'train_loss': history.history['loss'],
            'train_mae': history.history.get('mae', history.history.get('mean_absolute_error', [])),
            'epochs_trained': len(history.history['loss']),
            'best_epoch': best_epoch,
        }
        
        if X_val is not None:
            enhanced_history['val_loss'] = history.history['val_loss']
            enhanced_history['val_mae'] = history.history.get('val_mae', history.history.get('val_mean_absolute_error', []))
        
        logger.info(f"Best epoch: {best_epoch}, best {monitor_metric}: {history.history[monitor_metric][best_epoch-1]:.4f}")
        
        return enhanced_history

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Generate predictions for input sequences.

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

    def _create_targets(self, returns: np.ndarray, forecast_horizon: int) -> np.ndarray:
        """Create forward returns targets.

        Not actively used (create_sequences handles this), but kept for reference.
        """
        targets = []
        for i in range(len(returns) - forecast_horizon + 1):
            targets.append(returns[i : i + forecast_horizon].sum(axis=0))
        return np.array(targets)


__all__ = ["LSTMPredictor"]

# 🎯 PHASE 5.5 MODULE 5 - LSTM/TRANSFORMER PROMPT

## CONTEXT

**Module 5** implémente **deep learning time series forecasting** avec LSTM + Transformer.

**Objectif** : Prédire retours futurs (1-20 jours) via réseaux de neurones avancés.

**Features** :
- LSTM/GRU pour séquences temporelles
- Transformer avec attention mechanism
- Feature scaling (MinMaxScaler)
- Training pipeline avec early stopping
- Hyperparameter tuning (learning rate, layers, etc.)
- Backtesting sur données hors-sample

---

## 📚 INSPIRATIONS AUDITS

**Lis ces sections** :

1. **AUDIT_FINANCE_PARTIE_5_ML.md** (19 KB) :
   - LSTM patterns pour finance
   - Attention mechanisms
   - Feature engineering pour deep learning
   - Return prediction targets

2. **AUDIT_ML4T_BOOK.md** (29 KB) :
   - Deep learning for trading
   - Lookback windows (sequences)
   - Target engineering (labels)

---

## 📄 PROMPT FOR COPILOT

**COPY-PASTE THIS ENTIRE PROMPT TO COPILOT** :

```
PHASE 5.5 MODULE 5 : LSTM/TRANSFORMER PRICE PREDICTION

Génère 2 fichiers + tests complets :

================================================================================
1. src/financial_analyzer/deep_learning/lstm_predictor.py (400 LOC)
================================================================================

"""
LSTM/GRU Price Predictor - Production Grade Deep Learning.

Implements LSTM/GRU networks for multi-asset return prediction.

Features:
- LSTM/GRU/Bidirectional architectures
- Sequence-to-scalar prediction (many-to-one)
- Feature scaling (MinMaxScaler per asset)
- Training pipeline (train/val/test split 60/20/20)
- Early stopping (patience=10, restore_best_weights=True)
- Hyperparameter tuning (learning rate, layers, dropout)
- Prediction on future returns (1-20 day forward returns)

Audit references:
- AUDIT_FINANCE_PARTIE_5_ML.md pp.10-18 (LSTM for finance)
- AUDIT_ML4T_BOOK.md pp.15-25 (deep learning trading patterns)

Example:
    >>> from financial_analyzer.deep_learning import LSTMPredictor
    >>> import pandas as pd
    >>> import numpy as np
    >>> 
    >>> # Load returns (DatetimeIndex, assets as columns)
    >>> returns = pd.read_csv('returns.csv', index_col=0, parse_dates=True)
    >>> 
    >>> # Initialize predictor
    >>> predictor = LSTMPredictor(
    ...     lookback_window=60,  # 60-day sequences
    ...     forecast_horizon=5,  # Predict 5 days ahead
    ...     lstm_units=64,
    ...     dropout=0.2
    ... )
    >>> 
    >>> # Prepare data (generates sequences + targets)
    >>> X_train, y_train = predictor.prepare_data(returns.iloc[:-100])
    >>> 
    >>> # Train
    >>> history = predictor.fit(
    ...     X_train, y_train,
    ...     epochs=50,
    ...     batch_size=32,
    ...     validation_split=0.2
    ... )
    >>> 
    >>> # Predict on future window
    >>> X_test = predictor.create_sequences(returns.iloc[-100:-5])
    >>> y_pred = predictor.predict(X_test)  # Shape: (95, n_assets)
"""

Implement:

class LSTMPredictor:
    """
    LSTM/GRU predictor for multi-asset return forecasting.
    
    Architecture:
    - Input: (batch, lookback_window, n_assets)
    - LSTM/GRU layers with optional attention
    - Output: (batch, n_assets) [scalar per asset]
    
    Workflow:
    1. Create sequences (lookback_window days)
    2. Scale features (MinMaxScaler)
    3. Build model (LSTM + Dense)
    4. Train with early stopping
    5. Predict on new data
    6. Inverse scale predictions
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
        use_gru: bool = False
    ):
        """
        Initialize LSTM predictor.
        
        Args:
            lookback_window: Number of past days to use (ex: 60)
            forecast_horizon: Days ahead to predict (ex: 5 = 5-day return)
            lstm_units: Hidden units per LSTM cell (ex: 64)
            lstm_layers: Number of LSTM layers (ex: 2)
            dropout: Dropout rate (ex: 0.2)
            bidirectional: Use bidirectional LSTM
            use_attention: Add attention layer after LSTM
            use_gru: Use GRU instead of LSTM
        """
        # Validate parameters
        # Initialize scalers (per asset)
        # Build model architecture
        pass
    
    def build_model(self) -> None:
        """
        Build Keras Sequential model.
        
        Architecture:
        - Bidirectional LSTM/GRU layers
        - Optional: Attention layer
        - Dense layers for regression
        - Output: n_assets predictions
        
        Model compiled with:
        - Optimizer: Adam(learning_rate=0.001)
        - Loss: mean_squared_error
        - Metrics: ['mae', 'mape']
        """
        # Sequential model
        # Add Bidirectional LSTM/GRU layers
        # Optional: Add Attention layer
        # Add Dense layers
        # Add output layer (n_assets)
        # Compile
        pass
    
    def create_sequences(
        self,
        data: pd.DataFrame
    ) -> np.ndarray:
        """
        Create lookback sequences from returns.
        
        Input:  (n_samples, n_assets)
        Output: (n_sequences, lookback_window, n_assets)
        
        Example:
            data = [[0.01, 0.02], [0.015, 0.01], ...] (10 days, 2 assets)
            lookback_window = 3
            output:
            [
                [[0.01, 0.02], [0.015, 0.01], ...],  # seq 0 (days 0-2)
                [[0.015, 0.01], ..., ...],             # seq 1 (days 1-3)
                ...
            ]
        
        Returns:
            np.ndarray (n_sequences, lookback_window, n_assets)
        """
        # Initialize sequences list
        # Iterate: for i in range(len(data) - lookback_window + 1)
        # Append data[i:i+lookback_window]
        # Return as numpy array
        pass
    
    def prepare_data(
        self,
        returns: pd.DataFrame,
        train_size: float = 0.6,
        val_size: float = 0.2
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """
        Prepare sequences + targets for training.
        
        Args:
            returns: DataFrame (DatetimeIndex, assets as columns)
            train_size: Train split (default 0.6)
            val_size: Validation split (default 0.2, test = 0.2)
        
        Returns:
            Tuple[X_train, y_train, X_val, y_val]
            - X_train: (n_train_seq, lookback_window, n_assets)
            - y_train: (n_train_seq, n_assets) [forward returns]
        
        Process:
        1. Create sequences (lookback_window)
        2. Create targets (forward_horizon returns)
        3. Scale features (MinMaxScaler)
        4. Split train/val/test
        5. Return arrays
        """
        # Create sequences
        # Create targets (forward_horizon returns)
        # Scale X with MinMaxScaler
        # Split by indices
        # Return (X_train, y_train, X_val, y_val)
        pass
    
    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        epochs: int = 50,
        batch_size: int = 32,
        learning_rate: float = 0.001,
        early_stopping_patience: int = 10
    ) -> Dict:
        """
        Train LSTM model.
        
        Args:
            X_train: Training sequences (n_train, lookback, n_assets)
            y_train: Training targets (n_train, n_assets)
            X_val, y_val: Validation data
            epochs: Max epochs (default 50)
            batch_size: Batch size (default 32)
            learning_rate: Adam learning rate (default 0.001)
            early_stopping_patience: Patience for early stopping (default 10)
        
        Returns:
            Dict with 'history' (training logs) and 'best_epoch'
        
        Features:
        - Early stopping (val_loss)
        - Learning rate scheduling (optional)
        - Checkpoint best weights
        """
        # Compile model with learning_rate
        # Add callbacks: EarlyStopping, ModelCheckpoint
        # Train: model.fit(X_train, y_train, ...)
        # Return history dict
        pass
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict on new sequences.
        
        Args:
            X: Input sequences (n_samples, lookback_window, n_assets)
        
        Returns:
            Predictions (n_samples, n_assets) [next forward_horizon returns]
        
        Example:
            y_pred = predictor.predict(X_test)
            # y_pred shape: (100, 2) → 100 predictions, 2 assets
        """
        # model.predict(X)
        # Inverse scale predictions (via scalers)
        # Return predictions
        pass
    
    def _create_targets(
        self,
        returns: pd.DataFrame,
        forecast_horizon: int
    ) -> np.ndarray:
        """
        Create forward returns targets.
        
        Input:  returns (n_samples, n_assets)
        Output: targets (n_targets, n_assets)
        
        For each sample i:
        target[i] = sum(returns[i+1:i+1+forecast_horizon])
        (i.e., forward forecast_horizon days return)
        
        Returns:
            np.ndarray (n_targets, n_assets)
        """
        # Initialize targets array
        # For i, append sum of next forecast_horizon days
        # Return targets
        pass


__all__ = ['LSTMPredictor']

================================================================================
2. src/financial_analyzer/deep_learning/transformer_predictor.py (300 LOC)
================================================================================

"""
Transformer-based Price Predictor - Attention Mechanism.

Implements Transformer encoder for multi-asset return prediction.

Features:
- Multi-head self-attention
- Positional encoding
- Transformer encoder blocks
- Comparable to LSTM but better for long sequences

Audit reference:
- AUDIT_FINANCE_PARTIE_5_ML.md pp.12-14 (Attention patterns)

Example:
    >>> from financial_analyzer.deep_learning import TransformerPredictor
    >>> 
    >>> transformer = TransformerPredictor(
    ...     lookback_window=60,
    ...     forecast_horizon=5,
    ...     embed_dim=64,
    ...     num_heads=4,
    ...     num_layers=2
    ... )
    >>> history = transformer.fit(X_train, y_train, epochs=50)
    >>> y_pred = transformer.predict(X_test)
"""

Implement:

class TransformerPredictor:
    """
    Transformer predictor for return forecasting.
    
    Architecture:
    - Input embedding
    - Positional encoding (sinusoidal)
    - Multi-head self-attention layers
    - Feed-forward networks
    - Output: scalar predictions per asset
    
    Advantages over LSTM:
    - Parallel processing (faster training)
    - Better for long sequences (no gradient vanishing)
    - Attention weights interpretable
    """
    
    def __init__(
        self,
        lookback_window: int = 60,
        forecast_horizon: int = 5,
        embed_dim: int = 64,
        num_heads: int = 4,
        num_layers: int = 2,
        dropout: float = 0.1,
        feed_forward_dim: int = 256
    ):
        """
        Initialize Transformer predictor.
        
        Args:
            lookback_window: Sequence length
            forecast_horizon: Forward prediction days
            embed_dim: Embedding dimension (must be divisible by num_heads)
            num_heads: Number of attention heads (ex: 4)
            num_layers: Number of transformer blocks (ex: 2)
            dropout: Dropout rate (default 0.1)
            feed_forward_dim: Feed-forward hidden dimension (ex: 256)
        """
        # Validate embed_dim % num_heads == 0
        # Initialize scalers
        # Build model
        pass
    
    def build_model(self) -> None:
        """
        Build Keras model with Transformer architecture.
        
        Layers:
        - Input: (batch, lookback_window, n_assets)
        - Dense embedding: (batch, lookback_window, embed_dim)
        - Positional encoding (add)
        - MultiHeadAttention blocks (num_layers)
        - Global average pooling
        - Dense layers
        - Output: (batch, n_assets)
        
        Note: Use Keras functional API (not Sequential)
        """
        # Define Input layer
        # Embedding layer (Dense)
        # Add positional encoding
        # Stack TransformerBlock layers
        # Global pooling
        # Dense output
        # Create Model
        pass
    
    def fit(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        epochs: int = 50,
        batch_size: int = 32,
        validation_split: float = 0.2
    ) -> Dict:
        """
        Train Transformer model.
        
        Returns:
            Dict with training history
        """
        # Build model
        # Compile with Adam optimizer
        # Add EarlyStopping callback
        # Train
        # Return history
        pass
    
    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Predict on new sequences.
        
        Args:
            X: Input sequences (n_samples, lookback_window, n_assets)
        
        Returns:
            Predictions (n_samples, n_assets)
        """
        # model.predict(X)
        # Inverse scale
        # Return
        pass


__all__ = ['TransformerPredictor']

================================================================================
3. TESTS (20 TOTAL)
================================================================================

tests/test_deep_learning/test_lstm_predictor.py (12 tests)
- test_init_default()
- test_build_model_lstm()
- test_build_model_gru()
- test_create_sequences_shape()
- test_create_sequences_values()
- test_prepare_data_split_sizes()
- test_fit_reduces_loss()
- test_predict_shape()
- test_predict_range()
- test_bidirectional_lstm()
- test_attention_layer()
- test_invalid_lookback_raises()

tests/test_deep_learning/test_transformer_predictor.py (8 tests)
- test_init_default()
- test_build_model_shape()
- test_fit_reduces_loss()
- test_predict_shape()
- test_embed_dim_validation()
- test_positional_encoding()
- test_attention_heads()
- test_invalid_embed_dim_raises()

================================================================================
REQUIREMENTS
================================================================================

✅ Type hints 100%
✅ Google/NumPy docstrings 100%
✅ 20 tests passing 100%
✅ Logging (info/warning/error)
✅ Error handling with try/except
✅ Zero Pylance errors
✅ Production-ready

CRITICAL:
- Use TensorFlow/Keras (not PyTorch)
- LSTM/GRU via keras.layers.LSTM/GRU
- MultiHeadAttention via keras.layers.MultiHeadAttention
- MinMaxScaler via sklearn.preprocessing
- Early stopping + ModelCheckpoint for training
- Create sequences: many-to-one (lookback → scalar)
- Targets: forward returns (sum of forecast_horizon days)
- All tests mock model predictions (no GPU training in tests)
- Return predictions before inverse scaling for metric evaluation

Refs: AUDIT_FINANCE_PARTIE_5_ML.md, AUDIT_ML4T_BOOK.md
```

---

## 📋 QUICK REFERENCE

**Files to generate:**
1. ✅ `lstm_predictor.py` (400 LOC) - LSTM/GRU/Bidirectional
2. ✅ `transformer_predictor.py` (300 LOC) - Transformer with attention
3. ✅ 2 test files (20 tests total: 12 + 8)

**Key features:**
- Sequence generation (lookback windows)
- Feature scaling per asset
- LSTM + GRU variants
- Bidirectional processing
- Attention mechanism
- Transformer encoder blocks
- Early stopping training
- MinMaxScaler for predictions

---

## 📊 EXPECTED OUTPUT

**After Copilot generates:**

```
✅ lstm_predictor.py (400 LOC)
✅ transformer_predictor.py (300 LOC)
✅ test_lstm_predictor.py (12 tests)
✅ test_transformer_predictor.py (8 tests)

Total: 700 LOC + 20 tests
All passing: 20/20 ✅
```

---

## 🎯 MODULE 5 COMPLEXITY

**Module 5 est le PLUS TECHNIQUE** :
- Deep learning (Keras/TensorFlow)
- Time series sequences
- Attention mechanisms
- Neural architecture design

**Attendu** : 2-2.5h par Copilot (le module le plus long)

---

**COPY THE PROMPT ABOVE AND SEND TO COPILOT NOW!** 🚀🚀🚀

This is the **most advanced deep learning module** of Phase 5.5! 💪

"""
Meta-Labeling Module.

Meta-labeling : utiliser ML pour améliorer une stratégie primaire existante.
Au lieu de prédire la direction (up/down), le modèle ML prédit :
1. **Side** : Faut-il prendre le trade ou non ? (binary: trade / no-trade)
2. **Size** : Quelle taille de position ? (regression)

Avantages :
- Réduit faux signaux de la stratégie primaire
- Améliore Sharpe ratio
- Évite over-trading

Based on : Prado, M. L. de. (2018). Advances in Financial Machine Learning, Chapter 3.
"""

from typing import Dict, List, Optional, Tuple, Callable
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class MetaLabeler:
    """
    Meta-labeler pour filtrer et dimensionner trades d'une stratégie primaire.
    
    La stratégie primaire génère des signaux (long/short). Le meta-label prédit :
    - **Side meta-label** : Prendre ou ignorer le signal ? (classification)
    - **Size meta-label** : Quelle taille ? (régression)
    
    Attributes:
        primary_model: Stratégie primaire (fonction ou classe)
        meta_model_side: Modèle ML pour side prediction
        meta_model_size: Modèle ML pour size prediction (optionnel)
    
    Example:
        >>> # Stratégie primaire : SMA crossover
        >>> def primary_strategy(data):
        ...     signals = (data['sma_fast'] > data['sma_slow']).astype(int)
        ...     return signals  # 1 = long, 0 = short
        >>> 
        >>> meta = MetaLabeler(primary_strategy)
        >>> meta.fit(X_train, returns_train, primary_signals_train)
        >>> filtered_signals = meta.predict_side(X_test, primary_signals_test)
    """
    
    def __init__(
        self,
        primary_model: Optional[Callable] = None,
        meta_model_side: Optional[any] = None,
        meta_model_size: Optional[any] = None,
        side_threshold: float = 0.5,
        min_return_threshold: float = 0.0
    ):
        """
        Initialise MetaLabeler.
        
        Args:
            primary_model: Stratégie primaire (callable)
            meta_model_side: Modèle sklearn pour side (si None, RandomForest par défaut)
            meta_model_size: Modèle sklearn pour size (si None, RandomForest par défaut)
            side_threshold: Seuil probabilité pour prendre trade (0.5 par défaut)
            min_return_threshold: Return min pour considérer trade profitable
        """
        self.primary_model = primary_model
        
        # Modèles par défaut : Random Forest
        if meta_model_side is None:
            self.meta_model_side = RandomForestClassifier(
                n_estimators=100,
                max_depth=5,
                random_state=42,
                n_jobs=-1
            )
        else:
            self.meta_model_side = meta_model_side
        
        if meta_model_size is None:
            self.meta_model_size = RandomForestRegressor(
                n_estimators=100,
                max_depth=5,
                random_state=42,
                n_jobs=-1
            )
        else:
            self.meta_model_size = meta_model_size
        
        self.side_threshold = side_threshold
        self.min_return_threshold = min_return_threshold
        
        self._is_fitted_side = False
        self._is_fitted_size = False
        
        logger.debug("MetaLabeler initialized")
    
    def create_meta_labels_side(
        self,
        returns: pd.Series,
        primary_signals: pd.Series,
        horizon: int = 5
    ) -> pd.Series:
        """
        Crée les meta-labels pour side prediction.
        
        Meta-label = 1 si le signal primaire mène à un profit, 0 sinon.
        
        Args:
            returns: Series de returns
            primary_signals: Signaux de la stratégie primaire (1=long, 0/=-1=short)
            horizon: Horizon de holding (nombre de périodes)
        
        Returns:
            Series de meta-labels (1 = take trade, 0 = skip trade)
        
        Example:
            >>> meta_labels = meta.create_meta_labels_side(returns, signals, horizon=5)
        """
        meta_labels = []
        
        for i in range(len(returns) - horizon):
            signal = primary_signals.iloc[i]
            
            if signal == 0 or pd.isna(signal):
                # Pas de signal primaire
                meta_labels.append(0)
                continue
            
            # Calculer return sur horizon
            future_returns = returns.iloc[i+1:i+1+horizon].sum()
            
            # Si signal = long (1) : profitable si future_returns > threshold
            # Si signal = short (-1) : profitable si future_returns < -threshold
            if signal > 0:  # Long
                profitable = future_returns > self.min_return_threshold
            else:  # Short
                profitable = future_returns < -self.min_return_threshold
            
            meta_labels.append(1 if profitable else 0)
        
        # Remplir dernières valeurs
        meta_labels.extend([0] * horizon)
        
        return pd.Series(meta_labels, index=returns.index)
    
    def create_meta_labels_size(
        self,
        returns: pd.Series,
        primary_signals: pd.Series,
        horizon: int = 5,
        method: str = 'abs_return'
    ) -> pd.Series:
        """
        Crée les meta-labels pour size prediction.
        
        Meta-label = magnitude du return attendu (pour sizing).
        
        Args:
            returns: Series de returns
            primary_signals: Signaux primaires
            horizon: Horizon de holding
            method: 'abs_return' (return absolu) ou 'sharpe' (return/vol)
        
        Returns:
            Series de meta-labels pour size (valeurs continues)
        """
        size_labels = []
        
        for i in range(len(returns) - horizon):
            signal = primary_signals.iloc[i]
            
            if signal == 0 or pd.isna(signal):
                size_labels.append(0.0)
                continue
            
            # Future returns
            future_rets = returns.iloc[i+1:i+1+horizon]
            
            if method == 'abs_return':
                # Magnitude du return (ajustée pour direction)
                total_ret = future_rets.sum()
                if signal > 0:  # Long
                    size = max(total_ret, 0.0)  # Seulement si profitable
                else:  # Short
                    size = max(-total_ret, 0.0)
            
            elif method == 'sharpe':
                # Sharpe-like : return / vol
                total_ret = future_rets.sum()
                vol = future_rets.std() if len(future_rets) > 1 else 0.01
                if signal > 0:
                    size = max(total_ret / vol, 0.0)
                else:
                    size = max(-total_ret / vol, 0.0)
            
            else:
                size = 0.0
            
            size_labels.append(float(size))
        
        size_labels.extend([0.0] * horizon)
        
        return pd.Series(size_labels, index=returns.index)
    
    def fit_side(
        self,
        X: pd.DataFrame,
        returns: pd.Series,
        primary_signals: pd.Series,
        horizon: int = 5
    ):
        """
        Entraîne le modèle side meta-labeling.
        
        Args:
            X: Features pour ML
            returns: Returns historiques
            primary_signals: Signaux stratégie primaire
            horizon: Horizon pour créer labels
        """
        # Créer meta-labels
        meta_labels = self.create_meta_labels_side(returns, primary_signals, horizon)
        
        # Filtrer : seulement où il y a un signal primaire
        mask = primary_signals != 0
        X_filtered = X[mask]
        y_filtered = meta_labels[mask]
        
        # Entraîner
        self.meta_model_side.fit(X_filtered, y_filtered)
        self._is_fitted_side = True
        
        # Métriques train
        y_pred = self.meta_model_side.predict(X_filtered)
        accuracy = accuracy_score(y_filtered, y_pred)
        precision = precision_score(y_filtered, y_pred, zero_division=0)
        
        logger.info(f"Side model fitted: accuracy={accuracy:.4f}, precision={precision:.4f}")
    
    def fit_size(
        self,
        X: pd.DataFrame,
        returns: pd.Series,
        primary_signals: pd.Series,
        horizon: int = 5,
        method: str = 'abs_return'
    ):
        """
        Entraîne le modèle size meta-labeling.
        
        Args:
            X: Features
            returns: Returns
            primary_signals: Signaux primaires
            horizon: Horizon
            method: Méthode sizing
        """
        # Créer meta-labels
        size_labels = self.create_meta_labels_size(returns, primary_signals, horizon, method)
        
        # Filtrer : seulement signaux primaires
        mask = primary_signals != 0
        X_filtered = X[mask]
        y_filtered = size_labels[mask]
        
        # Entraîner
        self.meta_model_size.fit(X_filtered, y_filtered)
        self._is_fitted_size = True
        
        # Métriques train
        y_pred = self.meta_model_size.predict(X_filtered)
        mse = np.mean((y_filtered - y_pred) ** 2)
        
        logger.info(f"Size model fitted: MSE={mse:.6f}")
    
    def fit(
        self,
        X: pd.DataFrame,
        returns: pd.Series,
        primary_signals: pd.Series,
        horizon: int = 5,
        fit_size: bool = False,
        size_method: str = 'abs_return'
    ):
        """
        Entraîne side (et optionnellement size).
        
        Args:
            X: Features
            returns: Returns
            primary_signals: Signaux primaires
            horizon: Horizon
            fit_size: Si True, entraîne aussi size model
            size_method: Méthode pour size labels
        """
        self.fit_side(X, returns, primary_signals, horizon)
        
        if fit_size:
            self.fit_size(X, returns, primary_signals, horizon, size_method)
        
        logger.info("MetaLabeler fitted successfully")
    
    def predict_side(
        self,
        X: pd.DataFrame,
        primary_signals: pd.Series,
        return_proba: bool = False
    ) -> pd.Series:
        """
        Prédit side meta-labels (prendre ou non le trade).
        
        Args:
            X: Features
            primary_signals: Signaux primaires
            return_proba: Si True, retourne probabilités au lieu de 0/1
        
        Returns:
            Series de predictions (0=skip, 1=take) ou probabilités
        """
        if not self._is_fitted_side:
            raise ValueError("Side model not fitted yet. Call fit() first.")
        
        # Prédire seulement où il y a signal primaire
        # dtype float : les probabilités (return_proba) ne tiennent pas dans un
        # int64 et pandas >= 3 refuse le downcast silencieux à l'assignation
        predictions = pd.Series(0.0, index=X.index)
        mask = primary_signals != 0
        
        if mask.sum() == 0:
            logger.warning("No primary signals to filter")
            return predictions
        
        X_filtered = X[mask]
        
        if return_proba:
            # Probabilités
            proba = self.meta_model_side.predict_proba(X_filtered)[:, 1]
            predictions[mask] = proba
        else:
            # Binary predictions
            preds = self.meta_model_side.predict(X_filtered)
            predictions[mask] = preds
        
        return predictions
    
    def predict_size(
        self,
        X: pd.DataFrame,
        primary_signals: pd.Series
    ) -> pd.Series:
        """
        Prédit size meta-labels (taille de position).
        
        Args:
            X: Features
            primary_signals: Signaux primaires
        
        Returns:
            Series de sizes prédites
        """
        if not self._is_fitted_size:
            raise ValueError("Size model not fitted yet. Call fit(fit_size=True) first.")
        
        # Prédire size
        sizes = pd.Series(0.0, index=X.index)
        mask = primary_signals != 0
        
        if mask.sum() == 0:
            return sizes
        
        X_filtered = X[mask]
        size_preds = self.meta_model_size.predict(X_filtered)
        sizes[mask] = size_preds
        
        return sizes
    
    def filter_signals(
        self,
        X: pd.DataFrame,
        primary_signals: pd.Series,
        use_size: bool = False
    ) -> pd.Series:
        """
        Filtre signaux primaires avec meta-labeling.
        
        Args:
            X: Features
            primary_signals: Signaux primaires (1=long, -1=short, 0=neutral)
            use_size: Si True, applique aussi size prediction
        
        Returns:
            Series de signaux filtrés (avec sizes si use_size=True)
        """
        # Side prediction
        side_preds = self.predict_side(X, primary_signals, return_proba=True)
        
        # Filtrer : garder seulement signaux avec proba > threshold
        filtered_signals = primary_signals.copy()
        filtered_signals[side_preds < self.side_threshold] = 0
        
        # Optionnel : appliquer sizing
        if use_size and self._is_fitted_size:
            sizes = self.predict_size(X, filtered_signals)
            # Multiplier signal par size (ex: signal=1, size=0.5 -> position=0.5)
            filtered_signals = filtered_signals * sizes
        
        logger.debug(f"Filtered signals: {(filtered_signals != 0).sum()} / {(primary_signals != 0).sum()} kept")
        
        return filtered_signals
    
    def evaluate(
        self,
        X: pd.DataFrame,
        returns: pd.Series,
        primary_signals: pd.Series,
        horizon: int = 5
    ) -> Dict:
        """
        Évalue performance du meta-labeling.
        
        Args:
            X: Features
            returns: Returns
            primary_signals: Signaux primaires
            horizon: Horizon
        
        Returns:
            Dict avec métriques side + amélioration vs primary
        """
        if not self._is_fitted_side:
            raise ValueError("Model not fitted")
        
        # Créer true labels
        true_labels = self.create_meta_labels_side(returns, primary_signals, horizon)
        
        # Prédictions
        pred_labels = self.predict_side(X, primary_signals, return_proba=False)
        
        # Métriques (seulement où signal primaire existe)
        mask = primary_signals != 0
        y_true = true_labels[mask]
        y_pred = pred_labels[mask]
        
        metrics = {
            'accuracy': accuracy_score(y_true, y_pred),
            'precision': precision_score(y_true, y_pred, zero_division=0),
            'recall': recall_score(y_true, y_pred, zero_division=0),
            'f1': f1_score(y_true, y_pred, zero_division=0),
            'n_signals_primary': int((primary_signals != 0).sum()),
            'n_signals_filtered': int((pred_labels != 0).sum())
        }
        
        logger.info(f"Meta-labeling evaluation: accuracy={metrics['accuracy']:.4f}, precision={metrics['precision']:.4f}")
        
        return metrics


def create_meta_labels(
    returns: pd.Series,
    primary_signals: pd.Series,
    horizon: int = 5,
    min_return: float = 0.0
) -> pd.Series:
    """
    Fonction convenience pour créer meta-labels side.
    
    Args:
        returns: Returns series
        primary_signals: Signaux primaires
        horizon: Horizon
        min_return: Return min pour label=1
    
    Returns:
        Series de meta-labels (0 ou 1)
    
    Example:
        >>> meta_labels = create_meta_labels(returns, signals, horizon=5)
    """
    meta = MetaLabeler(min_return_threshold=min_return)
    labels = meta.create_meta_labels_side(returns, primary_signals, horizon)
    
    return labels

"""
Purged K-Fold Cross-Validation Module.

K-Fold CV adapté aux time series avec :
- Purging : Suppression des observations qui chevauchent train/test
- Embargo : Période de buffer après chaque test set
- Time-series awareness : Respecte l'ordre temporel
- Leakage prevention : Évite les fuites d'information

Based on : Prado, M. L. de. (2018). Advances in Financial Machine Learning, Chapter 7.
"""

from typing import Dict, List, Optional, Tuple, Generator
import numpy as np
import pandas as pd
from datetime import timedelta

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class PurgedKFold:
    """
    K-Fold cross-validation avec purging et embargo pour time series.
    
    Le purging élimine les observations train qui overlappent avec test
    (basé sur timestamps ou indices). L'embargo ajoute un buffer temporel
    après le test set pour éviter look-ahead bias.
    
    Attributes:
        n_splits: Nombre de folds
        pct_embargo: % de données à embargoer après test (0.01 = 1%)
        purge_method: 'simple' (indices) ou 'timestamps' (dates)
    
    Example:
        >>> cv = PurgedKFold(n_splits=5, pct_embargo=0.01)
        >>> for train_idx, test_idx in cv.split(data, timestamps):
        ...     train_data = data.iloc[train_idx]
        ...     test_data = data.iloc[test_idx]
        ...     # Train/test model
    """
    
    def __init__(
        self,
        n_splits: int = 5,
        pct_embargo: float = 0.01,
        purge_method: str = 'simple'
    ):
        """
        Initialise PurgedKFold.
        
        Args:
            n_splits: Nombre de folds (doit être >= 2)
            pct_embargo: Pourcentage données à embargoer après test
            purge_method: 'simple' (index-based) ou 'timestamps' (time-based)
        
        Raises:
            ValueError: Si n_splits < 2 ou pct_embargo invalide
        """
        if n_splits < 2:
            raise ValueError(f"n_splits must be >= 2, got {n_splits}")
        
        if not 0 <= pct_embargo < 1:
            raise ValueError(f"pct_embargo must be in [0, 1), got {pct_embargo}")
        
        if purge_method not in ['simple', 'timestamps']:
            raise ValueError(f"purge_method must be 'simple' or 'timestamps', got {purge_method}")
        
        self.n_splits = n_splits
        self.pct_embargo = pct_embargo
        self.purge_method = purge_method
        
        logger.debug(f"PurgedKFold initialized: {n_splits} splits, embargo {pct_embargo:.2%}")
    
    def split(
        self,
        X: pd.DataFrame,
        timestamps: Optional[pd.Series] = None,
        groups: Optional[pd.Series] = None
    ) -> Generator[Tuple[np.ndarray, np.ndarray], None, None]:
        """
        Génère indices (train, test) pour chaque fold.
        
        Args:
            X: DataFrame avec features
            timestamps: Series avec t1 timestamps (fin de chaque observation)
            groups: Groupes optionnels (non utilisé pour l'instant)
        
        Yields:
            (train_indices, test_indices) pour chaque fold
        
        Example:
            >>> for train_idx, test_idx in cv.split(X, timestamps):
            ...     print(f"Train: {len(train_idx)}, Test: {len(test_idx)}")
        """
        n = len(X)
        indices = np.arange(n)
        
        # Taille de chaque fold
        test_fold_size = n // self.n_splits
        embargo_size = int(test_fold_size * self.pct_embargo)
        
        for fold_idx in range(self.n_splits):
            # Test set indices
            test_start = fold_idx * test_fold_size
            test_end = test_start + test_fold_size if fold_idx < self.n_splits - 1 else n
            test_indices = indices[test_start:test_end]
            
            # Embargo : ajouter buffer après test
            embargo_end = min(test_end + embargo_size, n)
            
            # Train set : tout sauf test + embargo
            if self.purge_method == 'simple':
                # Simple : exclure juste les indices test + embargo
                train_mask = np.ones(n, dtype=bool)
                train_mask[test_start:embargo_end] = False
                train_indices = indices[train_mask]
            
            else:  # timestamps
                if timestamps is None:
                    logger.warning("timestamps=None but purge_method='timestamps', falling back to simple")
                    train_mask = np.ones(n, dtype=bool)
                    train_mask[test_start:embargo_end] = False
                    train_indices = indices[train_mask]
                else:
                    # Purging basé sur timestamps : éliminer train qui overlap avec test
                    train_indices = self._purge_by_timestamps(
                        indices, test_indices, timestamps, embargo_end
                    )
            
            logger.debug(f"Fold {fold_idx}: train={len(train_indices)}, test={len(test_indices)}, embargo={embargo_size}")
            
            yield train_indices, test_indices
    
    def _purge_by_timestamps(
        self,
        all_indices: np.ndarray,
        test_indices: np.ndarray,
        timestamps: pd.Series,
        embargo_end: int
    ) -> np.ndarray:
        """
        Purge train set basé sur timestamps (élimine overlaps).
        
        Args:
            all_indices: Tous les indices disponibles
            test_indices: Indices du test set
            timestamps: t1 timestamps (fin observation)
            embargo_end: Index fin d'embargo
        
        Returns:
            Train indices purgés
        """
        # t0 = index (début observation), t1 = timestamp (fin observation)
        test_t0 = test_indices[0] if len(test_indices) > 0 else embargo_end
        test_t1_max = timestamps.iloc[test_indices].max() if len(test_indices) > 0 else timestamps.iloc[embargo_end - 1]
        
        # Purger : garder seulement train où t1 < test_t0 (avant test)
        # OU t0 >= embargo_end (après embargo)
        train_mask = (
            (timestamps < timestamps.iloc[test_t0]) |  # Avant test
            (all_indices >= embargo_end)  # Après embargo
        )
        
        train_indices = all_indices[train_mask]
        
        return train_indices
    
    def get_n_splits(self, X=None, y=None, groups=None) -> int:
        """Retourne nombre de splits."""
        return self.n_splits


def purged_kfold_split(
    X: pd.DataFrame,
    n_splits: int = 5,
    pct_embargo: float = 0.01,
    timestamps: Optional[pd.Series] = None
) -> List[Tuple[np.ndarray, np.ndarray]]:
    """
    Fonction convenience pour générer tous les splits purged k-fold.
    
    Args:
        X: DataFrame avec features
        n_splits: Nombre de folds
        pct_embargo: % embargo
        timestamps: t1 timestamps optionnels
    
    Returns:
        Liste de tuples (train_indices, test_indices)
    
    Example:
        >>> splits = purged_kfold_split(X, n_splits=5, pct_embargo=0.02)
        >>> for train_idx, test_idx in splits:
        ...     # Utiliser splits
    """
    cv = PurgedKFold(n_splits=n_splits, pct_embargo=pct_embargo)
    splits = list(cv.split(X, timestamps))
    
    logger.info(f"Generated {len(splits)} purged k-fold splits")
    
    return splits


class CombinatorialPurgedCV:
    """
    Combinatorial Purged Cross-Validation.
    
    Génère backtest paths avec différentes combinaisons de train/test splits
    pour tester robustesse et éviter overfitting sur une séquence spécifique.
    
    Attributes:
        n_splits: Nombre de splits K-Fold
        n_paths: Nombre de paths à générer
        pct_embargo: % embargo
    
    Example:
        >>> cv = CombinatorialPurgedCV(n_splits=5, n_paths=10)
        >>> paths = cv.generate_paths(X, timestamps)
        >>> for path in paths:
        ...     # Backtest chaque path
    
    Based on : Prado (2018), Chapter 7.
    """
    
    def __init__(
        self,
        n_splits: int = 5,
        n_paths: int = 10,
        pct_embargo: float = 0.01
    ):
        """
        Initialise CombinatorialPurgedCV.
        
        Args:
            n_splits: Nombre de K-Fold splits
            n_paths: Nombre de combinatorial paths
            pct_embargo: % embargo
        """
        self.n_splits = n_splits
        self.n_paths = n_paths
        self.pct_embargo = pct_embargo
        
        self.base_cv = PurgedKFold(n_splits=n_splits, pct_embargo=pct_embargo)
        
        logger.debug(f"CombinatorialPurgedCV: {n_splits} splits, {n_paths} paths")
    
    def generate_paths(
        self,
        X: pd.DataFrame,
        timestamps: Optional[pd.Series] = None
    ) -> List[List[Tuple[np.ndarray, np.ndarray]]]:
        """
        Génère N backtest paths combinatoriaux.
        
        Chaque path est une permutation aléatoire des K splits.
        
        Args:
            X: DataFrame features
            timestamps: t1 timestamps
        
        Returns:
            Liste de paths, chaque path = liste de (train, test) splits
        
        Example:
            >>> paths = cv.generate_paths(X)
            >>> for path_idx, path in enumerate(paths):
            ...     print(f"Path {path_idx}: {len(path)} splits")
        """
        # Générer base splits
        base_splits = list(self.base_cv.split(X, timestamps))
        
        # Générer N paths avec permutations
        paths = []
        rng = np.random.default_rng(seed=42)
        
        for _ in range(self.n_paths):
            # Permuter ordre des splits
            split_order = rng.permutation(len(base_splits))
            path = [base_splits[i] for i in split_order]
            paths.append(path)
        
        logger.info(f"Generated {len(paths)} combinatorial paths")
        
        return paths
    
    def backtest_paths(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        model_class: type,
        timestamps: Optional[pd.Series] = None,
        **model_kwargs
    ) -> Dict:
        """
        Backtest sur tous les paths combinatoriaux.
        
        Args:
            X: Features
            y: Target
            model_class: Classe du modèle (sklearn-like)
            timestamps: t1 timestamps
            **model_kwargs: Arguments pour instancier modèle
        
        Returns:
            Dict avec résultats par path + agrégés
        
        Example:
            >>> from sklearn.ensemble import RandomForestClassifier
            >>> results = cv.backtest_paths(X, y, RandomForestClassifier, n_estimators=100)
        """
        paths = self.generate_paths(X, timestamps)
        
        path_results = []
        
        for path_idx, path in enumerate(paths):
            logger.info(f"Backtesting path {path_idx + 1}/{len(paths)}")
            
            path_predictions = []
            path_true_labels = []
            
            for train_idx, test_idx in path:
                # Train
                X_train = X.iloc[train_idx]
                y_train = y.iloc[train_idx]
                
                model = model_class(**model_kwargs)
                model.fit(X_train, y_train)
                
                # Test
                X_test = X.iloc[test_idx]
                y_test = y.iloc[test_idx]
                
                predictions = model.predict(X_test)
                
                path_predictions.extend(predictions)
                path_true_labels.extend(y_test)
            
            # Métriques pour ce path
            from sklearn.metrics import accuracy_score, precision_score, recall_score
            
            accuracy = accuracy_score(path_true_labels, path_predictions)
            precision = precision_score(path_true_labels, path_predictions, average='weighted', zero_division=0)
            recall = recall_score(path_true_labels, path_predictions, average='weighted', zero_division=0)
            
            path_results.append({
                'path_idx': path_idx,
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall,
                'n_predictions': len(path_predictions)
            })
        
        # Agrégation
        accuracies = [r['accuracy'] for r in path_results]
        precisions = [r['precision'] for r in path_results]
        recalls = [r['recall'] for r in path_results]
        
        results = {
            'n_paths': len(paths),
            'path_results': path_results,
            'aggregate': {
                'mean_accuracy': float(np.mean(accuracies)),
                'std_accuracy': float(np.std(accuracies)),
                'mean_precision': float(np.mean(precisions)),
                'std_precision': float(np.std(precisions)),
                'mean_recall': float(np.mean(recalls)),
                'std_recall': float(np.std(recalls))
            }
        }
        
        logger.info(f"Combinatorial CV complete: mean accuracy = {results['aggregate']['mean_accuracy']:.4f}")
        
        return results


def generate_backtest_paths(
    X: pd.DataFrame,
    n_splits: int = 5,
    n_paths: int = 10,
    pct_embargo: float = 0.01,
    timestamps: Optional[pd.Series] = None
) -> List[List[Tuple[np.ndarray, np.ndarray]]]:
    """
    Fonction convenience pour générer backtest paths combinatoriaux.
    
    Args:
        X: Features DataFrame
        n_splits: Nombre de K-Fold splits
        n_paths: Nombre de paths
        pct_embargo: % embargo
        timestamps: t1 timestamps
    
    Returns:
        Liste de paths
    
    Example:
        >>> paths = generate_backtest_paths(X, n_splits=5, n_paths=10)
    """
    cv = CombinatorialPurgedCV(n_splits=n_splits, n_paths=n_paths, pct_embargo=pct_embargo)
    paths = cv.generate_paths(X, timestamps)
    
    return paths

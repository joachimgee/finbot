"""
Feature Importance Analysis Module.

Méthodes avancées pour mesurer importance des features ML :
1. **SHAP** (SHapley Additive exPlanations) : game-theory based
2. **Permutation Importance** : robuste, model-agnostic
3. **MDI** (Mean Decrease Impurity) : pour tree-based models
4. **MDA** (Mean Decrease Accuracy) : drop-column importance

Based on: 
- Lundberg, S., & Lee, S. (2017). A Unified Approach to Interpreting Model Predictions.
- Prado, M. L. de. (2018). Advances in Financial Machine Learning, Chapter 8.
"""

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.metrics import accuracy_score, mean_squared_error, log_loss
from sklearn.inspection import permutation_importance

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class FeatureImportanceAnalyzer:
    """
    Analyseur d'importance features avec méthodes avancées.
    
    Attributes:
        model: Modèle ML entraîné
        X_train: Features train
        y_train: Target train
        X_test: Features test
        y_test: Target test
    
    Example:
        >>> fia = FeatureImportanceAnalyzer(model, X_train, y_train, X_test, y_test)
        >>> mdi_scores = fia.get_mdi_importance()
        >>> mda_scores = fia.get_mda_importance()
        >>> shap_values = fia.get_shap_importance()
    """
    
    def __init__(
        self,
        model: Any,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_test: pd.DataFrame,
        y_test: pd.Series
    ):
        """
        Initialise FeatureImportanceAnalyzer.
        
        Args:
            model: Modèle sklearn entraîné
            X_train: Features train
            y_train: Target train
            X_test: Features test
            y_test: Target test
        """
        self.model = model
        self.X_train = X_train
        self.y_train = y_train
        self.X_test = X_test
        self.y_test = y_test
        
        self.feature_names = X_train.columns.tolist()
        
        logger.debug(f"FeatureImportanceAnalyzer initialized with {len(self.feature_names)} features")
    
    def get_mdi_importance(self) -> pd.Series:
        """
        Mean Decrease Impurity (MDI) importance.
        
        Disponible pour tree-based models (RandomForest, GradientBoosting, etc.).
        Mesure : réduction moyenne d'impureté (Gini ou entropy) par feature.
        
        Returns:
            Series d'importance normalisée (somme = 1)
        
        Raises:
            ValueError: Si modèle n'a pas feature_importances_
        
        Example:
            >>> mdi = fia.get_mdi_importance()
            >>> print(mdi.sort_values(ascending=False).head(10))
        """
        if not hasattr(self.model, 'feature_importances_'):
            raise ValueError("Model does not have feature_importances_ attribute")
        
        importances = self.model.feature_importances_
        
        result = pd.Series(
            importances,
            index=self.feature_names,
            name='mdi_importance'
        ).sort_values(ascending=False)
        
        logger.info(f"MDI importance computed: top feature={result.index[0]} ({result.iloc[0]:.3f})")
        
        return result
    
    def get_mda_importance(
        self,
        n_repeats: int = 10,
        scoring: Optional[str] = None,
        random_state: int = 42
    ) -> pd.Series:
        """
        Mean Decrease Accuracy (MDA) importance.
        
        Stratégie :
        1. Calculer score baseline (modèle entraîné)
        2. Pour chaque feature :
           - Permuter feature (shuffle)
           - Recalculer score
           - Importance = baseline - score_permuted
        3. Répéter n_repeats fois et moyenner
        
        Args:
            n_repeats: Nombre de permutations par feature
            scoring: Métrique ('accuracy', 'neg_log_loss', etc.)
            random_state: Seed pour reproductibilité
        
        Returns:
            Series d'importance
        
        Example:
            >>> mda = fia.get_mda_importance(n_repeats=20)
        """
        # Auto-détecter scoring
        if scoring is None:
            if hasattr(self.model, 'predict_proba'):
                scoring = 'neg_log_loss'  # Classification
            else:
                scoring = 'neg_mean_squared_error'  # Regression
        
        # Permutation importance (sklearn)
        result = permutation_importance(
            self.model,
            self.X_test,
            self.y_test,
            n_repeats=n_repeats,
            random_state=random_state,
            n_jobs=-1
        )
        
        importances = pd.Series(
            result.importances_mean,
            index=self.feature_names,
            name='mda_importance'
        ).sort_values(ascending=False)
        
        logger.info(f"MDA importance computed: top feature={importances.index[0]} ({importances.iloc[0]:.4f})")
        
        return importances
    
    def get_shap_importance(
        self,
        use_kernel: bool = False,
        n_samples: int = 100
    ) -> pd.DataFrame:
        """
        SHAP (SHapley Additive exPlanations) importance.
        
        SHAP utilise game theory pour attribuer importance.
        Avantages :
        - Consistant : somme SHAP values = prédiction - baseline
        - Local + global explanations
        - Model-agnostic
        
        Args:
            use_kernel: Si True, utilise KernelExplainer (plus lent, model-agnostic)
            n_samples: Nombre samples pour KernelExplainer
        
        Returns:
            DataFrame avec mean_shap_value par feature
        
        Raises:
            ImportError: Si shap non installé
        
        Example:
            >>> shap_df = fia.get_shap_importance()
            >>> print(shap_df.sort_values('mean_abs_shap', ascending=False))
        """
        try:
            import shap
        except ImportError:
            logger.error("SHAP not installed. Install with: pip install shap")
            raise ImportError("SHAP library required. Install with: pip install shap")
        
        # Explainer
        if use_kernel:
            logger.info("Using SHAP KernelExplainer (model-agnostic)")
            explainer = shap.KernelExplainer(
                self.model.predict_proba if hasattr(self.model, 'predict_proba') else self.model.predict,
                shap.sample(self.X_train, n_samples)
            )
        else:
            # TreeExplainer (plus rapide pour tree-based models)
            if hasattr(self.model, 'estimators_'):  # RandomForest, etc.
                logger.info("Using SHAP TreeExplainer")
                explainer = shap.TreeExplainer(self.model)
            else:
                logger.info("Fallback to SHAP KernelExplainer")
                explainer = shap.KernelExplainer(
                    self.model.predict,
                    shap.sample(self.X_train, n_samples)
                )
        
        # Calculer SHAP values
        shap_values = explainer.shap_values(self.X_test)
        
        # Si classification multi-class, prendre classe 1
        if isinstance(shap_values, list):
            shap_values = shap_values[1]
        
        # Importance = moyenne abs(SHAP)
        mean_abs_shap = np.abs(shap_values).mean(axis=0)
        
        result = pd.DataFrame({
            'feature': self.feature_names,
            'mean_abs_shap': mean_abs_shap
        }).sort_values('mean_abs_shap', ascending=False)
        
        logger.info(f"SHAP importance computed: top feature={result.iloc[0]['feature']} ({result.iloc[0]['mean_abs_shap']:.4f})")
        
        return result
    
    def get_combined_importance(
        self,
        methods: List[str] = ['mdi', 'mda'],
        weights: Optional[Dict[str, float]] = None
    ) -> pd.Series:
        """
        Combine plusieurs méthodes d'importance.
        
        Stratégie : moyenne pondérée des ranks.
        
        Args:
            methods: Liste de méthodes ('mdi', 'mda', 'shap')
            weights: Poids pour chaque méthode (si None, équi-pondéré)
        
        Returns:
            Series d'importance combinée
        
        Example:
            >>> combined = fia.get_combined_importance(methods=['mdi', 'mda', 'shap'])
        """
        if weights is None:
            weights = {m: 1.0 / len(methods) for m in methods}
        
        # Calculer ranks pour chaque méthode
        ranks = {}
        
        if 'mdi' in methods:
            mdi = self.get_mdi_importance()
            ranks['mdi'] = mdi.rank(ascending=False)
        
        if 'mda' in methods:
            mda = self.get_mda_importance()
            ranks['mda'] = mda.rank(ascending=False)
        
        if 'shap' in methods:
            shap_df = self.get_shap_importance()
            shap_series = shap_df.set_index('feature')['mean_abs_shap']
            ranks['shap'] = shap_series.rank(ascending=False)
        
        # Moyenne pondérée des ranks
        combined_rank = pd.Series(0.0, index=self.feature_names)
        
        for method, rank_series in ranks.items():
            combined_rank += rank_series * weights[method]
        
        # Lower rank = plus important
        result = combined_rank.sort_values()
        result.name = 'combined_importance_rank'
        
        logger.info(f"Combined importance: top feature={result.index[0]}")
        
        return result
    
    def plot_importance_comparison(self) -> pd.DataFrame:
        """
        Compare MDI, MDA, et SHAP dans un DataFrame.
        
        Returns:
            DataFrame avec 3 colonnes (mdi, mda, shap)
        
        Example:
            >>> df = fia.plot_importance_comparison()
            >>> df.plot(kind='barh')
        """
        mdi = self.get_mdi_importance()
        mda = self.get_mda_importance()
        
        try:
            shap_df = self.get_shap_importance()
            shap_series = shap_df.set_index('feature')['mean_abs_shap']
        except Exception as e:
            logger.warning(f"SHAP failed: {e}")
            shap_series = pd.Series(0, index=self.feature_names)
        
        comparison = pd.DataFrame({
            'mdi': mdi,
            'mda': mda,
            'shap': shap_series
        })
        
        # Normaliser chaque colonne [0, 1]
        for col in comparison.columns:
            comparison[col] = (comparison[col] - comparison[col].min()) / (comparison[col].max() - comparison[col].min() + 1e-8)
        
        return comparison.sort_values('mdi', ascending=False)
    
    def detect_feature_interactions(
        self,
        top_n: int = 10,
        method: str = 'shap'
    ) -> pd.DataFrame:
        """
        Détecte interactions entre features (SHAP interaction values).
        
        Args:
            top_n: Top N features à analyser
            method: Méthode ('shap' pour l'instant)
        
        Returns:
            DataFrame avec paires de features et interaction strength
        
        Example:
            >>> interactions = fia.detect_feature_interactions(top_n=5)
        """
        if method != 'shap':
            raise ValueError("Only SHAP interactions supported for now")
        
        try:
            import shap
        except ImportError:
            raise ImportError("SHAP required for interaction detection")
        
        # TreeExplainer avec interactions
        if not hasattr(self.model, 'estimators_'):
            logger.warning("Interaction detection requires tree-based model")
            return pd.DataFrame()
        
        explainer = shap.TreeExplainer(self.model)
        shap_interaction = explainer.shap_interaction_values(self.X_test[:100])  # Limiter pour performance
        
        # Si multi-class, prendre classe 1
        if isinstance(shap_interaction, list):
            shap_interaction = shap_interaction[1]
        
        # Extraire interactions (triangular supérieur)
        n_features = len(self.feature_names)
        interactions = []
        
        for i in range(n_features):
            for j in range(i + 1, n_features):
                interaction_strength = np.abs(shap_interaction[:, i, j]).mean()
                interactions.append({
                    'feature1': self.feature_names[i],
                    'feature2': self.feature_names[j],
                    'interaction_strength': interaction_strength
                })
        
        result = pd.DataFrame(interactions).sort_values('interaction_strength', ascending=False)
        
        logger.info(f"Detected {len(result)} feature interactions")
        
        return result.head(top_n)


def get_feature_importance(
    model: Any,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    method: str = 'mdi'
) -> pd.Series:
    """
    Fonction convenience pour feature importance.
    
    Args:
        model: Modèle entraîné
        X_train: Features train
        y_train: Target train
        X_test: Features test
        y_test: Target test
        method: 'mdi', 'mda', ou 'shap'
    
    Returns:
        Series d'importance
    
    Example:
        >>> importance = get_feature_importance(rf_model, X_train, y_train, X_test, y_test, method='mda')
    """
    fia = FeatureImportanceAnalyzer(model, X_train, y_train, X_test, y_test)
    
    if method == 'mdi':
        return fia.get_mdi_importance()
    elif method == 'mda':
        return fia.get_mda_importance()
    elif method == 'shap':
        return fia.get_shap_importance()
    else:
        raise ValueError(f"Unknown method: {method}")

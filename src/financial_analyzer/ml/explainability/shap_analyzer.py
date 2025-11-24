"""
SHAP Analyzer for ML Model Explainability.

Provides SHAP value computation for feature importance analysis of ML models.
Supports tree-based models (Random Forest, XGBoost) and deep learning (LSTM, neural networks).

Author: FinBot Team
Created: 2025
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from matplotlib.figure import Figure

from financial_analyzer.utils.helpers import get_logger

matplotlib.use("Agg")  # Non-interactive backend for server environments

logger = get_logger(__name__)


@dataclass
class SHAPResult:
    """
    Container for SHAP analysis results.
    
    Attributes:
        shap_values: SHAP values array (n_samples, n_features)
        base_value: Expected value (baseline prediction)
        feature_names: List of feature names
        feature_importance: Dict mapping feature names to importance scores
        data: Original input data used for SHAP computation
    """

    shap_values: np.ndarray
    base_value: Union[float, np.ndarray]
    feature_names: List[str]
    feature_importance: Dict[str, float] = field(default_factory=dict)
    data: Optional[np.ndarray] = None


class SHAPAnalyzer:
    """
    SHAP-based model explainability analyzer.
    
    Computes SHAP values to explain model predictions and rank feature importance.
    Supports multiple model types with automatic explainer selection.
    
    Args:
        model: Trained ML model (sklearn, keras, torch, or custom predictor)
        feature_names: List of feature names (must match model input dim)
        model_type: Type of model ('tree', 'deep', 'linear', 'kernel', 'auto')
            - 'tree': TreeExplainer for Random Forest, XGBoost, LightGBM
            - 'deep': DeepExplainer for neural networks (Keras/PyTorch)
            - 'linear': LinearExplainer for linear models
            - 'kernel': KernelExplainer (model-agnostic, slower)
            - 'auto': Auto-detect based on model type
        background_data: Background dataset for KernelExplainer (optional)
        max_display: Maximum features to display in plots (default: 20)
        cache_shap_values: Whether to cache computed SHAP values (default: True)
    
    Example:
        >>> from sklearn.ensemble import RandomForestClassifier
        >>> from financial_analyzer.ml.explainability import SHAPAnalyzer
        >>> 
        >>> # Train a model
        >>> model = RandomForestClassifier(n_estimators=100)
        >>> model.fit(X_train, y_train)
        >>> 
        >>> # Create analyzer
        >>> analyzer = SHAPAnalyzer(
        ...     model=model,
        ...     feature_names=['price_rsi', 'volume_obv', 'macd'],
        ...     model_type='tree'
        ... )
        >>> 
        >>> # Compute SHAP values
        >>> result = analyzer.compute_shap_values(X_test[:100])
        >>> print(result.feature_importance)
        >>> 
        >>> # Visualize
        >>> analyzer.plot_feature_importance(result, save_path="importance.png")
    """

    def __init__(
        self,
        model: Any,
        feature_names: List[str],
        model_type: str = "auto",
        background_data: Optional[np.ndarray] = None,
        max_display: int = 20,
        cache_shap_values: bool = True,
    ):
        """Initialize SHAP analyzer with model and configuration."""
        self.model = model
        self.feature_names = feature_names
        self.model_type = model_type
        self.background_data = background_data
        self.max_display = max_display
        self.cache_shap_values = cache_shap_values

        # Cache for computed SHAP values
        self._shap_cache: Dict[str, SHAPResult] = {}

        # Initialize explainer
        self.explainer = self._create_explainer()

        logger.info(
            f"SHAPAnalyzer initialized with {len(feature_names)} features, "
            f"model_type={model_type}"
        )

    def _create_explainer(self) -> shap.Explainer:
        """
        Create appropriate SHAP explainer based on model type.
        
        Returns:
            SHAP explainer instance
        
        Raises:
            ValueError: If model type is unsupported or auto-detection fails
        """
        model_type = self.model_type.lower()

        # Auto-detect model type
        if model_type == "auto":
            model_type = self._detect_model_type()
            logger.info(f"Auto-detected model type: {model_type}")

        try:
            if model_type == "tree":
                # Tree-based models (RF, XGBoost, LightGBM)
                return shap.TreeExplainer(self.model)

            elif model_type == "deep":
                # Deep learning models (Keras, PyTorch)
                if self.background_data is None:
                    raise ValueError(
                        "background_data required for DeepExplainer. "
                        "Provide representative sample of training data."
                    )
                return shap.DeepExplainer(self.model, self.background_data)

            elif model_type == "linear":
                # Linear models: Use KernelExplainer (LinearExplainer has masker limitations)
                if self.background_data is None:
                    raise ValueError(
                        "background_data required for LinearExplainer. "
                        "Provide representative sample of training data."
                    )
                predict_fn = self._get_predict_function()
                return shap.KernelExplainer(predict_fn, self.background_data)

            elif model_type == "kernel":
                # Model-agnostic explainer (slower)
                if self.background_data is None:
                    raise ValueError(
                        "background_data required for KernelExplainer. "
                        "Provide representative sample of training data."
                    )
                predict_fn = self._get_predict_function()
                return shap.KernelExplainer(predict_fn, self.background_data)

            else:
                raise ValueError(
                    f"Unsupported model_type: {model_type}. "
                    f"Use 'tree', 'deep', 'linear', 'kernel', or 'auto'."
                )

        except Exception as e:
            logger.error(f"Failed to create SHAP explainer: {e}")
            raise ValueError(f"Could not create explainer for model: {e}") from e

    def _detect_model_type(self) -> str:
        """
        Auto-detect model type from model class.
        
        Returns:
            Detected model type string
        """
        model_class_name = self.model.__class__.__name__.lower()

        # Tree-based models
        if any(
            name in model_class_name
            for name in ["forest", "tree", "xgb", "lightgbm", "catboost"]
        ):
            return "tree"

        # Deep learning models
        if any(
            name in model_class_name
            for name in ["sequential", "model", "lstm", "gru", "transformer"]
        ):
            return "deep"

        # Linear models
        if any(
            name in model_class_name
            for name in ["linear", "logistic", "ridge", "lasso"]
        ):
            return "linear"

        # Default to kernel explainer (model-agnostic)
        logger.warning(
            f"Could not auto-detect model type for {model_class_name}. "
            "Defaulting to KernelExplainer (may be slow)."
        )
        return "kernel"

    def _get_predict_function(self) -> callable:
        """
        Get appropriate prediction function from model.
        
        Returns:
            Prediction function callable
        """
        # Try common prediction methods
        if hasattr(self.model, "predict_proba"):
            return self.model.predict_proba
        elif hasattr(self.model, "predict"):
            return self.model.predict
        elif callable(self.model):
            return self.model
        else:
            raise ValueError(
                "Model must have 'predict', 'predict_proba', or be callable"
            )

    def compute_shap_values(
        self,
        X: Union[np.ndarray, pd.DataFrame],
        cache_key: Optional[str] = None,
        compute_importance: bool = True,
    ) -> SHAPResult:
        """
        Compute SHAP values for input data.
        
        Args:
            X: Input data (n_samples, n_features)
            cache_key: Optional key for caching results
            compute_importance: Whether to compute feature importance (default: True)
        
        Returns:
            SHAPResult containing shap_values, base_value, and feature_importance
        
        Raises:
            ValueError: If input shape doesn't match feature_names
        
        Example:
            >>> result = analyzer.compute_shap_values(X_test[:100])
            >>> print(f"Base value: {result.base_value:.4f}")
            >>> print(f"Top feature: {max(result.feature_importance, key=result.feature_importance.get)}")
        """
        # Check cache
        if cache_key and self.cache_shap_values and cache_key in self._shap_cache:
            logger.debug(f"Using cached SHAP values for key: {cache_key}")
            return self._shap_cache[cache_key]

        # Convert to numpy array
        if isinstance(X, pd.DataFrame):
            X = X.values

        # Validate input shape
        if X.shape[1] != len(self.feature_names):
            raise ValueError(
                f"Input has {X.shape[1]} features but expected "
                f"{len(self.feature_names)} (feature_names length)"
            )

        logger.info(f"Computing SHAP values for {X.shape[0]} samples...")

        try:
            # Compute SHAP values
            shap_values_raw = self.explainer.shap_values(X)

            # Handle multi-class output
            if isinstance(shap_values_raw, list):
                # Multi-class as list: use positive class (index 1) for binary
                shap_values = shap_values_raw[1] if len(shap_values_raw) > 1 else shap_values_raw[0]
            elif isinstance(shap_values_raw, np.ndarray) and len(shap_values_raw.shape) == 3:
                # Multi-class as 3D array: use positive class (index 1)
                shap_values = shap_values_raw[:, :, 1]
            else:
                shap_values = shap_values_raw

            # Get base value (expected value)
            if hasattr(self.explainer, "expected_value"):
                base_value = self.explainer.expected_value
                if isinstance(base_value, (list, np.ndarray)):
                    base_value = base_value[1] if len(base_value) > 1 else base_value[0]
                if isinstance(base_value, np.ndarray):
                    base_value = float(base_value.item())
            else:
                base_value = 0.0

            # Compute feature importance
            feature_importance = {}
            if compute_importance:
                feature_importance = self._compute_feature_importance(shap_values)

            # Create result
            result = SHAPResult(
                shap_values=shap_values,
                base_value=base_value,
                feature_names=self.feature_names,
                feature_importance=feature_importance,
                data=X,
            )

            # Cache result
            if cache_key and self.cache_shap_values:
                self._shap_cache[cache_key] = result

            logger.info("SHAP values computed successfully")
            return result

        except Exception as e:
            logger.error(f"Failed to compute SHAP values: {e}")
            raise RuntimeError(f"SHAP computation failed: {e}") from e

    def _compute_feature_importance(self, shap_values: np.ndarray) -> Dict[str, float]:
        """
        Compute feature importance from SHAP values.
        
        Importance is mean absolute SHAP value across all samples.
        
        Args:
            shap_values: SHAP values array (n_samples, n_features)
        
        Returns:
            Dict mapping feature names to importance scores (sorted descending)
        """
        # Handle TreeExplainer output (can have extra dimensions for multi-class)
        if len(shap_values.shape) == 3:
            # Multi-output: Take mean across outputs first
            shap_values = shap_values.mean(axis=2)
        
        # Mean absolute SHAP value per feature
        importance_values = np.abs(shap_values).mean(axis=0)

        # Ensure 1D array
        if len(importance_values.shape) > 1:
            importance_values = importance_values.flatten()

        # Create dict and sort by importance
        importance_dict = {}
        for name, value in zip(self.feature_names, importance_values):
            # Convert numpy types to native Python float
            if isinstance(value, np.ndarray):
                value = float(value.item())
            else:
                value = float(value)
            importance_dict[name] = value

        importance_dict = dict(
            sorted(importance_dict.items(), key=lambda x: x[1], reverse=True)
        )

        logger.debug(
            f"Feature importance computed. Top 3: "
            f"{list(importance_dict.keys())[:3]}"
        )

        return importance_dict

    def get_feature_importance(
        self, result: Optional[SHAPResult] = None, top_k: Optional[int] = None
    ) -> Dict[str, float]:
        """
        Get feature importance ranking.
        
        Args:
            result: SHAPResult from compute_shap_values (if None, uses last cached)
            top_k: Return only top k features (default: all)
        
        Returns:
            Dict mapping feature names to importance scores (sorted descending)
        
        Example:
            >>> importance = analyzer.get_feature_importance(result, top_k=10)
            >>> for name, score in importance.items():
            ...     print(f"{name}: {score:.4f}")
        """
        if result is None:
            # Use last cached result
            if not self._shap_cache:
                raise ValueError("No SHAP values available. Run compute_shap_values() first.")
            result = list(self._shap_cache.values())[-1]

        importance = result.feature_importance

        if top_k is not None:
            importance = dict(list(importance.items())[:top_k])

        return importance

    def plot_feature_importance(
        self,
        result: SHAPResult,
        top_k: Optional[int] = None,
        save_path: Optional[Union[str, Path]] = None,
        figsize: tuple = (10, 8),
        title: str = "Feature Importance (SHAP)",
    ) -> Figure:
        """
        Plot feature importance bar chart.
        
        Args:
            result: SHAPResult from compute_shap_values
            top_k: Show only top k features (default: max_display)
            save_path: Path to save figure (PNG/PDF)
            figsize: Figure size (width, height)
            title: Plot title
        
        Returns:
            Matplotlib Figure object
        
        Example:
            >>> fig = analyzer.plot_feature_importance(result, top_k=15, save_path="importance.png")
        """
        top_k = top_k or self.max_display
        importance = self.get_feature_importance(result, top_k=top_k)

        # Create bar chart
        fig, ax = plt.subplots(figsize=figsize)

        features = list(importance.keys())
        values = list(importance.values())

        ax.barh(features[::-1], values[::-1], color="steelblue", alpha=0.8)
        ax.set_xlabel("Mean |SHAP Value|", fontsize=12)
        ax.set_ylabel("Feature", fontsize=12)
        ax.set_title(title, fontsize=14, fontweight="bold")
        ax.grid(axis="x", alpha=0.3)

        plt.tight_layout()

        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            fig.savefig(save_path, dpi=300, bbox_inches="tight")
            logger.info(f"Feature importance plot saved to {save_path}")

        return fig

    def plot_waterfall(
        self,
        result: SHAPResult,
        idx: int = 0,
        save_path: Optional[Union[str, Path]] = None,
        max_display: Optional[int] = None,
    ) -> Figure:
        """
        Plot SHAP waterfall for single prediction.
        
        Shows how each feature contributes to pushing prediction from base value.
        
        Args:
            result: SHAPResult from compute_shap_values
            idx: Index of sample to explain
            save_path: Path to save figure (PNG/PDF)
            max_display: Max features to display (default: self.max_display)
        
        Returns:
            Matplotlib Figure object
        
        Example:
            >>> # Explain first prediction
            >>> fig = analyzer.plot_waterfall(result, idx=0, save_path="waterfall_0.png")
        """
        max_display = max_display or self.max_display

        # Create SHAP Explanation object
        explanation = shap.Explanation(
            values=result.shap_values[idx],
            base_values=result.base_value,
            data=result.data[idx] if result.data is not None else None,
            feature_names=result.feature_names,
        )

        # Plot waterfall
        fig = plt.figure(figsize=(10, 8))
        shap.plots.waterfall(explanation, max_display=max_display, show=False)

        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            logger.info(f"Waterfall plot saved to {save_path}")

        return fig

    def plot_dependence(
        self,
        result: SHAPResult,
        feature_name: str,
        interaction_feature: Optional[str] = None,
        save_path: Optional[Union[str, Path]] = None,
        figsize: tuple = (10, 6),
    ) -> Figure:
        """
        Plot SHAP dependence (feature value vs SHAP value).
        
        Shows how feature value affects SHAP value (partial dependence).
        
        Args:
            result: SHAPResult from compute_shap_values
            feature_name: Feature to analyze
            interaction_feature: Feature to color points by (auto if None)
            save_path: Path to save figure (PNG/PDF)
            figsize: Figure size (width, height)
        
        Returns:
            Matplotlib Figure object
        
        Example:
            >>> # Show how RSI affects prediction
            >>> fig = analyzer.plot_dependence(result, "price_rsi", save_path="dependence_rsi.png")
        """
        if feature_name not in self.feature_names:
            raise ValueError(f"Feature '{feature_name}' not in feature_names")

        feature_idx = self.feature_names.index(feature_name)

        # Determine interaction feature
        if interaction_feature:
            if interaction_feature not in self.feature_names:
                raise ValueError(f"Interaction feature '{interaction_feature}' not in feature_names")
            interaction_idx = self.feature_names.index(interaction_feature)
        else:
            interaction_idx = "auto"

        # Plot dependence
        fig = plt.figure(figsize=figsize)
        shap.dependence_plot(
            feature_idx,
            result.shap_values,
            result.data,
            feature_names=self.feature_names,
            interaction_index=interaction_idx,
            show=False,
        )

        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            logger.info(f"Dependence plot saved to {save_path}")

        return fig

    def plot_summary(
        self,
        result: SHAPResult,
        plot_type: str = "dot",
        save_path: Optional[Union[str, Path]] = None,
        max_display: Optional[int] = None,
        figsize: tuple = (10, 8),
    ) -> Figure:
        """
        Plot SHAP summary (all samples).
        
        Args:
            result: SHAPResult from compute_shap_values
            plot_type: 'dot' (beeswarm) or 'bar' or 'violin'
            save_path: Path to save figure (PNG/PDF)
            max_display: Max features to display (default: self.max_display)
            figsize: Figure size (width, height)
        
        Returns:
            Matplotlib Figure object
        
        Example:
            >>> fig = analyzer.plot_summary(result, plot_type="dot", save_path="summary.png")
        """
        max_display = max_display or self.max_display

        fig = plt.figure(figsize=figsize)
        shap.summary_plot(
            result.shap_values,
            result.data,
            feature_names=result.feature_names,
            plot_type=plot_type,
            max_display=max_display,
            show=False,
        )

        if save_path:
            save_path = Path(save_path)
            save_path.parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=300, bbox_inches="tight")
            logger.info(f"Summary plot saved to {save_path}")

        return fig

    def clear_cache(self) -> None:
        """Clear cached SHAP values."""
        self._shap_cache.clear()
        logger.info("SHAP cache cleared")

    def get_top_features_for_sample(
        self, result: SHAPResult, idx: int, top_k: int = 5
    ) -> Dict[str, float]:
        """
        Get top contributing features for single prediction.
        
        Args:
            result: SHAPResult from compute_shap_values
            idx: Sample index
            top_k: Number of top features to return
        
        Returns:
            Dict mapping feature names to SHAP values (sorted by abs value)
        
        Example:
            >>> top_features = analyzer.get_top_features_for_sample(result, idx=0, top_k=5)
            >>> for name, shap_val in top_features.items():
            ...     print(f"{name}: {shap_val:+.4f}")
        """
        shap_vals = result.shap_values[idx]
        feature_shap = {
            name: float(val) for name, val in zip(result.feature_names, shap_vals)
        }

        # Sort by absolute value
        feature_shap = dict(
            sorted(feature_shap.items(), key=lambda x: abs(x[1]), reverse=True)
        )

        return dict(list(feature_shap.items())[:top_k])

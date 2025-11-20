# 1. Stdlib
import os
import pickle
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass
from datetime import datetime
import logging

# 2. Données & Calculs
import numpy as np
import pandas as pd

# 3. Financier (optionnel selon ratios)
# from financetoolkit import Toolkit  # non requis ici

# 4. ML & NLP
from sklearn.model_selection import TimeSeriesSplit, GridSearchCV
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression

try:
    from xgboost import XGBRegressor  # type: ignore
    HAS_XGB = True
except Exception:  # pragma: no cover
    HAS_XGB = False

# 5. PurgedKFold CV (financial time series)
try:
    from financial_analyzer.ml.cross_validation import get_purged_kfold_cv
    HAS_PURGED_KFOLD = True
except Exception:  # pragma: no cover
    HAS_PURGED_KFOLD = False

# 6. Projet local
from financial_analyzer.utils.helpers import get_logger


@dataclass
class MLPredictorConfig:
    """Configuration pour MLPredictor."""
    target_horizon: int = 5  # jours à prédire
    rsi_period: int = 14
    bb_window: int = 20
    bb_num_std: float = 2.0
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    sentiment_ma_window: int = 5  # fenêtre MA pour sentiment
    tscv_splits: int = 5
    random_state: int = 42


class MLPredictor:
    """
    Prédicteur ML pour les rendements futurs (1d/5d/1m) basé sur OHLCV, sentiment et ratios.

    - Feature engineering: prices (returns, RSI, MACD, Bollinger), volume (ratios), sentiment (scores), ratios (PE, PB, ROE, D/E)
    - Modèles: 'random_forest', 'xgboost' (si dispo), 'gradient_boosting', 'linear'
    - CV temporelle (TimeSeriesSplit) et GridSearchCV optionnel

    Args:
        config: Configuration du prédicteur (horizons et indicateurs)

    Example:
        >>> predictor = MLPredictor(target_horizon=5)
        >>> X, y = predictor.prepare_features(df_prices, daily_sentiment)
        >>> predictor.train(X, y, model_type='random_forest')
        >>> preds = predictor.predict(X.tail(30))
        >>> metrics = predictor.evaluate(X.tail(30), y.tail(30))
        >>> fi = predictor.get_feature_importance()
        >>> predictor.save_model("./models/aapl_rf_5d.pkl")
        >>> predictor2 = MLPredictor(target_horizon=5)
        >>> predictor2.load_model("./models/aapl_rf_5d.pkl")
    """

    def __init__(self, target_horizon: int = 5, config: Optional[MLPredictorConfig] = None) -> None:
        if target_horizon <= 0:
            raise ValueError("target_horizon doit être > 0")
        self.config = config or MLPredictorConfig(target_horizon=target_horizon)
        self.logger = get_logger(__name__)

        # Modèle / scaler / features
        self.model: Optional[Any] = None
        self.scaler: Optional[StandardScaler] = None
        self.feature_names: List[str] = []
        self.model_type: Optional[str] = None
        self.best_params_: Optional[Dict[str, Any]] = None
        self._is_trained: bool = False

    # ------------------------ Feature Engineering ------------------------
    @staticmethod
    def _calculate_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
        delta = prices.diff()
        gain = delta.clip(lower=0).rolling(window=period).mean()
        loss = (-delta.clip(upper=0)).rolling(window=period).mean()
        rs = gain / (loss + 1e-12)
        rsi = 100 - (100 / (1 + rs))
        return rsi

    @staticmethod
    def _calculate_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Tuple[pd.Series, pd.Series, pd.Series]:
        ema_fast = prices.ewm(span=fast, adjust=False).mean()
        ema_slow = prices.ewm(span=slow, adjust=False).mean()
        macd = ema_fast - ema_slow
        macd_signal = macd.ewm(span=signal, adjust=False).mean()
        macd_hist = macd - macd_signal
        return macd, macd_signal, macd_hist

    @staticmethod
    def _calculate_bollinger(prices: pd.Series, window: int = 20, num_std: float = 2.0) -> Tuple[pd.Series, pd.Series, pd.Series]:
        ma = prices.rolling(window).mean()
        std = prices.rolling(window).std()
        upper = ma + num_std * std
        lower = ma - num_std * std
        width = (upper - lower) / (ma + 1e-12)
        return upper, lower, width

    def prepare_features(
        self,
        df_prices: pd.DataFrame,
        df_sentiment: Optional[pd.DataFrame] = None,
        df_ratios: Optional[pd.DataFrame] = None,
    ) -> Tuple[pd.DataFrame, pd.Series]:
        """
        Construit X, y à partir des prix (OHLCV), du sentiment agrégé et des ratios facultatifs.

        - X: features normalisées (StandardScaler sera ajusté lors du train)
        - y: rendement futur target_horizon (ex: 5 jours)

        Args:
            df_prices: DataFrame OHLCV avec colonnes ['Open','High','Low','Close','Volume'] et DatetimeIndex
            df_sentiment: DataFrame avec colonnes ['sentiment_score','positive','negative','neutral'] (index temporel)
            df_ratios: DataFrame optionnel de ratios financiers (PE, PB, ROE, Debt/Equity), index temporel

        Returns:
            Tuple (X, y)

        Raises:
            ValueError: si colonnes manquantes ou index invalide
        """
        # Validations basiques
        required_cols = {"Close", "Volume"}
        if not isinstance(df_prices.index, pd.DatetimeIndex):
            raise ValueError("df_prices index doit être un DatetimeIndex")
        if not required_cols.issubset(df_prices.columns):
            raise ValueError("df_prices doit contenir au minimum 'Close' et 'Volume'")

        df_prices = df_prices.sort_index().copy()
        # Remplissage fwd/bwd pour trous mineurs
        df_prices[["Close", "Volume"]] = df_prices[["Close", "Volume"]].ffill().bfill()

        close = df_prices["Close"].astype(float)
        volume = df_prices["Volume"].astype(float)

        # Prix features
        returns_1d = close.pct_change(1)
        returns_5d = close.pct_change(5)
        returns_20d = close.pct_change(20)
        volatility_20d = returns_1d.rolling(20).std()
        rsi_14 = self._calculate_rsi(close, period=self.config.rsi_period)
        macd, macd_signal, macd_hist = self._calculate_macd(
            close, fast=self.config.macd_fast, slow=self.config.macd_slow, signal=self.config.macd_signal
        )
        bb_upper, bb_lower, bb_width = self._calculate_bollinger(
            close, window=self.config.bb_window, num_std=self.config.bb_num_std
        )

        # Volume features
        volume_sma_20 = volume.rolling(20).mean()
        volume_ratio = volume / (volume_sma_20 + 1e-12)

        feats = pd.DataFrame(
            {
                "ret_1d": returns_1d,
                "ret_5d": returns_5d,
                "ret_20d": returns_20d,
                "vol_20d": volatility_20d,
                "rsi_14": rsi_14,
                "macd": macd,
                "macd_signal": macd_signal,
                "macd_hist": macd_hist,
                "bb_width": bb_width,
                "volume_ratio": volume_ratio,
                "volume_sma_20": volume_sma_20,
            },
            index=df_prices.index,
        )

        # Sentiment features (optionnels)
        if df_sentiment is not None:
            if not isinstance(df_sentiment.index, pd.DatetimeIndex):
                raise ValueError("df_sentiment index doit être un DatetimeIndex")
            sent = df_sentiment.copy()
            # Garder colonnes pertinentes si dispo
            cols = [c for c in ["sentiment_score", "positive", "negative", "neutral"] if c in sent.columns]
            if "sentiment_score" not in cols:
                self.logger.warning("df_sentiment sans 'sentiment_score' — colonnes sentiment ignorées")
                cols = []
            if cols:
                sent = sent[cols].sort_index()
                # Lissage et variations
                sent["sentiment_ma_5d"] = sent.get("sentiment_score", pd.Series(index=sent.index)).rolling(self.config.sentiment_ma_window).mean()
                sent["sentiment_change"] = sent.get("sentiment_score", pd.Series(index=sent.index)).diff()
                # Aligner à la fréquence des prix
                sent = sent.reindex(feats.index).ffill().bfill()
                feats = feats.join(sent, how="left")

        # Ratios (optionnels)
        if df_ratios is not None and not df_ratios.empty:
            if not isinstance(df_ratios.index, pd.DatetimeIndex):
                raise ValueError("df_ratios index doit être un DatetimeIndex")
            ratios = df_ratios.copy().sort_index()
            candidate_cols = [
                "PE", "PB", "ROE", "DebtToEquity", "Debt/Equity", "PriceToEarnings", "PriceToBook", "ReturnOnEquity",
            ]
            cols_present = [c for c in candidate_cols if c in ratios.columns]
            if cols_present:
                ratios = ratios[cols_present]
                # Normaliser quelques noms usuels
                rename_map = {
                    "PriceToEarnings": "PE",
                    "PriceToBook": "PB",
                    "ReturnOnEquity": "ROE",
                    "Debt/Equity": "DebtToEquity",
                }
                ratios = ratios.rename(columns=rename_map)
                # Propager aux dates quotidiennes
                ratios = ratios.reindex(feats.index).ffill().bfill()
                feats = feats.join(ratios, how="left")

        # Target: rendement futur sur target_horizon
        h = int(self.config.target_horizon)
        y = close.pct_change(h).shift(-h)

        # Nettoyage final: drop NaN synchronisés
        data = feats.join(y.rename("target"), how="left")
        data = data.replace([np.inf, -np.inf], np.nan).dropna()

        X = data.drop(columns=["target"])  # features brutes (non-scalées ici)
        y = data["target"]

        # Sauvegarde du schéma de features
        self.feature_names = list(X.columns)
        self.logger.info(
            f"Features préparées: {X.shape[1]} colonnes, {X.shape[0]} lignes après nettoyage. Horizon={h} jours."
        )
        return X, y

    # ------------------------ Modélisation ------------------------
    def _get_model(self, model_type: str) -> Any:
        model_type = model_type.lower()
        if model_type == "random_forest":
            return RandomForestRegressor(
                n_estimators=300,
                max_depth=None,
                min_samples_split=2,
                n_jobs=-1,
                random_state=self.config.random_state,
            )
        if model_type == "gradient_boosting":
            return GradientBoostingRegressor(random_state=self.config.random_state)
        if model_type == "linear":
            return LinearRegression(n_jobs=None)
        if model_type == "xgboost":
            if not HAS_XGB:
                raise ValueError("XGBoost indisponible: installez xgboost pour utiliser 'xgboost'.")
            return XGBRegressor(
                n_estimators=500,
                max_depth=5,
                learning_rate=0.05,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=self.config.random_state,
                n_jobs=-1,
                tree_method="hist",
            )
        if model_type == "lstm":  # optionnel/non implémenté
            self.logger.warning("'lstm' non implémenté dans cette version. Utilisez un modèle sklearn.")
            raise NotImplementedError("LSTM non implémenté.")
        raise ValueError(f"model_type inconnu: {model_type}")

    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        model_type: str = "random_forest",
        param_grid: Optional[Dict[str, List[Any]]] = None,
        cv_splits: Optional[int] = None,
        scoring: str = "neg_mean_absolute_error",
        verbose: int = 0,
        use_purged_kfold: bool = False,
        samples_info_sets: Optional[pd.Series] = None,
        pct_embargo: float = 0.01,
    ) -> Any:
        """
        Entraîne le modèle avec normalisation des features et CV temporelle.

        - Si param_grid est fourni, utilise GridSearchCV + TimeSeriesSplit (ou PurgedKFold).
        - Le scaler est ajusté sur X_train uniquement et sauvegardé.
        - Optionally use PurgedKFold CV to prevent temporal leakage in financial data.

        Args:
            X_train: Features d'entraînement (DataFrame)
            y_train: Cible d'entraînement (Series)
            model_type: Type de modèle ('random_forest' | 'xgboost' | 'gradient_boosting' | 'linear')
            param_grid: Grille d'hyperparamètres pour GridSearchCV
            cv_splits: Nombre de splits TimeSeries/PurgedKFold (défaut config)
            scoring: Métrique de score pour GridSearchCV
            verbose: Niveau de verbosité GridSearchCV (0=silencieux, 1+=progressif)
            use_purged_kfold: If True, use PurgedKFold CV instead of TimeSeriesSplit
            samples_info_sets: Series mapping sample index → label end time (t1), required for PurgedKFold
            pct_embargo: Embargo size as fraction of n_samples (for PurgedKFold)

        Returns:
            Le modèle entraîné
        
        Example:
            >>> # Standard TimeSeriesSplit
            >>> predictor.train(X, y, model_type='random_forest', cv_splits=5)
            >>> 
            >>> # PurgedKFold (prevents temporal leakage)
            >>> from financial_analyzer.ml.labeling import triple_barrier_labels
            >>> labels, t1, _ = triple_barrier_labels(prices, pt_sl=[0.02, 0.02])
            >>> predictor.train(X, y, use_purged_kfold=True, samples_info_sets=t1, pct_embargo=0.01)
        """
        if not isinstance(X_train, pd.DataFrame) or not isinstance(y_train, pd.Series):
            raise ValueError("X_train doit être DataFrame et y_train Series")
        if X_train.empty or y_train.empty:
            raise ValueError("X_train / y_train ne doivent pas être vides")

        self.model_type = model_type.lower()
        base_model = self._get_model(self.model_type)
        self.scaler = StandardScaler()

        # On scale toutes features pour homogénéité; arbres n'en ont pas besoin mais OK
        pipeline = Pipeline([
            ("scaler", self.scaler),
            ("model", base_model),
        ])

        # Choose CV strategy: PurgedKFold or TimeSeriesSplit
        if use_purged_kfold:
            if not HAS_PURGED_KFOLD:
                self.logger.warning(
                    "PurgedKFold not available, falling back to TimeSeriesSplit. "
                    "Ensure financial_analyzer.ml.cross_validation is installed."
                )
                tscv = TimeSeriesSplit(n_splits=cv_splits or self.config.tscv_splits)
            else:
                if samples_info_sets is None:
                    self.logger.warning(
                        "use_purged_kfold=True but samples_info_sets not provided. "
                        "Falling back to TimeSeriesSplit. Provide t1 from triple_barrier_labels."
                    )
                    tscv = TimeSeriesSplit(n_splits=cv_splits or self.config.tscv_splits)
                else:
                    # Use PurgedKFold with t1
                    tscv = get_purged_kfold_cv(
                        n_splits=cv_splits or self.config.tscv_splits,
                        samples_info_sets=samples_info_sets,
                        pct_embargo=pct_embargo
                    )
                    self.logger.info(
                        f"Using PurgedKFold CV with {cv_splits or self.config.tscv_splits} splits, "
                        f"embargo={pct_embargo*100:.1f}%"
                    )
        else:
            tscv = TimeSeriesSplit(n_splits=cv_splits or self.config.tscv_splits)

        if param_grid:
            # Adapter la grille aux hyperparamètres imbriqués du pipeline
            grid = {f"model__{k}": v for k, v in param_grid.items()}
            search = GridSearchCV(
                estimator=pipeline,
                param_grid=grid,
                scoring=scoring,
                cv=tscv,
                n_jobs=-1,
                verbose=verbose,
            )
            search.fit(X_train, y_train)
            self.best_params_ = search.best_params_
            self.model = search.best_estimator_
            self.logger.info(f"GridSearchCV terminé. Best params: {self.best_params_}")
        else:
            pipeline.fit(X_train, y_train)
            self.model = pipeline
            self.best_params_ = None

        self._is_trained = True
        return self.model

    def predict(self, X_test: pd.DataFrame) -> np.ndarray:
        """
        Prédit les rendements futurs pour X_test.

        Args:
            X_test: Features en DataFrame (mêmes colonnes que X_train)

        Returns:
            np.ndarray des prédictions
        """
        if not self._is_trained or self.model is None:
            raise ValueError("Modèle non entraîné. Appelez train() d'abord.")
        # Assurer les mêmes colonnes/ordre
        missing = [c for c in self.feature_names if c not in X_test.columns]
        if missing:
            raise ValueError(f"Colonnes manquantes dans X_test: {missing}")
        extra = [c for c in X_test.columns if c not in self.feature_names]
        if extra:
            self.logger.warning(f"Colonnes supplémentaires dans X_test (ignorées): {extra}")
        X_aligned = X_test[self.feature_names]
        preds = self.model.predict(X_aligned)
        return np.asarray(preds)

    def evaluate(self, X_test: pd.DataFrame, y_test: pd.Series) -> Dict[str, float]:
        """
        Évalue le modèle sur un jeu de test.

        Métriques:
        - MAE, MSE, RMSE, R2, MAPE
        """
        y_pred = self.predict(X_test)
        mae = float(mean_absolute_error(y_test, y_pred))
        mse = float(mean_squared_error(y_test, y_pred))
        rmse = float(np.sqrt(mse))
        r2 = float(r2_score(y_test, y_pred))
        
        # MAPE robuste: exclure y_test == 0
        if (y_test == 0).any():
            self.logger.warning("y_test contient des zéros, MAPE peut être imprécis")
        mask = y_test != 0
        if mask.sum() > 0:
            mape = float(np.mean(np.abs((y_test[mask] - y_pred[mask]) / y_test[mask])))
        else:
            mape = float('nan')
        
        metrics = {"mae": mae, "mse": mse, "rmse": rmse, "r2": r2, "mape": mape}
        self.logger.info(f"Evaluation: {metrics}")
        return metrics

    def get_feature_importance(self) -> pd.DataFrame:
        """
        Retourne l'importance des features si disponible.

        - Essaye feature_importances_ (arbres) ou coef_ (linéaire)
        - Retourne DataFrame trié décroissant avec colonnes ['feature','importance']
        """
        if not self._is_trained or self.model is None:
            raise ValueError("Modèle non entraîné. Appelez train() d'abord.")

        # Extraire le dernier step du pipeline
        model = None
        try:
            model = self.model.named_steps.get("model")  # type: ignore
        except Exception:
            model = self.model

        importances: Optional[np.ndarray] = None
        if hasattr(model, "feature_importances_"):
            importances = getattr(model, "feature_importances_")  # type: ignore
        elif hasattr(model, "coef_"):
            coefs = getattr(model, "coef_")  # type: ignore
            importances = np.abs(np.atleast_1d(coefs))
        else:
            self.logger.warning("Importance non disponible pour ce modèle.")
            return pd.DataFrame(columns=["feature", "importance"])  # vide

        fi = pd.DataFrame({"feature": self.feature_names, "importance": importances})
        fi = fi.sort_values("importance", ascending=False).reset_index(drop=True)
        return fi

    # ------------------------ Persistance ------------------------
    def save_model(self, path: str) -> None:
        """
        Sauvegarde le modèle, le scaler et les métadonnées (features, config).

        Args:
            path: Chemin du fichier .pkl à écrire
        """
        if not self._is_trained or self.model is None:
            raise ValueError("Modèle non entraîné. Appelez train() d'abord.")
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        payload = {
            "model": self.model,
            "scaler": self.scaler,
            "feature_names": self.feature_names,
            "config": self.config,
            "model_type": self.model_type,
            "best_params_": self.best_params_,
        }
        with open(path, "wb") as f:
            pickle.dump(payload, f)
        self.logger.info(f"Modèle sauvegardé: {path}")

    def load_model(self, path: str) -> None:
        """
        Charge un modèle sauvé avec save_model().
        """
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        with open(path, "rb") as f:
            payload = pickle.load(f)
        self.model = payload["model"]
        self.scaler = payload.get("scaler")
        self.feature_names = payload.get("feature_names", [])
        self.config = payload.get("config", self.config)
        self.model_type = payload.get("model_type")
        self.best_params_ = payload.get("best_params_")
        self._is_trained = True
        self.logger.info(f"Modèle chargé: {path}")

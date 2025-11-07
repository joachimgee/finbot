"""
Module de pipeline de features pour combiner technical + fundamental features.

Ce module orchestre la création, l'alignement et la normalisation des features
pour le machine learning.

Author: FinBot Team
Date: 2025-11-06
Version: 2.0.0
"""

from typing import Dict, List, Optional, Union

import numpy as np
import pandas as pd
from sklearn.preprocessing import MinMaxScaler, RobustScaler, StandardScaler

from financial_analyzer.features.fundamental import FundamentalFeatureEngine
from financial_analyzer.features.technical import TechnicalFeatureEngine
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class FeaturePipeline:
    """
    Pipeline pour combiner et préparer features techniques et fondamentales.
    
    Supporte method chaining pour créer des pipelines fluides :
    features = pipeline.add_technical_features()
                       .add_fundamental_features()
                       .align_features()
                       .handle_missing_values()
                       .get_features()
    
    Attributes:
        ohlcv (pd.DataFrame): DataFrame OHLCV (Open, High, Low, Close, Volume).
        fundamentals (Optional[pd.DataFrame]): DataFrame avec ratios financiers.
        handle_nan (str): Stratégie pour gérer NaN ('drop', 'forward_fill', 'bfill', 'interpolate').
        remove_outliers (bool): Si True, détecte et gère les outliers.
        outlier_std (float): Nombre d'écarts-types pour détection outliers.
        features (pd.DataFrame): DataFrame avec toutes les features combinées.
    
    Example:
        >>> from financial_analyzer.features.pipeline import FeaturePipeline
        >>> pipeline = FeaturePipeline(ohlcv_df, fundamentals_df, handle_nan='forward_fill')
        >>> features = pipeline.add_technical_features()
        ...                     .add_fundamental_features()
        ...                     .align_features()
        ...                     .handle_missing_values()
        ...                     .get_features()
        >>> print(features.shape)
        (252, 65)
    """
    
    def __init__(
        self,
        ohlcv: pd.DataFrame,
        fundamentals: Optional[pd.DataFrame] = None,
        handle_nan: str = 'drop',
        remove_outliers: bool = False,
        outlier_std: float = 3.0,
    ):
        """
        Initialise le pipeline de features.
        
        Args:
            ohlcv: DataFrame avec données OHLCV (index: DatetimeIndex).
            fundamentals: DataFrame optionnel avec ratios financiers.
            handle_nan: Stratégie NaN ('drop', 'forward_fill', 'bfill', 'interpolate').
            remove_outliers: Si True, détecte et remplace outliers.
            outlier_std: Nombre d'écarts-types pour seuil outlier (default: 3.0).
        
        Raises:
            ValueError: Si ohlcv invalide ou handle_nan inconnu.
        
        Example:
            >>> pipeline = FeaturePipeline(ohlcv_df, handle_nan='forward_fill', remove_outliers=True)
        """
        logger.info("Initialisation FeaturePipeline")
        
        # Valider inputs
        self._validate_inputs(ohlcv, fundamentals, handle_nan)
        
        # Stocker données originales
        self.ohlcv = ohlcv.copy()
        self.fundamentals = fundamentals.copy() if fundamentals is not None else None
        
        # Configuration
        self.handle_nan = handle_nan
        self.remove_outliers_flag = remove_outliers
        self.outlier_std = outlier_std
        
        # Features DataFrame (commence avec OHLCV)
        self.features = self.ohlcv.copy()
        
        # Tracking
        self._technical_added = False
        self._fundamental_added = False
        self._aligned = False
        
        logger.info(f"Pipeline créé: OHLCV shape={ohlcv.shape}, "
                   f"fundamentals={'provided' if fundamentals is not None else 'None'}")
    
    def add_technical_features(
        self,
        periods_sma: List[int] = [20, 50, 200],
    ) -> 'FeaturePipeline':
        """
        Ajoute features techniques (SMA, EMA, RSI, MACD, Bollinger, ATR, ROC).
        
        Args:
            periods_sma: Liste de périodes SMA à calculer (default: [20, 50, 200]).
        
        Returns:
            self (pour method chaining).
        
        Example:
            >>> pipeline.add_technical_features(periods_sma=[20, 50, 200])
        """
        logger.info("Ajout features techniques")
        
        try:
            # Créer engine technique
            tech_engine = TechnicalFeatureEngine(self.ohlcv)
            
            # Calculer toutes les features techniques
            tech_features = tech_engine.calculate_all_features()
            
            # Ajouter au pipeline (éviter duplicates OHLCV)
            ohlcv_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
            tech_only = tech_features.drop(columns=ohlcv_cols, errors='ignore')
            
            # Merge avec features existantes
            self.features = pd.concat([self.features, tech_only], axis=1)
            
            self._technical_added = True
            logger.info(f"Features techniques ajoutées: {len(tech_only.columns)} colonnes")
            
        except Exception as e:
            logger.error(f"Échec ajout features techniques: {e}")
            raise
        
        return self
    
    def add_fundamental_features(
        self,
        historical_periods: int = 4,
    ) -> 'FeaturePipeline':
        """
        Ajoute features fondamentales (growth, valuation, quality, profitability, efficiency).
        
        Args:
            historical_periods: Nombre de périodes pour calcul YoY (default: 4 trimestres).
        
        Returns:
            self (pour method chaining).
        
        Raises:
            ValueError: Si fundamentals est None.
        
        Example:
            >>> pipeline.add_fundamental_features(historical_periods=4)
        """
        logger.info("Ajout features fondamentales")
        
        if self.fundamentals is None:
            raise ValueError("Impossible d'ajouter features fondamentales: fundamentals est None")
        
        try:
            # Créer engine fondamental
            fund_engine = FundamentalFeatureEngine(
                self.fundamentals,
                historical_periods=historical_periods
            )
            
            # Calculer toutes les features fondamentales
            fund_features = fund_engine.calculate_all_features()
            
            # Stocker pour alignment ultérieur
            self._fund_features = fund_features
            
            self._fundamental_added = True
            logger.info(f"Features fondamentales calculées: {len(fund_features.columns)} colonnes")
            logger.warning("Features fondamentales stockées, appeler .align_features() pour les intégrer")
            
        except Exception as e:
            logger.error(f"Échec ajout features fondamentales: {e}")
            raise
        
        return self
    
    def align_features(self) -> 'FeaturePipeline':
        """
        Aligne features techniques (daily) et fondamentales (quarterly).
        
        Forward fill les features fondamentales pour matcher l'index OHLCV daily.
        
        Returns:
            self (pour method chaining).
        
        Example:
            >>> pipeline.align_features()
        """
        logger.info("Alignement features techniques et fondamentales")
        
        if not self._fundamental_added:
            logger.warning("Pas de features fondamentales à aligner")
            self._aligned = True
            return self
        
        try:
            # Reindex fundamentals sur index OHLCV (daily)
            fund_aligned = self._fund_features.reindex(self.features.index)
            
            # Forward fill (données trimestrielles → daily)
            fund_aligned = fund_aligned.ffill()
            
            # Compter NaN restants (début de série)
            nan_count = fund_aligned.isna().sum().sum()
            if nan_count > 0:
                logger.warning(f"{nan_count} valeurs NaN restantes après forward fill "
                              "(périodes avant premier trimestre)")
            
            # Merge avec features existantes
            self.features = pd.concat([self.features, fund_aligned], axis=1)
            
            self._aligned = True
            logger.info(f"Alignment terminé: features shape={self.features.shape}")
            
        except Exception as e:
            logger.error(f"Échec alignment features: {e}")
            raise
        
        return self
    
    def handle_missing_values(self) -> 'FeaturePipeline':
        """
        Applique stratégie de gestion des valeurs manquantes.
        
        Stratégies:
            - 'drop': Supprime lignes avec NaN
            - 'forward_fill': Forward fill (utilise valeur précédente)
            - 'bfill': Backward fill (utilise valeur suivante)
            - 'interpolate': Interpolation linéaire
        
        Returns:
            self (pour method chaining).
        
        Example:
            >>> pipeline.handle_missing_values()
        """
        logger.info(f"Gestion valeurs manquantes (stratégie: {self.handle_nan})")
        
        # Compter NaN avant
        nan_before = self.features.isna().sum().sum()
        rows_before = len(self.features)
        
        try:
            if self.handle_nan == 'drop':
                self.features = self.features.dropna()
                rows_after = len(self.features)
                logger.info(f"Lignes supprimées: {rows_before - rows_after}")
                
            elif self.handle_nan == 'forward_fill':
                self.features = self.features.ffill()
                nan_after = self.features.isna().sum().sum()
                logger.info(f"NaN avant: {nan_before}, après forward fill: {nan_after}")
                
                # Si encore des NaN, bfill pour les premiers jours
                if nan_after > 0:
                    self.features = self.features.bfill()
                    nan_final = self.features.isna().sum().sum()
                    logger.info(f"Backward fill appliqué, NaN final: {nan_final}")
                
            elif self.handle_nan == 'bfill':
                self.features = self.features.bfill()
                nan_after = self.features.isna().sum().sum()
                logger.info(f"NaN avant: {nan_before}, après backward fill: {nan_after}")
                
            elif self.handle_nan == 'interpolate':
                self.features = self.features.interpolate(method='linear')
                nan_after = self.features.isna().sum().sum()
                logger.info(f"NaN avant: {nan_before}, après interpolation: {nan_after}")
                
                # Si encore des NaN (début/fin), ffill puis bfill
                if nan_after > 0:
                    self.features = self.features.ffill().bfill()
                    nan_final = self.features.isna().sum().sum()
                    logger.info(f"Fill supplémentaire appliqué, NaN final: {nan_final}")
            
            # Vérifier colonnes avec trop de NaN
            nan_per_col = self.features.isna().sum()
            high_nan_cols = nan_per_col[nan_per_col > len(self.features) * 0.5]
            if len(high_nan_cols) > 0:
                logger.warning(f"Colonnes avec >50% NaN: {list(high_nan_cols.index)}")
            
        except Exception as e:
            logger.error(f"Échec gestion valeurs manquantes: {e}")
            raise
        
        return self
    
    def remove_outliers_iqr(self) -> 'FeaturePipeline':
        """
        Détecte et remplace outliers via méthode IQR ou écarts-types.
        
        Détection:
            - Si outlier_std fourni: valeur > mean ± (outlier_std × std)
            - Sinon IQR: valeur < Q1 - 1.5×IQR ou valeur > Q3 + 1.5×IQR
        
        Returns:
            self (pour method chaining).
        
        Example:
            >>> pipeline.remove_outliers_iqr()
        """
        if not self.remove_outliers_flag:
            logger.info("Suppression outliers désactivée (remove_outliers=False)")
            return self
        
        logger.info(f"Détection outliers (méthode: std={self.outlier_std})")
        
        try:
            outliers_count = 0
            
            # Traiter chaque colonne numérique
            numeric_cols = self.features.select_dtypes(include=[np.number]).columns
            
            for col in numeric_cols:
                # Détecter outliers via écarts-types
                mask = self._detect_outliers_std(self.features[col], self.outlier_std)
                n_outliers = mask.sum()
                
                if n_outliers > 0:
                    # Remplacer par NaN
                    self.features.loc[mask, col] = np.nan
                    outliers_count += n_outliers
                    logger.info(f"Colonne '{col}': {n_outliers} outliers détectés")
            
            logger.info(f"Total outliers détectés et remplacés par NaN: {outliers_count}")
            
            # Re-appliquer stratégie NaN si outliers trouvés
            if outliers_count > 0:
                logger.info("Application stratégie NaN après suppression outliers")
                self.handle_missing_values()
            
        except Exception as e:
            logger.error(f"Échec suppression outliers: {e}")
            raise
        
        return self
    
    def scale_features(
        self,
        method: str = 'minmax',
        exclude_cols: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """
        Normalise features via méthode spécifiée.
        
        NOTE: Cette méthode retourne le DataFrame normalisé (pas self).
        
        Args:
            method: Méthode de scaling ('minmax', 'standard', 'robust').
            exclude_cols: Colonnes à exclure du scaling (ex: scores déjà 0-100).
        
        Returns:
            DataFrame avec features normalisées.
        
        Example:
            >>> scaled_features = pipeline.scale_features(method='standard')
        """
        logger.info(f"Normalisation features (méthode: {method})")
        
        if exclude_cols is None:
            exclude_cols = []
        
        try:
            # Copier features
            scaled_df = self.features.copy()
            
            # Identifier colonnes à scaler
            numeric_cols = scaled_df.select_dtypes(include=[np.number]).columns
            cols_to_scale = [col for col in numeric_cols if col not in exclude_cols]
            
            # Créer scaler
            if method == 'minmax':
                scaler = MinMaxScaler()
            elif method == 'standard':
                scaler = StandardScaler()
            elif method == 'robust':
                scaler = RobustScaler()
            else:
                raise ValueError(f"Méthode inconnue: {method}. "
                               f"Options: 'minmax', 'standard', 'robust'")
            
            # Appliquer scaling
            scaled_df[cols_to_scale] = scaler.fit_transform(scaled_df[cols_to_scale])
            
            logger.info(f"Scaling appliqué sur {len(cols_to_scale)} colonnes "
                       f"({len(exclude_cols)} colonnes exclues)")
            
            return scaled_df
            
        except Exception as e:
            logger.error(f"Échec normalisation features: {e}")
            raise
    
    def get_features(
        self,
        include_technical: bool = True,
        include_fundamental: bool = True,
    ) -> pd.DataFrame:
        """
        Retourne DataFrame avec features sélectionnées.
        
        Args:
            include_technical: Si True, inclut features techniques.
            include_fundamental: Si True, inclut features fondamentales.
        
        Returns:
            DataFrame avec features filtrées.
        
        Example:
            >>> features = pipeline.get_features(include_fundamental=False)
        """
        logger.info(f"Récupération features (tech={include_technical}, fund={include_fundamental})")
        
        # Identifier groupes de colonnes
        feature_groups = self._build_feature_groups()
        
        # Construire liste colonnes à inclure
        cols_to_include = []
        
        # Toujours inclure OHLCV
        cols_to_include.extend(feature_groups['original'])
        
        if include_technical:
            cols_to_include.extend(feature_groups['technical'])
        
        if include_fundamental:
            cols_to_include.extend(feature_groups['fundamental'])
        
        # Filtrer features
        result = self.features[cols_to_include]
        
        logger.info(f"Features retournées: {result.shape}")
        return result
    
    def get_feature_info(self) -> Dict[str, Union[int, Dict]]:
        """
        Retourne métadonnées sur features du pipeline.
        
        Returns:
            Dict avec:
                - n_features: Nombre total de features
                - n_rows: Nombre de lignes
                - features_by_type: Dict des features par type (technical, fundamental, original)
                - missing_values: Dict avec nombre de NaN par colonne
                - dtype_summary: Dict avec comptage par dtype
        
        Example:
            >>> info = pipeline.get_feature_info()
            >>> print(info['n_features'])
            65
        """
        logger.info("Génération métadonnées features")
        
        # Build feature groups
        feature_groups = self._build_feature_groups()
        
        # Count missing values
        missing_values = self.features.isna().sum().to_dict()
        missing_values = {k: int(v) for k, v in missing_values.items() if v > 0}
        
        # Count dtypes
        dtype_counts = self.features.dtypes.value_counts().to_dict()
        dtype_summary = {str(k): int(v) for k, v in dtype_counts.items()}
        
        info = {
            'n_features': len(self.features.columns),
            'n_rows': len(self.features),
            'features_by_type': feature_groups,
            'missing_values': missing_values,
            'dtype_summary': dtype_summary,
        }
        
        logger.info(f"Métadonnées générées: {info['n_features']} features, {info['n_rows']} rows")
        
        return info
    
    # ===== HELPER METHODS PRIVÉES =====
    
    def _validate_inputs(
        self,
        ohlcv: pd.DataFrame,
        fundamentals: Optional[pd.DataFrame],
        handle_nan: str,
    ) -> None:
        """
        Valide les inputs du pipeline.
        
        Args:
            ohlcv: DataFrame OHLCV à valider.
            fundamentals: DataFrame fundamentals optionnel.
            handle_nan: Stratégie NaN à valider.
        
        Raises:
            ValueError: Si inputs invalides.
        """
        # Valider OHLCV
        if ohlcv is None or ohlcv.empty:
            raise ValueError("OHLCV DataFrame ne peut pas être vide")
        
        if not isinstance(ohlcv.index, pd.DatetimeIndex):
            raise ValueError("OHLCV index doit être DatetimeIndex")
        
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        missing_cols = [col for col in required_cols if col not in ohlcv.columns]
        if missing_cols:
            raise ValueError(f"Colonnes OHLCV manquantes: {missing_cols}")
        
        # Valider fundamentals si fourni
        if fundamentals is not None:
            if not isinstance(fundamentals, pd.DataFrame):
                raise ValueError("fundamentals doit être un DataFrame")
            
            if fundamentals.empty:
                logger.warning("fundamentals DataFrame est vide")
        
        # Valider handle_nan
        valid_strategies = ['drop', 'forward_fill', 'bfill', 'interpolate']
        if handle_nan not in valid_strategies:
            raise ValueError(f"handle_nan inconnu: {handle_nan}. Options: {valid_strategies}")
    
    def _build_feature_groups(self) -> Dict[str, List[str]]:
        """
        Identifie et groupe les colonnes par type (original, technical, fundamental).
        
        Returns:
            Dict avec listes de colonnes par type.
        """
        # Colonnes originales OHLCV
        original_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        original = [col for col in original_cols if col in self.features.columns]
        
        # Features techniques (heuristique: SMA, EMA, RSI, MACD, BB, ATR, ROC, Returns)
        tech_keywords = ['SMA', 'EMA', 'RSI', 'MACD', 'BB_', 'ATR', 'ROC', 'Returns', 'Volume_SMA']
        technical = [
            col for col in self.features.columns
            if any(kw in col for kw in tech_keywords) and col not in original
        ]
        
        # Features fondamentales (heuristique: Growth, PE, PB, ROE, ROA, Quality, etc.)
        fund_keywords = [
            'Growth', 'PE', 'PB', 'PS', 'PEG', 'ROE', 'ROA', 'Valuation', 'Quality',
            'Leverage', 'Liquidity', 'Interest', 'Margin', 'FCF', 'Turnover', 'DSO',
            'Efficiency', 'Debt', 'Current', 'Assessment', 'Rating', 'Coverage'
        ]
        fundamental = [
            col for col in self.features.columns
            if any(kw in col for kw in fund_keywords) and col not in original + technical
        ]
        
        return {
            'original': original,
            'technical': technical,
            'fundamental': fundamental,
        }
    
    def _detect_outliers_std(self, col: pd.Series, std: float = 3.0) -> pd.Series:
        """
        Détecte outliers via écarts-types.
        
        Args:
            col: Series à analyser.
            std: Nombre d'écarts-types pour seuil (default: 3.0).
        
        Returns:
            Series boolean mask (True = outlier).
        """
        mean = col.mean()
        std_dev = col.std()
        
        # Protection division par zéro (valeurs constantes)
        if std_dev == 0:
            return pd.Series([False] * len(col), index=col.index)
        
        # Outlier si |valeur - mean| > std × std_dev
        lower_bound = mean - (std * std_dev)
        upper_bound = mean + (std * std_dev)
        
        mask = (col < lower_bound) | (col > upper_bound)
        
        return mask
    
    def _detect_outliers_iqr(self, col: pd.Series) -> pd.Series:
        """
        Détecte outliers via méthode IQR (Interquartile Range).
        
        Args:
            col: Series à analyser.
        
        Returns:
            Series boolean mask (True = outlier).
        """
        Q1 = col.quantile(0.25)
        Q3 = col.quantile(0.75)
        IQR = Q3 - Q1
        
        # Outlier si < Q1 - 1.5×IQR ou > Q3 + 1.5×IQR
        lower_bound = Q1 - (1.5 * IQR)
        upper_bound = Q3 + (1.5 * IQR)
        
        mask = (col < lower_bound) | (col > upper_bound)
        
        return mask

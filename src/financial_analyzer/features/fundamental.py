"""
Module de calcul des features fondamentales.

Ce module transforme les ratios financiers bruts en features ML-friendly
incluant croissance, valuation, qualité, profitabilité et efficience.

Author: FinBot Team
Date: 2025-11-06
Version: 2.0.0
"""

from typing import Optional, Tuple

import numpy as np
import pandas as pd

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class FundamentalFeatureEngine:
    """
    Moteur de calcul des features fondamentales à partir de ratios financiers.
    
    Transforme les ratios bruts (PE, PB, ROE, etc.) en features utiles pour
    le machine learning : croissance, scores de valuation, métriques de qualité.
    
    Attributes:
        df (pd.DataFrame): DataFrame avec ratios financiers (input).
        historical_periods (int): Nombre de périodes pour calculs YoY/QoQ (default: 4).
    
    Example:
        >>> from financial_analyzer.data.fundamentals import FundamentalsProvider
        >>> provider = FundamentalsProvider(api_key="key")
        >>> fundamentals = provider.get_all_ratios('AAPL', period='quarterly', limit=8)
        >>> 
        >>> engine = FundamentalFeatureEngine(fundamentals, historical_periods=4)
        >>> features = engine.calculate_all_features()
        >>> print(features.shape)
        (8, 45)
    """
    
    def __init__(
        self,
        fundamentals: pd.DataFrame,
        historical_periods: int = 4,
    ):
        """
        Initialise le moteur avec des données fondamentales.
        
        Args:
            fundamentals: DataFrame avec ratios financiers.
                         Index: DatetimeIndex ou MultiIndex (ticker, date).
                         Colonnes: PE, PB, ROE, Revenue, NetIncome, etc.
            historical_periods: Nombre de périodes historiques pour calculs de croissance.
                              Default: 4 (4 trimestres = 1 an).
        
        Raises:
            ValueError: Si DataFrame invalide ou colonnes critiques manquantes.
        
        Example:
            >>> engine = FundamentalFeatureEngine(fundamentals_df, historical_periods=4)
        """
        logger.info("Initialisation FundamentalFeatureEngine")
        
        if fundamentals is None or fundamentals.empty:
            raise ValueError("DataFrame fundamentals ne peut pas être vide")
        
        # Valider colonnes critiques
        critical_columns = ['PE', 'PB', 'ROE', 'ROA']
        missing_cols = [col for col in critical_columns if col not in fundamentals.columns]
        if missing_cols:
            logger.warning(f"Colonnes critiques manquantes (utilisation limitée): {missing_cols}")
        
        # Valider historical_periods
        if historical_periods <= 0:
            raise ValueError(f"historical_periods doit être > 0, obtenu: {historical_periods}")
        
        self.df = fundamentals.copy()
        self.historical_periods = historical_periods
        
        logger.info(f"FundamentalFeatureEngine initialisé: {len(self.df)} périodes, "
                   f"{len(self.df.columns)} colonnes")
    
    def calculate_growth_features(self) -> pd.DataFrame:
        """
        Calcule les features de croissance (QoQ = Quarter over Quarter).
        
        Calcule la croissance trimestre sur trimestre pour toutes les colonnes
        numériques disponibles (Revenue, NetIncome, TotalAssets, etc.).
        
        Returns:
            DataFrame avec colonnes {original}_QoQ_Growth (%).
            Index: Same as input.
        
        Example:
            >>> growth = engine.calculate_growth_features()
            >>> print(growth[['Revenue_QoQ_Growth', 'NetIncome_QoQ_Growth']].head(3))
                       Revenue_QoQ_Growth  NetIncome_QoQ_Growth
            2023-Q1                  NaN                   NaN
            2023-Q2                 5.2                   8.1
            2023-Q3                 3.7                   4.5
        """
        logger.info("Calcul des features de croissance (QoQ)")
        
        growth_features = pd.DataFrame(index=self.df.index)
        
        # Identifier colonnes numériques pour calcul croissance
        numeric_cols = self.df.select_dtypes(include=[np.number]).columns
        
        # Colonnes typiques pour croissance
        growth_candidates = [
            'Revenue', 'NetIncome', 'TotalAssets', 'EBITDA',
            'OperatingIncome', 'FreeCashFlow', 'TotalDebt', 'Equity'
        ]
        
        # Filtrer colonnes disponibles
        cols_for_growth = [col for col in growth_candidates if col in numeric_cols]
        
        if not cols_for_growth:
            logger.warning("Aucune colonne appropriée trouvée pour calcul croissance")
            # Fallback: prendre toutes colonnes numériques (limité à 10 premières)
            cols_for_growth = list(numeric_cols[:10])
        
        for col in cols_for_growth:
            try:
                growth = self._get_qoq_growth(self.df[col])
                growth_features[f'{col}_QoQ_Growth'] = growth
            except Exception as e:
                logger.warning(f"Échec calcul croissance pour {col}: {e}")
        
        logger.info(f"Features de croissance calculées: {len(growth_features.columns)} colonnes")
        return growth_features
    
    def calculate_valuation_features(self) -> pd.DataFrame:
        """
        Calcule les features de valuation (PE, PB, PS, PEG, Valuation Score).
        
        Évalue si les ratios de valuation sont attractifs (cheap) ou chers (expensive)
        par rapport à la moyenne historique.
        
        Returns:
            DataFrame avec colonnes:
                - PE_Trend: 'Cheap', 'Fair', 'Expensive'
                - PB_Assessment: Score 0-100
                - PS_Assessment: Score 0-100
                - PEG_Ratio: PE / Growth Rate
                - Valuation_Score: Score global 0-100 (100=très bon marché)
        
        Example:
            >>> valuation = engine.calculate_valuation_features()
            >>> print(valuation[['PE_Trend', 'Valuation_Score']].head(3))
                       PE_Trend  Valuation_Score
            2023-Q1       Cheap             78.5
            2023-Q2        Fair             62.3
            2023-Q3   Expensive             42.1
        """
        logger.info("Calcul des features de valuation")
        
        valuation_features = pd.DataFrame(index=self.df.index)
        
        # 1. PE Trend
        if 'PE' in self.df.columns:
            pe_series = self.df['PE']
            pe_mean = pe_series.mean()
            pe_std = pe_series.std()
            
            # Classifier PE
            conditions = [
                pe_series < pe_mean - 0.5 * pe_std,  # Cheap
                pe_series > pe_mean + 0.5 * pe_std,  # Expensive
            ]
            choices = ['Cheap', 'Expensive']
            valuation_features['PE_Trend'] = np.select(conditions, choices, default='Fair')
            
            # PE Score (lower is better)
            valuation_features['PE_Score'] = self._score_feature(pe_series, lower_is_better=True)
        else:
            logger.warning("Colonne PE manquante, PE features skipped")
            valuation_features['PE_Trend'] = 'Unknown'
            valuation_features['PE_Score'] = 50.0  # Neutral
        
        # 2. PB Assessment
        if 'PB' in self.df.columns:
            pb_series = self.df['PB']
            valuation_features['PB_Assessment'] = self._score_feature(pb_series, lower_is_better=True)
        else:
            logger.warning("Colonne PB manquante")
            valuation_features['PB_Assessment'] = 50.0
        
        # 3. PS Assessment
        if 'PS' in self.df.columns:
            ps_series = self.df['PS']
            valuation_features['PS_Assessment'] = self._score_feature(ps_series, lower_is_better=True)
        else:
            logger.warning("Colonne PS manquante")
            valuation_features['PS_Assessment'] = 50.0
        
        # 4. PEG Ratio (PE / Growth Rate)
        if 'PE' in self.df.columns and 'NetIncome_QoQ_Growth' in self.df.columns:
            growth_rate = self.df.get('NetIncome_QoQ_Growth', pd.Series([np.nan] * len(self.df)))
            # Éviter division par zéro
            peg = self.df['PE'] / growth_rate.replace(0, np.nan)
            valuation_features['PEG_Ratio'] = peg
        elif 'PE' in self.df.columns:
            # Essayer calcul croissance si pas déjà fait
            try:
                growth = self._get_qoq_growth(self.df.get('NetIncome', pd.Series([100] * len(self.df))))
                peg = self.df['PE'] / growth.replace(0, np.nan)
                valuation_features['PEG_Ratio'] = peg
            except Exception as e:
                logger.warning(f"Impossible de calculer PEG Ratio: {e}")
                valuation_features['PEG_Ratio'] = np.nan
        else:
            valuation_features['PEG_Ratio'] = np.nan
        
        # 5. Valuation Score (moyenne des scores disponibles)
        score_cols = [col for col in valuation_features.columns if 'Score' in col or 'Assessment' in col]
        if score_cols:
            valuation_features['Valuation_Score'] = valuation_features[score_cols].mean(axis=1)
        else:
            valuation_features['Valuation_Score'] = 50.0  # Neutral
        
        logger.info(f"Features de valuation calculées: {len(valuation_features.columns)} colonnes")
        return valuation_features
    
    def calculate_quality_features(self) -> pd.DataFrame:
        """
        Calcule les features de qualité financière (ROE, ROA, Leverage, Liquidity).
        
        Évalue la qualité de l'entreprise via rentabilité, endettement, liquidité.
        
        Returns:
            DataFrame avec colonnes:
                - ROE_Quality: 'Excellent' (>15%), 'Good' (10-15%), 'Poor' (<10%)
                - ROA_Quality: Score 0-100
                - Leverage_Rating: Score basé sur Debt/Equity
                - Liquidity_Rating: Score basé sur Current Ratio
                - Interest_Coverage: EBIT / Interest Expense
                - Quality_Score: Score global 0-100
        
        Example:
            >>> quality = engine.calculate_quality_features()
            >>> print(quality[['ROE_Quality', 'Quality_Score']].head(3))
                       ROE_Quality  Quality_Score
            2023-Q1      Excellent           88.2
            2023-Q2           Good           75.4
            2023-Q3           Good           72.1
        """
        logger.info("Calcul des features de qualité")
        
        quality_features = pd.DataFrame(index=self.df.index)
        
        # 1. ROE Quality
        if 'ROE' in self.df.columns:
            roe_series = self.df['ROE']
            
            # Classifier ROE (en %)
            conditions = [
                roe_series > 15,   # Excellent
                roe_series > 10,   # Good
            ]
            choices = ['Excellent', 'Good']
            quality_features['ROE_Quality'] = np.select(conditions, choices, default='Poor')
            
            # ROE Score (higher is better)
            quality_features['ROE_Score'] = self._score_feature(roe_series, lower_is_better=False)
        else:
            logger.warning("Colonne ROE manquante")
            quality_features['ROE_Quality'] = 'Unknown'
            quality_features['ROE_Score'] = 50.0
        
        # 2. ROA Quality
        if 'ROA' in self.df.columns:
            roa_series = self.df['ROA']
            quality_features['ROA_Quality'] = self._score_feature(roa_series, lower_is_better=False)
        else:
            logger.warning("Colonne ROA manquante")
            quality_features['ROA_Quality'] = 50.0
        
        # 3. Leverage Rating (Debt to Equity)
        if 'DebtToEquity' in self.df.columns:
            leverage = self.df['DebtToEquity']
            # Lower is better (moins endetté = mieux)
            quality_features['Leverage_Rating'] = self._score_feature(leverage, lower_is_better=True)
        elif 'TotalDebt' in self.df.columns and 'Equity' in self.df.columns:
            # Calculer Debt/Equity
            leverage = self.df['TotalDebt'] / self.df['Equity'].replace(0, np.nan)
            quality_features['Leverage_Rating'] = self._score_feature(leverage, lower_is_better=True)
        else:
            logger.warning("Colonnes Debt/Equity manquantes")
            quality_features['Leverage_Rating'] = 50.0
        
        # 4. Liquidity Rating (Current Ratio)
        if 'CurrentRatio' in self.df.columns:
            liquidity = self.df['CurrentRatio']
            # Higher is better (plus liquide = mieux)
            quality_features['Liquidity_Rating'] = self._score_feature(liquidity, lower_is_better=False)
        else:
            logger.warning("Colonne CurrentRatio manquante")
            quality_features['Liquidity_Rating'] = 50.0
        
        # 5. Interest Coverage (EBIT / Interest Expense)
        if 'EBIT' in self.df.columns and 'InterestExpense' in self.df.columns:
            interest_coverage = self.df['EBIT'] / self.df['InterestExpense'].replace(0, np.nan)
            quality_features['Interest_Coverage'] = interest_coverage
            # Score (higher is better)
            quality_features['Interest_Coverage_Score'] = self._score_feature(
                interest_coverage, lower_is_better=False
            )
        else:
            logger.warning("Colonnes EBIT/InterestExpense manquantes")
            quality_features['Interest_Coverage'] = np.nan
            quality_features['Interest_Coverage_Score'] = 50.0
        
        # 6. Quality Score (moyenne des scores disponibles)
        score_cols = [col for col in quality_features.columns if 'Score' in col or 'Rating' in col]
        if score_cols:
            quality_features['Quality_Score'] = quality_features[score_cols].mean(axis=1)
        else:
            quality_features['Quality_Score'] = 50.0
        
        logger.info(f"Features de qualité calculées: {len(quality_features.columns)} colonnes")
        return quality_features
    
    def calculate_profitability_features(self) -> pd.DataFrame:
        """
        Calcule les features de profitabilité (marges, FCF).
        
        Analyse les marges (gross, operating, net) et leur tendance.
        
        Returns:
            DataFrame avec colonnes:
                - Gross_Margin_Trend: Croissance de la marge brute
                - Operating_Margin_Trend: Croissance de la marge opérationnelle
                - Net_Margin_Trend: Croissance de la marge nette
                - FCF_to_Revenue: Free Cash Flow / Revenue ratio
        
        Example:
            >>> profitability = engine.calculate_profitability_features()
            >>> print(profitability[['Net_Margin_Trend', 'FCF_to_Revenue']].head(3))
                       Net_Margin_Trend  FCF_to_Revenue
            2023-Q1                 NaN            0.18
            2023-Q2                2.3             0.19
            2023-Q3               -1.2             0.17
        """
        logger.info("Calcul des features de profitabilité")
        
        profitability_features = pd.DataFrame(index=self.df.index)
        
        # 1. Gross Margin Trend
        if 'GrossMargin' in self.df.columns:
            gross_margin = self.df['GrossMargin']
            profitability_features['Gross_Margin_Trend'] = self._get_qoq_growth(gross_margin)
        else:
            logger.warning("Colonne GrossMargin manquante")
            profitability_features['Gross_Margin_Trend'] = np.nan
        
        # 2. Operating Margin Trend
        if 'OperatingMargin' in self.df.columns:
            operating_margin = self.df['OperatingMargin']
            profitability_features['Operating_Margin_Trend'] = self._get_qoq_growth(operating_margin)
        else:
            logger.warning("Colonne OperatingMargin manquante")
            profitability_features['Operating_Margin_Trend'] = np.nan
        
        # 3. Net Margin Trend
        if 'NetMargin' in self.df.columns:
            net_margin = self.df['NetMargin']
            profitability_features['Net_Margin_Trend'] = self._get_qoq_growth(net_margin)
        elif 'NetIncome' in self.df.columns and 'Revenue' in self.df.columns:
            # Calculer Net Margin
            net_margin = (self.df['NetIncome'] / self.df['Revenue'].replace(0, np.nan)) * 100
            profitability_features['Net_Margin_Trend'] = self._get_qoq_growth(net_margin)
        else:
            logger.warning("Colonnes NetMargin/NetIncome/Revenue manquantes")
            profitability_features['Net_Margin_Trend'] = np.nan
        
        # 4. FCF to Revenue
        if 'FreeCashFlow' in self.df.columns and 'Revenue' in self.df.columns:
            fcf_to_revenue = self.df['FreeCashFlow'] / self.df['Revenue'].replace(0, np.nan)
            profitability_features['FCF_to_Revenue'] = fcf_to_revenue
        else:
            logger.warning("Colonnes FreeCashFlow/Revenue manquantes")
            profitability_features['FCF_to_Revenue'] = np.nan
        
        logger.info(f"Features de profitabilité calculées: {len(profitability_features.columns)} colonnes")
        return profitability_features
    
    def calculate_efficiency_features(self) -> pd.DataFrame:
        """
        Calcule les features d'efficience opérationnelle.
        
        Mesure l'efficacité avec laquelle l'entreprise utilise ses actifs.
        
        Returns:
            DataFrame avec colonnes:
                - Asset_Turnover: Revenue / Total Assets
                - Receivables_Turnover: Revenue / Accounts Receivable
                - DSO: Days Sales Outstanding (365 / Receivables Turnover)
                - Operating_Efficiency_Score: Score global 0-100
        
        Example:
            >>> efficiency = engine.calculate_efficiency_features()
            >>> print(efficiency[['Asset_Turnover', 'DSO']].head(3))
                       Asset_Turnover   DSO
            2023-Q1              1.23  42.5
            2023-Q2              1.28  39.8
            2023-Q3              1.31  38.2
        """
        logger.info("Calcul des features d'efficience")
        
        efficiency_features = pd.DataFrame(index=self.df.index)
        
        # 1. Asset Turnover
        if 'Revenue' in self.df.columns and 'TotalAssets' in self.df.columns:
            asset_turnover = self.df['Revenue'] / self.df['TotalAssets'].replace(0, np.nan)
            efficiency_features['Asset_Turnover'] = asset_turnover
            efficiency_features['Asset_Turnover_Score'] = self._score_feature(
                asset_turnover, lower_is_better=False
            )
        else:
            logger.warning("Colonnes Revenue/TotalAssets manquantes")
            efficiency_features['Asset_Turnover'] = np.nan
            efficiency_features['Asset_Turnover_Score'] = 50.0
        
        # 2. Receivables Turnover
        if 'Revenue' in self.df.columns and 'AccountsReceivable' in self.df.columns:
            receivables_turnover = self.df['Revenue'] / self.df['AccountsReceivable'].replace(0, np.nan)
            efficiency_features['Receivables_Turnover'] = receivables_turnover
            
            # 3. DSO (Days Sales Outstanding)
            dso = 365 / receivables_turnover.replace(0, np.nan)
            efficiency_features['DSO'] = dso
            efficiency_features['DSO_Score'] = self._score_feature(dso, lower_is_better=True)
        else:
            logger.warning("Colonnes Revenue/AccountsReceivable manquantes")
            efficiency_features['Receivables_Turnover'] = np.nan
            efficiency_features['DSO'] = np.nan
            efficiency_features['DSO_Score'] = 50.0
        
        # 4. Operating Efficiency Score (moyenne des scores)
        score_cols = [col for col in efficiency_features.columns if 'Score' in col]
        if score_cols:
            efficiency_features['Operating_Efficiency_Score'] = efficiency_features[score_cols].mean(axis=1)
        else:
            efficiency_features['Operating_Efficiency_Score'] = 50.0
        
        logger.info(f"Features d'efficience calculées: {len(efficiency_features.columns)} colonnes")
        return efficiency_features
    
    def calculate_all_features(self) -> pd.DataFrame:
        """
        Calcule TOUTES les features fondamentales.
        
        Combine ratios originaux + growth + valuation + quality + profitability + efficiency.
        
        Returns:
            DataFrame avec ~40-50 colonnes incluant:
                - Original ratios (PE, PB, ROE, etc.)
                - Growth features (QoQ)
                - Valuation features (scores, trends)
                - Quality features (ROE quality, leverage, liquidity)
                - Profitability features (margin trends, FCF)
                - Efficiency features (turnover, DSO)
        
        Example:
            >>> features = engine.calculate_all_features()
            >>> print(features.shape)
            (8, 47)
            >>> print(features.columns[:10])
            Index(['PE', 'PB', 'ROE', 'ROA', 'Revenue_QoQ_Growth', 'NetIncome_QoQ_Growth',
                   'PE_Trend', 'PE_Score', 'Valuation_Score', 'ROE_Quality'], dtype='object')
        """
        logger.info("Calcul de TOUTES les features fondamentales")
        
        # Calculer toutes les catégories
        growth = self.calculate_growth_features()
        valuation = self.calculate_valuation_features()
        quality = self.calculate_quality_features()
        profitability = self.calculate_profitability_features()
        efficiency = self.calculate_efficiency_features()
        
        # Combiner tout
        all_features = pd.concat(
            [self.df, growth, valuation, quality, profitability, efficiency],
            axis=1,
        )
        
        logger.info(f"TOUTES les features calculées: {all_features.shape} (rows, cols)")
        logger.info(f"Colonnes: {list(all_features.columns[:10])}... (10 premières)")
        
        return all_features
    
    # ===== MÉTHODES HELPER PRIVÉES =====
    
    def _get_qoq_growth(self, series: pd.Series) -> pd.Series:
        """
        Calcule la croissance Quarter over Quarter (%).
        
        Args:
            series: Series avec valeurs numériques.
        
        Returns:
            Series avec croissance QoQ en %.
            Première valeur = NaN (pas de période précédente).
        
        Example:
            >>> series = pd.Series([100, 105, 110])
            >>> growth = self._get_qoq_growth(series)
            >>> print(growth)
            0     NaN
            1     5.0
            2    4.76
            dtype: float64
        """
        return series.pct_change() * 100
    
    def _get_yoy_growth(self, series: pd.Series, periods: int = 4) -> pd.Series:
        """
        Calcule la croissance Year over Year (%).
        
        Args:
            series: Series avec valeurs numériques.
            periods: Nombre de périodes pour YoY (default: 4 trimestres = 1 an).
        
        Returns:
            Series avec croissance YoY en %.
            Premières `periods` valeurs = NaN.
        
        Example:
            >>> series = pd.Series([100, 102, 105, 108, 112, 115])
            >>> growth = self._get_yoy_growth(series, periods=4)
            >>> print(growth)
            0     NaN
            1     NaN
            2     NaN
            3     NaN
            4    12.0
            5    12.7
            dtype: float64
        """
        return series.pct_change(periods=periods) * 100
    
    def _calculate_margin(self, revenue: pd.Series, cost: pd.Series) -> pd.Series:
        """
        Calcule la marge (%).
        
        Args:
            revenue: Series avec revenus.
            cost: Series avec coûts.
        
        Returns:
            Series avec marge = (Revenue - Cost) / Revenue * 100.
        
        Example:
            >>> revenue = pd.Series([1000, 1100, 1200])
            >>> cost = pd.Series([700, 750, 800])
            >>> margin = self._calculate_margin(revenue, cost)
            >>> print(margin)
            0    30.0
            1    31.8
            2    33.3
            dtype: float64
        """
        return ((revenue - cost) / revenue.replace(0, np.nan)) * 100
    
    def _score_feature(
        self,
        values: pd.Series,
        lower_is_better: bool = False,
    ) -> pd.Series:
        """
        Normalise une feature en score 0-100 via percentile ranking.
        
        Args:
            values: Series avec valeurs à scorer.
            lower_is_better: Si True, valeurs basses = score élevé (ex: PE ratio).
                            Si False, valeurs hautes = score élevé (ex: ROE).
        
        Returns:
            Series avec scores 0-100.
            NaN si valeur originale = NaN.
        
        Example:
            >>> values = pd.Series([10, 20, 30, 40, 50])
            >>> scores = self._score_feature(values, lower_is_better=False)
            >>> print(scores)
            0     0.0
            1    25.0
            2    50.0
            3    75.0
            4   100.0
            dtype: float64
        """
        if values.isna().all():
            logger.warning("Toutes les valeurs sont NaN, retour scores neutres (50)")
            return pd.Series([50.0] * len(values), index=values.index)
        
        # Utiliser rank() pour percentile (robuste aux outliers)
        rank = values.rank(pct=True, method='average')  # Percentile 0-1
        
        if lower_is_better:
            # Inverser: valeur basse = score élevé
            scores = (1 - rank) * 100
        else:
            # Valeur haute = score élevé
            scores = rank * 100
        
        return scores

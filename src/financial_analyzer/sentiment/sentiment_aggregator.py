"""
Module d'agrégation des scores de sentiment financier.

Agrège les scores de sentiment par période (daily/weekly/monthly),
ticker, source de news, ou pondérés.

Supporte plusieurs méthodes d'agrégation:
- mean: Moyenne simple
- median: Médiane (robuste aux outliers)
- weighted: Pondéré par source ou autre dimension
- momentum: Changement jour/jour

Usage:
    >>> aggregator = SentimentAggregator()
    >>> daily = aggregator.aggregate_by_date(news_df, period='D')
    >>> ticker_scores = aggregator.aggregate_by_ticker(news_df)
    >>> source_scores = aggregator.aggregate_by_source(news_df)
    >>> trend = aggregator.get_sentiment_trend(news_df, period='W')
    >>> momentum = aggregator.get_sentiment_momentum(news_df, period='D')
"""

# 1. Stdlib
import os
from typing import List, Dict, Optional, Any, Union, TypedDict
import logging
from datetime import datetime, timedelta

# 2. Données & Calculs
import pandas as pd
import numpy as np

# 6. Projet local
from financial_analyzer.utils.helpers import get_logger, cache_result


# Type definitions for better typing
class SentimentScore(TypedDict):
    """Type pour un score de sentiment."""
    sentiment_score: float
    positive: float
    negative: float
    neutral: float
    label: str
    count: int


class SentimentAggregator:
    """
    Agrégateur de scores de sentiment financier multi-dimensions.

    Combine les scores de sentiment du module FinBERT et les agrège
    par période, ticker, source, ou avec pondérations.

    Features:
    - Agrégation par période (hourly, daily, weekly, monthly)
    - Agrégation par ticker et/ou source
    - Pondérations (par source, par récence)
    - Calcul du momentum (changement jour/jour)
    - Validation stricte des DataFrames

    Args:
        default_method: Méthode d'agrégation par défaut ('mean', 'median', 'weighted')

    Raises:
        ValueError: Si méthode d'agrégation invalide

    Example:
        >>> aggregator = SentimentAggregator(default_method='median')
        >>> 
        >>> # Agrégation par date
        >>> daily = aggregator.aggregate_by_date(news_df, period='D')
        >>> 
        >>> # Par ticker
        >>> ticker_scores = aggregator.aggregate_by_ticker(news_df)
        >>> 
        >>> # Trend avec momentum
        >>> trend = aggregator.get_sentiment_trend(news_df, period='W')
        >>> momentum = aggregator.get_sentiment_momentum(news_df, period='D')
        >>> 
        >>> # Pondéré
        >>> weights = {"Yahoo Finance": 0.5, "NewsAPI": 0.3}
        >>> weighted = aggregator.aggregate_weighted(news_df, weights=weights)
    """

    # Constants
    AGGREGATION_METHODS = ['mean', 'median', 'weighted']
    PERIODS = {
        'H': 'Hourly',
        'D': 'Daily',
        'W': 'Weekly',
        'M': 'Monthly'
    }
    REQUIRED_COLUMNS = ['sentiment_score', 'positive', 'negative', 'neutral', 'label']

    def __init__(self, default_method: str = 'mean') -> None:
        """
        Initialiser l'agrégateur.

        Args:
            default_method: Méthode d'agrégation par défaut

        Raises:
            ValueError: Si méthode invalide
        """
        if default_method not in self.AGGREGATION_METHODS:
            raise ValueError(
                f"Méthode '{default_method}' invalide. "
                f"Choisir parmi: {self.AGGREGATION_METHODS}"
            )

        self.default_method = default_method
        self.logger = get_logger(__name__)

        self.logger.info(
            f"SentimentAggregator initialisé | "
            f"Méthode par défaut: {default_method}"
        )

    def _validate_dataframe(
        self,
        df: pd.DataFrame,
        require_datetime_index: bool = False,
        required_columns: Optional[List[str]] = None
    ) -> None:
        """
        Valider un DataFrame d'entrée.

        Args:
            df: DataFrame à valider
            require_datetime_index: Vérifier que l'index est DatetimeIndex
            required_columns: Colonnes requises (défaut: REQUIRED_COLUMNS)

        Raises:
            ValueError: Si validation échoue
        """
        if df.empty:
            raise ValueError("DataFrame vide")

        cols_to_check = required_columns or self.REQUIRED_COLUMNS

        missing_cols = [col for col in cols_to_check if col not in df.columns]
        if missing_cols:
            raise ValueError(
                f"Colonnes manquantes: {missing_cols}. "
                f"Colonnes disponibles: {df.columns.tolist()}"
            )

        if require_datetime_index:
            if not isinstance(df.index, pd.DatetimeIndex):
                raise ValueError(
                    f"Index doit être DatetimeIndex, reçu {type(df.index).__name__}. "
                    f"Utilisez df.set_index('date') ou similaire."
                )

    def _get_label_from_scores(
        self,
        series: pd.Series,
        alternative: str = 'neutral'
    ) -> str:
        """
        Obtenir le label dominant d'une série.

        Args:
            series: Série de labels
            alternative: Label par défaut si mode vide

        Returns:
            Label dominant ou alternative
        """
        try:
            mode_result = series.mode()
            return mode_result[0] if len(mode_result) > 0 else alternative
        except Exception:
            return alternative

    def aggregate_by_date(
        self,
        df: pd.DataFrame,
        period: str = 'D',
        method: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Agréger les scores de sentiment par période temporelle.

        Resampling sur index DatetimeIndex et agrégation
        par mean/median/weighted.

        Args:
            df: DataFrame avec index DatetimeIndex
            period: Période ('H', 'D', 'W', 'M')
            method: Méthode d'agrégation (défaut: self.default_method)

        Returns:
            DataFrame agrégé avec colonnes:
            - sentiment_score (moyenne/médiane)
            - positive, negative, neutral (moyennes)
            - label (mode)
            - count (nombre d'articles)
            Index: DatetimeIndex trie décroissant

        Raises:
            ValueError: Si DataFrame invalide ou période non reconnue

        Example:
            >>> daily = aggregator.aggregate_by_date(news_df, period='D')
            >>> weekly = aggregator.aggregate_by_date(
            ...     news_df,
            ...     period='W',
            ...     method='median'
            ... )
        """
        # Validation
        self._validate_dataframe(df, require_datetime_index=True)

        if period not in self.PERIODS:
            self.logger.warning(
                f"Période '{period}' non reconnue. "
                f"Périodes supportées: {list(self.PERIODS.keys())}. "
                f"Utilisation de 'D'."
            )
            period = 'D'

        method = method or self.default_method

        self.logger.info(
            f"Agrégation par date | period={period} ({self.PERIODS[period]}) | "
            f"method={method} | lignes={len(df)}"
        )

        try:
            # ===== Resample et agréger =====
            if method == 'mean':
                agg_funcs = {
                    'sentiment_score': 'mean',
                    'positive': 'mean',
                    'negative': 'mean',
                    'neutral': 'mean'
                }
            elif method == 'median':
                agg_funcs = {
                    'sentiment_score': 'median',
                    'positive': 'median',
                    'negative': 'median',
                    'neutral': 'median'
                }
            else:  # weighted or default to mean
                agg_funcs = {
                    'sentiment_score': 'mean',
                    'positive': 'mean',
                    'negative': 'mean',
                    'neutral': 'mean'
                }

            agg_df = df.resample(period).agg(agg_funcs)

            # ===== Ajouter label et count =====
            agg_df['label'] = df.resample(period)['label'].apply(
                lambda x: self._get_label_from_scores(x, 'neutral')
            )
            agg_df['count'] = df.resample(period).size()

            # ===== Nettoyer (supprimer lignes vides) =====
            agg_df = agg_df[agg_df['count'] > 0].copy()

            if agg_df.empty:
                self.logger.warning("DataFrame agrégé vide après resample")
                return agg_df

            # ===== Trier par date décroissante =====
            agg_df = agg_df.sort_index(ascending=False)

            # ===== Arrondissement =====
            numeric_cols = ['sentiment_score', 'positive', 'negative', 'neutral']
            agg_df[numeric_cols] = agg_df[numeric_cols].round(4)

            self.logger.info(
                f"✓ Agrégation complétée | {len(agg_df)} périodes | "
                f"{agg_df['count'].sum()} articles"
            )

            return agg_df

        except Exception as e:
            self.logger.error(
                f"✗ Erreur agrégation par date: {type(e).__name__}: {str(e)}"
            )
            raise

    def aggregate_by_ticker(
        self,
        df: pd.DataFrame,
        ticker_column: str = 'ticker',
        method: Optional[str] = None
    ) -> Dict[str, SentimentScore]:
        """
        Agréger les scores de sentiment par ticker.

        Args:
            df: DataFrame avec colonne ticker
            ticker_column: Nom de la colonne ticker (défaut: 'ticker')
            method: Méthode d'agrégation

        Returns:
            Dict[ticker_symbol, SentimentScore]

        Raises:
            ValueError: Si colonne ticker manquante

        Example:
            >>> scores = aggregator.aggregate_by_ticker(news_df)
            >>> print(scores['AAPL'])
            {
                'sentiment_score': 0.65,
                'positive': 0.70,
                'negative': 0.10,
                'neutral': 0.20,
                'label': 'positive',
                'count': 45
            }
        """
        # Validation
        self._validate_dataframe(df)

        if ticker_column not in df.columns:
            raise ValueError(
                f"Colonne '{ticker_column}' non trouvée. "
                f"Colonnes disponibles: {df.columns.tolist()}"
            )

        method = method or self.default_method

        self.logger.info(
            f"Agrégation par ticker | method={method} | "
            f"colonnes uniques={df[ticker_column].nunique()}"
        )

        result = {}

        try:
            for ticker in sorted(df[ticker_column].unique()):
                ticker_df = df[df[ticker_column] == ticker]

                # Calculer scores
                if method == 'mean':
                    sentiment_score = float(ticker_df['sentiment_score'].mean())
                    positive = float(ticker_df['positive'].mean())
                    negative = float(ticker_df['negative'].mean())
                    neutral = float(ticker_df['neutral'].mean())

                elif method == 'median':
                    sentiment_score = float(ticker_df['sentiment_score'].median())
                    positive = float(ticker_df['positive'].median())
                    negative = float(ticker_df['negative'].median())
                    neutral = float(ticker_df['neutral'].median())

                else:  # weighted
                    sentiment_score = float(ticker_df['sentiment_score'].mean())
                    positive = float(ticker_df['positive'].mean())
                    negative = float(ticker_df['negative'].mean())
                    neutral = float(ticker_df['neutral'].mean())

                label = self._get_label_from_scores(ticker_df['label'], 'neutral')

                result[ticker] = {
                    'sentiment_score': round(sentiment_score, 4),
                    'positive': round(positive, 4),
                    'negative': round(negative, 4),
                    'neutral': round(neutral, 4),
                    'label': label,
                    'count': len(ticker_df)
                }

            self.logger.info(f"✓ Agrégation par ticker: {len(result)} tickers")

            return result

        except Exception as e:
            self.logger.error(
                f"✗ Erreur agrégation par ticker: {type(e).__name__}: {str(e)}"
            )
            raise

    def aggregate_by_source(
        self,
        df: pd.DataFrame,
        source_column: str = 'source',
        method: Optional[str] = None
    ) -> Dict[str, SentimentScore]:
        """
        Agréger les scores de sentiment par source de news.

        Args:
            df: DataFrame avec colonne source
            source_column: Nom de la colonne source (défaut: 'source')
            method: Méthode d'agrégation

        Returns:
            Dict[source_name, SentimentScore]

        Example:
            >>> scores = aggregator.aggregate_by_source(news_df)
            >>> print(scores['Yahoo Finance'])
        """
        # Validation
        self._validate_dataframe(df)

        if source_column not in df.columns:
            raise ValueError(
                f"Colonne '{source_column}' non trouvée. "
                f"Colonnes disponibles: {df.columns.tolist()}"
            )

        method = method or self.default_method

        self.logger.info(
            f"Agrégation par source | method={method} | "
            f"sources uniques={df[source_column].nunique()}"
        )

        result = {}

        try:
            for source in sorted(df[source_column].unique()):
                source_df = df[df[source_column] == source]

                if method == 'mean':
                    sentiment_score = float(source_df['sentiment_score'].mean())
                    positive = float(source_df['positive'].mean())
                    negative = float(source_df['negative'].mean())
                    neutral = float(source_df['neutral'].mean())

                elif method == 'median':
                    sentiment_score = float(source_df['sentiment_score'].median())
                    positive = float(source_df['positive'].median())
                    negative = float(source_df['negative'].median())
                    neutral = float(source_df['neutral'].median())

                else:
                    sentiment_score = float(source_df['sentiment_score'].mean())
                    positive = float(source_df['positive'].mean())
                    negative = float(source_df['negative'].mean())
                    neutral = float(source_df['neutral'].mean())

                label = self._get_label_from_scores(source_df['label'], 'neutral')

                result[source] = {
                    'sentiment_score': round(sentiment_score, 4),
                    'positive': round(positive, 4),
                    'negative': round(negative, 4),
                    'neutral': round(neutral, 4),
                    'label': label,
                    'count': len(source_df)
                }

            self.logger.info(f"✓ Agrégation par source: {len(result)} sources")

            return result

        except Exception as e:
            self.logger.error(
                f"✗ Erreur agrégation par source: {type(e).__name__}: {str(e)}"
            )
            raise

    def aggregate_weighted(
        self,
        df: pd.DataFrame,
        weights: Optional[Dict[str, float]] = None,
        weight_column: str = 'source'
    ) -> SentimentScore:
        """
        Agrégation pondérée des scores de sentiment.

        Args:
            df: DataFrame
            weights: Dict[key_value, weight] pour pondération
            weight_column: Colonne à utiliser pour poids

        Returns:
            SentimentScore avec résultats pondérés

        Example:
            >>> weights = {
            ...     "Yahoo Finance": 0.5,
            ...     "NewsAPI": 0.3,
            ...     "FinViz": 0.2
            ... }
            >>> weighted = aggregator.aggregate_weighted(
            ...     news_df,
            ...     weights=weights
            ... )
        """
        # Validation
        self._validate_dataframe(df)

        if weight_column not in df.columns:
            raise ValueError(f"Colonne '{weight_column}' non trouvée.")

        # Sans weights, utiliser moyenne simple
        if weights is None:
            self.logger.warning(
                "Pas de weights fournis, utilisation de moyenne simple"
            )
            return {
                'sentiment_score': round(float(df['sentiment_score'].mean()), 4),
                'positive': round(float(df['positive'].mean()), 4),
                'negative': round(float(df['negative'].mean()), 4),
                'neutral': round(float(df['neutral'].mean()), 4),
                'label': self._get_label_from_scores(df['label'], 'neutral'),
                'count': len(df)
            }

        try:
            # Appliquer weights
            df_weighted = df.copy()
            df_weighted['weight'] = df_weighted[weight_column].map(weights).fillna(1.0)

            total_weight = df_weighted['weight'].sum()

            if total_weight <= 0:
                self.logger.warning("Total weight = 0, utilisation de moyenne simple")
                total_weight = len(df)
                df_weighted['weight'] = 1.0

            # Calculer pondérés
            sentiment_score = float(
                (df_weighted['sentiment_score'] * df_weighted['weight']).sum() / total_weight
            )
            positive = float(
                (df_weighted['positive'] * df_weighted['weight']).sum() / total_weight
            )
            negative = float(
                (df_weighted['negative'] * df_weighted['weight']).sum() / total_weight
            )
            neutral = float(
                (df_weighted['neutral'] * df_weighted['weight']).sum() / total_weight
            )

            label = self._get_label_from_scores(df_weighted['label'], 'neutral')

            self.logger.info(f"✓ Agrégation pondérée: weight_column={weight_column}")

            return {
                'sentiment_score': round(sentiment_score, 4),
                'positive': round(positive, 4),
                'negative': round(negative, 4),
                'neutral': round(neutral, 4),
                'label': label,
                'count': len(df)
            }

        except Exception as e:
            self.logger.error(
                f"✗ Erreur agrégation pondérée: {type(e).__name__}: {str(e)}"
            )
            raise

    def get_sentiment_trend(
        self,
        df: pd.DataFrame,
        period: str = 'D',
        method: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Obtenir l'évolution du sentiment dans le temps.

        Alias pour aggregate_by_date avec tri automatique.

        Args:
            df: DataFrame avec index DatetimeIndex
            period: Période d'agrégation
            method: Méthode d'agrégation

        Returns:
            DataFrame de tendance temporelle

        Example:
            >>> trend = aggregator.get_sentiment_trend(news_df, period='W')
            >>> trend[['sentiment_score', 'count']].plot()
        """
        return self.aggregate_by_date(df, period=period, method=method)

    def get_sentiment_momentum(
        self,
        df: pd.DataFrame,
        period: str = 'D'
    ) -> pd.DataFrame:
        """
        Calculer le momentum du sentiment (changement jour/jour).

        Args:
            df: DataFrame avec index DatetimeIndex
            period: Période (défaut: 'D')

        Returns:
            DataFrame avec colonnes momentum:
            - sentiment_change: changement sentiment_score
            - positive_change: changement positive
            - negative_change: changement negative

        Example:
            >>> momentum = aggregator.get_sentiment_momentum(news_df, period='D')
            >>> print(momentum[['sentiment_change', 'count']].head())
        """
        # Valider
        self._validate_dataframe(df, require_datetime_index=True)

        self.logger.info(f"Calcul momentum sentiment | period={period}")

        try:
            # Obtenir trend
            trend = self.get_sentiment_trend(df, period=period)

            if len(trend) < 2:
                self.logger.warning(
                    "Pas assez de données pour calculer momentum "
                    "(besoin minimum 2 périodes)"
                )
                return trend

            # Calculer changements
            trend_copy = trend.copy()
            trend_copy['sentiment_change'] = trend_copy['sentiment_score'].diff()
            trend_copy['positive_change'] = trend_copy['positive'].diff()
            trend_copy['negative_change'] = trend_copy['negative'].diff()

            self.logger.info("✓ Calcul momentum complété")

            return trend_copy

        except Exception as e:
            self.logger.error(
                f"✗ Erreur calcul momentum: {type(e).__name__}: {str(e)}"
            )
            raise

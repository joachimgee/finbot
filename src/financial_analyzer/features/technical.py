"""
Module de calcul des features techniques (indicateurs TA).

Calcule des indicateurs techniques à partir de données OHLCV :
- SMA, EMA (Moving Averages)
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands
- ATR (Average True Range)
- ROC (Rate of Change)

Author: FinBot Team
Date: 2025-11-06
Version: 2.0.0
"""

from typing import Optional

import numpy as np
import pandas as pd

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class TechnicalFeatureEngine:
    """
    Moteur de calcul des features techniques.
    
    Calcule des indicateurs techniques (SMA, RSI, MACD, Bollinger, etc.)
    à partir de données OHLCV. Tous les calculs sont vectorisés avec pandas/numpy.
    
    Attributes:
        df: DataFrame OHLCV avec colonnes ['Open', 'High', 'Low', 'Close', 'Volume']
            et DatetimeIndex
    
    Example:
        >>> from financial_analyzer.data.market_data import MarketDataFetcher
        >>> from financial_analyzer.features.technical import TechnicalFeatureEngine
        >>> 
        >>> # Récupérer données OHLCV
        >>> fetcher = MarketDataFetcher()
        >>> ohlcv = fetcher.get_historical_data('AAPL', '2020-01-01', '2023-12-31')
        >>> 
        >>> # Calculer features techniques
        >>> engine = TechnicalFeatureEngine(ohlcv)
        >>> features = engine.calculate_all_features()
        >>> 
        >>> print(features.shape)
        (1008, 25)  # 1008 jours × 25 features
        >>> print(features.columns[:10])
        Index(['Open', 'High', 'Low', 'Close', 'Volume', 'SMA_20', 'EMA_20', 'RSI_14', 'MACD', 'Signal'], dtype='object')
    """
    
    def __init__(self, ohlcv: pd.DataFrame):
        """
        Initialise le moteur avec données OHLCV.
        
        Args:
            ohlcv: DataFrame avec colonnes OHLCV et DatetimeIndex
        
        Raises:
            ValueError: Si OHLCV invalide (colonnes manquantes, pas DatetimeIndex, NaN)
        
        Example:
            >>> engine = TechnicalFeatureEngine(ohlcv_df)
            >>> # ValueError si colonnes manquantes
            >>> invalid_df = pd.DataFrame({'Close': [100, 101, 102]})
            >>> engine = TechnicalFeatureEngine(invalid_df)
            Traceback (most recent call last):
            ...
            ValueError: Colonnes manquantes: ['Open', 'High', 'Low', 'Volume']
        """
        logger.info(f"Initialisation TechnicalFeatureEngine avec {len(ohlcv)} barres OHLCV")
        
        # Validation OHLCV
        self._validate_ohlcv(ohlcv)
        
        # Stocker données
        self.df = ohlcv.copy()
        logger.debug(f"OHLCV validé : {len(self.df)} barres, {self.df.index[0]} → {self.df.index[-1]}")
    
    def _validate_ohlcv(self, df: pd.DataFrame) -> None:
        """
        Valide le DataFrame OHLCV.
        
        Vérifie:
        - DatetimeIndex présent
        - Colonnes OHLCV présentes
        - Pas de NaN
        - Dates croissantes
        
        Args:
            df: DataFrame à valider
        
        Raises:
            ValueError: Si DataFrame invalide
        """
        if not isinstance(df.index, pd.DatetimeIndex):
            raise ValueError("Index doit être DatetimeIndex")
        
        required = ['Open', 'High', 'Low', 'Close', 'Volume']
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Colonnes manquantes: {missing}")
        
        if df[required].isnull().any().any():
            raise ValueError("Valeurs NaN détectées dans colonnes OHLCV")
        
        if not df.index.is_monotonic_increasing:
            raise ValueError("Dates non en ordre croissant")
    
    def calculate_sma(self, period: int = 20) -> pd.Series:
        """
        Calcule Simple Moving Average (SMA).
        
        Args:
            period: Période de calcul (nombre de barres)
        
        Returns:
            Series avec SMA, index=dates
            NaN pour les premières (period-1) barres
        
        Raises:
            ValueError: Si period <= 0
        
        Example:
            >>> engine = TechnicalFeatureEngine(ohlcv_df)
            >>> sma20 = engine.calculate_sma(period=20)
            >>> print(sma20.head(25))
            2020-01-01       NaN
            ...
            2020-01-20    150.25  # Première valeur après 20 barres
        """
        if period <= 0:
            raise ValueError(f"Period doit être > 0, reçu: {period}")
        
        if len(self.df) < period:
            logger.warning(
                f"Données insuffisantes pour SMA{period}: {len(self.df)} < {period} barres"
            )
        
        sma = self.df['Close'].rolling(window=period, min_periods=period).mean()
        logger.debug(f"SMA_{period} calculé : {(~sma.isna()).sum()} valeurs")
        return sma
    
    def calculate_ema(self, period: int = 20) -> pd.Series:
        """
        Calcule Exponential Moving Average (EMA).
        
        EMA donne plus de poids aux valeurs récentes.
        
        Args:
            period: Période de calcul
        
        Returns:
            Series avec EMA, index=dates
        
        Raises:
            ValueError: Si period <= 0
        
        Example:
            >>> engine = TechnicalFeatureEngine(ohlcv_df)
            >>> ema20 = engine.calculate_ema(period=20)
            >>> # EMA réagit plus vite que SMA aux changements de prix
        """
        if period <= 0:
            raise ValueError(f"Period doit être > 0, reçu: {period}")
        
        if len(self.df) < period:
            logger.warning(
                f"Données insuffisantes pour EMA{period}: {len(self.df)} < {period} barres"
            )
        
        ema = self.df['Close'].ewm(span=period, adjust=False).mean()
        logger.debug(f"EMA_{period} calculé : {len(ema)} valeurs")
        return ema
    
    def calculate_rsi(self, period: int = 14) -> pd.Series:
        """
        Calcule Relative Strength Index (RSI).
        
        RSI mesure la force du momentum :
        - RSI > 70 : Overbought (surachat)
        - RSI < 30 : Oversold (survente)
        - Range: 0-100
        
        Args:
            period: Période de calcul (typiquement 14)
        
        Returns:
            Series avec RSI, index=dates
            Range: 0-100
        
        Raises:
            ValueError: Si period <= 0
        
        Example:
            >>> engine = TechnicalFeatureEngine(ohlcv_df)
            >>> rsi14 = engine.calculate_rsi(period=14)
            >>> print(rsi14.describe())
            count    980.00
            mean      52.34
            min        8.12  # Oversold
            max       91.48  # Overbought
        """
        if period <= 0:
            raise ValueError(f"Period doit être > 0, reçu: {period}")
        
        if len(self.df) < period + 1:
            logger.warning(
                f"Données insuffisantes pour RSI{period}: {len(self.df)} < {period+1} barres"
            )
        
        # Calculer variations de prix
        delta = self.df['Close'].diff()
        
        # Séparer gains et pertes
        gain = delta.where(delta > 0, 0.0)
        loss = -delta.where(delta < 0, 0.0)
        
        # Moyenne mobile des gains et pertes
        avg_gain = gain.rolling(window=period, min_periods=period).mean()
        avg_loss = loss.rolling(window=period, min_periods=period).mean()
        
        # Calculer RS et RSI
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        logger.debug(
            f"RSI_{period} calculé : {(~rsi.isna()).sum()} valeurs, "
            f"range [{rsi.min():.2f}, {rsi.max():.2f}]"
        )
        return rsi
    
    def calculate_macd(
        self, fast: int = 12, slow: int = 26, signal: int = 9
    ) -> pd.DataFrame:
        """
        Calcule MACD (Moving Average Convergence Divergence).
        
        MACD = EMA(fast) - EMA(slow)
        Signal = EMA(MACD, signal)
        Histogram = MACD - Signal
        
        Args:
            fast: Période EMA rapide (défaut 12)
            slow: Période EMA lente (défaut 26)
            signal: Période signal line (défaut 9)
        
        Returns:
            DataFrame avec colonnes ['MACD', 'Signal', 'Histogram']
        
        Raises:
            ValueError: Si fast >= slow ou periods <= 0
        
        Example:
            >>> engine = TechnicalFeatureEngine(ohlcv_df)
            >>> macd = engine.calculate_macd()
            >>> print(macd.head())
                        MACD    Signal  Histogram
            2020-01-27  1.23     0.89       0.34
            # Signal d'achat quand MACD croise Signal vers le haut
            # Signal de vente quand MACD croise Signal vers le bas
        """
        if fast <= 0 or slow <= 0 or signal <= 0:
            raise ValueError(f"Tous les periods doivent être > 0")
        
        if fast >= slow:
            raise ValueError(f"Fast period ({fast}) doit être < slow period ({slow})")
        
        if len(self.df) < slow + signal:
            logger.warning(
                f"Données insuffisantes pour MACD({fast},{slow},{signal}): "
                f"{len(self.df)} < {slow+signal} barres"
            )
        
        # Calculer EMAs
        ema_fast = self.df['Close'].ewm(span=fast, adjust=False).mean()
        ema_slow = self.df['Close'].ewm(span=slow, adjust=False).mean()
        
        # MACD line
        macd_line = ema_fast - ema_slow
        
        # Signal line
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        
        # Histogram
        histogram = macd_line - signal_line
        
        result = pd.DataFrame(
            {
                'MACD': macd_line,
                'Signal': signal_line,
                'Histogram': histogram,
            },
            index=self.df.index,
        )
        
        logger.debug(
            f"MACD({fast},{slow},{signal}) calculé : "
            f"{(~result['MACD'].isna()).sum()} valeurs"
        )
        return result
    
    def calculate_bollinger_bands(
        self, period: int = 20, std_dev: float = 2.0
    ) -> pd.DataFrame:
        """
        Calcule Bollinger Bands.
        
        Bands = SMA ± (std_dev × standard_deviation)
        - Upper Band : SMA + (std_dev × σ)
        - Middle Band : SMA
        - Lower Band : SMA - (std_dev × σ)
        
        Args:
            period: Période SMA (défaut 20)
            std_dev: Nombre d'écarts-types (défaut 2)
        
        Returns:
            DataFrame avec colonnes ['Upper', 'Middle', 'Lower']
        
        Raises:
            ValueError: Si period <= 0 ou std_dev <= 0
        
        Example:
            >>> engine = TechnicalFeatureEngine(ohlcv_df)
            >>> bb = engine.calculate_bollinger_bands()
            >>> print(bb.head())
                        Upper    Middle   Lower
            2020-01-20  152.30   150.25  148.20
            # Prix touche Upper → potentiel overbought
            # Prix touche Lower → potentiel oversold
        """
        if period <= 0:
            raise ValueError(f"Period doit être > 0, reçu: {period}")
        
        if std_dev <= 0:
            raise ValueError(f"Std_dev doit être > 0, reçu: {std_dev}")
        
        if len(self.df) < period:
            logger.warning(
                f"Données insuffisantes pour BB{period}: {len(self.df)} < {period} barres"
            )
        
        # Calculer SMA et écart-type
        sma = self.df['Close'].rolling(window=period, min_periods=period).mean()
        std = self.df['Close'].rolling(window=period, min_periods=period).std()
        
        # Bands
        upper = sma + (std_dev * std)
        lower = sma - (std_dev * std)
        
        result = pd.DataFrame(
            {
                'Upper': upper,
                'Middle': sma,
                'Lower': lower,
            },
            index=self.df.index,
        )
        
        logger.debug(
            f"Bollinger Bands({period}, {std_dev}) calculé : "
            f"{(~result['Middle'].isna()).sum()} valeurs"
        )
        return result
    
    def calculate_atr(self, period: int = 14) -> pd.Series:
        """
        Calcule Average True Range (ATR).
        
        ATR mesure la volatilité :
        TR = max(High - Low, |High - Close_prev|, |Low - Close_prev|)
        ATR = moyenne mobile de TR
        
        Args:
            period: Période de calcul (défaut 14)
        
        Returns:
            Series avec ATR, index=dates
        
        Raises:
            ValueError: Si period <= 0
        
        Example:
            >>> engine = TechnicalFeatureEngine(ohlcv_df)
            >>> atr14 = engine.calculate_atr()
            >>> print(atr14.describe())
            mean    2.45  # Volatilité moyenne de 2.45 USD
            # ATR élevé → forte volatilité
            # ATR faible → faible volatilité
        """
        if period <= 0:
            raise ValueError(f"Period doit être > 0, reçu: {period}")
        
        if len(self.df) < period + 1:
            logger.warning(
                f"Données insuffisantes pour ATR{period}: {len(self.df)} < {period+1} barres"
            )
        
        high = self.df['High']
        low = self.df['Low']
        close_prev = self.df['Close'].shift(1)
        
        # True Range
        tr1 = high - low
        tr2 = (high - close_prev).abs()
        tr3 = (low - close_prev).abs()
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        
        # ATR = moyenne mobile de TR
        atr = tr.rolling(window=period, min_periods=period).mean()
        
        logger.debug(
            f"ATR_{period} calculé : {(~atr.isna()).sum()} valeurs, "
            f"moyenne {atr.mean():.2f}"
        )
        return atr
    
    def calculate_roc(self, period: int = 12) -> pd.Series:
        """
        Calcule Rate of Change (ROC).
        
        ROC mesure le momentum :
        ROC = ((Close - Close_n) / Close_n) × 100
        
        Args:
            period: Période de lookback (défaut 12)
        
        Returns:
            Series avec ROC en %, index=dates
        
        Raises:
            ValueError: Si period <= 0
        
        Example:
            >>> engine = TechnicalFeatureEngine(ohlcv_df)
            >>> roc12 = engine.calculate_roc()
            >>> print(roc12.describe())
            mean     0.52%   # Momentum moyen positif
            # ROC > 0 → prix en hausse
            # ROC < 0 → prix en baisse
        """
        if period <= 0:
            raise ValueError(f"Period doit être > 0, reçu: {period}")
        
        if len(self.df) < period + 1:
            logger.warning(
                f"Données insuffisantes pour ROC{period}: {len(self.df)} < {period+1} barres"
            )
        
        close = self.df['Close']
        close_n = close.shift(period)
        
        roc = ((close - close_n) / close_n) * 100
        
        logger.debug(
            f"ROC_{period} calculé : {(~roc.isna()).sum()} valeurs, "
            f"moyenne {roc.mean():.2f}%"
        )
        return roc
    
    def calculate_all_features(self) -> pd.DataFrame:
        """
        Calcule TOUTES les features techniques.
        
        Features calculées :
        - OHLCV (colonnes originales)
        - SMA (20, 50, 200)
        - EMA (12, 20, 50)
        - RSI (14)
        - MACD (12, 26, 9)
        - Bollinger Bands (20, 2σ)
        - ATR (14)
        - ROC (12)
        - Volume SMA (20)
        
        Returns:
            DataFrame avec toutes les features
            Colonnes : OHLCV + ~20 features techniques
            Index : DatetimeIndex (mêmes dates que OHLCV)
        
        Example:
            >>> engine = TechnicalFeatureEngine(ohlcv_df)
            >>> features = engine.calculate_all_features()
            >>> 
            >>> print(features.shape)
            (1008, 25)  # 1008 barres × 25 colonnes
            >>> 
            >>> print(features.columns.tolist())
            ['Open', 'High', 'Low', 'Close', 'Volume',
             'SMA_20', 'SMA_50', 'SMA_200',
             'EMA_12', 'EMA_20', 'EMA_50',
             'RSI_14',
             'MACD', 'Signal', 'Histogram',
             'BB_Upper', 'BB_Middle', 'BB_Lower',
             'ATR_14',
             'ROC_12',
             'Volume_SMA_20']
            >>> 
            >>> # Vérifier valeurs non-NaN
            >>> print(features.notna().sum())
            Open              1008
            Close             1008
            SMA_200            809  # NaN pour premières 199 barres
            RSI_14             994  # NaN pour premières 14 barres
        """
        logger.info(f"Calcul de toutes les features techniques pour {len(self.df)} barres")
        
        # Copier OHLCV
        result = self.df.copy()
        
        try:
            # Moving Averages
            result['SMA_20'] = self.calculate_sma(period=20)
            result['SMA_50'] = self.calculate_sma(period=50)
            result['SMA_200'] = self.calculate_sma(period=200)
            
            result['EMA_12'] = self.calculate_ema(period=12)
            result['EMA_20'] = self.calculate_ema(period=20)
            result['EMA_50'] = self.calculate_ema(period=50)
            
            # RSI
            result['RSI_14'] = self.calculate_rsi(period=14)
            
            # MACD
            macd = self.calculate_macd()
            result['MACD'] = macd['MACD']
            result['MACD_Signal'] = macd['Signal']
            result['MACD_Histogram'] = macd['Histogram']
            
            # Bollinger Bands
            bb = self.calculate_bollinger_bands()
            result['BB_Upper'] = bb['Upper']
            result['BB_Middle'] = bb['Middle']
            result['BB_Lower'] = bb['Lower']
            
            # ATR
            result['ATR_14'] = self.calculate_atr(period=14)
            
            # ROC
            result['ROC_12'] = self.calculate_roc(period=12)
            
            # Volume SMA
            result['Volume_SMA_20'] = self.df['Volume'].rolling(window=20, min_periods=20).mean()
            
            # Calcul ratio Bollinger Band Width
            result['BB_Width'] = (bb['Upper'] - bb['Lower']) / bb['Middle']
            
            # Returns
            result['Returns'] = self.df['Close'].pct_change()
            
            logger.info(
                f"Features calculées : {len(result.columns)} colonnes, "
                f"{result.notna().all(axis=1).sum()} barres complètes (sans NaN)"
            )
            
            return result
        
        except Exception as e:
            logger.error(f"Erreur calcul features : {e}")
            raise

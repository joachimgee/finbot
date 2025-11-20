"""
Microstructure Features Module.

Module pour extraire features de microstructure de marché :
- VWAP (Volume-Weighted Average Price) : Prix moyen pondéré par volume
- Order Flow : Déséquilibre buy/sell, pressure d'achat/vente
- Bid-Ask Spread : Spread, profondeur de marché, illiquidité
- Liquidity Metrics : Roll spread, effective spread, Kyle's Lambda

Applications :
- Détection de manipulation de prix
- Mesure d'impact de marché
- Optimal execution (VWAP strategies)
- Market quality assessment

Based on : Kyle (1985), Roll (1984), Amihud (2002).
"""

from typing import Dict, Optional, Tuple
import numpy as np
import pandas as pd

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class MicrostructureFeatures:
    """
    Extracteur de features de microstructure de marché.
    
    Attributes:
        window: Fenêtre de calcul (nombre de périodes)
    
    Example:
        >>> micro = MicrostructureFeatures(window=20)
        >>> features = micro.compute_all(data)
        >>> print(features['vwap'])
        >>> print(features['order_flow_imbalance'])
    """
    
    def __init__(self, window: int = 20):
        """
        Initialise MicrostructureFeatures.
        
        Args:
            window: Fenêtre de calcul
        """
        if window < 1:
            raise ValueError("window doit être >= 1")
        
        self.window = window
        
        logger.debug(f"MicrostructureFeatures initialized: window={window}")
    
    def compute_vwap(
        self,
        data: pd.DataFrame,
        price_col: str = 'close',
        volume_col: str = 'volume'
    ) -> pd.Series:
        """
        Calcule VWAP (Volume-Weighted Average Price).
        
        VWAP = Σ(Price * Volume) / Σ(Volume)
        
        Args:
            data: DataFrame avec prix et volume
            price_col: Colonne prix
            volume_col: Colonne volume
        
        Returns:
            Series VWAP
        
        Example:
            >>> vwap = micro.compute_vwap(data)
        """
        pv = data[price_col] * data[volume_col]
        cumsum_pv = pv.rolling(window=self.window).sum()
        cumsum_vol = data[volume_col].rolling(window=self.window).sum()
        
        vwap = cumsum_pv / cumsum_vol
        
        return vwap
    
    def compute_order_flow_imbalance(
        self,
        data: pd.DataFrame,
        volume_col: str = 'volume'
    ) -> pd.Series:
        """
        Calcule Order Flow Imbalance.
        
        OFI = (Buy Volume - Sell Volume) / Total Volume
        
        Approximation : Si prix monte → buy, si descend → sell
        
        Args:
            data: DataFrame avec prix et volume
            volume_col: Colonne volume
        
        Returns:
            Series OFI (-1 à 1)
        
        Example:
            >>> ofi = micro.compute_order_flow_imbalance(data)
        """
        price_change = data['close'].diff()
        
        # Approximation : prix up = buy, prix down = sell
        buy_volume = data[volume_col].where(price_change > 0, 0)
        sell_volume = data[volume_col].where(price_change < 0, 0)
        
        # Rolling imbalance
        buy_rolling = buy_volume.rolling(window=self.window).sum()
        sell_rolling = sell_volume.rolling(window=self.window).sum()
        total_rolling = data[volume_col].rolling(window=self.window).sum()
        
        ofi = (buy_rolling - sell_rolling) / total_rolling
        
        return ofi.fillna(0)
    
    def compute_bid_ask_spread(
        self,
        data: pd.DataFrame,
        method: str = 'roll'
    ) -> pd.Series:
        """
        Estime Bid-Ask Spread.
        
        Methods:
        - 'roll' : Roll (1984) estimator = 2 * sqrt(-Cov(ΔP_t, ΔP_{t-1}))
        - 'high_low' : (High - Low) / (High + Low)
        
        Args:
            data: DataFrame avec prix
            method: Méthode d'estimation
        
        Returns:
            Series spread estimé
        
        Example:
            >>> spread = micro.compute_bid_ask_spread(data, method='roll')
        """
        if method == 'roll':
            # Roll estimator
            returns = data['close'].pct_change()
            
            # Covariance entre returns consécutifs
            cov = returns.rolling(window=self.window).apply(
                lambda x: np.cov(x[:-1], x[1:])[0, 1] if len(x) > 1 else 0,
                raw=True
            )
            
            # Spread = 2 * sqrt(-cov)
            spread = 2 * np.sqrt(-cov.clip(upper=0))
            
            return spread.fillna(0)
        
        elif method == 'high_low':
            # High-Low spread
            high = data['high']
            low = data['low']
            
            spread = (high - low) / ((high + low) / 2)
            
            return spread.fillna(0)
        
        else:
            raise ValueError(f"Method inconnu: {method}")
    
    def compute_amihud_illiquidity(
        self,
        data: pd.DataFrame,
        volume_col: str = 'volume'
    ) -> pd.Series:
        """
        Calcule Amihud Illiquidity Ratio.
        
        Illiquidity = |Return| / Volume
        
        Mesure l'impact de prix par unité de volume.
        
        Args:
            data: DataFrame avec prix et volume
            volume_col: Colonne volume
        
        Returns:
            Series illiquidity ratio
        
        Example:
            >>> illiq = micro.compute_amihud_illiquidity(data)
        """
        returns = data['close'].pct_change().abs()
        volume = data[volume_col]
        
        # Illiquidity = |return| / volume (en millions pour normaliser)
        illiquidity = returns / (volume / 1e6)
        
        # Rolling average
        illiquidity_rolling = illiquidity.rolling(window=self.window).mean()
        
        return illiquidity_rolling.fillna(0)
    
    def compute_kyles_lambda(
        self,
        data: pd.DataFrame,
        volume_col: str = 'volume'
    ) -> float:
        """
        Estime Kyle's Lambda (price impact coefficient).
        
        ΔPrice = λ * OrderFlow + noise
        
        λ mesure l'impact de prix d'un ordre.
        
        Args:
            data: DataFrame avec prix et volume
            volume_col: Colonne volume
        
        Returns:
            Kyle's Lambda (float)
        
        Example:
            >>> lambda_kyle = micro.compute_kyles_lambda(data)
        """
        # Price changes
        price_change = data['close'].diff()
        
        # Order flow (approximation via signed volume)
        price_direction = np.sign(price_change)
        signed_volume = price_direction * data[volume_col]
        
        # Regression : ΔP ~ OrderFlow
        valid_mask = (~price_change.isna()) & (~signed_volume.isna())
        
        if valid_mask.sum() < 10:
            logger.warning("Pas assez de données pour Kyle's Lambda")
            return 0.0
        
        x = signed_volume[valid_mask].values
        y = price_change[valid_mask].values
        
        # OLS
        if len(x) > 0 and np.std(x) > 0:
            lambda_kyle = np.cov(x, y)[0, 1] / np.var(x)
        else:
            lambda_kyle = 0.0
        
        return lambda_kyle
    
    def compute_effective_spread(
        self,
        data: pd.DataFrame,
        volume_col: str = 'volume'
    ) -> pd.Series:
        """
        Calcule Effective Spread.
        
        Effective Spread = 2 * |Trade Price - Midpoint|
        
        Approximation : Midpoint = (High + Low) / 2
        
        Args:
            data: DataFrame avec OHLC
            volume_col: Colonne volume
        
        Returns:
            Series effective spread
        
        Example:
            >>> eff_spread = micro.compute_effective_spread(data)
        """
        midpoint = (data['high'] + data['low']) / 2
        trade_price = data['close']
        
        effective_spread = 2 * (trade_price - midpoint).abs()
        
        # Normalize par prix
        effective_spread_pct = effective_spread / midpoint
        
        return effective_spread_pct.fillna(0)
    
    def compute_volume_concentration(
        self,
        data: pd.DataFrame,
        volume_col: str = 'volume'
    ) -> pd.Series:
        """
        Calcule Volume Concentration (Herfindahl Index).
        
        Mesure la distribution du volume : haute concentration = peu de trades larges.
        
        Args:
            data: DataFrame avec volume
            volume_col: Colonne volume
        
        Returns:
            Series concentration index
        
        Example:
            >>> conc = micro.compute_volume_concentration(data)
        """
        volume = data[volume_col]
        
        # Rolling window
        def herfindahl(x):
            if len(x) == 0 or x.sum() == 0:
                return 0
            shares = x / x.sum()
            return (shares ** 2).sum()
        
        concentration = volume.rolling(window=self.window).apply(herfindahl, raw=True)
        
        return concentration.fillna(0)
    
    def compute_price_impact(
        self,
        data: pd.DataFrame,
        volume_col: str = 'volume'
    ) -> pd.Series:
        """
        Calcule Price Impact par unité de volume.
        
        Price Impact = |ΔPrice| / Volume
        
        Args:
            data: DataFrame avec prix et volume
            volume_col: Colonne volume
        
        Returns:
            Series price impact
        
        Example:
            >>> impact = micro.compute_price_impact(data)
        """
        price_change = data['close'].pct_change().abs()
        volume = data[volume_col]
        
        # Impact = |ΔP| / Volume (normalize)
        impact = price_change / (volume / volume.rolling(window=self.window).mean())
        
        return impact.fillna(0)
    
    def compute_all(
        self,
        data: pd.DataFrame,
        volume_col: str = 'volume'
    ) -> Dict[str, pd.Series]:
        """
        Calcule toutes les features de microstructure.
        
        Args:
            data: DataFrame avec OHLCV
            volume_col: Colonne volume
        
        Returns:
            Dict avec toutes les features
        
        Example:
            >>> features = micro.compute_all(data)
            >>> print(features['vwap'])
            >>> print(features['order_flow_imbalance'])
        """
        features = {}
        
        # VWAP
        features['vwap'] = self.compute_vwap(data, volume_col=volume_col)
        
        # Order flow
        features['order_flow_imbalance'] = self.compute_order_flow_imbalance(data, volume_col=volume_col)
        
        # Spreads
        features['bid_ask_spread_roll'] = self.compute_bid_ask_spread(data, method='roll')
        features['bid_ask_spread_hl'] = self.compute_bid_ask_spread(data, method='high_low')
        features['effective_spread'] = self.compute_effective_spread(data, volume_col=volume_col)
        
        # Liquidity
        features['amihud_illiquidity'] = self.compute_amihud_illiquidity(data, volume_col=volume_col)
        features['volume_concentration'] = self.compute_volume_concentration(data, volume_col=volume_col)
        features['price_impact'] = self.compute_price_impact(data, volume_col=volume_col)
        
        # Kyle's Lambda (scalar)
        features['kyles_lambda'] = self.compute_kyles_lambda(data, volume_col=volume_col)
        
        logger.info(f"Computed all microstructure features: Kyle's λ={features['kyles_lambda']:.6f}")
        
        return features


def compute_vwap(
    data: pd.DataFrame,
    window: int = 20,
    price_col: str = 'close',
    volume_col: str = 'volume'
) -> pd.Series:
    """
    Fonction convenience pour VWAP.
    
    Args:
        data: DataFrame avec prix et volume
        window: Fenêtre de calcul
        price_col: Colonne prix
        volume_col: Colonne volume
    
    Returns:
        Series VWAP
    
    Example:
        >>> vwap = compute_vwap(data, window=20)
    """
    micro = MicrostructureFeatures(window=window)
    return micro.compute_vwap(data, price_col=price_col, volume_col=volume_col)

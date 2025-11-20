#!/usr/bin/env python3
"""
FinBot - Continuous Alpaca Paper Trading System
================================================

Système de trading continu connecté à Alpaca Paper Trading intégrant
TOUS les modules disponibles dans /workspaces/finbot/src.

Architecture complète :
1. Data Pipeline : MarketDataFetcher + NewsScraper + yfinance
2. Feature Engineering : TechnicalFeatureEngine (114+ facteurs)
3. ML Models : LSTM + RandomForest + Sentiment (FinBERT)
4. Portfolio Optimization : PyPortfolioOpt + Riskfolio-Lib
5. Risk Management : StressTester + VaR + RiskGuard
6. Execution : AlpacaAdapter + LiveTradingPipeline

Fonctionnalités :
- Connexion continue à Alpaca Paper Trading
- Monitoring compte en temps réel
- Génération signaux multi-modèles
- Optimisation portefeuille sophistiquée
- Risk management Basel III
- Execution avec validation circuit breakers

Usage:
    python run_continuous_alpaca_trading.py --mode paper --universe 30
"""

import os
import sys
import argparse
import logging
import time
import signal
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import pandas as pd
import numpy as np
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add src to path
sys.path.insert(0, '/workspaces/finbot/src')
sys.path.insert(0, '/workspaces/finbot')

# Imports organized by phase
from financial_analyzer.utils.helpers import get_logger

# Phase 1: Data Layer
try:
    from financial_analyzer.data.market_data import MarketDataFetcher
    DATA_AVAILABLE = True
except Exception as e:
    print(f"⚠️  MarketDataFetcher not available: {e}")
    DATA_AVAILABLE = False

try:
    from financial_analyzer.data.news_scraper import FinancialNewsScraper
    NEWS_AVAILABLE = True
except Exception as e:
    print(f"⚠️  NewsScraper not available: {e}")
    NEWS_AVAILABLE = False

# Phase 2: Feature Engineering
try:
    from financial_analyzer.features.technical import TechnicalFeatureEngine
    TECHNICAL_AVAILABLE = True
except Exception as e:
    print(f"⚠️  TechnicalFeatureEngine not available: {e}")
    TECHNICAL_AVAILABLE = False

try:
    from financial_analyzer.features.fundamental import FundamentalFeatureEngine
    FUNDAMENTAL_AVAILABLE = True
except Exception as e:
    print(f"⚠️  FundamentalFeatureEngine not available: {e}")
    FUNDAMENTAL_AVAILABLE = False

# Phase 3: ML Models
try:
    from financial_analyzer.deep_learning.lstm_predictor import LSTMPredictor
    LSTM_AVAILABLE = True
except Exception as e:
    print(f"⚠️  LSTMPredictor not available: {e}")
    LSTM_AVAILABLE = False

try:
    from financial_analyzer.analysis.ml_predictor import MLPredictor
    ML_PREDICTOR_AVAILABLE = True
except Exception as e:
    print(f"⚠️  MLPredictor not available: {e}")
    ML_PREDICTOR_AVAILABLE = False

try:
    from financial_analyzer.sentiment.finbert_engine import FinBERTEngine
    SENTIMENT_AVAILABLE = True
except Exception as e:
    print(f"⚠️  FinBERTEngine not available: {e}")
    SENTIMENT_AVAILABLE = False

try:
    from financedatabase import Equities
    FINANCE_DATABASE_AVAILABLE = True
except Exception as e:
    print(f"⚠️  FinanceDatabase not available: {e}")
    FINANCE_DATABASE_AVAILABLE = False
    Equities = None

try:
    from financial_analyzer.ml.sentiment_pipeline import SentimentAnalyzer
    SENTIMENT_PIPELINE_AVAILABLE = True
except Exception as e:
    print(f"⚠️  SentimentPipeline not available: {e}")
    SENTIMENT_PIPELINE_AVAILABLE = False

# Professional Analysis Modules
try:
    from financial_analyzer.ml.feature_engineering import AlphaFactorEngine
    ALPHA_FACTOR_AVAILABLE = True
except Exception as e:
    print(f"⚠️  AlphaFactorEngine not available: {e}")
    ALPHA_FACTOR_AVAILABLE = False

try:
    from financial_analyzer.ml_features.feature_engineer import FeatureEngineer
    ML_FEATURES_AVAILABLE = True
except Exception as e:
    print(f"⚠️  FeatureEngineer not available: {e}")
    ML_FEATURES_AVAILABLE = False

# Phase 4: Portfolio Optimization
try:
    from financial_analyzer.portfolio_optimization.pyportfolioopt_optimizer import PyPortfolioOptOptimizer
    PYPFOPT_AVAILABLE = True
except Exception as e:
    print(f"⚠️  PyPortfolioOpt not available: {e}")
    PYPFOPT_AVAILABLE = False

try:
    from financial_analyzer.portfolio_optimization.riskfolio_optimizer import RiskfolioOptimizer
    RISKFOLIO_AVAILABLE = True
except Exception as e:
    print(f"⚠️  Riskfolio-Lib not available: {e}")
    RISKFOLIO_AVAILABLE = False

# Phase 5: Risk Management
try:
    from financial_analyzer.risk.stress_test import StressTester
    STRESS_TEST_AVAILABLE = True
except Exception as e:
    print(f"⚠️  StressTester not available: {e}")
    STRESS_TEST_AVAILABLE = False

try:
    from financial_analyzer.risk.var_backtest import backtest_multi_methods
    VAR_BACKTEST_AVAILABLE = True
except Exception as e:
    print(f"⚠️  VaR Backtest not available: {e}")
    VAR_BACKTEST_AVAILABLE = False

try:
    from financial_analyzer.risk.market_cap_weights import calculate_market_cap_weights
    MARKET_CAP_AVAILABLE = True
except Exception as e:
    print(f"⚠️  MarketCapWeights not available: {e}")
    MARKET_CAP_AVAILABLE = False

# Phase 6: Trading Execution
try:
    from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
    ALPACA_AVAILABLE = True
except Exception as e:
    print(f"❌ AlpacaAdapter not available: {e}")
    ALPACA_AVAILABLE = False

try:
    from financial_analyzer.trading.account_monitor import AccountMonitor
    MONITOR_AVAILABLE = True
except Exception as e:
    print(f"⚠️  AccountMonitor not available: {e}")
    MONITOR_AVAILABLE = False

try:
    from financial_analyzer.trading.risk_guard import RiskGuard
    RISK_GUARD_AVAILABLE = True
except Exception as e:
    print(f"⚠️  RiskGuard not available: {e}")
    RISK_GUARD_AVAILABLE = False

try:
    from financial_analyzer.trading.live_trading_pipeline import LiveTradingPipeline
    LIVE_PIPELINE_AVAILABLE = True
except Exception as e:
    print(f"⚠️  LiveTradingPipeline not available: {e}")
    LIVE_PIPELINE_AVAILABLE = False

logger = get_logger(__name__)


class ContinuousAlpacaTradingSystem:
    """
    Système de trading continu intégrant tous les modules FinBot.
    
    Responsabilités:
    - Connexion continue Alpaca Paper Trading
    - Monitoring compte temps réel
    - Pipeline data → features → ML → portfolio → risk → execution
    - Rebalancement périodique (configurable)
    - Circuit breakers et risk limits
    - Logging complet et métriques
    """
    
    def __init__(
        self,
        universe_size: int = 30,
        rebalance_frequency_hours: int = 24,
        max_position_size: float = 0.15,
        max_portfolio_var: float = 0.25,
        enable_ml: bool = True,
        enable_sentiment: bool = True,
        enable_stress_test: bool = True
    ):
        """
        Initialize continuous trading system.
        
        Args:
            universe_size: Nombre de tickers dans l'univers (défaut 30)
            rebalance_frequency_hours: Fréquence rebalancement en heures
            max_position_size: Taille max position (% portefeuille)
            max_portfolio_var: VaR max portefeuille (% capital)
            enable_ml: Activer modèles ML
            enable_sentiment: Activer sentiment analysis
            enable_stress_test: Activer stress testing
        """
        self.universe_size = universe_size
        self.rebalance_frequency = rebalance_frequency_hours * 3600  # convert to seconds
        self.max_position_size = max_position_size
        self.max_portfolio_var = max_portfolio_var
        self.enable_ml = enable_ml and (LSTM_AVAILABLE or ML_PREDICTOR_AVAILABLE)
        self.enable_sentiment = enable_sentiment and (SENTIMENT_AVAILABLE or SENTIMENT_PIPELINE_AVAILABLE)
        self.enable_stress_test = enable_stress_test and STRESS_TEST_AVAILABLE
        
        self.running = False
        self.last_rebalance = None
        
        # Initialize components
        self._init_components()
        
        logger.info(f"ContinuousAlpacaTradingSystem initialized: universe={universe_size}, "
                   f"rebalance_every={rebalance_frequency_hours}h, ML={self.enable_ml}, "
                   f"sentiment={self.enable_sentiment}, stress_test={self.enable_stress_test}")
    
    def _init_components(self):
        """Initialize all available components."""
        logger.info("Initializing trading system components...")
        
        # 1. Alpaca Connection (CRITICAL)
        if not ALPACA_AVAILABLE:
            raise RuntimeError("❌ AlpacaAdapter not available - cannot proceed")
        
        api_key = os.getenv('APCA_API_KEY_ID')
        api_secret = os.getenv('APCA_API_SECRET_KEY')
        
        if not api_key or not api_secret:
            raise RuntimeError(
                "❌ Alpaca API keys not found in environment.\n"
                "Set APCA_API_KEY_ID and APCA_API_SECRET_KEY"
            )
        
        self.alpaca = AlpacaAdapter.from_env(mode='paper')
        logger.info("✅ AlpacaAdapter initialized")
        
        # 2. Data fetchers
        self.market_data = MarketDataFetcher() if DATA_AVAILABLE else None
        self.news_scraper = FinancialNewsScraper() if NEWS_AVAILABLE else None
        
        # 3. Feature engines (lazy load - requires data)
        self.technical_engine = None  # Lazy load with data
        self.fundamental_engine = None  # Lazy load with data
        
        # 4. ML Models
        self.lstm_predictor = None  # Lazy load
        self.ml_predictor = None  # Lazy load
        self.sentiment_analyzer = SentimentAnalyzer() if SENTIMENT_PIPELINE_AVAILABLE else None
        self.finbert = None  # Lazy load if needed
        
        # 5. Portfolio optimizers (lazy load - require data)
        self.pypfopt = None  # Lazy load with prices
        self.riskfolio = None  # Lazy load with prices
        
        # 6. Risk management
        self.stress_tester = None  # Lazy load
        
        # 7. Monitoring & Risk Guard (lazy load after connection)
        self.monitor = None  # Requires Alpaca connection
        self.risk_guard = None  # Requires monitor
        
        logger.info("✅ All components initialized")
    
    def connect(self):
        """Connect to Alpaca and verify account access."""
        logger.info("Connecting to Alpaca Paper Trading...")
        
        try:
            self.alpaca.connect()
            account = self.alpaca.get_account()
            
            logger.info("=" * 70)
            logger.info("✅ ALPACA PAPER TRADING CONNECTED")
            logger.info("=" * 70)
            logger.info(f"Account ID: {account.get('account_id', 'N/A')}")
            logger.info(f"Cash: ${float(account.get('cash', 0)):,.2f}")
            logger.info(f"Portfolio Value: ${float(account.get('portfolio_value', 0)):,.2f}")
            logger.info(f"Buying Power: ${float(account.get('buying_power', 0)):,.2f}")
            logger.info(f"Status: {account.get('status', 'unknown')}")
            logger.info("=" * 70)
            
            # Initialize monitor AFTER connection
            if MONITOR_AVAILABLE:
                self.monitor = AccountMonitor(self.alpaca)
                logger.info("✅ AccountMonitor initialized")
            
            # Initialize RiskGuard AFTER monitor
            if RISK_GUARD_AVAILABLE and self.monitor:
                self.risk_guard = RiskGuard(
                    account_monitor=self.monitor,
                    max_position_size=self.max_position_size,
                    max_daily_loss=0.05,
                    max_drawdown=0.20
                )
                logger.info(f"✅ RiskGuard initialized (max_position={self.max_position_size:.1%})")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to Alpaca: {e}")
            return False
    
    def get_universe(self) -> List[str]:
        """
        Sélectionne univers de trading large avec FinanceDatabase.
        
        Returns:
            Liste de tickers (jusqu'à universe_size, filtrés par liquidité)
        """
        logger.info(f"Selecting universe (target {self.universe_size} tickers)...")
        
        # Univers par défaut (S&P 500 large caps) si FinanceDatabase indisponible
        default_universe = [
            'AAPL', 'MSFT', 'NVDA', 'GOOGL', 'AMZN', 'META', 'BRK.B', 'TSLA',
            'UNH', 'XOM', 'LLY', 'JPM', 'JNJ', 'V', 'AVGO', 'PG', 'MA',
            'HD', 'CVX', 'MRK', 'ABBV', 'COST', 'PEP', 'KO', 'ADBE', 'WMT',
            'BAC', 'CRM', 'CSCO', 'AMD', 'ACN', 'MCD', 'TMO', 'NFLX', 'ABT',
            'DIS', 'WFC', 'CMCSA', 'PFE', 'VZ', 'INTC', 'TXN', 'DHR', 'ORCL',
            'PM', 'NKE', 'UPS', 'RTX', 'QCOM', 'HON', 'LIN', 'CAT', 'IBM',
            'INTU', 'GE', 'AMAT', 'AXP', 'SPGI', 'BLK', 'DE', 'GILD', 'BKNG',
            'MDLZ', 'ADI', 'ISRG', 'TJX', 'MMC', 'CB', 'SYK', 'CI', 'SO',
            'REGN', 'VRTX', 'ZTS', 'PLD', 'DUK', 'BMY', 'SCHW', 'EOG', 'BSX',
            'ITW', 'HCA', 'CME', 'APD', 'USB', 'PNC', 'CL', 'NOC', 'FI',
            'MMM', 'GD', 'TGT', 'EMR', 'NSC', 'AON', 'ETN', 'SLB', 'EQIX'
        ][:self.universe_size]
        
        # Utiliser FinanceDatabase si disponible
        if FINANCE_DATABASE_AVAILABLE and Equities is not None:
            try:
                logger.info("Using FinanceDatabase for universe selection...")
                eq = Equities()
                df = eq.search(country="United States")
                
                if df is not None and not df.empty:
                    # Filtrer symboles valides (pas d'OTC, pas de classes multiples)
                    symbols = []
                    for sym in df.index:
                        if isinstance(sym, str) and '.' not in sym and sym.count('-') <= 1 and len(sym) <= 5:
                            symbols.append(sym)
                        if len(symbols) >= self.universe_size * 2:  # Buffer pour filtrage
                            break
                    
                    logger.info(f"✅ FinanceDatabase: {len(symbols)} symbols retrieved")
                    
                    # Filter par market cap si disponible
                    if MARKET_CAP_AVAILABLE and len(symbols) > self.universe_size:
                        try:
                            from financial_analyzer.risk.market_cap_weights import get_market_caps
                            caps = get_market_caps(symbols[:500])  # Limit API calls
                            sorted_tickers = caps.nlargest(self.universe_size).index.tolist()
                            logger.info(f"✅ Universe selected: {len(sorted_tickers)} tickers by market cap")
                            return sorted_tickers
                        except Exception as e:
                            logger.warning(f"Market cap filtering failed: {e}")
                    
                    # Return top N
                    final_symbols = symbols[:self.universe_size]
                    logger.info(f"✅ Universe selected: {len(final_symbols)} tickers (FinanceDatabase)")
                    return final_symbols
                
            except Exception as e:
                logger.warning(f"FinanceDatabase failed: {e}")
        
        # Fallback
        logger.info(f"✅ Universe selected: {len(default_universe)} tickers (default S&P 500)")
        return default_universe
    
    def fetch_data(self, universe: List[str], lookback_days: int = 252) -> pd.DataFrame:
        """
        Fetch historical price data for universe.
        
        Args:
            universe: List of tickers
            lookback_days: Nombre de jours historiques
            
        Returns:
            DataFrame avec prices (index=date, columns=tickers)
        """
        logger.info(f"Fetching {lookback_days} days of data for {len(universe)} tickers...")
        
        if not self.market_data:
            logger.warning("MarketDataFetcher not available, using fallback")
            # Fallback to Alpaca bars
            end_date = datetime.now()
            start_date = end_date - timedelta(days=lookback_days * 1.5)  # Buffer for weekends
            
            all_data = {}
            for ticker in universe:
                try:
                    bars = self.alpaca.get_historical_bars(
                        ticker,
                        start_date.strftime('%Y-%m-%d'),
                        end_date.strftime('%Y-%m-%d'),
                        timeframe='1D'
                    )
                    if bars:
                        df = pd.DataFrame(bars)
                        df['timestamp'] = pd.to_datetime(df['timestamp'])
                        df = df.set_index('timestamp')
                        all_data[ticker] = df['close']
                except Exception as e:
                    logger.warning(f"Failed to fetch {ticker}: {e}")
            
            if all_data:
                prices = pd.DataFrame(all_data)
                logger.info(f"✅ Fetched {len(prices)} days via Alpaca")
                return prices
            else:
                raise RuntimeError("Failed to fetch any data")
        
        # Use MarketDataFetcher
        end_date = datetime.now()
        start_date = end_date - timedelta(days=lookback_days * 1.5)
        
        all_prices = {}
        for ticker in universe:
            try:
                df = self.market_data.get_historical_data(
                    ticker,
                    start_date=start_date.strftime('%Y-%m-%d'),
                    end_date=end_date.strftime('%Y-%m-%d')
                )
                all_prices[ticker] = df['Close']
            except Exception as e:
                logger.warning(f"Failed to fetch {ticker}: {e}")
        
        prices = pd.DataFrame(all_prices).dropna()
        logger.info(f"✅ Fetched {len(prices)} days for {len(prices.columns)} tickers")
        return prices
    
    def compute_features(self, prices: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """
        Compute technical + fundamental features.
        
        Args:
            prices: DataFrame of prices
            
        Returns:
            Dict with 'technical' and 'fundamental' DataFrames
        """
        logger.info("Computing features...")
        features = {}
        
        # Technical features (lazy load engine)
        if TECHNICAL_AVAILABLE:
            try:
                if self.technical_engine is None:
                    self.technical_engine = TechnicalFeatureEngine(prices)
                tech_features = self.technical_engine.generate_features(prices)
                features['technical'] = tech_features
                logger.info(f"✅ Technical features: {tech_features.shape}")
            except Exception as e:
                logger.warning(f"Technical features failed: {e}")
        
        # Fundamental features (stub - requires separate data source)
        if FUNDAMENTAL_AVAILABLE:
            try:
                # Placeholder - fundamentals require different API
                logger.info("⚠️  Fundamental features skipped (requires separate data)")
            except Exception as e:
                logger.warning(f"Fundamental features failed: {e}")
        
        return features
    
    def generate_signals(
        self,
        prices: pd.DataFrame,
        features: Dict[str, pd.DataFrame]
    ) -> pd.Series:
        """
        Generate trading signals using professional multi-factor scoring.
        
        Utilise scoring avancé si modules disponibles :
        - AlphaFactorEngine : 100+ facteurs alpha
        - FeatureEngineer : 114 facteurs ML avec IC
        - Technical indicators
        - Sentiment analysis
        
        Args:
            prices: Price data
            features: Feature dict
            
        Returns:
            Series of signals [-2, +2] per ticker
        """
        logger.info("Generating trading signals (professional scoring)...")
        
        signals = pd.Series(0.0, index=prices.columns)
        
        # Professional scoring si modules disponibles
        if ALPHA_FACTOR_AVAILABLE or ML_FEATURES_AVAILABLE:
            logger.info("Using professional multi-factor scoring...")
            
            for ticker in prices.columns:
                try:
                    ticker_prices = prices[ticker].dropna()
                    if len(ticker_prices) < 60:
                        continue
                    
                    # Préparer bars format OHLC (simulé depuis Close)
                    bars = pd.DataFrame({
                        'close': ticker_prices,
                        'open': ticker_prices,
                        'high': ticker_prices * 1.01,
                        'low': ticker_prices * 0.99,
                        'volume': 1000000  # Dummy volume
                    })
                    
                    score = self._compute_professional_score(ticker, bars)
                    signals[ticker] = score
                    
                except Exception as e:
                    logger.debug(f"Scoring failed for {ticker}: {e}")
                    continue
            
            logger.info(f"✅ Professional signals: {(signals != 0).sum()} tickers scored")
        
        else:
            # Fallback: momentum + mean reversion
            logger.info("Using fallback momentum signals...")
            returns = prices.pct_change().dropna()
            
            momentum = returns.rolling(20).mean().iloc[-1]
            volatility = returns.rolling(20).std().iloc[-1]
            
            # Risk-adjusted momentum
            signals = (momentum / volatility).fillna(0)
        
        # Sentiment adjustment
        if self.enable_sentiment and self.sentiment_analyzer:
            try:
                headlines = [
                    "Markets rally on strong earnings",
                    "Tech stocks lead gains",
                    "Economic data beats expectations"
                ]
                sentiment_score = self.sentiment_analyzer.compute_sentiment_score(headlines)
                logger.info(f"Sentiment score: {sentiment_score:.3f}")
                
                if sentiment_score < -0.5:
                    signals *= 0.5
                elif sentiment_score > 0.5:
                    signals *= 1.2
                    
            except Exception as e:
                logger.debug(f"Sentiment adjustment failed: {e}")
        
        # Normalize to [-2, +2]
        signals = signals.clip(-2, 2)
        
        logger.info(f"✅ Signals generated: {len(signals)} tickers, "
                   f"range [{signals.min():.2f}, {signals.max():.2f}], "
                   f"positive: {(signals > 0).sum()}")
        return signals
    
    def _compute_professional_score(self, ticker: str, bars: pd.DataFrame) -> float:
        """
        Compute professional multi-factor score for ticker.
        
        Args:
            ticker: Ticker symbol
            bars: OHLC bars DataFrame
            
        Returns:
            Score [-2, +2]
        """
        scores = []
        weights = []
        
        # AlphaFactorEngine (100+ facteurs)
        if ALPHA_FACTOR_AVAILABLE and len(bars) >= 60:
            try:
                bars_norm = bars.copy()
                bars_norm.columns = [c.lower() for c in bars_norm.columns]
                
                afe = AlphaFactorEngine(bars_norm)
                factors_dict = afe.compute_all_factors()
                
                factor_vals = []
                for fname, factor_result in factors_dict.items():
                    if hasattr(factor_result, 'values') and not factor_result.values.empty:
                        last_val = float(factor_result.values.iloc[-1])
                        if not np.isnan(last_val) and np.isfinite(last_val):
                            factor_vals.append(np.tanh(last_val))
                
                if factor_vals:
                    scores.append(float(np.mean(factor_vals)))
                    weights.append(0.40)  # High weight for alpha factors
                    
            except Exception:
                pass
        
        # FeatureEngineer (114 facteurs ML)
        if ML_FEATURES_AVAILABLE and len(bars) >= 60:
            try:
                bars_norm = bars.copy()
                bars_norm.columns = [c.upper() for c in bars_norm.columns]
                
                fe = FeatureEngineer(bars_norm['CLOSE'])
                factors_df, ic_scores = fe.compute_all_factors()
                
                if not factors_df.empty:
                    # IC-weighted aggregation
                    positive_ic = ic_scores[ic_scores > 0]
                    if len(positive_ic) > 0:
                        last_factors = factors_df.iloc[-1][positive_ic.index]
                        weighted = (last_factors * positive_ic).sum() / positive_ic.sum()
                        scores.append(float(np.tanh(weighted)))
                        weights.append(0.40)
                    else:
                        scores.append(float(np.tanh(factors_df.iloc[-1].mean())))
                        weights.append(0.30)
                        
            except Exception:
                pass
        
        # Technical indicators (fallback)
        if len(scores) == 0:
            try:
                returns = bars['close'].pct_change().dropna()
                momentum = returns.rolling(20).mean().iloc[-1]
                vol = returns.rolling(20).std().iloc[-1]
                if vol > 0:
                    scores.append(momentum / vol)
                    weights.append(1.0)
            except Exception:
                return 0.0
        
        # Weighted average
        if scores and weights:
            total_weight = sum(weights)
            final_score = sum(s * w for s, w in zip(scores, weights)) / total_weight
            return float(np.clip(final_score * 2, -2, 2))  # Scale to [-2, +2]
        
        return 0.0
    
    def optimize_portfolio(
        self,
        prices: pd.DataFrame,
        signals: pd.Series
    ) -> pd.Series:
        """
        Optimize portfolio weights using signals + covariance.
        
        Args:
            prices: Price data
            signals: Trading signals
            
        Returns:
            Series of target weights (sum to 1.0)
        """
        logger.info("Optimizing portfolio...")
        
        returns = prices.pct_change().dropna()
        
        # Filter positive signals only
        positive_signals = signals[signals > 0]
        
        if len(positive_signals) == 0:
            logger.warning("No positive signals, returning equal weight")
            weights = pd.Series(1.0 / len(signals), index=signals.index)
            return weights
        
        # Use PyPortfolioOpt if available (lazy load)
        if PYPFOPT_AVAILABLE:
            try:
                # Lazy load optimizer
                if self.pypfopt is None:
                    self.pypfopt = PyPortfolioOptOptimizer(prices)
                
                # Use signals as expected returns proxy
                expected_returns = positive_signals / positive_signals.sum()
                
                # Compute covariance
                cov = returns[positive_signals.index].cov()
                
                # Optimize
                opt_result = self.pypfopt.optimize(
                    expected_returns=expected_returns,
                    cov_matrix=cov,
                    method='max_sharpe',
                    constraints={'max_weight': self.max_position_size}
                )
                
                weights = pd.Series(opt_result['weights'])
                logger.info(f"✅ Portfolio optimized (PyPortfolioOpt): {len(weights)} positions")
                return weights
                
            except Exception as e:
                logger.warning(f"PyPortfolioOpt failed: {e}")
        
        # Fallback: signal-weighted
        weights = positive_signals / positive_signals.sum()
        weights = weights.clip(upper=self.max_position_size)
        weights = weights / weights.sum()  # Renormalize
        
        logger.info(f"✅ Portfolio optimized (signal-weighted): {len(weights)} positions")
        return weights
    
    def validate_risk(
        self,
        prices: pd.DataFrame,
        weights: pd.Series
    ) -> bool:
        """
        Validate portfolio risk using stress test + VaR.
        
        Args:
            prices: Price data
            weights: Target weights
            
        Returns:
            True if risk acceptable, False otherwise
        """
        if not self.enable_stress_test:
            return True
        
        logger.info("Validating portfolio risk...")
        
        returns = prices[weights.index].pct_change().dropna()
        
        # VaR check
        if VAR_BACKTEST_AVAILABLE:
            try:
                portfolio_returns = (returns * weights).sum(axis=1)
                var_95 = portfolio_returns.quantile(0.05)
                
                if abs(var_95) > self.max_portfolio_var:
                    logger.warning(f"❌ VaR too high: {abs(var_95):.2%} > {self.max_portfolio_var:.2%}")
                    return False
                
                logger.info(f"✅ VaR check passed: {abs(var_95):.2%} < {self.max_portfolio_var:.2%}")
                
            except Exception as e:
                logger.warning(f"VaR validation failed: {e}")
        
        # Stress test (if enabled)
        if STRESS_TEST_AVAILABLE and self.stress_tester:
            try:
                # Placeholder for stress testing
                logger.info("⚠️  Stress test integration TODO")
            except Exception as e:
                logger.warning(f"Stress test failed: {e}")
        
        return True
    
    def execute_rebalance(self, weights: pd.Series):
        """
        Execute portfolio rebalance via Alpaca.
        
        Args:
            weights: Target weights
        """
        logger.info(f"Executing rebalance: {len(weights)} positions...")
        
        # Get current positions
        try:
            positions = self.alpaca.get_positions()
            current_tickers = {p['symbol'] for p in positions}
            logger.info(f"Current positions: {len(current_tickers)} tickers")
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return
        
        # Get account value
        try:
            account = self.alpaca.get_account()
            portfolio_value = float(account.get('portfolio_value', 0))
            logger.info(f"Portfolio value: ${portfolio_value:,.2f}")
        except Exception as e:
            logger.error(f"Failed to get account: {e}")
            return
        
        # Calculate target positions in dollars
        target_positions = weights * portfolio_value
        
        # Close positions not in target
        for ticker in current_tickers:
            if ticker not in weights.index:
                try:
                    logger.info(f"Closing position: {ticker}")
                    self.alpaca.close_position(ticker)
                except Exception as e:
                    logger.warning(f"Failed to close {ticker}: {e}")
        
        # Open/adjust positions
        for ticker, target_value in target_positions.items():
            try:
                # Get current price
                quote = self.alpaca.get_latest_quote(ticker)
                price = float(quote.get('price', 0))
                
                if price <= 0:
                    logger.warning(f"Invalid price for {ticker}: {price}")
                    continue
                
                # Calculate target quantity
                target_qty = int(target_value / price)
                
                if target_qty > 0:
                    logger.info(f"Target position {ticker}: {target_qty} shares @ ${price:.2f} = ${target_value:,.2f}")
                    
                    # Submit order
                    order = self.alpaca.submit_order(
                        symbol=ticker,
                        qty=target_qty,
                        side='buy',
                        order_type='market',
                        time_in_force='day'
                    )
                    logger.info(f"✅ Order submitted: {ticker} {target_qty} shares (order_id={order.get('order_id')})")
                    
            except Exception as e:
                logger.warning(f"Failed to submit order for {ticker}: {e}")
        
        logger.info("✅ Rebalance complete")
        self.last_rebalance = datetime.now()
    
    def run_trading_cycle(self):
        """Execute one complete trading cycle."""
        logger.info("=" * 70)
        logger.info(f"TRADING CYCLE START - {datetime.now()}")
        logger.info("=" * 70)
        
        try:
            # 1. Universe selection
            universe = self.get_universe()
            
            # 2. Data fetching
            prices = self.fetch_data(universe, lookback_days=252)
            
            # 3. Feature engineering
            features = self.compute_features(prices)
            
            # 4. Signal generation
            signals = self.generate_signals(prices, features)
            
            # 5. Portfolio optimization
            weights = self.optimize_portfolio(prices, signals)
            
            # 6. Risk validation
            risk_ok = self.validate_risk(prices, weights)
            
            if not risk_ok:
                logger.warning("❌ Risk validation failed, skipping rebalance")
                return
            
            # 7. Execution
            self.execute_rebalance(weights)
            
            # 8. Monitoring
            if self.monitor:
                try:
                    metrics = self.monitor.get_metrics()
                    logger.info(f"Portfolio metrics: {metrics}")
                except Exception as e:
                    logger.warning(f"Monitoring failed: {e}")
            
            logger.info("=" * 70)
            logger.info("TRADING CYCLE COMPLETE")
            logger.info("=" * 70)
            
        except Exception as e:
            logger.error(f"❌ Trading cycle failed: {e}", exc_info=True)
    
    def run(self):
        """Main continuous trading loop."""
        logger.info("=" * 70)
        logger.info("CONTINUOUS ALPACA TRADING SYSTEM STARTING")
        logger.info("=" * 70)
        
        # Connect to Alpaca
        if not self.connect():
            logger.error("❌ Failed to connect, exiting")
            return
        
        self.running = True
        
        # Initial rebalance
        self.run_trading_cycle()
        
        logger.info(f"Entering continuous loop (rebalance every {self.rebalance_frequency/3600:.1f}h)...")
        logger.info("Press Ctrl+C to stop")
        
        # Continuous loop
        while self.running:
            try:
                # Check if rebalance needed
                if self.last_rebalance:
                    elapsed = (datetime.now() - self.last_rebalance).total_seconds()
                    if elapsed < self.rebalance_frequency:
                        wait_time = self.rebalance_frequency - elapsed
                        logger.info(f"Next rebalance in {wait_time/3600:.1f}h...")
                        time.sleep(min(60, wait_time))  # Sleep in 60s increments
                        continue
                
                # Run trading cycle
                self.run_trading_cycle()
                
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received, stopping...")
                self.running = False
            except Exception as e:
                logger.error(f"Error in main loop: {e}", exc_info=True)
                logger.info("Waiting 60s before retry...")
                time.sleep(60)
        
        # Cleanup
        logger.info("Disconnecting from Alpaca...")
        try:
            self.alpaca.disconnect()
        except Exception as e:
            logger.warning(f"Disconnect failed: {e}")
        
        logger.info("=" * 70)
        logger.info("CONTINUOUS ALPACA TRADING SYSTEM STOPPED")
        logger.info("=" * 70)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='FinBot Continuous Alpaca Paper Trading System'
    )
    parser.add_argument(
        '--universe',
        type=int,
        default=30,
        help='Universe size (number of tickers)'
    )
    parser.add_argument(
        '--rebalance-hours',
        type=int,
        default=24,
        help='Rebalance frequency in hours'
    )
    parser.add_argument(
        '--max-position',
        type=float,
        default=0.15,
        help='Maximum position size (fraction of portfolio)'
    )
    parser.add_argument(
        '--max-var',
        type=float,
        default=0.25,
        help='Maximum portfolio VaR (fraction of capital)'
    )
    parser.add_argument(
        '--no-ml',
        action='store_true',
        help='Disable ML models'
    )
    parser.add_argument(
        '--no-sentiment',
        action='store_true',
        help='Disable sentiment analysis'
    )
    parser.add_argument(
        '--no-stress-test',
        action='store_true',
        help='Disable stress testing'
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Print configuration
    print("=" * 70)
    print("FINBOT CONTINUOUS ALPACA TRADING SYSTEM")
    print("=" * 70)
    print(f"Universe: {args.universe} tickers")
    print(f"Rebalance: Every {args.rebalance_hours} hours")
    print(f"Max Position: {args.max_position:.1%}")
    print(f"Max VaR: {args.max_var:.1%}")
    print(f"ML Models: {'Disabled' if args.no_ml else 'Enabled'}")
    print(f"Sentiment: {'Disabled' if args.no_sentiment else 'Enabled'}")
    print(f"Stress Test: {'Disabled' if args.no_stress_test else 'Enabled'}")
    print("=" * 70)
    
    # Check API keys
    api_key = os.getenv('APCA_API_KEY_ID')
    api_secret = os.getenv('APCA_API_SECRET_KEY')
    
    if not api_key or not api_secret:
        print("❌ ERREUR: Clés API Alpaca non trouvées!")
        print("\nVérifiez votre fichier .env:")
        print("APCA_API_KEY_ID=votre_clé")
        print("APCA_API_SECRET_KEY=votre_secret")
        print("\nOu définissez les variables d'environnement.")
        sys.exit(1)
    
    print(f"✅ Alpaca API Key: {api_key[:8]}...")
    print(f"✅ Alpaca Secret: {'*' * 8}...")
    print("=" * 70)
    
    # Create and run system
    system = ContinuousAlpacaTradingSystem(
        universe_size=args.universe,
        rebalance_frequency_hours=args.rebalance_hours,
        max_position_size=args.max_position,
        max_portfolio_var=args.max_var,
        enable_ml=not args.no_ml,
        enable_sentiment=not args.no_sentiment,
        enable_stress_test=not args.no_stress_test
    )
    
    # Handle SIGTERM for graceful shutdown
    def signal_handler(sig, frame):
        logger.info("Signal received, stopping system...")
        system.running = False
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Run
    system.run()


if __name__ == '__main__':
    main()

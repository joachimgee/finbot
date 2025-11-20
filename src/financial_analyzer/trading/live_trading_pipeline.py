"""
Live Trading Pipeline - Execute trading strategy in real-time.

Features:
- Schedule execution (market open, daily, weekly, monthly)
- Data fetching (prices, fundamentals, news, sentiment)
- Signal generation (ML models, technical indicators, sentiment)
- Portfolio optimization (Riskfolio-Lib, PyPortfolioOpt)
- Order generation from target weights
- Risk validation (RiskGuard with circuit breakers)
- Order execution (via BrokerAdapter)
- Performance tracking (AccountMonitor)
- Logging & metrics (Prometheus compatible)

Integrates:
- Phase 6.1: BrokerAdapter (Alpaca, IB)
- Phase 6.2: AccountMonitor, RiskGuard
- Phase 5: ML models, portfolio optimization, backtesting

Architecture:
    LiveTradingPipeline
         ├─ BrokerAdapter (fetch data, submit orders)
         ├─ AccountMonitor (track portfolio state)
         ├─ RiskGuard (validate orders)
         └─ SignalGenerator (ML models, indicators)
"""

from __future__ import annotations
from typing import Dict, List, Optional, Literal, Callable
from datetime import datetime, time as dt_time, timedelta
from dataclasses import dataclass
import pandas as pd
import numpy as np
import logging
from collections import defaultdict
import time

logger = logging.getLogger(__name__)

from .broker_adapter import BrokerAdapter
from .account_monitor import AccountMonitor
from .risk_guard import RiskGuard, CircuitBreakerTriggered

try:
    from financial_analyzer.portfolio_optimization.pyportfolioopt_optimizer import PyPortfolioOptOptimizer
except Exception:
    PyPortfolioOptOptimizer = None

try:
    from financial_analyzer.portfolio_optimization.riskfolio_optimizer import RiskfolioOptimizer
except Exception:
    RiskfolioOptimizer = None

try:
    from financial_analyzer.data.market_data import MarketDataFetcher
except Exception:
    MarketDataFetcher = None

try:
    from financial_analyzer.features.technical import TechnicalFeatureEngine
except Exception:
    TechnicalFeatureEngine = None

try:
    from financial_analyzer.sentiment.finbert_engine import FinBERTEngine
except Exception:
    FinBERTEngine = None

try:
    from financial_analyzer.data.news_scraper import FinancialNewsScraper
except Exception:
    FinancialNewsScraper = None

try:
    from financial_analyzer.deep_learning.lstm_predictor import LSTMPredictor
except Exception:
    LSTMPredictor = None

try:
    from financial_analyzer.analysis.ml_predictor import MLPredictor
except Exception:
    MLPredictor = None


@dataclass
class TradingSchedule:
    """
    Trading schedule configuration.
    
    Attributes:
        execution_time: Time to execute (HH:MM format, ET timezone)
        frequency: Execution frequency ('daily', 'weekly', 'monthly')
        day_of_week: Day of week (0=Monday, 4=Friday) for weekly
        day_of_month: Day of month (1-31) for monthly
        enabled: Schedule enabled
    
    Example:
        >>> # Execute daily at 9:35 AM ET
        >>> schedule = TradingSchedule(
        ...     execution_time="09:35",
        ...     frequency='daily',
        ...     enabled=True
        ... )
        >>> 
        >>> # Execute weekly on Mondays at 10:00 AM
        >>> schedule = TradingSchedule(
        ...     execution_time="10:00",
        ...     frequency='weekly',
        ...     day_of_week=0
        ... )
    """
    execution_time: str = "09:35"  # 5 min after market open
    frequency: Literal['daily', 'weekly', 'monthly'] = 'daily'
    day_of_week: int = 0  # Monday for weekly
    day_of_month: int = 1  # 1st for monthly
    enabled: bool = True
    
    def should_execute_today(self, now: datetime) -> bool:
        """
        Check if should execute today.
        
        Args:
            now: Current datetime
        
        Returns:
            True if should execute today based on frequency
        
        Example:
            >>> schedule = TradingSchedule(frequency='weekly', day_of_week=0)
            >>> now = datetime(2025, 11, 10)  # Monday
            >>> schedule.should_execute_today(now)
            True
        """
        if not self.enabled:
            return False
        
        if self.frequency == 'daily':
            return True
        elif self.frequency == 'weekly':
            return now.weekday() == self.day_of_week
        elif self.frequency == 'monthly':
            return now.day == self.day_of_month
        
        return False
    
    def get_execution_time(self) -> dt_time:
        """
        Get execution time as time object.
        
        Returns:
            time object for execution time
        
        Example:
            >>> schedule = TradingSchedule(execution_time="09:35")
            >>> t = schedule.get_execution_time()
            >>> print(t)  # 09:35:00
        """
        hour, minute = map(int, self.execution_time.split(':'))
        return dt_time(hour=hour, minute=minute)


class LiveTradingPipeline:
    """
    Live trading pipeline for executing strategies in real-time.
    
    Integrates signal generation, portfolio optimization, risk management,
    and order execution into a single automated pipeline.
    
    Attributes:
        broker: BrokerAdapter instance for market data and order execution
        tickers: List of ticker symbols to trade
        strategy: Strategy name being used
        monitor: AccountMonitor for portfolio tracking
        risk_guard: RiskGuard for pre-trade validation
        schedule: TradingSchedule for automated execution
        is_running: Whether pipeline is currently running
        last_execution: Timestamp of last execution
        execution_history: List of execution results
    
    Example:
        >>> from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
        >>> 
        >>> # Setup
        >>> adapter = AlpacaAdapter(api_key='...', api_secret='...', paper=True)
        >>> 
        >>> # Initialize pipeline
        >>> pipeline = LiveTradingPipeline(
        ...     broker_adapter=adapter,
        ...     tickers=['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA'],
        ...     initial_capital=100000.0,
        ...     strategy='factor_ensemble'
        ... )
        >>> 
        >>> # Run (manual)
        >>> result = pipeline.run(force=True)
        >>> print(f"Status: {result['status']}")
        >>> print(f"Orders executed: {result['orders_executed']}")
    """
    
    def __init__(
        self,
        broker_adapter: BrokerAdapter,
        tickers: List[str],
        initial_capital: float = 100000.0,
        strategy: str = 'factor_ensemble',
        risk_config: Optional[Dict] = None,
        schedule_config: Optional[TradingSchedule] = None,
        enable_logging: bool = True
    ) -> None:
        """
        Initialize live trading pipeline.
        
        Args:
            broker_adapter: Connected BrokerAdapter instance
            tickers: List of ticker symbols to trade
            initial_capital: Initial capital for tracking
            strategy: Strategy name ('factor_ensemble', 'sentiment_momentum', 'ml_fusion')
            risk_config: Risk limits config (default: conservative)
            schedule_config: Execution schedule config
            enable_logging: Enable detailed logging
        
        Raises:
            ValueError: If broker_adapter not connected or tickers empty
        
        Example:
            >>> adapter = AlpacaAdapter(api_key='...', api_secret='...', paper=True)
            >>> pipeline = LiveTradingPipeline(
            ...     broker_adapter=adapter,
            ...     tickers=['AAPL', 'MSFT'],
            ...     initial_capital=50000.0
            ... )
        """
        if not broker_adapter.connected:
            raise ValueError("BrokerAdapter must be connected. Call connect() first.")
        
        if not tickers:
            raise ValueError("Tickers list cannot be empty")
        
        self.broker = broker_adapter
        self.tickers = tickers
        self.strategy = strategy
        
        # Initialize AccountMonitor
        self.monitor = AccountMonitor(
            broker_adapter=broker_adapter,
            initial_capital=initial_capital,
            track_history=True
        )
        
        # Initialize RiskGuard with config
        risk_config = risk_config or self._default_risk_config()
        self.risk_guard = RiskGuard(
            account_monitor=self.monitor,
            **risk_config
        )
        
        # Schedule
        self.schedule = schedule_config or TradingSchedule()
        
        # State
        self.is_running = False
        self.last_execution: Optional[datetime] = None
        self.execution_history: List[Dict] = []
        
        # Logging
        self.enable_logging = enable_logging
        
        logger.info(
            f"LiveTradingPipeline initialized: "
            f"tickers={len(tickers)}, strategy={strategy}, "
            f"mode={broker_adapter.mode if hasattr(broker_adapter, 'mode') else 'unknown'}"
        )
    
    @staticmethod
    def _default_risk_config() -> Dict:
        """
        Get default risk configuration (conservative).
        
        Returns:
            Dict with conservative risk limits
        
        Example:
            >>> config = LiveTradingPipeline._default_risk_config()
            >>> print(config['max_position_pct'])
            0.25
        """
        return {
            'max_position_size': 50000.0,
            'max_position_pct': 0.25,
            'max_total_positions': 20,
            'max_drawdown': -0.15,
            'max_daily_loss': 5000.0,
            'max_leverage': 2.0,
            'enable_circuit_breaker': True
        }
    
    def run(self, force: bool = False) -> Dict:
        """
        Execute trading pipeline (single run).
        
        Steps:
        1. Check if market is open
        2. Check schedule (unless force=True)
        3. Update account monitor
        4. Fetch latest data
        5. Generate signals
        6. Optimize portfolio (target weights)
        7. Generate orders
        8. Validate orders (risk checks)
        9. Execute orders
        10. Update monitor
        11. Log results
        
        Args:
            force: Force execution even if schedule says no
        
        Returns:
            Dict with execution results:
            - status: 'success', 'skipped', 'failed'
            - reason: Reason if skipped/failed
            - orders_generated: Number of orders generated
            - orders_executed: Number of orders executed
            - orders_rejected: Number of orders rejected (risk)
            - portfolio_value: Current portfolio value
            - daily_pnl: Daily P&L
            - execution_time: Execution timestamp
        
        Example:
            >>> pipeline = LiveTradingPipeline(broker, ['AAPL', 'MSFT'])
            >>> result = pipeline.run(force=True)
            >>> if result['status'] == 'success':
            ...     print(f"Executed {result['orders_executed']} orders")
        """
        now = datetime.now()
        
        try:
            # 1. Check market open (unless forced)
            if not force and not self.broker.is_market_open():
                logger.warning("Market is closed")
                return self._result('skipped', 'market_closed')
            
            # 2. Check schedule
            if not force and not self.schedule.should_execute_today(now):
                logger.info(f"Not scheduled for today ({self.schedule.frequency})")
                return self._result('skipped', 'not_scheduled')
            
            # 3. Update monitor
            logger.info("Updating account monitor...")
            self.monitor.update()
            
            # Log current state
            logger.info(
                f"Portfolio: ${self.monitor.portfolio_value:.2f}, "
                f"Daily P&L: ${self.monitor.daily_pnl:+.2f}, "
                f"Positions: {len(self.monitor.positions)}"
            )
            
            # 4. Fetch data
            logger.info(f"Fetching data for {len(self.tickers)} tickers...")
            data = self._fetch_data()
            
            # 5. Generate signals
            logger.info(f"Generating signals (strategy={self.strategy})...")
            signals = self._generate_signals(data)
            
            # 6. Optimize portfolio
            logger.info("Optimizing portfolio...")
            target_weights = self._optimize_portfolio(signals, data)
            
            # 7. Generate orders
            logger.info("Generating orders...")
            orders = self._generate_orders(target_weights, data)
            
            logger.info(f"Generated {len(orders)} orders")
            
            # 8. Validate & Execute orders
            execution_results = self._execute_orders_with_risk_checks(orders)
            
            # 9. Update monitor after execution
            self.monitor.update()
            
            # 10. Log results
            result = self._result(
                status='success',
                orders_generated=len(orders),
                orders_executed=sum(1 for r in execution_results if r['status'] == 'executed'),
                orders_rejected=sum(1 for r in execution_results if r['status'] == 'rejected'),
                execution_results=execution_results
            )
            
            # Save to history
            self.last_execution = now
            self.execution_history.append(result)
            
            logger.info(
                f"Execution complete: "
                f"{result['orders_executed']}/{result['orders_generated']} executed, "
                f"{result['orders_rejected']} rejected"
            )
            
            return result
        
        except CircuitBreakerTriggered as e:
            logger.critical(f"Circuit breaker triggered: {e}")
            return self._result('failed', f'circuit_breaker: {e}')
        
        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)
            return self._result('failed', str(e))
    
    def _fetch_data(self) -> Dict:
        """
        Fetch latest market data for all tickers.
        
        Returns:
            Dict with keys:
            - prices: Dict[symbol, DataFrame] - Historical prices
            - fundamentals: Dict[symbol, Dict] - Fundamental metrics
            - news: Dict[symbol, List] - Recent news (optional)
            - sentiment: Dict[symbol, float] - Sentiment scores (optional)
        
        Example:
            >>> data = pipeline._fetch_data()
            >>> print(data['prices']['AAPL'].tail())
        """
        data = {
            'prices': {},
            'fundamentals': {},
            'news': {},
            'sentiment': {}
        }
        
        # Fetch prices (last 60 days for indicators)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=60)
        
        # Prefer batched fetching when available (reduces API calls, better for 1000+ tickers)
        if hasattr(self.broker, 'get_bars_multi'):
            try:
                multi = getattr(self.broker, 'get_bars_multi')(
                    self.tickers, start_date, end_date, timeframe='1D'
                )
                if isinstance(multi, dict):
                    for ticker, df in multi.items():
                        if df is not None and not df.empty:
                            data['prices'][ticker] = df
                    logger.info(f"Fetched data (batched) for {len(data['prices'])}/{len(self.tickers)} tickers")
                else:
                    logger.warning("get_bars_multi returned non-dict; falling back to single requests")
                    raise RuntimeError("invalid_multi_return")
            except Exception as e:
                logger.warning(f"Batched fetch failed ({e}); falling back to single requests")
                # Fallback per-symbol
                for ticker in self.tickers:
                    try:
                        df = self.broker.get_bars(
                            symbol=ticker,
                            start=start_date,
                            end=end_date,
                            timeframe='1D'
                        )
                        if not df.empty:
                            data['prices'][ticker] = df
                            logger.debug(f"Fetched {len(df)} bars for {ticker}")
                        else:
                            logger.warning(f"No price data for {ticker}")
                    except Exception as ie:
                        logger.error(f"Failed to fetch data for {ticker}: {ie}")
        else:
            for ticker in self.tickers:
                try:
                    # Get historical bars
                    df = self.broker.get_bars(
                        symbol=ticker,
                        start=start_date,
                        end=end_date,
                        timeframe='1D'
                    )
                    
                    if not df.empty:
                        data['prices'][ticker] = df
                        logger.debug(f"Fetched {len(df)} bars for {ticker}")
                    else:
                        logger.warning(f"No price data for {ticker}")
                
                except Exception as e:
                    logger.error(f"Failed to fetch data for {ticker}: {e}")
        
        # Log summary
        fetched = len(data['prices'])
        logger.info(f"Fetched data for {fetched}/{len(self.tickers)} tickers")
        
        # Fetch fundamentals if MarketDataFetcher available
        if MarketDataFetcher is not None:
            try:
                mdf = MarketDataFetcher(api_key=None)  # yfinance fallback
                for ticker in list(data['prices'].keys())[:10]:  # limit to avoid timeout
                    try:
                        statements = mdf.get_financial_statements(ticker)
                        data['fundamentals'][ticker] = statements
                    except Exception:
                        pass
                logger.debug(f"Fetched fundamentals for {len(data['fundamentals'])} tickers")
            except Exception as e:
                logger.debug(f"Fundamentals fetch skipped: {e}")
        
        # Fetch news if FinancialNewsScraper available
        if FinancialNewsScraper is not None:
            try:
                scraper = FinancialNewsScraper()
                for ticker in list(data['prices'].keys())[:20]:  # limit for performance
                    try:
                        news_items = scraper.get_news(ticker, limit=5)
                        if news_items:
                            data['news'][ticker] = news_items
                    except Exception:
                        pass
                logger.debug(f"Fetched news for {len(data['news'])} tickers")
            except Exception as e:
                logger.debug(f"News fetch skipped: {e}")
        
        # Sentiment analysis via FinBERT if available
        if FinBERTEngine is not None and data['news']:
            try:
                analyzer = FinBERTEngine()
                for ticker, news_list in data['news'].items():
                    try:
                        texts = [item.get('title', '') + ' ' + item.get('description', '') for item in news_list[:3]]
                        texts = [t for t in texts if t.strip()]
                        if texts:
                            scores = [analyzer.analyze_text(t) for t in texts]
                            avg_score = float(np.mean(scores)) if scores else 0.0
                            data['sentiment'][ticker] = avg_score
                        else:
                            data['sentiment'][ticker] = 0.0
                    except Exception:
                        data['sentiment'][ticker] = 0.0
                logger.debug(f"Analyzed sentiment for {len(data['sentiment'])} tickers")
            except Exception as e:
                logger.debug(f"Sentiment analysis skipped: {e}")
                # Fallback neutral
                for ticker in data['prices']:
                    data['sentiment'][ticker] = 0.0
        else:
            # Fallback neutral if no sentiment analyzer
            for ticker in data['prices']:
                data['sentiment'][ticker] = 0.0
        
        return data
    
    def _generate_signals(self, data: Dict) -> Dict[str, float]:
        """
        Generate trading signals for each ticker.
        
        Combines multiple signal sources:
        - Technical indicators (RSI, MACD, Bollinger, etc.)
        - ML models (LSTM predictions if available)
        - Sentiment analysis (FinBERT scores)
        - Momentum (20D fallback)
        
        Args:
            data: Market data dict from _fetch_data()
        
        Returns:
            Dict mapping symbol to signal (-1 to +1)
            +1 = strong buy, 0 = neutral, -1 = strong sell
        
        Example:
            >>> signals = pipeline._generate_signals(data)
            >>> print(signals)  # {'AAPL': 0.65, 'MSFT': -0.23, ...}
        """
        signals = {}
        
        for ticker in self.tickers:
            if ticker not in data['prices']:
                signals[ticker] = 0.0
                continue
            
            df = data['prices'][ticker]
            
            if len(df) < 20:
                signals[ticker] = 0.0
                continue
            
            # Component signals
            tech_signal = 0.0
            ml_signal = 0.0
            sentiment_signal = 0.0
            momentum_signal = 0.0
            
            # 1. Technical Indicators
            if TechnicalFeatureEngine is not None:
                try:
                    engine = TechnicalFeatureEngine()
                    features = engine.generate_features(df)
                    if not features.empty and len(features) > 0:
                        # RSI signal
                        if 'rsi_14' in features.columns:
                            rsi = float(features['rsi_14'].iloc[-1])
                            if rsi < 30:
                                tech_signal += 0.5  # oversold
                            elif rsi > 70:
                                tech_signal -= 0.5  # overbought
                        # MACD signal
                        if 'macd' in features.columns and 'macd_signal' in features.columns:
                            macd = float(features['macd'].iloc[-1])
                            macd_sig = float(features['macd_signal'].iloc[-1])
                            if macd > macd_sig:
                                tech_signal += 0.3
                            else:
                                tech_signal -= 0.3
                        tech_signal = np.clip(tech_signal, -1, 1)
                except Exception as e:
                    logger.debug(f"Technical signal failed for {ticker}: {e}")
            
            # 2. ML Prediction (LSTM if available)
            if LSTMPredictor is not None:
                try:
                    # Try to load pre-trained model
                    predictor = LSTMPredictor(input_size=5, hidden_size=64, num_layers=2)
                    # Placeholder: would need to load weights and predict
                    # For now, skip if model not trained
                    pass
                except Exception:
                    pass
            
            # 3. Sentiment
            if ticker in data['sentiment']:
                sentiment_signal = float(data['sentiment'][ticker])
                sentiment_signal = np.clip(sentiment_signal, -1, 1)
            
            # 4. Momentum (always computed as fallback)
            try:
                returns_20d = (df['close'].iloc[-1] / df['close'].iloc[-20] - 1)
                momentum_signal = float(np.tanh(returns_20d * 10))
            except Exception:
                momentum_signal = 0.0
            
            # Combine signals (weighted average)
            weights = {
                'technical': 0.3,
                'ml': 0.2,
                'sentiment': 0.2,
                'momentum': 0.3
            }
            
            combined = (
                tech_signal * weights['technical'] +
                ml_signal * weights['ml'] +
                sentiment_signal * weights['sentiment'] +
                momentum_signal * weights['momentum']
            )
            
            signals[ticker] = float(np.clip(combined, -1, 1))
        
        logger.info(f"Generated signals for {len(signals)} tickers (Technical: {TechnicalFeatureEngine is not None}, Sentiment: {FinBERTEngine is not None})")
        return signals
    
    def _optimize_portfolio(self, signals: Dict[str, float], data: Dict) -> Dict[str, float]:
        """
        Optimize portfolio weights based on signals.
        
        Uses PyPortfolioOpt (Max Sharpe) or Riskfolio-Lib (Mean-CVaR) if available,
        otherwise falls back to signal-proportional allocation.
        
        Args:
            signals: Trading signals for each ticker
            data: Market data
        
        Returns:
            Dict[str, float]: mapping symbol to target weight (0-1, sum=1)
        
        Example:
            >>> signals = {'AAPL': 0.8, 'MSFT': 0.6, 'GOOGL': -0.2}
            >>> weights = pipeline._optimize_portfolio(signals, data)
            >>> print(weights) # {'AAPL': 0.57, 'MSFT': 0.43}
        """
        # Filter positive signals only (long-only for now)
        positive_signals = {k: v for k, v in signals.items() if v > 0}
        
        if not positive_signals:
            logger.warning("No positive signals, no positions")
            return {}
        
        # Build prices DataFrame for optimization
        price_frames = []
        for sym in positive_signals:
            if sym in data['prices'] and not data['prices'][sym].empty:
                close = data['prices'][sym]['close'].rename(sym)
                price_frames.append(close)
        
        if not price_frames:
            logger.warning("No price data for optimization; fallback to proportional")
            total_signal = sum(positive_signals.values())
            return {symbol: signal / total_signal for symbol, signal in positive_signals.items()}
        
        prices_df = pd.concat(price_frames, axis=1).dropna()
        if prices_df.empty or len(prices_df) < 20:
            logger.warning("Insufficient price data; fallback to proportional")
            total_signal = sum(positive_signals.values())
            return {symbol: signal / total_signal for symbol, signal in positive_signals.items()}
        
        # Try PyPortfolioOpt first (Max Sharpe)
        if PyPortfolioOptOptimizer is not None:
            try:
                opt = PyPortfolioOptOptimizer(prices_df)
                weights_series = opt.optimize_max_sharpe()
                weights_dict = weights_series.to_dict()
                # Normalize and clip
                total = sum(weights_dict.values())
                if total > 0:
                    weights_dict = {k: max(0, v / total) for k, v in weights_dict.items()}
                    logger.info("Optimized with PyPortfolioOpt (Max Sharpe)")
                    return weights_dict
            except Exception as e:
                logger.warning(f"PyPortfolioOpt failed: {e}; trying Riskfolio")
        
        # Fallback: Riskfolio (Mean-CVaR)
        if RiskfolioOptimizer is not None:
            try:
                returns = prices_df.pct_change().dropna()
                if len(returns) < 10:
                    raise ValueError("Not enough returns")
                opt = RiskfolioOptimizer(returns, covariance_method='ledoit_wolf')
                weights_series = opt.optimize_mean_cvar(risk_aversion=1.0, cvar_alpha=0.05)
                weights_dict = weights_series.to_dict()
                total = sum(weights_dict.values())
                if total > 0:
                    weights_dict = {k: max(0, v / total) for k, v in weights_dict.items()}
                    logger.info("Optimized with Riskfolio (Mean-CVaR)")
                    return weights_dict
            except Exception as e:
                logger.warning(f"Riskfolio failed: {e}; fallback to proportional")
        
        # Final fallback: proportional to signals
        total_signal = sum(positive_signals.values())
        target_weights = {symbol: signal / total_signal for symbol, signal in positive_signals.items()}
        logger.info("Using signal-proportional allocation (fallback)")
        return target_weights
    
    def _generate_orders(self, target_weights: Dict[str, float], data: Dict) -> List[Dict]:
        """
        Generate orders to reach target weights.
        
        Args:
            target_weights: Target weights for each ticker
            data: Market data (for current prices)
        
        Returns:
            List of order dicts:
            - symbol: Ticker symbol
            - qty: Quantity to buy/sell
            - side: 'buy' or 'sell'
            - price: Current market price
            - order_type: 'market'
        
        Example:
            >>> weights = {'AAPL': 0.6, 'MSFT': 0.4}
            >>> orders = pipeline._generate_orders(weights, data)
            >>> print(orders[0])
            {'symbol': 'AAPL', 'qty': 40, 'side': 'buy', 'price': 150.0, ...}
        """
        orders = []
        
        portfolio_value = self.monitor.portfolio_value
        current_positions = {p['symbol']: p for p in self.monitor.positions}
        
        # Target positions
        for symbol, target_weight in target_weights.items():
            target_value = portfolio_value * target_weight
            
            # Current position
            current_pos = current_positions.get(symbol)
            current_value = current_pos['market_value'] if current_pos else 0.0
            
            # Delta
            delta_value = target_value - current_value
            
            # Skip small changes (< 1% of portfolio)
            if abs(delta_value) < portfolio_value * 0.01:
                continue
            
            # Get current price
            if symbol not in data['prices'] or data['prices'][symbol].empty:
                logger.warning(f"No price data for {symbol}, skipping")
                continue
            
            price = float(data['prices'][symbol]['close'].iloc[-1])
            
            # Calculate quantity
            qty = int(abs(delta_value) / price)
            
            if qty == 0:
                continue
            
            side = 'buy' if delta_value > 0 else 'sell'
            
            orders.append({
                'symbol': symbol,
                'qty': qty,
                'side': side,
                'price': price,
                'order_type': 'market'
            })
        
        # Close positions not in target weights
        for symbol, pos in current_positions.items():
            if symbol not in target_weights and pos['qty'] > 0:
                price = pos['current_price']
                
                orders.append({
                    'symbol': symbol,
                    'qty': pos['qty'],
                    'side': 'sell',
                    'price': price,
                    'order_type': 'market'
                })
        
        return orders
    
    def _execute_orders_with_risk_checks(self, orders: List[Dict]) -> List[Dict]:
        """
        Execute orders with risk validation.
        
        Args:
            orders: List of order dicts
        
        Returns:
            List of execution results:
            - status: 'executed', 'rejected', 'failed'
            - order: Original order
            - result: Broker result (if executed)
            - reason: Rejection/failure reason
        
        Example:
            >>> orders = [{'symbol': 'AAPL', 'qty': 10, 'side': 'buy', 'price': 150.0}]
            >>> results = pipeline._execute_orders_with_risk_checks(orders)
            >>> print(results[0]['status'])  # 'executed' or 'rejected'
        """
        results = []
        
        for order in orders:
            try:
                # Risk check
                self.risk_guard.validate_order(
                    symbol=order['symbol'],
                    qty=order['qty'],
                    side=order['side'],
                    price=order['price']
                )
                
                # Submit to broker
                broker_result = self.broker.submit_order(
                    symbol=order['symbol'],
                    qty=order['qty'],
                    side=order['side'],
                    order_type=order.get('order_type', 'market')
                )
                
                results.append({
                    'status': 'executed',
                    'order': order,
                    'result': broker_result
                })
                
                logger.info(
                    f"Order executed: {order['side']} {order['qty']} {order['symbol']} "
                    f"@ ${order['price']:.2f} (order_id={broker_result.get('order_id', 'N/A')})")
            
            except Exception as e:
                results.append({
                    'status': 'rejected',
                    'order': order,
                    'reason': str(e)
                })
                
                logger.warning(f"Order rejected: {order} - {e}")
        
        return results
    
    def _result(self, status: str, reason: str = '', **kwargs) -> Dict:
        """
        Build result dict.
        
        Args:
            status: Result status ('success', 'skipped', 'failed')
            reason: Reason for skipped/failed
            **kwargs: Additional key-value pairs to include
        
        Returns:
            Dict with execution result details
        """
        result = {
            'status': status,
            'reason': reason,
            'timestamp': datetime.now(),
            'portfolio_value': self.monitor.portfolio_value,
            'daily_pnl': self.monitor.daily_pnl,
            'num_positions': len(self.monitor.positions),
            'circuit_breaker_active': self.risk_guard.circuit_breaker_active
        }
        result.update(kwargs)
        return result
    
    def get_status(self) -> Dict:
        """
        Get current pipeline status.
        
        Returns:
            Dict with pipeline status, schedule, portfolio, and risk summary
        
        Example:
            >>> status = pipeline.get_status()
            >>> print(f"Last execution: {status['last_execution']}")
            >>> print(f"Portfolio value: ${status['portfolio']['portfolio_value']:.2f}")
            >>> print(f"Circuit breaker: {status['circuit_breaker_active']}")
        """
        return {
            'is_running': self.is_running,
            'last_execution': self.last_execution,
            'num_executions': len(self.execution_history),
            'schedule': {
                'enabled': self.schedule.enabled,
                'frequency': self.schedule.frequency,
                'execution_time': self.schedule.execution_time
            },
            'portfolio': self.monitor.get_summary(),
            'risk': self.risk_guard.get_risk_summary(),
            'circuit_breaker_active': self.risk_guard.circuit_breaker_active
        }
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        mode = self.broker.mode if hasattr(self.broker, 'mode') else 'unknown'
        return (
            f"LiveTradingPipeline("
            f"tickers={len(self.tickers)}, "
            f"strategy='{self.strategy}', "
            f"mode='{mode}')"
        )


# ==================== TESTING HELPERS ====================

def create_demo_pipeline(mode: str = 'paper') -> LiveTradingPipeline:
    """
    Create demo pipeline for testing.
    
    Args:
        mode: 'paper' or 'live'
    
    Returns:
        LiveTradingPipeline instance
        Note: Broker may not be connected if credentials invalid (demo mode)
    
    Raises:
        ValueError: If invalid mode
    
    Example:
        >>> pipeline = create_demo_pipeline(mode='paper')
        >>> # Broker auto-connects if ALPACA_API_KEY env var set
        >>> if pipeline.broker.connected:
        ...     result = pipeline.run(force=True)
        >>> else:
        ...     print("Broker not connected (demo mode - provide credentials)")
    
    Notes:
        - If ALPACA_API_KEY and ALPACA_SECRET_KEY are set, broker connects automatically
        - If not set, creates unconnected adapter (demo mode)
        - Always use paper=True for testing, never live mode
    """
    from .alpaca_adapter import AlpacaAdapter
    import os
    
    api_key = os.environ.get('APCA_API_KEY_ID') or os.environ.get('ALPACA_API_KEY', 'DEMO_KEY')
    secret_key = os.environ.get('APCA_API_SECRET_KEY') or os.environ.get('ALPACA_API_SECRET') or os.environ.get('ALPACA_SECRET_KEY', 'DEMO_SECRET')

    adapter = AlpacaAdapter(api_key=api_key, secret_key=secret_key, mode=('paper' if mode == 'paper' else 'live'))
    
    # Try to connect if real credentials, otherwise enable demo-connected mode
    if api_key != 'DEMO_KEY':
        try:
            logger.info("Attempting to connect to broker...")
            adapter.connect()
        except Exception as e:
            logger.warning(f"Could not connect broker: {e}")
    else:
        # Demo mode: mark as connected to allow pipeline construction in tests
        try:
            adapter.connected = True
            logger.info("Demo mode: broker marked as connected (no real API calls).")
        except Exception:
            pass
    
    pipeline = LiveTradingPipeline(
        broker_adapter=adapter,
        tickers=['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA'],
        initial_capital=100000.0,
        strategy='factor_ensemble'
    )
    
    return pipeline

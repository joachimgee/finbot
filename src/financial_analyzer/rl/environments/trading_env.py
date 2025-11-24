"""
Trading Environment for Reinforcement Learning.

OpenAI Gym environment for stock trading using FinBot's existing modules
(MarketDataFetcher, TechnicalFeatureEngine, FinBERTEngine, RiskMetrics).

Architecture:
    State Space (Box):
        - Cash balance (1)
        - Holdings per asset (N)
        - Current prices (N)
        - Technical indicators (N × M features)
        - Sentiment scores (N)
        - Portfolio risk metrics (K metrics)
        
    Action Space (Box):
        - Continuous [-1, 1] per asset
        - -1 = sell all position
        - 0 = hold current position
        - +1 = buy maximum allowed
        
    Reward:
        - Sharpe ratio improvement
        - Risk-adjusted returns (Sortino, Calmar)
        - Profit factor consideration

Integration:
    - financial_analyzer.data.market_data.MarketDataFetcher
    - financial_analyzer.features.technical.TechnicalFeatureEngine
    - financial_analyzer.sentiment.finbert_engine.FinBERTEngine
    - financial_analyzer.risk.risk_metrics

References:
    - FinRL (Yang et al. 2020): DRL for automated trading
    - Stable-Baselines3: gym.Env standard
    - FinBot Portfolio Learning: Kelly Criterion, Risk Budgeting

Example:
    >>> from financial_analyzer.rl.environments import TradingEnvironment
    >>> env = TradingEnvironment(
    ...     symbols=['AAPL', 'MSFT', 'GOOGL'],
    ...     start_date='2020-01-01',
    ...     end_date='2023-12-31',
    ...     initial_capital=100_000
    ... )
    >>> state = env.reset()
    >>> action = env.action_space.sample()
    >>> next_state, reward, done, info = env.step(action)
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any

import gymnasium as gym
import numpy as np
import pandas as pd
from gymnasium import spaces

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

# Lazy imports pour éviter circular dependencies
MarketDataFetcher = None
TechnicalFeatureEngine = None
FinBERTEngine = None


def _lazy_imports():
    """Lazy import modules to avoid circular dependencies."""
    global MarketDataFetcher, TechnicalFeatureEngine, FinBERTEngine
    
    if MarketDataFetcher is None:
        try:
            from financial_analyzer.data.market_data import MarketDataFetcher as MDF
            MarketDataFetcher = MDF
        except ImportError:
            logger.warning("MarketDataFetcher not available")
    
    if TechnicalFeatureEngine is None:
        try:
            from financial_analyzer.features.technical import TechnicalFeatureEngine as TFE
            TechnicalFeatureEngine = TFE
        except ImportError:
            logger.warning("TechnicalFeatureEngine not available")
    
    if FinBERTEngine is None:
        try:
            from financial_analyzer.sentiment.finbert_engine import FinBERTEngine as FBE
            FinBERTEngine = FBE
        except ImportError:
            logger.warning("FinBERTEngine not available")


class TradingEnvironment(gym.Env):
    """
    Reinforcement Learning environment for stock trading.
    
    Compatible with OpenAI Gym / Gymnasium API for use with
    Stable-Baselines3 (DQN, PPO, DDPG, A2C, SAC, TD3).
    
    Attributes:
        action_space: Continuous Box [-1, 1] per asset
        observation_space: Box with [cash, holdings, prices, indicators, sentiment, risk]
        metadata: Dict with render modes
    
    Methods:
        reset: Initialize environment to starting state
        step: Execute action and return (observation, reward, terminated, truncated, info)
        render: Optional visualization of environment state
        close: Cleanup resources
    """
    
    metadata = {"render_modes": ["human", "rgb_array"], "render_fps": 4}
    
    def __init__(
        self,
        symbols: List[str],
        start_date: str,
        end_date: str,
        initial_capital: float = 100_000.0,
        commission: float = 0.002,
        lookback_window: int = 20,
        use_technical_indicators: bool = True,
        use_sentiment: bool = False,
        use_risk_metrics: bool = True,
        max_position_size: float = 0.3,
        cash_penalty_proportion: float = 0.05,
        render_mode: Optional[str] = None,
        random_start: bool = True,
    ):
        """
        Initialize Trading Environment.
        
        Args:
            symbols: List of stock ticker symbols
            start_date: Start date for historical data (YYYY-MM-DD)
            end_date: End date for historical data (YYYY-MM-DD)
            initial_capital: Starting cash amount
            commission: Transaction cost (0.002 = 0.2%)
            lookback_window: Number of historical days for state
            use_technical_indicators: Include technical features in state
            use_sentiment: Include FinBERT sentiment in state
            use_risk_metrics: Include portfolio risk metrics in state
            max_position_size: Maximum position size per asset (0.3 = 30%)
            cash_penalty_proportion: Penalty for low cash reserves
            render_mode: Visualization mode ("human" or "rgb_array")
            random_start: Start at random position in data (for training diversity)
        """
        super().__init__()
        
        _lazy_imports()
        
        self.symbols = symbols
        self.n_assets = len(symbols)
        self.start_date = start_date
        self.end_date = end_date
        self.initial_capital = initial_capital
        self.commission = commission
        self.lookback_window = lookback_window
        self.use_technical_indicators = use_technical_indicators
        self.use_sentiment = use_sentiment
        self.use_risk_metrics = use_risk_metrics
        self.max_position_size = max_position_size
        self.cash_penalty_proportion = cash_penalty_proportion
        self.render_mode = render_mode
        self.random_start = random_start
        
        # Initialize data fetcher
        self.data_fetcher = None
        self.technical_engine = None
        self.sentiment_engine = None
        
        # Load historical data
        self._load_data()
        
        # Define action space: continuous [-1, 1] per asset
        self.action_space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(self.n_assets,),
            dtype=np.float32
        )
        
        # Define observation space
        self._define_observation_space()
        
        # Episode tracking
        self.current_step = 0
        self.max_steps = len(self.dates) - self.lookback_window - 1
        self.episode = 0
        
        # Portfolio state
        self.cash = self.initial_capital
        self.holdings = np.zeros(self.n_assets, dtype=np.float32)
        self.portfolio_value = self.initial_capital
        
        # Performance tracking
        self.portfolio_values = []
        self.actions_memory = []
        self.returns = []
        
        logger.info(
            f"TradingEnvironment initialized: {self.n_assets} assets, "
            f"{self.max_steps} steps, state_dim={self.observation_space.shape[0]}"
        )
    
    def _load_data(self) -> None:
        """Load historical market data and compute features."""
        logger.info(f"Loading data for {len(self.symbols)} symbols from {self.start_date} to {self.end_date}")
        
        if MarketDataFetcher is not None:
            try:
                self.data_fetcher = MarketDataFetcher()
                
                # Fetch OHLCV data for all symbols
                self.price_data = {}
                for symbol in self.symbols:
                    df = self.data_fetcher.get_price_history(
                        symbol=symbol,
                        start_date=self.start_date,
                        end_date=self.end_date,
                        interval='1d'
                    )
                    if df is not None and len(df) > 0:
                        self.price_data[symbol] = df
                    else:
                        logger.warning(f"No data for {symbol}, using synthetic")
                        self.price_data[symbol] = self._generate_synthetic_data()
                
                if not self.price_data:
                    raise ValueError("No price data loaded")
                    
            except Exception as e:
                logger.warning(f"MarketDataFetcher failed: {e}, using synthetic data")
                self._generate_synthetic_data_all()
        else:
            logger.warning("MarketDataFetcher not available, using synthetic data")
            self._generate_synthetic_data_all()
        
        # Align all data to common dates
        self._align_dates()
        
        # Compute technical indicators if requested
        if self.use_technical_indicators and TechnicalFeatureEngine is not None:
            try:
                self.technical_engine = TechnicalFeatureEngine()
                self.technical_features = {}
                
                for symbol in self.symbols:
                    df = self.price_data[symbol]
                    features = self.technical_engine.compute_features(df)
                    self.technical_features[symbol] = features
                    
                logger.info(f"Technical indicators computed: {len(self.technical_features[self.symbols[0]].columns)} features")
            except Exception as e:
                logger.warning(f"Technical features failed: {e}")
                self.use_technical_indicators = False
        
        # Compute sentiment if requested
        if self.use_sentiment and FinBERTEngine is not None:
            try:
                self.sentiment_engine = FinBERTEngine()
                logger.info("FinBERT sentiment engine initialized")
            except Exception as e:
                logger.warning(f"FinBERT initialization failed: {e}")
                self.use_sentiment = False
    
    def _generate_synthetic_data_all(self) -> None:
        """Generate synthetic OHLCV data for all symbols."""
        self.price_data = {}
        for symbol in self.symbols:
            self.price_data[symbol] = self._generate_synthetic_data()
    
    def _generate_synthetic_data(self) -> pd.DataFrame:
        """Generate synthetic OHLCV data for testing."""
        dates = pd.date_range(start=self.start_date, end=self.end_date, freq='B')
        n_days = len(dates)
        
        # Random walk with drift
        np.random.seed(hash(self.start_date) % 2**32)
        returns = np.random.normal(0.0005, 0.02, n_days)
        prices = 100 * np.exp(np.cumsum(returns))
        
        df = pd.DataFrame({
            'open': prices * (1 + np.random.normal(0, 0.005, n_days)),
            'high': prices * (1 + np.abs(np.random.normal(0, 0.01, n_days))),
            'low': prices * (1 - np.abs(np.random.normal(0, 0.01, n_days))),
            'close': prices,
            'volume': np.random.randint(1_000_000, 10_000_000, n_days),
        }, index=dates)
        
        return df
    
    def _align_dates(self) -> None:
        """Align all price data to common date index."""
        # Find common dates across all symbols
        common_dates = set(self.price_data[self.symbols[0]].index)
        for symbol in self.symbols[1:]:
            common_dates &= set(self.price_data[symbol].index)
        
        self.dates = sorted(list(common_dates))
        
        # Reindex all data to common dates
        for symbol in self.symbols:
            self.price_data[symbol] = self.price_data[symbol].loc[self.dates]
        
        if self.use_technical_indicators and hasattr(self, 'technical_features'):
            for symbol in self.symbols:
                if symbol in self.technical_features:
                    self.technical_features[symbol] = self.technical_features[symbol].loc[self.dates]
        
        logger.info(f"Data aligned: {len(self.dates)} trading days")
    
    def _define_observation_space(self) -> None:
        """Define observation space dimensions."""
        # Base state: cash (1) + holdings (N) + prices (N)
        state_dim = 1 + self.n_assets + self.n_assets
        
        # Technical indicators
        if self.use_technical_indicators:
            # Estimate 25 indicators per asset (SMA, RSI, MACD, etc.)
            state_dim += self.n_assets * 25
        
        # Sentiment scores
        if self.use_sentiment:
            state_dim += self.n_assets
        
        # Risk metrics (portfolio level)
        if self.use_risk_metrics:
            # Volatility, Sharpe, Sortino, Max DD, VaR, CVaR
            state_dim += 6
        
        self.observation_space = spaces.Box(
            low=-np.inf,
            high=np.inf,
            shape=(state_dim,),
            dtype=np.float32
        )
        
        logger.info(f"Observation space defined: {state_dim} dimensions")
    
    def reset(
        self,
        seed: Optional[int] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Reset environment to initial state.
        
        Args:
            seed: Random seed for reproducibility
            options: Additional reset options
            
        Returns:
            observation: Initial state vector
            info: Additional information dictionary
        """
        super().reset(seed=seed)
        
        # Reset episode tracking
        self.episode += 1
        
        # Random start position for training diversity
        if self.random_start and self.max_steps > 1:
            max_start = max(1, self.max_steps // 2)
            self.current_step = self.np_random.integers(0, max_start)
        else:
            self.current_step = 0
        
        # Reset portfolio state
        self.cash = self.initial_capital
        self.holdings = np.zeros(self.n_assets, dtype=np.float32)
        self.portfolio_value = self.initial_capital
        
        # Reset tracking
        self.portfolio_values = [self.initial_capital]
        self.actions_memory = []
        self.returns = []
        
        # Get initial observation
        observation = self._get_observation()
        info = self._get_info()
        
        logger.debug(f"Episode {self.episode} reset: step={self.current_step}, value=${self.portfolio_value:,.2f}")
        
        return observation, info
    
    def step(
        self,
        action: np.ndarray
    ) -> Tuple[np.ndarray, float, bool, bool, Dict[str, Any]]:
        """
        Execute one time step with given action.
        
        Args:
            action: Action vector (continuous [-1, 1] per asset)
            
        Returns:
            observation: Next state vector
            reward: Reward for this step
            terminated: Whether episode ended (max steps)
            truncated: Whether episode truncated (e.g., bankruptcy)
            info: Additional information
        """
        # Store action
        self.actions_memory.append(action.copy())
        
        # Execute trades based on action
        self._execute_trades(action)
        
        # Move to next time step
        self.current_step += 1
        
        # Calculate reward
        reward = self._calculate_reward()
        
        # Check if episode ended
        terminated = self.current_step >= self.max_steps
        truncated = self.cash < 0  # Bankruptcy
        
        # Get next observation
        observation = self._get_observation()
        info = self._get_info()
        
        # Track performance
        self.portfolio_values.append(self.portfolio_value)
        
        if terminated or truncated:
            logger.info(
                f"Episode {self.episode} ended: "
                f"steps={self.current_step}, "
                f"final_value=${self.portfolio_value:,.2f}, "
                f"return={self._calculate_total_return():.2%}"
            )
        
        return observation, reward, terminated, truncated, info
    
    def _execute_trades(self, action: np.ndarray) -> None:
        """
        Execute trades based on action vector.
        
        Action interpretation:
            action[i] = -1: Sell all of asset i
            action[i] = 0: Hold current position
            action[i] = +1: Buy maximum allowed of asset i
        """
        current_prices = self._get_current_prices()
        
        for i, target_action in enumerate(action):
            current_holding = self.holdings[i]
            current_price = current_prices[i]
            
            if current_price <= 0:
                continue
            
            # Calculate target position
            if target_action > 0:
                # Buy signal: allocate proportion of available cash
                max_shares = (self.cash * self.max_position_size) / current_price
                target_shares = current_holding + (max_shares * target_action)
            elif target_action < 0:
                # Sell signal: reduce position
                target_shares = current_holding * (1 + target_action)
            else:
                # Hold
                continue
            
            # Execute trade
            shares_to_trade = target_shares - current_holding
            
            if abs(shares_to_trade) < 0.01:
                continue
            
            trade_value = abs(shares_to_trade) * current_price
            trade_commission = trade_value * self.commission
            
            if shares_to_trade > 0:
                # Buy
                total_cost = trade_value + trade_commission
                if total_cost <= self.cash:
                    self.cash -= total_cost
                    self.holdings[i] = target_shares
            else:
                # Sell
                proceeds = trade_value - trade_commission
                self.cash += proceeds
                self.holdings[i] = target_shares
        
        # Update portfolio value
        self._update_portfolio_value()
    
    def _get_current_prices(self) -> np.ndarray:
        """Get current closing prices for all assets."""
        idx = self.current_step + self.lookback_window
        if idx >= len(self.dates):
            idx = len(self.dates) - 1  # clamp to last date
        current_date = self.dates[idx]
        prices = np.zeros(self.n_assets, dtype=np.float32)
        
        for i, symbol in enumerate(self.symbols):
            try:
                prices[i] = self.price_data[symbol].loc[current_date, 'close']
            except (KeyError, IndexError):
                prices[i] = 0.0
        
        return prices
    
    def _update_portfolio_value(self) -> None:
        """Update total portfolio value (cash + holdings)."""
        current_prices = self._get_current_prices()
        holdings_value = np.sum(self.holdings * current_prices)
        self.portfolio_value = self.cash + holdings_value
    
    def _calculate_reward(self) -> float:
        """
        Calculate reward for current step.
        
        Reward components:
            1. Portfolio return (log return for stability)
            2. Cash penalty (encourage maintaining reserves)
            3. Risk adjustment (penalize high volatility)
        """
        # Portfolio return
        if len(self.portfolio_values) > 0:
            prev_value = self.portfolio_values[-1]
            if prev_value > 0:
                log_return = np.log(self.portfolio_value / prev_value)
                self.returns.append(log_return)
            else:
                log_return = 0.0
        else:
            log_return = 0.0
        
        # Cash penalty (if cash reserves too low)
        min_cash = self.portfolio_value * self.cash_penalty_proportion
        cash_penalty = 0.0
        if self.cash < min_cash:
            cash_penalty = -0.01 * (min_cash - self.cash) / self.portfolio_value
        
        # Risk adjustment (penalize high recent volatility)
        risk_penalty = 0.0
        if len(self.returns) >= 5:
            recent_volatility = np.std(self.returns[-5:])
            risk_penalty = -0.1 * recent_volatility
        
        # Combined reward
        reward = log_return + cash_penalty + risk_penalty
        
        return float(reward)
    
    def _get_observation(self) -> np.ndarray:
        """
        Construct observation vector from current state.
        
        State components:
            - Cash balance (normalized)
            - Holdings per asset (normalized)
            - Current prices (normalized)
            - Technical indicators (if enabled)
            - Sentiment scores (if enabled)
            - Risk metrics (if enabled)
        """
        state = []
        
        # Cash (normalized by initial capital)
        state.append(self.cash / self.initial_capital)
        
        # Holdings (normalized by total holdings)
        total_shares = np.sum(np.abs(self.holdings)) + 1e-8
        normalized_holdings = self.holdings / total_shares
        state.extend(normalized_holdings)
        
        # Current prices (normalized by first price)
        current_prices = self._get_current_prices()
        first_prices = self._get_prices_at_step(0)
        normalized_prices = current_prices / (first_prices + 1e-8)
        state.extend(normalized_prices)
        
        # Technical indicators
        if self.use_technical_indicators and hasattr(self, 'technical_features'):
            for symbol in self.symbols:
                if symbol in self.technical_features:
                    idx = self.current_step + self.lookback_window
                    if idx >= len(self.dates):
                        idx = len(self.dates) - 1
                    current_date = self.dates[idx]
                    try:
                        features = self.technical_features[symbol].loc[current_date]
                        # Take first 25 features, fill NaN with 0
                        feature_values = features.fillna(0).values[:25]
                        state.extend(feature_values)
                    except (KeyError, IndexError):
                        state.extend([0.0] * 25)
        
        # Sentiment scores
        if self.use_sentiment:
            # Placeholder: could fetch real-time sentiment
            sentiment_scores = np.zeros(self.n_assets)
            state.extend(sentiment_scores)
        
        # Risk metrics
        if self.use_risk_metrics:
            risk_metrics = self._calculate_portfolio_risk_metrics()
            state.extend(risk_metrics)
        
        return np.array(state, dtype=np.float32)
    
    def _get_prices_at_step(self, step: int) -> np.ndarray:
        """Get prices at specific step."""
        idx = step + self.lookback_window
        if idx >= len(self.dates):
            idx = len(self.dates) - 1
        date = self.dates[idx]
        prices = np.zeros(self.n_assets, dtype=np.float32)
        
        for i, symbol in enumerate(self.symbols):
            try:
                prices[i] = self.price_data[symbol].loc[date, 'close']
            except (KeyError, IndexError):
                prices[i] = 1.0
        
        return prices
    
    def _calculate_portfolio_risk_metrics(self) -> List[float]:
        """
        Calculate portfolio-level risk metrics.
        
        Returns:
            [volatility, sharpe, sortino, max_dd, var_95, cvar_95]
        """
        if len(self.returns) < 2:
            return [0.0] * 6
        
        returns_array = np.array(self.returns)
        
        # Volatility (annualized)
        volatility = np.std(returns_array) * np.sqrt(252)
        
        # Sharpe ratio (annualized, rf=2%)
        mean_return = np.mean(returns_array) * 252
        sharpe = (mean_return - 0.02) / (volatility + 1e-8)
        
        # Sortino ratio (downside deviation only)
        downside_returns = returns_array[returns_array < 0]
        if len(downside_returns) > 0:
            downside_std = np.std(downside_returns) * np.sqrt(252)
            sortino = (mean_return - 0.02) / (downside_std + 1e-8)
        else:
            sortino = sharpe
        
        # Maximum drawdown
        cumulative = np.exp(np.cumsum(returns_array))
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / (running_max + 1e-8)
        max_dd = np.min(drawdown)
        
        # VaR (95%)
        var_95 = np.percentile(returns_array, 5)
        
        # CVaR (95%)
        cvar_95 = np.mean(returns_array[returns_array <= var_95])
        
        return [volatility, sharpe, sortino, max_dd, var_95, cvar_95]
    
    def _calculate_total_return(self) -> float:
        """Calculate total portfolio return."""
        if self.initial_capital > 0:
            return (self.portfolio_value - self.initial_capital) / self.initial_capital
        return 0.0
    
    def _get_info(self) -> Dict[str, Any]:
        """Get additional information dictionary."""
        idx = self.current_step + self.lookback_window
        current_date = self.dates[idx] if idx < len(self.dates) else None
        return {
            'portfolio_value': self.portfolio_value,
            'cash': self.cash,
            'holdings': self.holdings.copy(),
            'total_return': self._calculate_total_return(),
            'step': self.current_step,
            'date': current_date
        }
    
    def render(self) -> Optional[np.ndarray]:
        """Render environment (optional visualization)."""
        if self.render_mode == "human":
            print(f"Step: {self.current_step}, Value: ${self.portfolio_value:,.2f}, Cash: ${self.cash:,.2f}")
        return None
    
    def close(self) -> None:
        """Cleanup resources."""
        pass


__all__ = ['TradingEnvironment']

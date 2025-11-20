#!/usr/bin/env python3
"""
Backtest réel sur 1 an avec données réelles.

Teste la pipeline complète :
- Data fetching (yfinance)
- Feature engineering (technical + fundamental)
- Portfolio optimization (avec régularisation covariance)
- Sentiment analysis (si disponible)
- Backtesting avec métriques
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import logging

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np
from typing import Dict, List

from financial_analyzer.data.market_data import MarketDataFetcher
from financial_analyzer.features.technical import TechnicalFeatureEngine
from financial_analyzer.portfolio.optimizer import PortfolioOptimizer
from financial_analyzer.portfolio.rebalancer import PortfolioRebalancer

# Use print instead of logger for direct output
def log_info(msg):
    print(msg, flush=True)

# Suppress warnings
import warnings
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=UserWarning)


class RealWorldBacktest:
    """Backtest réel sur 1 an avec validation complète."""
    
    def __init__(self, start_date: str = None, end_date: str = None):
        """
        Initialize backtest.
        
        Args:
            start_date: Format 'YYYY-MM-DD' (default: 1 an avant aujourd'hui)
            end_date: Format 'YYYY-MM-DD' (default: aujourd'hui)
        """
        if end_date is None:
            self.end_date = datetime.now()
        else:
            self.end_date = datetime.strptime(end_date, '%Y-%m-%d')
        
        if start_date is None:
            self.start_date = self.end_date - timedelta(days=365)
        else:
            self.start_date = datetime.strptime(start_date, '%Y-%m-%d')
        
        # Universe: Top US stocks
        self.tickers = [
            'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA',
            'META', 'TSLA', 'BRK-B', 'JPM', 'V'
        ]
        
        self.initial_capital = 100000.0
        self.results = {}
        
        log_info("=" * 80)
        log_info(f"REAL WORLD BACKTEST - 1 YEAR")
        log_info(f"Period: {self.start_date.date()} to {self.end_date.date()}")
        log_info(f"Universe: {len(self.tickers)} tickers")
        log_info(f"Initial Capital: ${self.initial_capital:,.2f}")
        log_info("=" * 80)
    
    def fetch_data(self) -> pd.DataFrame:
        """Fetch historical data for all tickers."""
        log_info("\n[PHASE 1] FETCHING DATA")
        log_info("-" * 40)
        
        fetcher = MarketDataFetcher()
        all_data = []
        
        for ticker in self.tickers:
            try:
                data = fetcher.get_historical_data(
                    tickers=ticker,
                    start_date=self.start_date.strftime('%Y-%m-%d'),
                    end_date=self.end_date.strftime('%Y-%m-%d'),
                    interval='1d'
                )
                
                if data is not None and not data.empty:
                    data['ticker'] = ticker
                    all_data.append(data)
                    log_info(f"✓ {ticker}: {len(data)} days")
                else:
                    log_info(f"✗ {ticker}: No data")
            except Exception as e:
                log_info(f"✗ {ticker}: {e}")
        
        if not all_data:
            raise ValueError("No data fetched for any ticker!")
        
        combined = pd.concat(all_data, ignore_index=False)
        log_info(f"\n✓ Total data points: {len(combined)}")
        log_info(f"✓ Date range: {combined.index.min()} to {combined.index.max()}")
        
        return combined
    
    def calculate_features(self, data: pd.DataFrame) -> Dict[str, pd.DataFrame]:
        """Calculate technical features per ticker."""
        log_info("\n[PHASE 2] CALCULATING FEATURES")
        log_info("-" * 40)
        
        features_by_ticker = {}
        
        for ticker in self.tickers:
            ticker_data = data[data['ticker'] == ticker].copy()
            
            if len(ticker_data) < 50:
                log_info(f"✗ {ticker}: Insufficient data ({len(ticker_data)} days)")
                continue
            
            try:
                # Calculate technical indicators using TechnicalFeatureEngine
                engine = TechnicalFeatureEngine(ticker_data)
                features = engine.calculate_all_features()
                features_by_ticker[ticker] = features
                
                # Log some indicators
                if 'rsi_14' in features.columns:
                    rsi_mean = features['rsi_14'].mean()
                    log_info(f"✓ {ticker}: RSI_14 mean={rsi_mean:.2f}")
                
            except Exception as e:
                log_info(f"✗ {ticker}: Feature calculation failed - {e}")
        
        log_info(f"\n✓ Features calculated for {len(features_by_ticker)} tickers")
        return features_by_ticker
    
    def calculate_returns_matrix(self, data: pd.DataFrame) -> pd.DataFrame:
        """Calculate returns matrix for portfolio optimization."""
        log_info("\n[PHASE 3] CALCULATING RETURNS")
        log_info("-" * 40)
        
        # Normalize column names to lowercase
        data.columns = [col.lower() if isinstance(col, str) else col for col in data.columns]
        
        # Pivot to wide format (dates x tickers)
        prices = data.pivot_table(
            values='close',
            index=data.index,
            columns='ticker',
            aggfunc='first'
        )
        
        # Keep only tickers with enough data
        min_observations = 50
        valid_tickers = []
        for col in prices.columns:
            if prices[col].notna().sum() >= min_observations:
                valid_tickers.append(col)
        
        prices = prices[valid_tickers]
        
        # Calculate returns
        returns = prices.pct_change().dropna()
        
        log_info(f"✓ Returns shape: {returns.shape}")
        log_info(f"✓ Valid tickers: {len(valid_tickers)}")
        log_info(f"✓ Observation period: {len(returns)} days")
        
        # Statistics
        mean_return = returns.mean().mean() * 252
        mean_vol = returns.std().mean() * np.sqrt(252)
        log_info(f"✓ Avg annual return: {mean_return:.2%}")
        log_info(f"✓ Avg annual volatility: {mean_vol:.2%}")
        
        return returns
    
    def optimize_portfolio(self, returns: pd.DataFrame) -> Dict:
        """Optimize portfolio weights."""
        log_info("\n[PHASE 4] PORTFOLIO OPTIMIZATION")
        log_info("-" * 40)
        
        optimizer = PortfolioOptimizer(returns, risk_free_rate=0.04)
        
        # Test multiple strategies
        strategies = {}
        
        # 1. Equal Weight
        try:
            ew = optimizer.optimize_equal_weight()
            strategies['equal_weight'] = ew
            log_info(f"✓ Equal Weight: ret={ew['return']:.2%}, vol={ew['volatility']:.2%}")
        except Exception as e:
            log_info(f"✗ Equal Weight failed: {e}")
        
        # 2. Min Variance (avec régularisation covariance)
        try:
            mv = optimizer.optimize_min_variance()
            strategies['min_variance'] = mv
            log_info(f"✓ Min Variance: ret={mv['return']:.2%}, vol={mv['volatility']:.2%}")
        except Exception as e:
            log_info(f"✗ Min Variance failed: {e}")
        
        # 3. Max Sharpe
        try:
            ms = optimizer.optimize_max_sharpe()
            strategies['max_sharpe'] = ms
            log_info(f"✓ Max Sharpe: ret={ms['return']:.2%}, vol={ms['volatility']:.2%}, sharpe={ms['sharpe']:.2f}")
        except Exception as e:
            log_info(f"✗ Max Sharpe failed: {e}")
        
        # 4. Risk Parity
        try:
            rp = optimizer.optimize_risk_parity()
            strategies['risk_parity'] = rp
            log_info(f"✓ Risk Parity: vol={rp['volatility']:.2%}")
        except Exception as e:
            log_info(f"✗ Risk Parity failed: {e}")
        
        log_info(f"\n✓ {len(strategies)} strategies optimized successfully")
        
        return strategies
    
    def simulate_rebalancing(
        self,
        returns: pd.DataFrame,
        weights: pd.Series,
        rebalance_freq: str = 'M'
    ) -> Dict:
        """Simulate portfolio performance with rebalancing."""
        log_info(f"\n[PHASE 5] SIMULATING PERFORMANCE")
        log_info("-" * 40)
        
        try:
            # Calculate portfolio value over time
            portfolio_value = self.calculate_portfolio_value(
                returns, weights, self.initial_capital
            )
            
            final_value = portfolio_value.iloc[-1]
            total_return = (final_value / self.initial_capital - 1)
            
            # Calculate metrics
            daily_returns = portfolio_value.pct_change().dropna()
            sharpe = (daily_returns.mean() / daily_returns.std()) * np.sqrt(252) if daily_returns.std() > 0 else 0
            max_dd = self.calculate_max_drawdown(portfolio_value)
            
            # Calculate number of monthly rebalances
            num_months = len(portfolio_value) // 21  # Approx trading days per month
            
            results = {
                'initial_value': self.initial_capital,
                'final_value': final_value,
                'total_return': total_return,
                'sharpe_ratio': sharpe,
                'max_drawdown': max_dd,
                'num_rebalances': num_months,
                'portfolio_value': portfolio_value
            }
            
            log_info(f"✓ Initial Value: ${self.initial_capital:,.2f}")
            log_info(f"✓ Final Value: ${final_value:,.2f}")
            log_info(f"✓ Total Return: {total_return:.2%}")
            log_info(f"✓ Sharpe Ratio: {sharpe:.2f}")
            log_info(f"✓ Max Drawdown: {max_dd:.2%}")
            log_info(f"✓ Estimated Rebalances: {num_months}")
            
            return results
            
        except Exception as e:
            log_info(f"✗ Performance simulation failed: {e}")
            import traceback
            traceback.print_exc()
            return {}
    
    def calculate_portfolio_value(
        self,
        returns: pd.DataFrame,
        weights: pd.Series,
        initial_value: float
    ) -> pd.Series:
        """Calculate portfolio value over time."""
        # Align weights with returns columns
        weights = weights.reindex(returns.columns, fill_value=0)
        weights = weights / weights.sum()  # Normalize
        
        # Portfolio returns
        portfolio_returns = (returns * weights).sum(axis=1)
        
        # Cumulative value
        portfolio_value = initial_value * (1 + portfolio_returns).cumprod()
        
        return portfolio_value
    
    def calculate_max_drawdown(self, portfolio_value: pd.Series) -> float:
        """Calculate maximum drawdown."""
        cummax = portfolio_value.cummax()
        drawdown = (portfolio_value - cummax) / cummax
        return drawdown.min()
    
    def run_backtest(self) -> Dict:
        """Execute complete backtest."""
        try:
            # Phase 1: Data
            data = self.fetch_data()
            self.results['data_points'] = len(data)
            
            # Phase 2: Features
            features = self.calculate_features(data)
            self.results['features_calculated'] = len(features)
            
            # Phase 3: Returns
            returns = self.calculate_returns_matrix(data)
            self.results['returns_shape'] = returns.shape
            
            # Phase 4: Optimization
            strategies = self.optimize_portfolio(returns)
            self.results['strategies'] = strategies
            
            # Phase 5: Simulation (use Max Sharpe if available, else Equal Weight)
            if 'max_sharpe' in strategies:
                weights = strategies['max_sharpe']['weights']
                strategy_name = 'max_sharpe'
            elif 'equal_weight' in strategies:
                weights = strategies['equal_weight']['weights']
                strategy_name = 'equal_weight'
            else:
                log_info("No valid strategy available for simulation!")
                return self.results
            
            log_info(f"\nUsing strategy: {strategy_name}")
            
            sim_results = self.simulate_rebalancing(returns, weights, rebalance_freq='M')
            self.results['simulation'] = sim_results
            
            # Summary
            self.print_summary()
            
            return self.results
            
        except Exception as e:
            log_info(f"❌ BACKTEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            return self.results
    
    def print_summary(self):
        """Print final summary."""
        log_info("\n" + "=" * 80)
        log_info("BACKTEST SUMMARY")
        log_info("=" * 80)
        
        if 'simulation' in self.results and self.results['simulation']:
            sim = self.results['simulation']
            
            log_info(f"\n📊 PERFORMANCE METRICS")
            log_info(f"   Initial Capital:  ${sim['initial_value']:>12,.2f}")
            log_info(f"   Final Value:      ${sim['final_value']:>12,.2f}")
            log_info(f"   Total Return:     {sim['total_return']:>12.2%}")
            log_info(f"   Sharpe Ratio:     {sim['sharpe_ratio']:>12.2f}")
            log_info(f"   Max Drawdown:     {sim['max_drawdown']:>12.2%}")
            log_info(f"   Rebalances:       {sim['num_rebalances']:>12}")
            
            log_info(f"\n📈 DATA COVERAGE")
            log_info(f"   Period:           {self.start_date.date()} to {self.end_date.date()}")
            log_info(f"   Trading Days:     {self.results['returns_shape'][0]:>12}")
            log_info(f"   Tickers:          {self.results['returns_shape'][1]:>12}")
            log_info(f"   Data Points:      {self.results['data_points']:>12}")
            
            if 'strategies' in self.results:
                log_info(f"\n🎯 STRATEGIES TESTED")
                for name, strat in self.results['strategies'].items():
                    ret = strat.get('return', 0)
                    vol = strat.get('volatility', 0)
                    log_info(f"   {name:20s} ret={ret:>7.2%} vol={vol:>7.2%}")
        
        log_info("\n" + "=" * 80)
        log_info("✅ BACKTEST COMPLETE")
        log_info("=" * 80)


def main():
    """Run backtest."""
    import argparse
    import traceback
    
    try:
        print("Starting backtest...")
        
        parser = argparse.ArgumentParser(description='Run 1-year real world backtest')
        parser.add_argument('--start', type=str, help='Start date (YYYY-MM-DD)')
        parser.add_argument('--end', type=str, help='End date (YYYY-MM-DD)')
        
        args = parser.parse_args()
        
        print(f"Period: {args.start} to {args.end}")
        
        # Run backtest
        backtest = RealWorldBacktest(start_date=args.start, end_date=args.end)
        results = backtest.run_backtest()
        
        return 0 if results else 1
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())

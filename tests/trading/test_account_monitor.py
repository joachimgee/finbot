"""
Tests for AccountMonitor.

Tests real-time portfolio tracking, P&L calculation, drawdown tracking.
Uses mock BrokerAdapter (no real API calls).
"""

from __future__ import annotations
import pytest
from unittest.mock import Mock
from datetime import datetime
import pandas as pd
from financial_analyzer.trading.account_monitor import AccountMonitor
from financial_analyzer.trading.broker_adapter import BrokerAPIError


@pytest.fixture
def mock_broker():
    """Mock broker adapter."""
    broker = Mock()
    broker.connected = True
    broker.get_account.return_value = {
        'cash': 50000.0,
        'equity': 100000.0,
        'portfolio_value': 100000.0,
        'buying_power': 200000.0,
        'initial_margin': 0.0,
        'maintenance_margin': 0.0,
        'daytrade_count': 0
    }
    broker.get_positions.return_value = [
        {
            'symbol': 'AAPL',
            'qty': 100,
            'avg_entry_price': 150.0,
            'current_price': 155.0,
            'market_value': 15500.0,
            'unrealized_pl': 500.0,
            'unrealized_plpc': 0.0333
        },
        {
            'symbol': 'MSFT',
            'qty': 50,
            'avg_entry_price': 360.0,
            'current_price': 380.0,
            'market_value': 19000.0,
            'unrealized_pl': 1000.0,
            'unrealized_plpc': 0.0556
        }
    ]
    return broker


@pytest.fixture
def monitor(mock_broker):
    """Create AccountMonitor with mock broker."""
    return AccountMonitor(mock_broker, initial_capital=100000.0)


class TestAccountMonitorInitialization:
    """Test initialization."""
    
    def test_init_success(self, mock_broker):
        """Test successful initialization."""
        monitor = AccountMonitor(mock_broker, initial_capital=100000)
        
        assert monitor.broker is mock_broker
        assert monitor.initial_capital == 100000
        assert monitor.portfolio_value == 100000
        assert monitor.daily_pnl == 0.0
        assert monitor.max_drawdown == 0.0
        assert monitor.peak_value == 100000
        assert monitor.track_history is True
        assert monitor.history is not None
    
    def test_init_disconnected_broker_raises(self):
        """Test initialization with disconnected broker raises error."""
        mock_broker = Mock()
        mock_broker.connected = False
        
        with pytest.raises(ValueError, match="must be connected"):
            AccountMonitor(mock_broker)
    
    def test_init_without_history(self, mock_broker):
        """Test initialization without history tracking."""
        monitor = AccountMonitor(mock_broker, track_history=False)
        
        assert monitor.history is None
    
    def test_init_custom_history_size(self, mock_broker):
        """Test initialization with custom history size."""
        monitor = AccountMonitor(mock_broker, max_history_size=100)
        
        assert monitor.history.maxlen == 100


class TestAccountMonitorUpdate:
    """Test update functionality."""
    
    def test_update_state(self, monitor, mock_broker):
        """Test update fetches latest state."""
        monitor.update()
        
        assert monitor.portfolio_value == 100000.0
        assert monitor.cash == 50000.0
        assert monitor.equity == 100000.0
        assert len(monitor.positions) == 2
        assert monitor.last_update is not None
        
        # Verify broker was called
        mock_broker.get_account.assert_called_once()
        mock_broker.get_positions.assert_called_once()
    
    def test_calculate_daily_pnl(self, monitor, mock_broker):
        """Test daily P&L calculation."""
        monitor.last_portfolio_value = 95000.0
        
        mock_broker.get_account.return_value['portfolio_value'] = 100000.0
        monitor.update()
        
        assert monitor.daily_pnl == 5000.0
    
    def test_calculate_cumulative_pnl(self, monitor, mock_broker):
        """Test cumulative P&L calculation."""
        mock_broker.get_account.return_value['portfolio_value'] = 110000.0
        monitor.update()
        
        assert monitor.cumulative_pnl == 10000.0  # 110k - 100k initial
    
    def test_update_drawdown_increase(self, monitor, mock_broker):
        """Test drawdown tracking when portfolio increases."""
        # Portfolio increases to new peak
        mock_broker.get_account.return_value['portfolio_value'] = 110000.0
        monitor.update()
        
        assert monitor.peak_value == 110000.0
        assert monitor.current_drawdown == 0.0  # At peak
    
    def test_update_drawdown_decrease(self, monitor, mock_broker):
        """Test drawdown tracking when portfolio decreases."""
        # Set peak
        monitor.peak_value = 110000.0
        
        # Portfolio decreases
        mock_broker.get_account.return_value['portfolio_value'] = 99000.0
        monitor.update()
        
        expected_dd = (99000.0 - 110000.0) / 110000.0
        assert monitor.current_drawdown == pytest.approx(expected_dd, rel=1e-6)
        assert monitor.max_drawdown == pytest.approx(expected_dd, rel=1e-6)
    
    def test_update_max_drawdown(self, monitor, mock_broker):
        """Test max drawdown is tracked correctly."""
        # First drawdown
        monitor.peak_value = 110000.0
        mock_broker.get_account.return_value['portfolio_value'] = 100000.0
        monitor.update()
        
        first_dd = monitor.max_drawdown
        
        # Recover partially
        mock_broker.get_account.return_value['portfolio_value'] = 105000.0
        monitor.update()
        
        # Max drawdown should not improve (it's the worst ever)
        assert monitor.max_drawdown == first_dd
    
    def test_update_error_handling(self, monitor, mock_broker):
        """Test error handling during update."""
        mock_broker.get_account.side_effect = BrokerAPIError("API error")
        
        with pytest.raises(BrokerAPIError):
            monitor.update()


class TestAccountMonitorMetrics:
    """Test metric calculations."""
    
    def test_position_concentration(self, monitor):
        """Test position concentration calculation."""
        monitor.update()
        conc = monitor.get_position_concentration()
        
        assert 'AAPL' in conc
        assert 'MSFT' in conc
        assert conc['AAPL'] == pytest.approx(0.155, rel=1e-2)
        assert conc['MSFT'] == pytest.approx(0.19, rel=1e-2)
    
    def test_position_concentration_empty(self, mock_broker):
        """Test concentration when no positions."""
        mock_broker.get_positions.return_value = []
        monitor = AccountMonitor(mock_broker, initial_capital=100000)
        monitor.update()
        
        conc = monitor.get_position_concentration()
        assert conc == {}
    
    def test_exposure_metrics_long_only(self, monitor):
        """Test exposure metrics with long positions only."""
        monitor.update()
        exposure = monitor.get_exposure_metrics()
        
        assert exposure['long_exposure'] == 34500.0
        assert exposure['short_exposure'] == 0.0
        assert exposure['net_exposure'] == 34500.0
        assert exposure['gross_exposure'] == 34500.0
        assert exposure['leverage'] == pytest.approx(0.345, rel=1e-2)
        assert exposure['long_pct'] == pytest.approx(34.5, rel=1e-2)
        assert exposure['short_pct'] == 0.0
    
    def test_exposure_metrics_with_short(self, monitor, mock_broker):
        """Test exposure metrics with short positions."""
        mock_broker.get_positions.return_value = [
            {
                'symbol': 'AAPL',
                'qty': 100,
                'avg_entry_price': 150.0,
                'current_price': 155.0,
                'market_value': 15500.0,
                'unrealized_pl': 500.0,
                'unrealized_plpc': 0.0333
            },
            {
                'symbol': 'TSLA',
                'qty': -50,  # Short position
                'avg_entry_price': 200.0,
                'current_price': 195.0,
                'market_value': -9750.0,
                'unrealized_pl': 250.0,
                'unrealized_plpc': 0.025
            }
        ]
        
        monitor.update()
        exposure = monitor.get_exposure_metrics()
        
        assert exposure['long_exposure'] == 15500.0
        assert exposure['short_exposure'] == 9750.0
        assert exposure['net_exposure'] == 5750.0  # 15500 - 9750
        assert exposure['gross_exposure'] == 25250.0  # 15500 + 9750
    
    def test_position_pnl(self, monitor):
        """Test per-position P&L."""
        monitor.update()
        pnl = monitor.get_position_pnl()
        
        assert 'AAPL' in pnl
        assert 'MSFT' in pnl
        assert pnl['AAPL']['unrealized_pl'] == 500.0
        assert pnl['MSFT']['unrealized_pl'] == 1000.0
        assert pnl['AAPL']['qty'] == 100
        assert pnl['MSFT']['qty'] == 50
    
    def test_summary(self, monitor):
        """Test summary generation."""
        monitor.update()
        summary = monitor.get_summary()
        
        # Check all required keys
        assert 'timestamp' in summary
        assert 'portfolio_value' in summary
        assert 'cash' in summary
        assert 'equity' in summary
        assert 'initial_capital' in summary
        assert 'daily_pnl' in summary
        assert 'cumulative_pnl' in summary
        assert 'daily_return_pct' in summary
        assert 'cumulative_return_pct' in summary
        assert 'current_drawdown' in summary
        assert 'max_drawdown' in summary
        assert 'peak_value' in summary
        assert 'num_positions' in summary
        assert 'concentration' in summary
        assert 'exposure' in summary
        assert 'position_pnl' in summary
        
        # Check values
        assert summary['portfolio_value'] == 100000.0
        assert summary['num_positions'] == 2
        assert isinstance(summary['concentration'], dict)
        assert isinstance(summary['exposure'], dict)
        assert isinstance(summary['position_pnl'], dict)
    
    def test_summary_returns(self, monitor, mock_broker):
        """Test return calculations in summary."""
        monitor.last_portfolio_value = 95000.0
        mock_broker.get_account.return_value['portfolio_value'] = 100000.0
        monitor.update()
        
        summary = monitor.get_summary()
        
        # Daily return: 5000 / 95000 = 5.26%
        assert summary['daily_return_pct'] == pytest.approx(5.0, rel=1e-2)
        
        # Cumulative return: 0 / 100000 = 0%
        assert summary['cumulative_return_pct'] == pytest.approx(0.0, abs=0.1)


class TestAccountMonitorHistory:
    """Test history tracking."""
    
    def test_history_tracking_enabled(self, monitor):
        """Test history is tracked when enabled."""
        monitor.update()
        monitor.update()
        monitor.update()
        
        assert len(monitor.history) == 3
    
    def test_history_disabled(self, mock_broker):
        """Test history not tracked when disabled."""
        monitor = AccountMonitor(mock_broker, track_history=False)
        monitor.update()
        
        assert monitor.history is None
    
    def test_history_df(self, monitor):
        """Test history as DataFrame."""
        monitor.update()
        monitor.update()
        
        df = monitor.get_history_df()
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert 'portfolio_value' in df.columns
        assert 'cash' in df.columns
        assert 'equity' in df.columns
        assert 'daily_pnl' in df.columns
        assert 'cumulative_pnl' in df.columns
        assert 'current_drawdown' in df.columns
        assert 'num_positions' in df.columns
        assert df.index.name == 'timestamp'
    
    def test_history_df_empty(self, mock_broker):
        """Test history DataFrame when no history."""
        monitor = AccountMonitor(mock_broker, track_history=False)
        
        df = monitor.get_history_df()
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
    
    def test_history_max_size(self):
        """Test history max size enforced."""
        mock_broker = Mock()
        mock_broker.connected = True
        mock_broker.get_account.return_value = {
            'cash': 50000, 
            'equity': 100000, 
            'portfolio_value': 100000,
            'buying_power': 200000,
            'initial_margin': 0,
            'maintenance_margin': 0,
            'daytrade_count': 0
        }
        mock_broker.get_positions.return_value = []
        
        monitor = AccountMonitor(mock_broker, max_history_size=5)
        
        for _ in range(10):
            monitor.update()
        
        assert len(monitor.history) == 5  # Capped at max_history_size
    
    def test_history_content(self, monitor):
        """Test history entries contain expected data."""
        monitor.update()
        
        assert len(monitor.history) == 1
        entry = monitor.history[0]
        
        assert 'timestamp' in entry
        assert 'portfolio_value' in entry
        assert 'cash' in entry
        assert 'equity' in entry
        assert 'daily_pnl' in entry
        assert 'cumulative_pnl' in entry
        assert 'current_drawdown' in entry
        assert 'num_positions' in entry
        
        assert isinstance(entry['timestamp'], datetime)
        assert entry['portfolio_value'] == 100000.0
        assert entry['num_positions'] == 2


class TestAccountMonitorReset:
    """Test reset functionality."""
    
    def test_reset_stats(self, monitor):
        """Test stats reset."""
        monitor.daily_pnl = 1000.0
        monitor.portfolio_value = 105000.0
        monitor.last_portfolio_value = 100000.0
        
        monitor.reset_stats()
        
        assert monitor.daily_pnl == 0.0
        assert monitor.last_portfolio_value == 105000.0  # Updated to current
    
    def test_reset_preserves_other_stats(self, monitor):
        """Test reset doesn't affect other stats."""
        monitor.portfolio_value = 105000.0
        monitor.cumulative_pnl = 5000.0
        monitor.max_drawdown = -0.05
        monitor.positions = [{'symbol': 'AAPL'}]
        
        monitor.reset_stats()
        
        assert monitor.portfolio_value == 105000.0
        assert monitor.cumulative_pnl == 5000.0
        assert monitor.max_drawdown == -0.05
        assert len(monitor.positions) == 1


class TestAccountMonitorRepr:
    """Test string representation."""
    
    def test_repr(self, monitor):
        """Test __repr__ output."""
        monitor.update()
        
        repr_str = repr(monitor)
        
        assert 'AccountMonitor' in repr_str
        assert '100000' in repr_str  # portfolio value
        assert '2' in repr_str  # num positions
        assert '%' in repr_str  # drawdown percentage


class TestAccountMonitorEquityCurve:
    """Test equity curve functionality."""
    
    def test_equity_curve_with_history(self, monitor):
        """Test equity curve generation with data."""
        # Build history
        monitor.update()
        monitor.update()
        monitor.update()
        
        equity_curve = monitor.get_equity_curve()
        
        assert isinstance(equity_curve, pd.Series)
        assert len(equity_curve) == 3
        assert equity_curve.name == 'portfolio_value'
        assert all(equity_curve == 100000.0)  # All same value
    
    def test_equity_curve_empty_history(self, mock_broker):
        """Test equity curve with no history."""
        monitor = AccountMonitor(mock_broker, track_history=False)
        
        equity_curve = monitor.get_equity_curve()
        
        assert isinstance(equity_curve, pd.Series)
        assert len(equity_curve) == 0
        assert equity_curve.name == 'portfolio_value'
    
    def test_equity_curve_has_timestamps(self, monitor):
        """Test equity curve has timestamp index."""
        monitor.update()
        monitor.update()
        
        equity_curve = monitor.get_equity_curve()
        
        assert isinstance(equity_curve.index, pd.DatetimeIndex)
        assert len(equity_curve.index) == 2

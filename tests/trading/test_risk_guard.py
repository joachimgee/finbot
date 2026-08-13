"""
Tests for RiskGuard.

Tests pre-trade risk validation, circuit breakers, and limit enforcement.
Uses mock AccountMonitor and BrokerAdapter (no real API calls).
"""

from __future__ import annotations
import numpy as np
import pandas as pd
import pytest
from unittest.mock import Mock
from datetime import datetime
from financial_analyzer.trading.risk_guard import (
    RiskGuard,
    RiskLimitExceeded,
    CircuitBreakerTriggered,
    InvalidOrderError
)


@pytest.fixture
def mock_monitor():
    """Mock account monitor."""
    monitor = Mock()
    monitor.broker = Mock()
    monitor.portfolio_value = 100000.0
    monitor.cash = 50000.0
    monitor.equity = 100000.0
    monitor.daily_pnl = 0.0
    monitor.current_drawdown = 0.0
    monitor.positions = [
        {
            'symbol': 'AAPL',
            'qty': 100,
            'avg_entry_price': 150.0,
            'current_price': 155.0,
            'market_value': 15500.0
        }
    ]
    
    monitor.get_exposure_metrics.return_value = {
        'long_exposure': 15500.0,
        'short_exposure': 0.0,
        'net_exposure': 15500.0,
        'gross_exposure': 15500.0,
        'leverage': 0.155
    }
    
    monitor.get_position_concentration.return_value = {
        'AAPL': 0.155
    }
    
    return monitor


@pytest.fixture
def guard(mock_monitor):
    """Create RiskGuard with mock monitor."""
    return RiskGuard(
        account_monitor=mock_monitor,
        max_position_size=50000.0,
        max_position_pct=0.25,
        max_total_positions=20,
        max_drawdown=-0.15,
        max_daily_loss=5000.0,
        max_leverage=2.0
    )


class TestRiskGuardInitialization:
    """Test initialization."""
    
    def test_init_success(self, mock_monitor):
        """Test successful initialization."""
        guard = RiskGuard(mock_monitor)
        
        assert guard.account_monitor is mock_monitor
        assert guard.broker is mock_monitor.broker
        assert guard.max_position_size == 50000.0
        assert guard.max_position_pct == 0.25
        assert guard.max_drawdown == -0.15
        assert guard.circuit_breaker_active is False
    
    def test_init_custom_limits(self, mock_monitor):
        """Test initialization with custom limits."""
        guard = RiskGuard(
            mock_monitor,
            max_position_size=20000.0,
            max_position_pct=0.10,
            max_drawdown=-0.05
        )
        
        assert guard.max_position_size == 20000.0
        assert guard.max_position_pct == 0.10
        assert guard.max_drawdown == -0.05


class TestOrderParameterValidation:
    """Test order parameter validation."""
    
    def test_validate_valid_order(self, guard):
        """Test validation of valid order."""
        guard.validate_order('AAPL', qty=10, side='buy', price=150.0)
        # Should not raise
    
    def test_invalid_symbol_empty(self, guard):
        """Test invalid symbol (empty)."""
        with pytest.raises(InvalidOrderError, match="Invalid symbol"):
            guard.validate_order('', qty=10, side='buy', price=150.0)
    
    def test_invalid_symbol_format(self, guard):
        """Test invalid symbol format."""
        with pytest.raises(InvalidOrderError, match="Invalid symbol format"):
            guard.validate_order('AA@PL', qty=10, side='buy', price=150.0)
    
    def test_invalid_qty_zero(self, guard):
        """Test invalid qty (zero)."""
        with pytest.raises(InvalidOrderError, match="Invalid qty"):
            guard.validate_order('AAPL', qty=0, side='buy', price=150.0)
    
    def test_invalid_qty_negative(self, guard):
        """Test invalid qty (negative)."""
        with pytest.raises(InvalidOrderError, match="Invalid qty"):
            guard.validate_order('AAPL', qty=-10, side='buy', price=150.0)
    
    def test_invalid_side(self, guard):
        """Test invalid side."""
        with pytest.raises(InvalidOrderError, match="Invalid side"):
            guard.validate_order('AAPL', qty=10, side='hold', price=150.0)
    
    def test_invalid_price_zero(self, guard):
        """Test invalid price (zero)."""
        with pytest.raises(InvalidOrderError, match="Invalid price"):
            guard.validate_order('AAPL', qty=10, side='buy', price=0.0)
    
    def test_invalid_price_negative(self, guard):
        """Test invalid price (negative)."""
        with pytest.raises(InvalidOrderError, match="Invalid price"):
            guard.validate_order('AAPL', qty=10, side='buy', price=-150.0)


class TestPositionSizeLimit:
    """Test position size limit."""
    
    def test_position_size_within_limit(self, guard, mock_monitor):
        """Test position size within limit."""
        guard.validate_order('MSFT', qty=50, side='buy', price=350.0)
        # 50 * 350 = 17,500 < 50,000 limit, 17.5% < 25% concentration
    
    def test_position_size_exceeds_limit(self, guard, mock_monitor):
        """Test position size exceeds limit."""
        with pytest.raises(RiskLimitExceeded, match="Position size limit exceeded"):
            guard.validate_order('MSFT', qty=500, side='buy', price=350.0)
            # 500 * 350 = 175,000 > 50,000 limit
    
    def test_position_size_adding_to_existing(self, guard, mock_monitor):
        """Test adding to existing position."""
        # AAPL: currently 100 shares @ 155 = 15,500
        # Adding 50 @ 150 = 7,500
        # Total: 23,000 = 23% < 25% concentration limit
        guard.validate_order('AAPL', qty=50, side='buy', price=150.0)
    
    def test_position_size_exceeds_when_adding(self, guard, mock_monitor):
        """Test position size exceeds when adding to existing."""
        # AAPL: currently 100 shares
        # Adding 400 @ 150 = total 500 * 150 = 75,000 > 50,000 limit
        with pytest.raises(RiskLimitExceeded, match="Position size limit exceeded"):
            guard.validate_order('AAPL', qty=400, side='buy', price=150.0)


class TestConcentrationLimit:
    """Test concentration limit."""
    
    def test_concentration_within_limit(self, guard, mock_monitor):
        """Test concentration within limit."""
        # Portfolio: 100,000
        # New position: 100 * 200 = 20,000 = 20% < 25% limit
        guard.validate_order('TSLA', qty=100, side='buy', price=200.0)
    
    def test_concentration_exceeds_limit(self, guard, mock_monitor):
        """Test concentration exceeds limit."""
        # Portfolio: 100,000
        # New position: 200 * 200 = 40,000 = 40% > 25% limit
        with pytest.raises(RiskLimitExceeded, match="Concentration limit exceeded"):
            guard.validate_order('TSLA', qty=200, side='buy', price=200.0)


class TestTotalPositionsLimit:
    """Test total positions limit."""
    
    def test_positions_within_limit(self, guard, mock_monitor):
        """Test adding position within limit."""
        # Currently 1 position, max 20
        guard.validate_order('MSFT', qty=10, side='buy', price=350.0)
    
    def test_positions_at_limit(self, guard, mock_monitor):
        """Test adding position when at limit."""
        # Set positions to max
        mock_monitor.positions = [
            {'symbol': f'SYM{i}', 'qty': 10, 'current_price': 100.0}
            for i in range(20)
        ]
        
        with pytest.raises(RiskLimitExceeded, match="Total positions limit exceeded"):
            guard.validate_order('NEWSTOCK', qty=10, side='buy', price=100.0)
    
    def test_adding_to_existing_position_ok(self, guard, mock_monitor):
        """Test adding to existing position is OK even at limit."""
        # Set positions to max
        mock_monitor.positions = [
            {'symbol': 'AAPL', 'qty': 100, 'current_price': 155.0}
        ] + [
            {'symbol': f'SYM{i}', 'qty': 10, 'current_price': 100.0}
            for i in range(19)
        ]
        
        # Adding to existing AAPL position should be OK
        guard.validate_order('AAPL', qty=10, side='buy', price=150.0)


class TestLeverageLimit:
    """Test leverage limit."""
    
    def test_leverage_within_limit(self, guard, mock_monitor):
        """Test leverage within limit."""
        # Current gross: 15,500
        # Adding: 100 * 150 = 15,000
        # New gross: 30,500
        # Leverage: 30,500 / 100,000 = 0.305 < 2.0
        guard.validate_order('MSFT', qty=100, side='buy', price=150.0)
    
    def test_leverage_exceeds_limit(self, guard, mock_monitor):
        """Test leverage exceeds limit but fails concentration first."""
        # Current gross: 15,500
        # Adding: 1000 * 100 = 100,000
        # New gross: 115,500
        # Leverage: 115,500 / 100,000 = 1.155 < 2.0
        # But concentration: 100% > 25%
        with pytest.raises(RiskLimitExceeded):
            guard.validate_order('MSFT', qty=1000, side='buy', price=100.0)


class TestDrawdownLimit:
    """Test drawdown circuit breaker."""
    
    def test_drawdown_within_limit(self, guard, mock_monitor):
        """Test drawdown within limit."""
        mock_monitor.current_drawdown = -0.05  # 5% drawdown
        guard.validate_order('AAPL', qty=10, side='buy', price=150.0)
    
    def test_drawdown_exceeds_limit(self, guard, mock_monitor):
        """Test drawdown exceeds limit."""
        mock_monitor.current_drawdown = -0.20  # 20% drawdown > 15% limit
        
        with pytest.raises(CircuitBreakerTriggered, match="Drawdown limit exceeded"):
            guard.validate_order('AAPL', qty=10, side='buy', price=150.0)
        
        assert guard.circuit_breaker_active is True
    
    def test_circuit_breaker_blocks_subsequent_orders(self, guard, mock_monitor):
        """Test circuit breaker blocks subsequent orders."""
        # Trigger circuit breaker
        mock_monitor.current_drawdown = -0.20
        
        with pytest.raises(CircuitBreakerTriggered):
            guard.validate_order('AAPL', qty=10, side='buy', price=150.0)
        
        # Try another order (should be blocked)
        mock_monitor.current_drawdown = 0.0  # Reset drawdown
        
        with pytest.raises(CircuitBreakerTriggered, match="Circuit breaker active"):
            guard.validate_order('MSFT', qty=10, side='buy', price=350.0)


class TestDailyLossLimit:
    """Test daily loss circuit breaker."""
    
    def test_daily_loss_within_limit(self, guard, mock_monitor):
        """Test daily loss within limit."""
        mock_monitor.daily_pnl = -1000.0  # Loss < 5,000 limit
        guard.validate_order('AAPL', qty=10, side='buy', price=150.0)
    
    def test_daily_loss_exceeds_limit(self, guard, mock_monitor):
        """Test daily loss exceeds limit."""
        mock_monitor.daily_pnl = -6000.0  # Loss > 5,000 limit
        
        with pytest.raises(CircuitBreakerTriggered, match="Daily loss limit exceeded"):
            guard.validate_order('AAPL', qty=10, side='buy', price=150.0)
        
        assert guard.circuit_breaker_active is True


class TestCircuitBreaker:
    """Test circuit breaker functionality."""
    
    def test_circuit_breaker_can_be_reset(self, guard, mock_monitor):
        """Test circuit breaker can be manually reset."""
        # Trigger circuit breaker
        mock_monitor.current_drawdown = -0.20
        
        with pytest.raises(CircuitBreakerTriggered):
            guard.validate_order('AAPL', qty=10, side='buy', price=150.0)
        
        assert guard.circuit_breaker_active is True
        
        # Reset
        guard.reset_circuit_breaker()
        
        assert guard.circuit_breaker_active is False
        assert guard.circuit_breaker_reason is None
        
        # Now orders should work (if limits OK)
        mock_monitor.current_drawdown = 0.0
        guard.validate_order('AAPL', qty=10, side='buy', price=150.0)
    
    def test_circuit_breaker_disabled(self, guard, mock_monitor):
        """Test circuit breaker logs warning when disabled."""
        guard.enable_circuit_breaker = False
        
        # This would normally trigger circuit breaker
        mock_monitor.current_drawdown = -0.20
        
        # With circuit breaker disabled, should log warning but not raise
        # (order may still fail other limits, but not circuit breaker)
        guard.validate_order('AAPL', qty=10, side='buy', price=150.0)
        
        # Circuit breaker should NOT be active
        assert guard.circuit_breaker_active is False
    
    def test_circuit_breaker_records_time_and_reason(self, guard, mock_monitor):
        """Test circuit breaker records trigger time and reason."""
        mock_monitor.current_drawdown = -0.20
        
        try:
            guard.validate_order('AAPL', qty=10, side='buy', price=150.0)
        except CircuitBreakerTriggered:
            pass
        
        assert guard.circuit_breaker_triggered_at is not None
        assert isinstance(guard.circuit_breaker_triggered_at, datetime)
        assert guard.circuit_breaker_reason is not None
        assert 'Drawdown' in guard.circuit_breaker_reason


class TestRiskSummary:
    """Test risk summary."""
    
    def test_get_risk_summary(self, guard, mock_monitor):
        """Test risk summary generation."""
        summary = guard.get_risk_summary()
        
        assert 'position_count' in summary
        assert 'largest_position_pct' in summary
        assert 'leverage' in summary
        assert 'drawdown' in summary
        assert 'daily_pnl' in summary
        assert 'circuit_breaker_active' in summary
        
        assert summary['position_count']['current'] == 1
        assert summary['position_count']['max'] == 20
        assert summary['leverage']['max'] == 2.0
        assert summary['drawdown']['max'] == -0.15
    
    def test_risk_summary_with_circuit_breaker(self, guard, mock_monitor):
        """Test risk summary includes circuit breaker status."""
        # Trigger circuit breaker
        mock_monitor.current_drawdown = -0.20
        
        try:
            guard.validate_order('AAPL', qty=10, side='buy', price=150.0)
        except CircuitBreakerTriggered:
            pass
        
        summary = guard.get_risk_summary()
        
        assert summary['circuit_breaker_active'] is True
        assert summary['circuit_breaker_reason'] is not None


class TestPriceEstimation:
    """Test price estimation fallback."""
    
    def test_estimate_price_from_position(self, guard, mock_monitor):
        """Test price estimation uses current position price."""
        # AAPL is in positions at 155.0
        price = guard._estimate_current_price('AAPL')
        assert price == 155.0
    
    def test_estimate_price_fallback(self, guard, mock_monitor):
        """Test price estimation fallback for unknown symbol."""
        price = guard._estimate_current_price('UNKNOWN')
        assert price == 100.0  # Fallback value


class TestRepr:
    """Test string representation."""
    
    def test_repr(self, guard):
        """Test __repr__ output."""
        repr_str = repr(guard)
        
        assert 'RiskGuard' in repr_str
        assert '50,000' in repr_str or '50000' in repr_str
        assert '-15' in repr_str or '0.15' in repr_str
        assert 'False' in repr_str  # circuit breaker not active


class TestRiskScore:
    """Test risk score calculation."""
    
    def test_risk_score_no_positions(self, guard, mock_monitor):
        """Test risk score with no positions."""
        mock_monitor.positions = []
        
        score = guard.get_risk_score()
        
        assert score == 0.0
    
    def test_risk_score_circuit_breaker_active(self, guard, mock_monitor):
        """Test risk score when circuit breaker active."""
        guard.circuit_breaker_active = True
        
        score = guard.get_risk_score()
        
        assert score == 100.0
    
    def test_risk_score_low_risk(self, guard, mock_monitor):
        """Test risk score with low risk portfolio."""
        # Small position, low leverage
        mock_monitor.positions = [
            {'symbol': 'AAPL', 'qty': 10, 'current_price': 155.0, 'market_value': 1550.0}
        ]
        mock_monitor.portfolio_value = 100000.0
        mock_monitor.daily_pnl = 100.0  # Positive
        mock_monitor.current_drawdown = -0.02  # Small drawdown
        
        mock_monitor.get_position_concentration.return_value = {'AAPL': 0.0155}
        mock_monitor.get_exposure_metrics.return_value = {
            'leverage': 0.0155
        }
        
        score = guard.get_risk_score()
        
        assert 0 < score < 30  # Low risk
    
    def test_risk_score_high_risk(self, guard, mock_monitor):
        """Test risk score with high risk portfolio."""
        # Large positions, high leverage, drawdown, loss
        mock_monitor.positions = [
            {'symbol': f'SYM{i}', 'qty': 100, 'current_price': 100.0, 'market_value': 10000.0}
            for i in range(18)
        ]
        mock_monitor.portfolio_value = 100000.0
        mock_monitor.daily_pnl = -4500.0  # Large loss
        mock_monitor.current_drawdown = -0.13  # Large drawdown
        
        mock_monitor.get_position_concentration.return_value = {
            f'SYM{i}': 0.10 for i in range(18)
        }
        mock_monitor.get_exposure_metrics.return_value = {
            'leverage': 1.8
        }
        
        score = guard.get_risk_score()
        
        assert 60 < score < 100  # High risk
    
    def test_risk_score_medium_risk(self, guard, mock_monitor):
        """Test risk score with medium risk portfolio."""
        # AAPL position from fixture (15,500 / 100,000 = 15.5%)
        score = guard.get_risk_score()
        
        assert 10 < score < 50  # Medium risk


class TestEdgeCases:
    """Test edge cases."""
    
    def test_validate_order_no_price(self, guard, mock_monitor):
        """Test validation with no price specified."""
        # Should use price estimation
        guard.validate_order('AAPL', qty=10, side='buy', price=None)
    
    def test_validate_sell_order(self, guard, mock_monitor):
        """Test validation of sell order."""
        # Selling existing AAPL position
        guard.validate_order('AAPL', qty=50, side='sell', price=155.0)
    
    def test_validate_order_updates_monitor(self, guard, mock_monitor):
        """Test validation calls monitor.update()."""
        guard.validate_order('AAPL', qty=10, side='buy', price=150.0)
        
        mock_monitor.update.assert_called()


# --- Contrôle PRÉ-TRADE au niveau portefeuille (corrélation-aware) -----------

def _close_panel(vol: float, n: int = 200, k: int = 6, seed: int = 0,
                 common: float = 0.0) -> pd.DataFrame:
    """Panel de clôtures ; ``common`` injecte un facteur commun (corrélation)."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    mkt = rng.normal(0, vol, n)
    cols = {}
    for j in range(k):
        r = common * mkt + (1 - common) * rng.normal(0, vol, n)
        cols[f"S{j}"] = 100 * np.exp(np.cumsum(r))
    return pd.DataFrame(cols, index=idx)


def _guard(monitor, **kw):
    return RiskGuard(account_monitor=monitor, **kw)


def test_validate_portfolio_effective_bets_blocks_concentration(mock_monitor):
    """Un book concentré (peu de paris effectifs) est refusé."""
    guard = _guard(mock_monitor, min_effective_bets=3.0)
    with pytest.raises(RiskLimitExceeded, match="paris"):
        guard.validate_portfolio({"S0": 0.8, "S1": 0.2}, None)  # 1/(.68+.04) ≈ 1.4


def test_validate_portfolio_diversified_book_passes(mock_monitor):
    guard = _guard(mock_monitor, min_effective_bets=3.0)
    w = {f"S{i}": 1 / 6 for i in range(6)}  # nombre effectif de paris = 6
    diag = guard.validate_portfolio(w, None)
    assert diag["effective_bets"] == pytest.approx(6.0, abs=1e-6)


def test_validate_portfolio_vol_limit_blocks_risky_book(mock_monitor):
    """Un book très volatil (vol ex-ante élevée) dépasse la limite -> refus."""
    guard = _guard(mock_monitor, max_portfolio_vol=0.15)
    close = _close_panel(vol=0.04, common=0.8, seed=1)  # corrélé + volatil
    w = {c: 1 / close.shape[1] for c in close.columns}
    with pytest.raises(RiskLimitExceeded, match="Vol ex-ante"):
        guard.validate_portfolio(w, close)


def test_validate_portfolio_calm_book_within_vol_limit(mock_monitor):
    guard = _guard(mock_monitor, max_portfolio_vol=0.60)
    close = _close_panel(vol=0.006, common=0.0, seed=2)  # calme, décorrélé
    w = {c: 1 / close.shape[1] for c in close.columns}
    diag = guard.validate_portfolio(w, close)  # ne lève pas
    assert diag["ex_ante_vol"] is not None and diag["ex_ante_vol"] < 0.60
    assert diag["var_95_1d"] is not None


def test_validate_portfolio_var_limit(mock_monitor):
    guard = _guard(mock_monitor, max_var_95=0.005)  # 0.5% 1j : très serré
    close = _close_panel(vol=0.03, common=0.5, seed=3)
    w = {c: 1 / close.shape[1] for c in close.columns}
    with pytest.raises(RiskLimitExceeded, match="VaR"):
        guard.validate_portfolio(w, close)


def test_validate_portfolio_abstains_without_prices(mock_monitor):
    """Sans panel de prix, les limites vol/VaR s'abstiennent (pas de faux rejet)."""
    guard = _guard(mock_monitor, max_portfolio_vol=0.01, max_var_95=0.001)
    diag = guard.validate_portfolio({f"S{i}": 1 / 6 for i in range(6)}, None)
    assert diag["ex_ante_vol"] is None and diag["var_95_1d"] is None
    assert diag["effective_bets"] == pytest.approx(6.0, abs=1e-6)


def test_validate_portfolio_no_limits_is_noop(mock_monitor):
    """Aucune limite portefeuille configurée -> jamais de rejet (rétro-compat)."""
    guard = _guard(mock_monitor)  # défauts : toutes les limites portefeuille None
    close = _close_panel(vol=0.05, common=0.9, seed=4)
    w = {c: 1 / close.shape[1] for c in close.columns}
    guard.validate_portfolio(w, close)  # ne lève pas
    assert guard.validate_portfolio({}, None) == {
        "ex_ante_vol": None, "var_95_1d": None, "effective_bets": None}

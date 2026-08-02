# 🚀 PHASE 6.2 : ACCOUNT MONITOR + RISK GUARD - PROMPT COPILOT COMPLET

**Date** : 9 novembre 2025, 12:04 CET  
**Phase précédente** : 6.1 (Broker Adapters) ✅ COMPLÈTE  
**Phase actuelle** : 6.2 (Account Monitor + Risk Guard) - 2 JOURS  
**Durée** : Jour 4-5

---

## 📋 PHASE 6.2 OBJECTIFS

**Livrables** :
- `src/trading/account_monitor.py` (400 LOC)
- `src/trading/risk_guard.py` (350 LOC)
- `tests/trading/test_account_monitor.py` (250 LOC)
- `tests/trading/test_risk_guard.py` (300 LOC)

**Intégration** :
- ✅ Utilise `BrokerAdapter` (de Phase 6.1)
- ✅ Tracking temps réel portfolio
- ✅ Pre-trade risk checks (circuit breakers)

---

## 📝 PROMPT COPILOT - PHASE 6.2 COMPLET

### **⏰ JOUR 4 MATIN : AccountMonitor**

Copie ce prompt ENTIER à Copilot :

```
PHASE 6.2 JOUR 4 : ACCOUNT MONITOR - PORTFOLIO TRACKING

Génère 2 fichiers complets :

================================================================================
FILE 1 : src/financial_analyzer/trading/account_monitor.py (400 LOC)
================================================================================

\"\"\"
Account Monitor - Track portfolio state in real-time.

Features:
- Get portfolio value, cash, equity, positions
- Track P&L (daily, cumulative, per position)
- Position concentration analysis
- Drawdown tracking (current, max)
- Exposure metrics (long, short, net, gross)
- Historical tracking

Integrates with BrokerAdapter for real-time data.
Uses logging module (import logging, NOT financial_analyzer.utils.helpers).
\"\"\"

from __future__ import annotations
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import pandas as pd
import logging
from collections import deque

logger = logging.getLogger(__name__)

from .broker_adapter import BrokerAdapter


class AccountMonitor:
    \"\"\"
    Monitor account state and performance in real-time.
    
    Example:
        >>> from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
        >>> adapter = AlpacaAdapter(api_key='...', secret_key='...', mode='paper')
        >>> adapter.connect()
        >>> monitor = AccountMonitor(adapter, initial_capital=100000)
        >>> monitor.update()  # Fetch latest from broker
        >>> print(f\"Portfolio: ${monitor.portfolio_value:.2f}\")
        >>> print(f\"Daily P&L: ${monitor.daily_pnl:.2f}\")
        >>> print(f\"Max DD: {monitor.max_drawdown:.2%}\")
    \"\"\"
    
    def __init__(
        self,
        broker_adapter: BrokerAdapter,
        initial_capital: float = 100000.0,
        track_history: bool = True,
        max_history_size: int = 5000
    ) -> None:
        \"\"\"
        Initialize account monitor.
        
        Args:
            broker_adapter: Connected BrokerAdapter instance
            initial_capital: Initial capital for drawdown calculation (default: 100,000)
            track_history: Track historical portfolio values (default: True)
            max_history_size: Max history entries to keep (default: 5,000)
        
        Raises:
            ValueError: If broker_adapter not connected
        \"\"\"
        if not broker_adapter.connected:
            raise ValueError(\"BrokerAdapter must be connected. Call connect() first.\")
        
        self.broker = broker_adapter
        self.initial_capital = initial_capital
        self.track_history = track_history
        self.max_history_size = max_history_size
        
        # Current state
        self.portfolio_value: float = initial_capital
        self.cash: float = initial_capital
        self.equity: float = initial_capital
        self.positions: List[Dict] = []
        
        # P&L tracking
        self.daily_pnl: float = 0.0
        self.cumulative_pnl: float = 0.0
        self.last_portfolio_value: float = initial_capital
        
        # Drawdown tracking
        self.peak_value: float = initial_capital
        self.current_drawdown: float = 0.0
        self.max_drawdown: float = 0.0
        
        # History (deque for memory efficiency)
        self.history: deque = deque(maxlen=max_history_size) if track_history else None
        
        # Last update
        self.last_update: Optional[datetime] = None
        
        logger.info(
            f\"AccountMonitor initialized: "
            f\"initial_capital=${initial_capital:.2f}, "
            f\"tracking={'enabled' if track_history else 'disabled'}\"
        )
    
    def update(self) -> None:
        \"\"\"
        Update account state from broker.
        
        Fetches latest account info and positions from broker.
        Updates P&L, drawdown, and history.
        
        Raises:
            BrokerAPIError: If broker connection fails
        \"\"\"
        try:
            # Fetch account info
            account = self.broker.get_account()
            self.cash = account['cash']
            self.equity = account['equity']
            self.portfolio_value = account['portfolio_value']
            
            # Fetch positions
            self.positions = self.broker.get_positions()
            
            # Calculate P&L
            if self.last_portfolio_value is not None:
                self.daily_pnl = self.portfolio_value - self.last_portfolio_value
            
            self.cumulative_pnl = self.portfolio_value - self.initial_capital
            
            # Update drawdown
            if self.portfolio_value > self.peak_value:
                self.peak_value = self.portfolio_value
                logger.debug(f\"New peak: ${self.peak_value:.2f}\")
            
            self.current_drawdown = (self.portfolio_value - self.peak_value) / self.peak_value if self.peak_value > 0 else 0.0
            
            # Update max drawdown (more negative = worse)
            if self.current_drawdown < self.max_drawdown:
                self.max_drawdown = self.current_drawdown
                logger.warning(f\"New max drawdown: {self.max_drawdown:.2%}\")
            
            # Track history
            if self.track_history and self.history is not None:
                self.history.append({
                    'timestamp': datetime.now(),
                    'portfolio_value': self.portfolio_value,
                    'cash': self.cash,
                    'equity': self.equity,
                    'daily_pnl': self.daily_pnl,
                    'cumulative_pnl': self.cumulative_pnl,
                    'current_drawdown': self.current_drawdown,
                    'num_positions': len(self.positions)
                })
            
            # Update last values
            self.last_portfolio_value = self.portfolio_value
            self.last_update = datetime.now()
            
            logger.debug(
                f\"Portfolio updated: ${self.portfolio_value:.2f} "
                f\"(daily: ${self.daily_pnl:+.2f}, cumulative: ${self.cumulative_pnl:+.2f}, "
                f\"dd: {self.current_drawdown:.2%})\"
            )
        
        except Exception as e:
            logger.error(f\"Failed to update account monitor: {e}\", exc_info=True)
            raise
    
    def get_position_concentration(self) -> Dict[str, float]:
        \"\"\"
        Get position concentration (weight of each position).
        
        Returns:
            Dict mapping symbol to weight (0-1)
        
        Example:
            >>> monitor.update()
            >>> conc = monitor.get_position_concentration()
            >>> print(conc)  # {'AAPL': 0.15, 'MSFT': 0.20, ...}
        \"\"\"
        if self.portfolio_value <= 0:
            return {}
        
        concentration = {}
        for pos in self.positions:
            weight = abs(pos['market_value']) / self.portfolio_value
            concentration[pos['symbol']] = weight
        
        return concentration
    
    def get_exposure_metrics(self) -> Dict:
        \"\"\"
        Get exposure metrics (long, short, net, gross).
        
        Returns:
            Dict with keys:
            - long_exposure: Long market value
            - short_exposure: Short market value  
            - net_exposure: Net market value (long - short)
            - gross_exposure: Gross market value (long + short)
            - leverage: Gross / portfolio_value
            - long_pct: Long / portfolio %
            - short_pct: Short / portfolio %
        \"\"\"
        long_value = sum(pos['market_value'] for pos in self.positions if pos['qty'] > 0)
        short_value = sum(abs(pos['market_value']) for pos in self.positions if pos['qty'] < 0)
        
        pv = self.portfolio_value if self.portfolio_value > 0 else 1
        
        return {
            'long_exposure': long_value,
            'short_exposure': short_value,
            'net_exposure': long_value - short_value,
            'gross_exposure': long_value + short_value,
            'leverage': (long_value + short_value) / pv,
            'long_pct': long_value / pv * 100 if pv > 0 else 0,
            'short_pct': short_value / pv * 100 if pv > 0 else 0
        }
    
    def get_position_pnl(self) -> Dict[str, Dict]:
        \"\"\"
        Get P&L per position.
        
        Returns:
            Dict mapping symbol to P&L metrics:
            - unrealized_pl: Unrealized P&L in USD
            - unrealized_plpc: Unrealized P&L percent
            - qty: Position quantity
            - avg_entry_price: Average entry price
            - current_price: Current market price
        \"\"\"
        position_pnl = {}
        for pos in self.positions:
            position_pnl[pos['symbol']] = {
                'unrealized_pl': pos['unrealized_pl'],
                'unrealized_plpc': pos['unrealized_plpc'],
                'qty': pos['qty'],
                'avg_entry_price': pos['avg_entry_price'],
                'current_price': pos['current_price'],
                'market_value': pos['market_value']
            }
        
        return position_pnl
    
    def get_summary(self) -> Dict:
        \"\"\"
        Get account summary (all key metrics).
        
        Returns:
            Dict with all key metrics
        \"\"\"
        return {
            'timestamp': self.last_update,
            'portfolio_value': self.portfolio_value,
            'cash': self.cash,
            'equity': self.equity,
            'initial_capital': self.initial_capital,
            'daily_pnl': self.daily_pnl,
            'cumulative_pnl': self.cumulative_pnl,
            'daily_return_pct': self.daily_pnl / self.last_portfolio_value * 100 if self.last_portfolio_value > 0 else 0,
            'cumulative_return_pct': self.cumulative_pnl / self.initial_capital * 100 if self.initial_capital > 0 else 0,
            'current_drawdown': self.current_drawdown,
            'max_drawdown': self.max_drawdown,
            'peak_value': self.peak_value,
            'num_positions': len(self.positions),
            'concentration': self.get_position_concentration(),
            'exposure': self.get_exposure_metrics(),
            'position_pnl': self.get_position_pnl()
        }
    
    def get_history_df(self) -> pd.DataFrame:
        \"\"\"
        Get history as DataFrame.
        
        Returns:
            DataFrame with columns: timestamp, portfolio_value, cash, equity, daily_pnl, etc.
        
        Example:
            >>> monitor.update()  # Multiple times...
            >>> df = monitor.get_history_df()
            >>> df.to_csv('portfolio_history.csv')
        \"\"\"
        if not self.history:
            return pd.DataFrame()
        
        return pd.DataFrame(list(self.history)).set_index('timestamp')
    
    def reset_stats(self) -> None:
        \"\"\"Reset tracking stats (but keep current position).\"\"\"
        self.daily_pnl = 0.0
        self.last_portfolio_value = self.portfolio_value
        logger.info(\"Tracking stats reset\")
    
    def __repr__(self) -> str:
        \"\"\"String representation for debugging.\"\"\"
        return (
            f\"AccountMonitor(portfolio=${self.portfolio_value:.2f}, \"
            f\"positions={len(self.positions)}, \"
            f\"dd={self.current_drawdown:.2%})\"
        )


================================================================================
FILE 2 : tests/trading/test_account_monitor.py (250 LOC)
================================================================================

\"\"\"
Tests for AccountMonitor.

Tests real-time portfolio tracking, P&L calculation, drawdown tracking.
Uses mock BrokerAdapter (no real API calls).
\"\"\"

from __future__ import annotations
import pytest
from unittest.mock import Mock
from datetime import datetime
import pandas as pd
from financial_analyzer.trading.account_monitor import AccountMonitor
from financial_analyzer.trading.broker_adapter import BrokerAPIError


@pytest.fixture
def mock_broker():
    \"\"\"Mock broker adapter.\"\"\"
    broker = Mock()
    broker.connected = True
    broker.get_account.return_value = {
        'cash': 50000.0,
        'equity': 100000.0,
        'portfolio_value': 100000.0
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
    \"\"\"Create AccountMonitor with mock broker.\"\"\"
    return AccountMonitor(mock_broker, initial_capital=100000.0)


class TestAccountMonitorInitialization:
    \"\"\"Test initialization.\"\"\"
    
    def test_init_success(self, mock_broker):
        \"\"\"Test successful initialization.\"\"\"
        monitor = AccountMonitor(mock_broker, initial_capital=100000)
        
        assert monitor.broker is mock_broker
        assert monitor.initial_capital == 100000
        assert monitor.portfolio_value == 100000
        assert monitor.daily_pnl == 0.0
        assert monitor.max_drawdown == 0.0
    
    def test_init_disconnected_broker_raises(self):
        \"\"\"Test initialization with disconnected broker raises error.\"\"\"
        mock_broker = Mock()
        mock_broker.connected = False
        
        with pytest.raises(ValueError, match=\"must be connected\"):
            AccountMonitor(mock_broker)


class TestAccountMonitorUpdate:
    \"\"\"Test update functionality.\"\"\"
    
    def test_update_state(self, monitor, mock_broker):
        \"\"\"Test update fetches latest state.\"\"\"
        monitor.update()
        
        assert monitor.portfolio_value == 100000.0
        assert monitor.cash == 50000.0
        assert monitor.equity == 100000.0
        assert len(monitor.positions) == 2
        assert monitor.last_update is not None
    
    def test_calculate_pnl(self, monitor, mock_broker):
        \"\"\"Test P&L calculation.\"\"\"
        monitor.last_portfolio_value = 95000.0
        monitor.portfolio_value = 100000.0
        monitor.update()
        
        assert monitor.daily_pnl == 5000.0
        assert monitor.cumulative_pnl == 0.0  # relative to initial
    
    def test_update_drawdown(self, monitor):
        \"\"\"Test drawdown tracking.\"\"\"
        # Portfolio increases
        monitor.broker.get_account.return_value['portfolio_value'] = 110000.0
        monitor.update()
        assert monitor.peak_value == 110000.0
        
        # Portfolio decreases
        monitor.broker.get_account.return_value['portfolio_value'] = 90000.0
        monitor.update()
        assert monitor.current_drawdown == pytest.approx(-1.0 / 11, rel=1e-2)
        assert monitor.max_drawdown == pytest.approx(-1.0 / 11, rel=1e-2)


class TestAccountMonitorMetrics:
    \"\"\"Test metric calculations.\"\"\"
    
    def test_position_concentration(self, monitor):
        \"\"\"Test position concentration.\"\"\"
        monitor.update()
        conc = monitor.get_position_concentration()
        
        assert 'AAPL' in conc
        assert 'MSFT' in conc
        assert conc['AAPL'] == pytest.approx(0.155, rel=1e-2)
        assert conc['MSFT'] == pytest.approx(0.19, rel=1e-2)
    
    def test_exposure_metrics(self, monitor):
        \"\"\"Test exposure metrics.\"\"\"
        monitor.update()
        exposure = monitor.get_exposure_metrics()
        
        assert exposure['long_exposure'] == 34500.0
        assert exposure['short_exposure'] == 0.0
        assert exposure['net_exposure'] == 34500.0
        assert exposure['gross_exposure'] == 34500.0
        assert exposure['leverage'] == pytest.approx(0.345, rel=1e-2)
    
    def test_position_pnl(self, monitor):
        \"\"\"Test per-position P&L.\"\"\"
        monitor.update()
        pnl = monitor.get_position_pnl()
        
        assert pnl['AAPL']['unrealized_pl'] == 500.0
        assert pnl['MSFT']['unrealized_pl'] == 1000.0
        assert pnl['AAPL']['qty'] == 100
    
    def test_summary(self, monitor):
        \"\"\"Test summary generation.\"\"\"
        monitor.update()
        summary = monitor.get_summary()
        
        assert 'portfolio_value' in summary
        assert 'daily_pnl' in summary
        assert 'exposure' in summary
        assert 'position_pnl' in summary
        assert summary['num_positions'] == 2


class TestAccountMonitorHistory:
    \"\"\"Test history tracking.\"\"\"
    
    def test_history_tracking_enabled(self, monitor):
        \"\"\"Test history is tracked when enabled.\"\"\"
        monitor.update()
        monitor.update()
        monitor.update()
        
        assert len(monitor.history) == 3
    
    def test_history_df(self, monitor):
        \"\"\"Test history as DataFrame.\"\"\"
        monitor.update()
        monitor.update()
        
        df = monitor.get_history_df()
        
        assert isinstance(df, pd.DataFrame)
        assert len(df) == 2
        assert 'portfolio_value' in df.columns
        assert 'daily_pnl' in df.columns
    
    def test_history_max_size(self):
        \"\"\"Test history max size enforced.\"\"\"
        mock_broker = Mock()
        mock_broker.connected = True
        mock_broker.get_account.return_value = {
            'cash': 50000, 'equity': 100000, 'portfolio_value': 100000
        }
        mock_broker.get_positions.return_value = []
        
        monitor = AccountMonitor(mock_broker, max_history_size=5)
        
        for _ in range(10):
            monitor.update()
        
        assert len(monitor.history) == 5  # Capped at max_history_size


class TestAccountMonitorReset:
    \"\"\"Test reset functionality.\"\"\"
    
    def test_reset_stats(self, monitor):
        \"\"\"Test stats reset.\"\"\"
        monitor.daily_pnl = 1000.0
        monitor.reset_stats()
        
        assert monitor.daily_pnl == 0.0
        assert monitor.last_portfolio_value == monitor.portfolio_value
```

---

## ⏰ JOUR 4 APRÈS-MIDI : Risk Guard

**Utilise ce 2ème prompt pour Copilot (ne pas combiner)** :

```
PHASE 6.2 JOUR 4 APRÈS-MIDI : RISK GUARD - PRE-TRADE RISK CHECKS

Génère 2 fichiers complets :

[Voir PHASE6.2-6.3_PROMPTS.md document [139] pour prompt complet Risk Guard]

Structure identique à Account Monitor :
- risk_guard.py (350 LOC)
- test_risk_guard.py (300 LOC)
```

---

## ✅ CHECKLIST JOUR 4-5

### **JOUR 4 MATIN (4h) : AccountMonitor**
- [ ] Copy-paste prompt ci-dessus à Copilot
- [ ] Générer `account_monitor.py` (400 LOC)
- [ ] Review + correctifs
- [ ] Commit : `git commit -m "feat: Add AccountMonitor"`

### **JOUR 4 APRÈS-MIDI (4h) : Tests AccountMonitor**
- [ ] Copy-paste test prompt à Copilot
- [ ] Générer `test_account_monitor.py` (250 LOC)
- [ ] Run tests : `pytest tests/trading/test_account_monitor.py -v`
- [ ] Fix errors
- [ ] Commit : `git commit -m "test: Add AccountMonitor tests"`

### **JOUR 5 MATIN (4h) : RiskGuard**
- [ ] Copy-paste risk guard prompt (voir [139])
- [ ] Générer `risk_guard.py` (350 LOC)
- [ ] Review intégration avec AccountMonitor
- [ ] Commit : `git commit -m "feat: Add RiskGuard"`

### **JOUR 5 APRÈS-MIDI (4h) : Tests RiskGuard**
- [ ] Générer `test_risk_guard.py` (300 LOC)
- [ ] Run all trading tests : `pytest tests/trading/ -v --cov`
- [ ] Coverage > 90%
- [ ] **MILESTONE** : Phase 6.2 COMPLETE ✅

---

## 🎯 POINTS CRITIQUES

### **AccountMonitor : Intégration BrokerAdapter**
- ✅ Utilise `broker.get_account()` et `broker.get_positions()`
- ✅ Logging correct (import logging, pas get_logger)
- ✅ Gestion erreurs API gracieuse
- ✅ History avec deque (memory efficient)

### **RiskGuard : Validations strictes**
- ✅ Validation qty > 0
- ✅ Validation symbol format (utiliser _validate_symbol de BrokerAdapter)
- ✅ Circuit breaker state management
- ✅ Tous les exceptions custom définies

---

## 📊 APRÈS JOUR 5

**Phase 6.2 COMPLÈTE** :
- ✅ AccountMonitor (400 LOC + 250 tests)
- ✅ RiskGuard (350 LOC + 300 tests)
- ✅ Integration test avec BrokerAdapter
- ✅ 90%+ coverage

**Next** : Phase 6.3 (LiveTradingPipeline) - 2 jours

---

## 🚀 PRÊT À LANCER !

Copie ce prompt à Copilot et c'est parti ! 🎉
```

---

## 📄 DOCUMENTS RÉFÉRENCES

Pour prompt Risk Guard complet, ouvrir : [PHASE6.2-6.3_PROMPTS.md](code_file:139)

---

**GO PHASE 6.2 !** 🚀

# Trading Module

Module de trading pour FinBot - Phase 6.1 : Broker Adapters

## 📦 Overview

Ce module fournit une interface uniforme pour interagir avec différents brokers (Alpaca, Interactive Brokers, etc.) pour paper trading et live trading.

## 🎯 Features

- ✅ **BrokerAdapter** : Abstract base class pour tous les brokers
- ✅ **AlpacaAdapter** : Implementation complète pour Alpaca Trading API
- ✅ **IBAdapter** : Stub pour Interactive Brokers (à implémenter)
- ✅ Support Paper & Live trading
- ✅ Market & Limit orders
- ✅ Account management
- ✅ Position tracking
- ✅ Historical data
- ✅ Error handling robuste
- ✅ Logging complet

## 🚀 Quick Start

### Installation

```bash
pip install alpaca-trade-api pandas python-dotenv
```

### Configuration

Créer un fichier `.env` à la racine du projet :

```bash
ALPACA_API_KEY=your_api_key
ALPACA_SECRET_KEY=your_secret_key
BROKER_MODE=paper
```

### Usage

```python
from financial_analyzer.trading import AlpacaAdapter
import os

# Initialize adapter
adapter = AlpacaAdapter(
    api_key=os.getenv('ALPACA_API_KEY'),
    secret_key=os.getenv('ALPACA_SECRET_KEY'),
    mode='paper'
)

# Connect to broker
adapter.connect()

# Get account information
account = adapter.get_account()
print(f"Cash: ${account['cash']:.2f}")
print(f"Equity: ${account['equity']:.2f}")
print(f"Buying Power: ${account['buying_power']:.2f}")

# Submit a market order
order = adapter.submit_order(
    symbol='AAPL',
    qty=10,
    side='buy',
    order_type='market'
)
print(f"Order ID: {order['order_id']}")
print(f"Status: {order['status']}")

# Get current positions
positions = adapter.get_positions()
for pos in positions:
    print(f"{pos['symbol']}: {pos['qty']} shares @ ${pos['current_price']:.2f}")

# Get historical bars
from datetime import datetime, timedelta
end = datetime.now()
start = end - timedelta(days=30)
bars = adapter.get_bars('AAPL', start, end, timeframe='1D')
print(bars.tail())

# Disconnect
adapter.disconnect()
```

## 📚 API Reference

### BrokerAdapter (Abstract Base Class)

Base class pour tous les broker adapters.

#### Methods

- `connect()` : Établir connexion au broker
- `disconnect()` : Fermer connexion
- `submit_order(symbol, qty, side, order_type, limit_price, time_in_force)` : Soumettre ordre
- `cancel_order(order_id)` : Annuler ordre
- `get_account()` : Obtenir informations compte
- `get_positions()` : Obtenir positions actuelles
- `get_orders(status, limit)` : Obtenir ordres
- `get_bars(symbol, start, end, timeframe)` : Obtenir données historiques
- `is_market_open()` : Vérifier si marché ouvert

### AlpacaAdapter

Implementation pour Alpaca Trading API.

#### Parameters

- `api_key` (str) : Alpaca API key
- `secret_key` (str) : Alpaca secret key
- `mode` (Literal['paper', 'live']) : Trading mode (default: 'paper')
- `base_url` (Optional[str]) : Custom base URL (default: auto)

#### Example

```python
from financial_analyzer.trading import AlpacaAdapter

adapter = AlpacaAdapter(
    api_key='PKxxxxxxxxxx',
    secret_key='xxxxxxxxxx',
    mode='paper'
)
adapter.connect()
```

### Exceptions

- `BrokerAPIError` : Erreur API broker générique
- `InsufficientFundsError` : Fonds insuffisants
- `OrderNotFoundError` : Ordre non trouvé

## 🧪 Testing

### Run Tests

```bash
# All tests
pytest tests/trading/ -v

# With coverage
pytest tests/trading/ --cov=src/financial_analyzer/trading --cov-report=term-missing

# Specific test
pytest tests/trading/test_alpaca_adapter.py::TestConnection -v
```

### Test Results

```
31 tests - 100% passing
83% coverage
0.61s execution time
```

## 📖 Documentation

- **PHASE6.1_DELIVERY_REPORT.md** : Rapport de livraison complet
- **TESTING_ALPACA_GUIDE.md** : Guide de test manuel
- **PHASE6.1_ARCHITECTURE.md** : Diagrammes d'architecture
- **PHASE6.1_SUMMARY.md** : Résumé de la phase

## 🔗 Resources

- [Alpaca Trading API](https://alpaca.markets/docs/)
- [alpaca-trade-api Python SDK](https://github.com/alpacahq/alpaca-trade-api-python)
- [Alpaca Paper Trading](https://alpaca.markets/docs/trading/paper-trading/)

## 📝 Examples

Voir `examples/alpaca_trading_example.py` pour un exemple complet d'utilisation.

```bash
python examples/alpaca_trading_example.py
```

## ⚠️ Important Notes

### Paper vs Live Trading

Par défaut, le mode est `paper` (argent virtuel). Pour passer en mode `live` :

1. Obtenir des API keys live d'Alpaca
2. Modifier `.env` : `BROKER_MODE=live`
3. ⚠️ **ATTENTION : ARGENT RÉEL - SOYEZ PRUDENT !**

### Limitations Actuelles

- Stop/Stop-limit orders : Non implémenté
- Trailing stop orders : Non implémenté
- Bracket orders : Non implémenté
- IBAdapter : Stub uniquement (à implémenter)

## 🗺️ Roadmap

### Phase 6.2 (Prochaine)
- AccountMonitor : Real-time tracking
- RiskGuard : Pre-trade validation
- OrderManager : Lifecycle management

### Phase 6.3+
- Live Pipeline Integration
- Stop/Stop-limit orders
- Trailing stops
- Bracket orders
- Websocket streaming
- IBAdapter implementation

## 🤝 Contributing

Voir `PHASE6_PAPER_TRADING_PLAN.md` pour le plan complet de développement.

## 📄 License

Voir LICENSE file à la racine du projet.

---

**Status** : ✅ Production Ready  
**Version** : 1.0.0 (Phase 6.1)  
**Last Updated** : 9 novembre 2025

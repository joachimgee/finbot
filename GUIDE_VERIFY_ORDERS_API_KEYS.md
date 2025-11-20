# ✅ GUIDE COMPLET : VERIFICATION ORDRES ALPACA + CONFIGURATION API KEYS

**Date** : 9 novembre 2025, 13:58 CET  
**Sujets** :
1. Comment vérifier les ordres réellement exécutés sur Alpaca
2. Configuration .env pour toutes les API keys
3. Debugging ordres qui ne s'exécutent pas
4. Checklist complète

---

## 🎯 QUESTION 1 : COMMENT VÉRIFIER QUE LES ORDRES SONT EXÉCUTÉS ?

### **Option 1 : Dashboard Alpaca Paper Trading** ✅ (MEILLEUR)

**Accès** :
1. Aller à : https://app.alpaca.markets/paper/dashboard
2. Login avec vos credentials Alpaca
3. Aller à "Orders" ou "Trade History"
4. **Vérifier** :
   - ✅ Ordres apparaissent (status : "filled", "pending", "cancelled")
   - ✅ Quantité correcte
   - ✅ Prix raisonnables
   - ✅ Timestamp correct

**Ordres visibles si** :
- ✅ API keys corrects
- ✅ `broker.connected = True`
- ✅ Ordres générés par pipeline
- ✅ `submit_order()` appelé avec succès

---

### **Option 2 : Script de Vérification** ✅ (BEST PRACTICE)

**Créer** : `scripts/verify_alpaca_orders.py`

```python
#!/usr/bin/env python3
"""
Verify Alpaca orders and positions.
"""

import os
import sys
from datetime import datetime, timedelta
from tabulate import tabulate

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter


def main():
    """Main verification script."""
    print("\n" + "="*80)
    print("  ALPACA ORDERS & POSITIONS VERIFICATION")
    print("="*80 + "\n")
    
    # Get credentials
    api_key = os.getenv('ALPACA_API_KEY')
    api_secret = os.getenv('ALPACA_SECRET_KEY')
    
    if not api_key or not api_secret:
        print("❌ ERROR: ALPACA_API_KEY or ALPACA_SECRET_KEY not set!")
        print("   Set them in .env file and try again")
        sys.exit(1)
    
    # Connect to Alpaca
    try:
        adapter = AlpacaAdapter(
            api_key=api_key,
            api_secret=api_secret,
            paper=True  # Paper trading
        )
        adapter.connect()
        print(f"✅ Connected to Alpaca Paper Trading\n")
    except Exception as e:
        print(f"❌ Failed to connect: {e}")
        sys.exit(1)
    
    # Get account info
    try:
        account = adapter.get_account()
        print("📊 ACCOUNT SUMMARY")
        print("-" * 80)
        account_data = [
            ["Portfolio Value", f"${account['portfolio_value']:,.2f}"],
            ["Cash", f"${account['cash']:,.2f}"],
            ["Equity", f"${account['equity']:,.2f}"],
            ["Buying Power", f"${account['buying_power']:,.2f}"],
            ["Day Trade Count", f"{account.get('daytrade_count', 0)}"],
        ]
        print(tabulate(account_data, tablefmt="grid"))
        print()
    except Exception as e:
        print(f"❌ Failed to get account: {e}\n")
    
    # Get positions
    try:
        positions = adapter.get_positions()
        
        if positions:
            print("📈 CURRENT POSITIONS")
            print("-" * 80)
            positions_data = []
            for pos in positions:
                positions_data.append([
                    pos['symbol'],
                    f"{pos['qty']}",
                    f"${pos['current_price']:.2f}",
                    f"${pos.get('market_value', 0):,.2f}",
                    f"${pos.get('unrealized_pl', 0):,.2f}",
                    f"{pos.get('unrealized_plpc', 0)*100:.2f}%"
                ])
            
            print(tabulate(
                positions_data,
                headers=["Symbol", "Qty", "Price", "Market Val", "P&L", "P&L %"],
                tablefmt="grid"
            ))
            print()
        else:
            print("⚠️  No open positions\n")
    except Exception as e:
        print(f"❌ Failed to get positions: {e}\n")
    
    # Get recent orders
    try:
        # Get orders from last 24 hours
        since = (datetime.utcnow() - timedelta(days=1)).isoformat()
        
        # Note: Alpaca API call (using REST if available)
        print("📋 RECENT ORDERS (last 24h)")
        print("-" * 80)
        
        try:
            # Try to get orders if method available
            orders = adapter.rest_client.list_orders(
                status='all',
                limit=20,
                after=since
            )
            
            if orders:
                orders_data = []
                for order in orders:
                    orders_data.append([
                        order.symbol,
                        order.qty,
                        order.side.upper(),
                        order.status.upper(),
                        order.filled_qty or 0,
                        f"${order.filled_avg_price:.2f}" if order.filled_avg_price else "N/A",
                        order.created_at.strftime("%H:%M:%S")
                    ])
                
                print(tabulate(
                    orders_data,
                    headers=["Symbol", "Qty", "Side", "Status", "Filled", "Fill Price", "Time"],
                    tablefmt="grid"
                ))
                
                # Summary
                total = len(orders)
                filled = sum(1 for o in orders if o.status == 'filled')
                pending = sum(1 for o in orders if o.status == 'pending')
                cancelled = sum(1 for o in orders if o.status == 'cancelled')
                
                print(f"\n  Total: {total} | Filled: {filled} | Pending: {pending} | Cancelled: {cancelled}")
                print()
            else:
                print("No orders in last 24 hours\n")
        
        except AttributeError:
            print("⚠️  Orders API not available (use dashboard instead)\n")
    
    except Exception as e:
        print(f"❌ Failed to get orders: {e}\n")
    
    # Summary
    print("="*80)
    print("✅ VERIFICATION COMPLETE")
    print("="*80)
    print("\n💡 TIPS:")
    print("  • Check dashboard: https://app.alpaca.markets/paper/dashboard")
    print("  • Verify API keys in .env file")
    print("  • Check logs: tail -f logs/live_trading.log")
    print("  • Run this script to check current state\n")


if __name__ == '__main__':
    main()
```

**Utilisation** :
```bash
# Installer tabulate si nécessaire
pip install tabulate

# Run
python scripts/verify_alpaca_orders.py

# Output exemple :
# ✅ Connected to Alpaca Paper Trading
# 
# 📊 ACCOUNT SUMMARY
# ┌─────────────────────────┬──────────────┐
# │ Portfolio Value         │ $100,000.00  │
# │ Cash                    │ $50,000.00   │
# │ Equity                  │ $100,000.00  │
# ├─────────────────────────┼──────────────┤
# │ Buying Power            │ $200,000.00  │
# └─────────────────────────┴──────────────┘
# 
# 📈 CURRENT POSITIONS
# ┌────────┬─────┬──────────┬──────────────┬──────────┬────────┐
# │ Symbol │ Qty │ Price    │ Market Val   │ P&L      │ P&L %  │
# ├────────┼─────┼──────────┼──────────────┼──────────┼────────┤
# │ AAPL   │ 100 │ $155.00  │ $15,500.00   │ $500.00  │ 3.33%  │
# └────────┴─────┴──────────┴──────────────┴──────────┴────────┘
```

---

### **Option 3 : Logs Détaillés** ✅

**Dans** : `logs/live_trading.log`

```bash
# Watch logs real-time
tail -f logs/live_trading.log | grep "Order"

# Exemple de log BON :
# 2025-11-09 14:00:35 - INFO - Order submitted: AAPL 10 buy @ $155.00
# 2025-11-09 14:00:36 - INFO - Order executed: AAPL 10 buy @ $154.98 (order_id=12345)
# 2025-11-09 14:00:36 - INFO - AccountMonitor updated: portfolio_value=$100,500.00

# Exemple de log MAUVAIS :
# 2025-11-09 14:00:35 - WARNING - No price data for AAPL, skipping
# 2025-11-09 14:00:35 - ERROR - Failed to fetch data for MSFT: APIError
# 2025-11-09 14:00:36 - WARNING - Order rejected: AAPL - RiskLimitExceeded
```

---

### **Option 4 : Debug Script** ✅

**Créer** : `scripts/debug_pipeline.py`

```python
#!/usr/bin/env python3
"""Debug script to trace pipeline execution."""

import os
import sys
import logging
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
from financial_analyzer.trading.live_trading_pipeline import LiveTradingPipeline


def main():
    """Debug pipeline execution."""
    print("\n🔍 DEBUGGING LIVE TRADING PIPELINE\n")
    
    # Setup
    api_key = os.getenv('ALPACA_API_KEY')
    api_secret = os.getenv('ALPACA_SECRET_KEY')
    
    if not api_key or not api_secret:
        print("❌ Missing API credentials!")
        sys.exit(1)
    
    # Create adapter
    print("[1/4] Creating Alpaca adapter...")
    adapter = AlpacaAdapter(
        api_key=api_key,
        api_secret=api_secret,
        paper=True
    )
    
    # Connect
    print("[2/4] Connecting to Alpaca...")
    try:
        adapter.connect()
        print(f"✅ Connected: {adapter.connected}\n")
    except Exception as e:
        print(f"❌ Connection failed: {e}\n")
        sys.exit(1)
    
    # Create pipeline
    print("[3/4] Creating pipeline...")
    pipeline = LiveTradingPipeline(
        broker_adapter=adapter,
        tickers=['AAPL', 'MSFT', 'GOOGL'],
        initial_capital=100000.0
    )
    print(f"✅ Pipeline created\n")
    
    # Run (dry-run mode for debug)
    print("[4/4] Running pipeline (DRY-RUN)...")
    print("-" * 60)
    
    result = pipeline.run(force=True)
    
    print("-" * 60)
    print("\n📊 EXECUTION RESULT:")
    print(f"  Status: {result['status']}")
    print(f"  Orders Generated: {result.get('orders_generated', 0)}")
    print(f"  Orders Executed: {result.get('orders_executed', 0)}")
    print(f"  Orders Rejected: {result.get('orders_rejected', 0)}")
    print(f"  Portfolio Value: ${result['portfolio_value']:,.2f}")
    print(f"  Daily P&L: ${result['daily_pnl']:+,.2f}")
    
    if result.get('reason'):
        print(f"  Reason: {result['reason']}")
    
    print()


if __name__ == '__main__':
    main()
```

---

## 🔑 QUESTION 2 : CONFIGURATION .ENV

### **Créer fichier .env** ✅

**Créer** : `.env` (à la racine du projet)

```bash
# ================== ALPACA ==================
ALPACA_API_KEY=your_alpaca_paper_key_here
ALPACA_SECRET_KEY=your_alpaca_paper_secret_here
ALPACA_BASE_URL=https://paper-api.alpaca.markets  # Paper trading
# ALPACA_BASE_URL=https://api.alpaca.markets  # Live trading (don't use!)

# ================== NEWS APIs ==================
NEWS_API_KEY=your_newsapi_key_here
FINNHUB_API_KEY=your_finnhub_key_here

# ================== OTHER APIs ==================
ALPHA_VANTAGE_API_KEY=your_alphavantage_key_here
POLYGON_IO_API_KEY=your_polygon_key_here
IEX_CLOUD_API_KEY=your_iexcloud_key_here

# ================== DATABASE ==================
DATABASE_URL=postgresql://user:password@localhost:5432/finbot_db

# ================== LOGGING ==================
LOG_LEVEL=INFO
LOG_FILE=logs/app.log

# ================== TRADING CONFIG ==================
TRADING_MODE=paper  # paper or live
INITIAL_CAPITAL=100000.0
MAX_DRAWDOWN=-0.15
MAX_DAILY_LOSS=5000.0
```

### **Comment obtenir les clés ?**

#### **1. Alpaca API Key** 📊
```
URL: https://app.alpaca.markets
1. Sign in / Create account
2. Account Settings → API Keys
3. Copy "API Key" (starts with PK...)
4. Copy "Secret Key" (long string)
5. IMPORTANT: Use "Paper Trading" endpoints!
```

#### **2. NewsAPI Key** 📰
```
URL: https://newsapi.org
1. Sign up free
2. Click your profile → API keys
3. Copy key
4. Limit: 100 req/day free tier
```

#### **3. Finnhub API Key** 📈
```
URL: https://finnhub.io
1. Sign up free
2. Dashboard → API keys
3. Copy key
4. Limit: 60 req/min free tier
```

#### **4. Alpha Vantage Key** 💹
```
URL: https://www.alphavantage.co
1. Sign up free
2. Email verification
3. Key sent via email
4. Limit: 5 req/min, 500 req/day
```

---

### **Load .env in Python** ✅

**Option 1 : python-dotenv**

```python
# At top of file
from dotenv import load_dotenv
import os

# Load .env
load_dotenv()

# Use
api_key = os.getenv('ALPACA_API_KEY')
news_key = os.getenv('NEWS_API_KEY')

# With default
log_level = os.getenv('LOG_LEVEL', 'INFO')
```

**Install** :
```bash
pip install python-dotenv
```

---

**Option 2 : Manual export (Linux/Mac)**

```bash
# Load manually before running
export $(cat .env | xargs)
python scripts/run_live_trading.py

# Or in one line
export ALPACA_API_KEY=pk_... && python scripts/run_live_trading.py
```

---

**Option 3 : In scripts/run_live_trading.py**

```python
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Now all env vars available
api_key = os.getenv('ALPACA_API_KEY')
```

---

### **Security : .gitignore** ⚠️

**IMPORTANT** : Never commit .env file!

**Créer** : `.gitignore` (ajouter)

```
# Environment variables
.env
.env.local
.env.*.local

# API Keys
**/api_keys.json
**/credentials.json

# Logs
logs/
*.log

# Cache
__pycache__/
*.pyc
.pytest_cache/
.coverage

# IDE
.vscode/
.idea/
*.swp
*.swo
```

---

## 🔴 POURQUOI LES ORDRES NE S'EXÉCUTENT PAS ?

### **Checklist Debug** ✅

1. **API Keys incorrect** ❌
   ```bash
   # Vérifier
   echo $ALPACA_API_KEY
   # Doit afficher: pk_... (pas vide!)
   ```
   
   **Fix** :
   - Copier clé EXACTEMENT depuis Alpaca dashboard
   - Vérifier pas d'espaces avant/après
   - Vérifier utilise version "Paper" des clés

2. **Broker not connected** ❌
   ```python
   # Check in code
   print(f"Connected: {adapter.connected}")
   # Doit être True
   ```
   
   **Fix** :
   ```python
   adapter.connect()  # Call before using!
   ```

3. **Market closed** ❌
   ```bash
   # Vérifier
   # Market hours: 09:30 - 16:00 ET, Lundi-Vendredi
   # Weekend/Holidays: No trading
   ```
   
   **Fix** :
   ```bash
   # Test avec --force pour ignorer schedule
   python scripts/run_live_trading.py --force
   ```

4. **No signals generated** ❌
   ```
   # Logs show "No positive signals"
   ```
   
   **Fix** :
   - Momentum signal trop faible
   - Données historiques insuffisantes
   - Check _generate_signals() implémentation

5. **Risk Guard rejetant ordres** ❌
   ```
   # Logs show "Order rejected: RiskLimitExceeded"
   ```
   
   **Fix** :
   ```bash
   # Utiliser config conservative
   python scripts/run_live_trading.py \\
       --config config/live_trading_conservative.yaml
   
   # Ou augmenter limites dans YAML
   ```

6. **Alpaca API rate limit** ❌
   ```
   # Error: "429 Too Many Requests"
   ```
   
   **Fix** :
   - Alpaca rate limit: 200 req/min
   - Sleep entre requêtes
   - Retry logic implémenté dans code

---

## 📋 TEST COMPLET - CHECKLIST

### **Step 1 : Setup .env**
```bash
# Créer .env
cat > .env << EOF
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
EOF

# Vérifier
grep ALPACA .env
```

### **Step 2 : Vérifier credentials**
```bash
# Test connection
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter

adapter = AlpacaAdapter(
    api_key=os.getenv('ALPACA_API_KEY'),
    api_secret=os.getenv('ALPACA_SECRET_KEY'),
    paper=True
)
adapter.connect()
print(f'✅ Connected: {adapter.connected}')

account = adapter.get_account()
print(f'Portfolio: ${account[\"portfolio_value\"]:,.2f}')
"
```

### **Step 3 : Vérifier dashboard**
```
1. Go to https://app.alpaca.markets/paper/dashboard
2. Check "Orders" section
3. Should see empty (no orders yet)
```

### **Step 4 : Run pipeline**
```bash
python scripts/run_live_trading.py --config config/live_trading_conservative.yaml --force
```

### **Step 5 : Check results**
```bash
# Check logs
tail -50 logs/live_trading.log | grep -i order

# Run verification
python scripts/verify_alpaca_orders.py

# Check dashboard
# Refresh: https://app.alpaca.markets/paper/dashboard/orders
```

### **Step 6 : Expected output** ✅

```
✅ Generated: 3 orders
✅ Executed: 3 orders  
✅ Rejected: 0 orders
✅ Portfolio Value: $100,500.00
✅ See orders in Alpaca dashboard
```

---

## 🎯 QUICK START - 5 MINUTES

```bash
# 1. Create .env
cat > .env << EOF
ALPACA_API_KEY=pk_your_key
ALPACA_SECRET_KEY=sk_your_secret
EOF

# 2. Test connection
python scripts/verify_alpaca_orders.py

# 3. Run pipeline
python scripts/run_live_trading.py --config config/live_trading_conservative.yaml --force

# 4. Check logs
tail -f logs/live_trading.log

# 5. Verify in dashboard
# https://app.alpaca.markets/paper/dashboard/orders
```

---

## 📞 TROUBLESHOOTING

| Error | Cause | Fix |
|-------|-------|-----|
| `ConnectionError: Invalid credentials` | API key wrong | Copy exact key from dashboard |
| `No orders generated` | Signals too weak | Lower momentum threshold |
| `RiskLimitExceeded` | Position too large | Use conservative.yaml config |
| `APIError: 429` | Rate limited | Wait a minute, retry |
| `Market closed` | Not trading hours | Use `--force` flag |
| `AttributeError: broker` | Adapter not connected | Call `adapter.connect()` |

---

**Ready to verify orders ? 🚀**

Próximo : Run verification script et check dashboard !

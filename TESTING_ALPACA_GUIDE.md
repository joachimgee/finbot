# 🧪 GUIDE DE TEST - ALPACA PAPER TRADING

Ce guide explique comment tester AlpacaAdapter avec un vrai compte paper trading Alpaca.

---

## 📋 PRÉREQUIS

### 1. Créer un compte Alpaca (GRATUIT)

1. Aller sur https://alpaca.markets/
2. Cliquer sur "Sign Up" (inscription gratuite)
3. Compléter le formulaire d'inscription
4. Vérifier votre email

### 2. Activer Paper Trading

1. Se connecter à votre compte Alpaca
2. Aller dans "Paper Trading" (menu gauche)
3. Le compte paper est automatiquement créé avec **$100,000 virtuels**

### 3. Générer API Keys

1. Dans le dashboard Paper Trading
2. Aller dans "API Keys" ou "View API Keys"
3. Cliquer sur "Generate New Keys"
4. **IMPORTANT** : Copier et sauvegarder les clés immédiatement
   - `API Key ID` (commence par `PK...`)
   - `Secret Key` (chaîne longue)
5. ⚠️ Les clés ne seront plus visibles après fermeture !

---

## ⚙️ CONFIGURATION

### 1. Configurer .env

Ouvrir `/workspaces/finbot/.env` et ajouter vos clés :

```bash
# Alpaca Paper Trading API Keys
ALPACA_API_KEY=PKxxxxxxxxxxxxxxxxxx
ALPACA_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
BROKER_MODE=paper
```

**Vérifier** :
- `ALPACA_API_KEY` commence par `PK` (Paper Key)
- `BROKER_MODE=paper` (PAS live !)

### 2. Vérifier l'installation

```bash
cd /workspaces/finbot
python -c "import alpaca_trade_api; print('✓ alpaca-trade-api installed')"
```

---

## 🚀 TESTS MANUELS

### Test 1 : Connection basique

```bash
cd /workspaces/finbot
python -c "
from financial_analyzer.trading import AlpacaAdapter
import os
from dotenv import load_dotenv

load_dotenv()

adapter = AlpacaAdapter(
    api_key=os.getenv('ALPACA_API_KEY'),
    secret_key=os.getenv('ALPACA_SECRET_KEY'),
    mode='paper'
)

adapter.connect()
print('✓ Connection successful!')
adapter.disconnect()
"
```

**Résultat attendu** :
```
✓ Connection successful!
```

### Test 2 : Account information

```bash
cd /workspaces/finbot
python -c "
from financial_analyzer.trading import AlpacaAdapter
import os
from dotenv import load_dotenv

load_dotenv()

adapter = AlpacaAdapter(
    api_key=os.getenv('ALPACA_API_KEY'),
    secret_key=os.getenv('ALPACA_SECRET_KEY'),
    mode='paper'
)

adapter.connect()
account = adapter.get_account()
print(f\"Cash: \${account['cash']:,.2f}\")
print(f\"Equity: \${account['equity']:,.2f}\")
print(f\"Buying Power: \${account['buying_power']:,.2f}\")
adapter.disconnect()
"
```

**Résultat attendu** :
```
Cash: $100,000.00
Equity: $100,000.00
Buying Power: $200,000.00
```

### Test 3 : Market status

```bash
cd /workspaces/finbot
python -c "
from financial_analyzer.trading import AlpacaAdapter
import os
from dotenv import load_dotenv

load_dotenv()

adapter = AlpacaAdapter(
    api_key=os.getenv('ALPACA_API_KEY'),
    secret_key=os.getenv('ALPACA_SECRET_KEY'),
    mode='paper'
)

adapter.connect()
is_open = adapter.is_market_open()
print(f\"Market is {'OPEN' if is_open else 'CLOSED'}\")
adapter.disconnect()
"
```

**Résultat attendu** :
```
Market is OPEN (ou CLOSED selon l'heure)
```

### Test 4 : Historical data

```bash
cd /workspaces/finbot
python -c "
from financial_analyzer.trading import AlpacaAdapter
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

adapter = AlpacaAdapter(
    api_key=os.getenv('ALPACA_API_KEY'),
    secret_key=os.getenv('ALPACA_SECRET_KEY'),
    mode='paper'
)

adapter.connect()
end = datetime.now()
start = end - timedelta(days=5)
bars = adapter.get_bars('AAPL', start, end, timeframe='1D')
print(f\"Fetched {len(bars)} bars for AAPL\")
print(bars.tail(3))
adapter.disconnect()
"
```

**Résultat attendu** :
```
Fetched 5 bars for AAPL
                                  open    high     low   close    volume
timestamp                                                               
2024-11-04 05:00:00+00:00  225.50  226.75  225.00  226.50  50000000
2024-11-05 05:00:00+00:00  226.50  227.00  225.75  226.80  48000000
2024-11-06 05:00:00+00:00  226.80  228.00  226.50  227.50  52000000
```

### Test 5 : Example complet

```bash
cd /workspaces/finbot
python examples/alpaca_trading_example.py
```

**Résultat attendu** :
- Connection successful
- Market status
- Account info
- Current positions (vide initialement)
- Open orders (vide initialement)
- Historical data for AAPL

---

## 📝 TEST AVEC ORDRES (OPTIONNEL)

⚠️ **ATTENTION** : Ceci soumet de VRAIS ordres (en paper trading).

### Test Order Submission

Décommenter la section "7. Submit test order" dans `examples/alpaca_trading_example.py` :

```python
# Ligne ~140-165
if is_open:
    logger.info("\n7. Submitting test market order...")
    order = adapter.submit_order(
        symbol='AAPL',
        qty=1,
        side='buy',
        order_type='market'
    )
    # ...
```

Puis exécuter :

```bash
python examples/alpaca_trading_example.py
```

**Résultat attendu** :
- Order submitted avec ID
- Order filled (si marché ouvert)
- Position créée (1 share AAPL)
- Order canceled (si commenté décommenter)

---

## 🐛 TROUBLESHOOTING

### Erreur : "Failed to connect"

**Causes possibles** :
1. API keys incorrectes
2. .env pas chargé
3. Pas de connexion internet

**Solutions** :
```bash
# Vérifier .env
cat .env | grep ALPACA

# Vérifier connexion
curl https://paper-api.alpaca.markets/v2/account -H "APCA-API-KEY-ID: $ALPACA_API_KEY" -H "APCA-API-SECRET-KEY: $ALPACA_SECRET_KEY"
```

### Erreur : "Insufficient buying power"

**Cause** : Pas assez de capital disponible

**Solution** :
- Compte paper commence avec $100k
- Vérifier positions existantes
- Calculer buying power disponible

### Erreur : "Market closed"

**Cause** : Marché fermé (hors heures de trading)

**Heures de trading US** :
- Lundi-Vendredi : 9:30 AM - 4:00 PM ET
- Fermé : weekends et jours fériés US

**Solution** :
- Attendre ouverture marché
- Ou utiliser extended hours (non implémenté)

### Erreur : "Order not found"

**Cause** : Order ID invalide ou déjà exécuté

**Solution** :
- Vérifier order ID
- Vérifier status (peut être déjà filled/canceled)

---

## 📊 VÉRIFIER DANS DASHBOARD ALPACA

1. Se connecter à https://alpaca.markets/
2. Aller dans "Paper Trading"
3. Vérifier :
   - **Account** : Cash, equity, positions
   - **Orders** : Ordres actifs/historiques
   - **Positions** : Positions ouvertes
   - **Activity** : Toutes les transactions

---

## 🎓 NEXT STEPS

Une fois tests manuels validés :

1. ✅ Exécuter tests automatiques : `pytest tests/trading/ -v`
2. ✅ Vérifier couverture : `pytest tests/trading/ --cov`
3. 📈 Passer à **Phase 6.2** : Account Monitor & Risk Guard

---

## 📚 RESSOURCES

- **Alpaca Docs** : https://alpaca.markets/docs/
- **API Reference** : https://alpaca.markets/docs/api-references/trading-api/
- **alpaca-trade-api** : https://github.com/alpacahq/alpaca-trade-api-python
- **Paper Trading Dashboard** : https://app.alpaca.markets/paper/dashboard/overview

---

## ⚠️ IMPORTANT REMINDERS

1. **Ne JAMAIS commit les API keys** dans Git
2. **Toujours utiliser mode=paper** pour tests
3. **Tester d'abord en paper** avant live
4. **Paper trading = argent virtuel** (sans risque)
5. **Live trading = argent réel** (⚠️ DANGER !)

---

**Date** : 9 novembre 2025  
**Phase** : 6.1 - Broker Adapters Testing  
**Status** : ✅ Ready for testing

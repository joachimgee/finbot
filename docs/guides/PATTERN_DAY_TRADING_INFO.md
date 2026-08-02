# 🚨 PATTERN DAY TRADING (PDT) - LIMITATION COMPTE PAPER

## ❌ PROBLÈME RENCONTRÉ

Lors de l'exécution avec `--execute`, toutes les ventes sont bloquées :

```
❌ Failed to sell ABAT: Alpaca API error: trade denied due to pattern day trading protection
❌ Failed to sell ABP: Alpaca API error: trade denied due to pattern day trading protection
❌ Failed to sell ABTC: Alpaca API error: trade denied due to pattern day trading protection
...
```

## 📖 EXPLICATION

### Qu'est-ce que le Pattern Day Trading (PDT) ?

**Pattern Day Trading** est une règle de la SEC (Securities and Exchange Commission) qui s'applique aux comptes de trading aux États-Unis :

- **Day Trade** = Acheter ET vendre le même symbole **le même jour**
- **Pattern Day Trader** = Effectuer **4+ day trades en 5 jours ouvrables**

### Règle PDT

Si votre compte a **moins de $25,000 USD** d'equity :
- ✅ Maximum **3 day trades par période de 5 jours**
- ❌ Au-delà de 3, le compte est **bloqué pour 90 jours**

Si votre compte a **$25,000+ USD** d'equity :
- ✅ Day trading illimité
- ✅ Aucune restriction

### Pourquoi sur compte Paper ?

**Alpaca Paper Trading simule les vraies conditions du marché**, incluant les restrictions PDT :

```
Equity actuelle : $959.25
Seuil PDT       : $25,000.00
→ PDT S'APPLIQUE ✅ (simulation réaliste)
```

## 🔍 DIAGNOSTIC

### Vérifier votre statut PDT

```bash
python -c "
from src.financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
adapter = AlpacaAdapter.from_env(mode='paper')
adapter.connect()
account = adapter.get_account()

equity = float(account.get('equity', 0))
pattern_day_trader = account.get('pattern_day_trader', False)
daytrade_count = account.get('daytrade_count', 0)

print(f'Equity: \${equity:,.2f}')
print(f'Pattern Day Trader: {pattern_day_trader}')
print(f'Day Trades (5 jours): {daytrade_count}')
print(f'PDT Protection: {\"ACTIVE\" if equity < 25000 else \"EXEMPT\"}')"
```

### Notre situation (20 nov 2025)

```
Equity: $959.25
Pattern Day Trader: False (pas encore flaggé)
Day Trades (5 jours): 0
PDT Protection: ACTIVE (< $25K)
```

**Problème** : Le système essaye de vendre des positions **achetées aujourd'hui même** → Bloqué par PDT

## ✅ SOLUTIONS

### Option 1 : Augmenter l'equity (COMPTE LIVE SEULEMENT)

**Sur compte Live** (pas Paper), déposez des fonds pour atteindre **$25,000+** :

```bash
# Vérifier compte Live (requiert dépôt réel)
python -c "
from src.financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
adapter = AlpacaAdapter.from_env(mode='live')
adapter.connect()
account = adapter.get_account()
print(f'Equity: \${float(account.get(\"equity\", 0)):,.2f}')
print(f'Cash: \${float(account.get(\"cash\", 0)):,.2f}')
"
```

⚠️ **Compte Paper ne permet PAS de bypass PDT** (simulation réaliste)

### Option 2 : Swing Trading (RECOMMANDÉ)

**Ne pas faire de day trading** : Acheter et garder **au moins 1 jour** :

**Stratégie actuelle** :
```
09:30 ET → Analyse 12K symboles
        → Décisions HOLD/SELL/BUY
        → Vente immédiate si hors top ❌ BLOQUÉ PDT
        → Achat nouvelles opportunités ✅ OK
```

**Stratégie Swing Trading** :
```
09:30 ET → Analyse 12K symboles
        → Décisions HOLD/BUY (pas de SELL same-day)
        → Achat nouvelles opportunités ✅ OK

DEMAIN 09:30 ET → Analyse 12K symboles
                → SELL positions d'hier ✅ OK (pas day trade)
                → Achat nouvelles ✅ OK
```

**Configuration** :

Modifier `scripts/portfolio_manager.py` pour **skip les ventes same-day** :

```python
def make_decisions(self, current_positions, top_opportunities, max_positions=200):
    from datetime import datetime, timedelta
    
    # Get positions acquired today
    today = datetime.now().date()
    
    for pos in current_positions:
        symbol = pos['symbol']
        # Check if acquired today (via order history)
        acquired_date = self._get_position_acquired_date(symbol)
        
        if acquired_date == today:
            # FORCE HOLD si acheté aujourd'hui (éviter PDT)
            decisions['hold'].append({
                'symbol': symbol,
                'qty': pos['qty'],
                'score': 0.0,  # Score doesn't matter
                'reason': 'Acquired today (PDT protection)'
            })
        elif symbol not in top_symbols:
            # Peut vendre si pas acheté aujourd'hui
            decisions['sell'].append({...})
```

### Option 3 : Mode Dry-Run (TESTING)

**Pour tester sans restrictions** :

```bash
# Dry-run : Simule sans exécuter
python scripts/run_daily_portfolio_management.py \
  --limit 12000 --max-positions 200 --max-investment 1000 \
  --mode paper

# Output : Décisions affichées, AUCUN ordre réel
```

### Option 4 : Attendre T+1 (SIMPLE)

**Laisser le système tourner normalement**, les ventes fonctionneront **demain** :

```bash
# Aujourd'hui 20 nov 14:57
- Achats : ✅ Fonctionnent
- Ventes : ❌ Bloquées (positions achetées aujourd'hui)

# Demain 21 nov 09:30
- Achats : ✅ Fonctionnent
- Ventes : ✅ Fonctionnent (positions d'hier, pas day trade)
```

## 🎯 RECOMMANDATION

### Court Terme (Aujourd'hui)

**Option 4 : Attendre demain**
- Laisser le système acheter aujourd'hui ✅
- Les ventes fonctionneront demain automatiquement ✅
- Aucune modification nécessaire ✅

### Moyen Terme (Cette semaine)

**Option 2 : Implémenter Swing Trading**
- Ajouter check `acquired_date == today` dans `portfolio_manager.py`
- Force HOLD pour positions same-day
- Permet ventes T+1 (lendemain)
- **Plus robuste pour comptes < $25K**

### Long Terme (Production)

**Option 1 : Compte Live avec $25K+**
- Ouvrir compte Alpaca Live
- Déposer $25,000+
- Day trading illimité
- **Production-ready**

## 📊 IMPACT SUR LE SYSTÈME

### Aujourd'hui (20 nov 2025)

**Test exécuté** :
```
Décisions prises :
- 🚫 CANCEL : 0
- 🔴 SELL    : 46 (tous bloqués par PDT)
- ✅ HOLD    : 5
- 🟢 BUY     : 1 (CDTX, succès)

Résultat :
- Ordres annulés : 0
- Positions vendues : 0 ❌ PDT
- Positions conservées : 5
- Nouvelles positions : 1 ✅
- Erreurs : 51 (46 SELL + 5 BUY échoués)
```

### Demain (21 nov 2025) - PRÉVU

**Si on relance** :
```
Décisions prises :
- 🔴 SELL : 46 positions d'hier ✅ FONCTIONNERA (pas day trade)
- ✅ HOLD : Positions encore dans top
- 🟢 BUY  : Nouvelles opportunités ✅

Résultat attendu :
- Positions vendues : ~40-45 ✅
- Cash libéré : ~$700
- Nouvelles positions : ~30-50 ✅
- Erreurs : 0-5 (uniquement symboles sans prix)
```

## 📝 NOTES IMPORTANTES

### PDT vs Wash Sale

**PDT (Pattern Day Trading)** :
- Restriction SEC
- Bloque ventes same-day si < $25K
- **S'applique sur compte Paper Alpaca** ✅

**Wash Sale Rule** :
- Règle fiscale IRS
- Vendre à perte puis racheter < 30 jours
- **Ne s'applique PAS sur compte Paper** ❌

### Compte Paper vs Live

| Aspect | Paper | Live |
|--------|-------|------|
| PDT Protection | ✅ Simulée | ✅ Réelle |
| Equity minimum | $100K virtuel | Dépôt réel |
| Orders réels | ❌ Simulés | ✅ Réels |
| Risque capital | ❌ Zéro | ⚠️ Réel |
| Bypass PDT | ❌ Impossible | ✅ Si $25K+ |

### Vérification Alpaca Dashboard

Connectez-vous sur https://app.alpaca.markets/paper/dashboard/overview

**Account Info** :
```
Portfolio Value : $959.25
Cash            : $240.71
Buying Power    : $240.71
Pattern Day Trader : No
Day Trade Count : 0 / 3
```

## 🔗 RESSOURCES

- [Alpaca PDT Documentation](https://alpaca.markets/learn/understanding-pattern-day-trading/)
- [SEC Pattern Day Trading](https://www.sec.gov/investor/pubs/daytradingmargin)
- [FINRA Day Trading Rules](https://www.finra.org/investors/learn-to-invest/advanced-investing/day-trading-margin-requirements-know-rules)

---

**Dernière mise à jour** : 20 novembre 2025, 15:05 ET
**Statut** : PDT Protection active, ventes T+1 fonctionneront demain
**Action** : Aucune requise, attendre 21 nov 09:30 ET

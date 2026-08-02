# 🤖 Portfolio Management System - Guide Complet

## 📋 Vue d'ensemble

Système automatisé de gestion de portefeuille intégrant :
1. **Analyse professionnelle** : 12,000 symboles, 300+ facteurs
2. **Portfolio Manager** : Décisions HOLD / SELL / BUY intelligentes
3. **Rebalancer** : Ajustements automatiques des positions
4. **Exécution Alpaca** : Ordres réels sur compte paper/live

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    DAILY WORKFLOW (09:30 ET)                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────┐
        │  1. ANALYSE PROFESSIONNELLE              │
        │  - 12,000 symboles globaux randomisés    │
        │  - 300+ facteurs (alpha, ML, tech, etc.) │
        │  - IC-weighted scoring                   │
        │  → professional_daily_global.csv         │
        └──────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────┐
        │  2. PORTFOLIO MANAGER                    │
        │  - Récupère positions Alpaca actuelles   │
        │  - Compare avec nouvelles opportunités   │
        │  - Décide: HOLD / SELL / BUY             │
        │  - Annule ordres obsolètes               │
        └──────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────┐
        │  3. EXÉCUTION                            │
        │  - Annule ordres hors top 200            │
        │  - Vend positions score < seuil          │
        │  - Conserve positions performantes       │
        │  - Achète nouvelles opportunités         │
        │  → Portfolio rebalancé                   │
        └──────────────────────────────────────────┘
                              │
                              ▼
        ┌──────────────────────────────────────────┐
        │  4. MONITORING                           │
        │  - État final du portefeuille            │
        │  - P/L par position                      │
        │  - Logs & artefacts GitHub               │
        └──────────────────────────────────────────┘
```

---

## 🚀 Utilisation

### 1. Exécution locale

#### Dry-run (sans exécuter les ordres)
```bash
python scripts/run_daily_portfolio_management.py \
  --limit 12000 \
  --max-positions 200 \
  --max-investment 1000
```

#### Exécution réelle
```bash
python scripts/run_daily_portfolio_management.py \
  --limit 12000 \
  --max-positions 200 \
  --max-investment 1000 \
  --execute
```

#### Skip analyse si récente (<24h)
```bash
python scripts/run_daily_portfolio_management.py \
  --skip-analysis \
  --execute
```

### 2. GitHub Actions (automatique)

**Horaire** : Chaque matin à **09:30 ET** (14:30 UTC), lundi-vendredi

**Configuration** : `.github/workflows/daily_professional_analysis_global_12k.yml`

**Workflow** :
1. ✅ Analyse 12,000 symboles
2. ✅ Gère le portefeuille (HOLD/SELL/BUY)
3. ✅ Exécute les ordres sur Alpaca Paper
4. ✅ Upload résultats (CSV + logs)

**Voir les résultats** :
- https://github.com/joachimgee/finbot/actions
- Télécharger "Artifacts" → `professional-analysis-global-12k-XXX`

---

## ⚙️ Configuration

### Paramètres principaux

| Paramètre | Description | Défaut | Recommandé |
|-----------|-------------|--------|------------|
| `--limit` | Nombre de symboles à analyser | 12000 | 12000 |
| `--max-positions` | Nombre max de positions | 200 | 50-200 |
| `--max-investment` | $ par position | 1000 | 100-1000 |
| `--hold-threshold` | Score min pour HOLD | 0.0 | 0.0 à 0.3 |
| `--regions` | Régions (global/us/eu/asia) | global | global |
| `--mode` | paper ou live | paper | paper |

### Variables d'environnement (.env)

```bash
# Alpaca API (requis)
APCA_API_KEY_ID=PKMB...
APCA_API_SECRET_KEY=8Cz4...
APCA_API_BASE_URL=https://paper-api.alpaca.markets

# Données financières (optionnel mais recommandé)
FINANCIAL_MODELING_PREP_API_KEY=jJq5...
ALPHA_VANTAGE_API_KEY=TGQC...
NEWS_API_KEY=c264...
```

### GitHub Secrets (pour workflows)

Configurer sur : https://github.com/joachimgee/finbot/settings/secrets/actions

- `APCA_API_KEY_ID`
- `APCA_API_SECRET_KEY`
- `APCA_API_BASE_URL`
- `FMP_API_KEY`
- `ALPHAVANTAGE_API_KEY`
- `NEWSAPI_KEY`

---

## 📊 Logique de décision

### HOLD (Conserver)
Position conservée si **TOUS** ces critères :
- ✅ Symbole dans le **top max_positions** des nouvelles opportunités
- ✅ Score composite >= `hold_threshold` (défaut: 0.0)

**Exemple** :
- Position actuelle : AAPL avec score 0.45
- hold_threshold : 0.3
- AAPL dans top 200 nouvelles opportunités
- → **HOLD** ✅

### SELL (Vendre)
Position vendue si **UN** de ces critères :
- ❌ Symbole **plus dans le top max_positions**
- ❌ Score composite < `hold_threshold`

**Exemple 1** :
- Position actuelle : TSLA
- TSLA plus dans top 200
- → **SELL** ❌

**Exemple 2** :
- Position actuelle : NVDA avec score 0.15
- hold_threshold : 0.3
- → **SELL** (score trop faible) ❌

### BUY (Acheter)
Nouvelle position si :
- ✅ Symbole dans **top max_positions**
- ✅ Pas déjà en position
- ✅ Pas d'ordre en attente
- ✅ Cash disponible

**Exemple** :
- CDTX : score 0.664, dans top 10
- Pas en portefeuille
- Cash : $5,000
- max_investment : $1,000
- → **BUY** $1,000 de CDTX 🟢

### CANCEL (Annuler ordre)
Ordre en attente annulé si :
- ❌ Symbole plus dans top max_positions

**Exemple** :
- Ordre BUY AAPL en attente (pas rempli)
- AAPL plus dans top 200 (nouvelle analyse)
- → **CANCEL** ordre ❌

---

## 🧮 Exemple concret

### État initial
- **Cash** : $10,000
- **Positions** : 50 (valeur $40,000)
- **Equity** : $50,000
- **Ordres en attente** : 5

### Après analyse (12,000 symboles)
- **Top 200** identifiés avec scores 0.1 à 0.8

### Décisions Portfolio Manager

#### HOLD (17 positions)
```
ALTO  : score=0.467, P/L=-0.68%  → HOLD ✅
ANNX  : score=0.617, P/L=-2.76%  → HOLD ✅
CNTB  : score=0.672, P/L=-7.62%  → HOLD ✅ (meilleur score!)
...
```

#### SELL (37 positions)
```
AACB  : Plus dans top 200        → SELL ❌
EVGOW : Plus dans top 200        → SELL ❌ (-23% loss)
ATHA  : Plus dans top 200        → SELL ❌
...
```

#### BUY (33 nouvelles)
```
CDTX  : score=0.664              → BUY $1,000 🟢
CMCT  : score=0.653              → BUY $1,000 🟢
EXAS  : score=0.646              → BUY $1,000 🟢
...
```

#### CANCEL (2 ordres)
```
Ordre BUY XYZ : Plus dans top    → CANCEL ❌
Ordre BUY ABC : Plus dans top    → CANCEL ❌
```

### Résultat final
- **Positions** : 50 (17 HOLD + 33 BUY)
- **Ordres annulés** : 2
- **Positions vendues** : 37
- **Cash récupéré** : ~$37,000 (des ventes)
- **Cash investi** : ~$33,000 (33 × $1,000)
- **Cash final** : ~$14,000

---

## 📈 Monitoring & Logs

### Logs locaux
```bash
# Logs d'analyse
logs/analysis_20251120_0930.log

# Logs de gestion portfolio (intégrés dans analyse)
```

### Artefacts GitHub Actions
- **professional_daily_global.csv** : Résultats d'analyse (top 2,930 symboles)
- **logs/*.log** : Logs complets d'exécution

### État du portefeuille
```bash
# Via script
python -c "
from src.financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
adapter = AlpacaAdapter.from_env(mode='paper')
adapter.connect()
account = adapter.get_account()
positions = adapter.get_positions()
print(f'Equity: ${float(account.get(\"equity\", 0)):,.2f}')
print(f'Positions: {len(positions)}')
"

# Via Alpaca dashboard
https://app.alpaca.markets/paper/dashboard/overview
```

---

## 🔧 Modules utilisés

### 1. professional_analysis_daemon.py
- **Rôle** : Analyse quotidienne 12K symboles
- **Modules** : AlphaFactor, ML, Technical, Fundamental, FinBERT
- **Output** : CSV avec scores composites

### 2. portfolio_manager.py
- **Rôle** : Décisions HOLD/SELL/BUY
- **Logique** :
  - Compare positions actuelles vs nouvelles opportunités
  - Applique seuils (hold_threshold)
  - Gère les ordres en attente
- **Intégration** : AlpacaAdapter pour ordres réels

### 3. rebalancer.py
- **Rôle** : Rebalancement périodique/threshold
- **Méthodes** :
  - `rebalance_periodic()` : Mensuel/trimestriel
  - `rebalance_threshold()` : Quand drift > seuil
  - `rebalance_calendar()` : Dates spécifiques
- **État** : Utilisable mais pas encore intégré dans workflow quotidien

### 4. run_daily_portfolio_management.py
- **Rôle** : Orchestrateur principal
- **Workflow** :
  1. Exécute analyse (ou skip si récente)
  2. Lance portfolio manager
  3. Affiche état final
- **Modes** : dry-run (défaut) ou --execute

---

## 🛡️ Sécurité & Limitations

### Mode Paper (recommandé pour testing)
- ✅ Argent virtuel ($100K par défaut)
- ✅ API réelles, positions simulées
- ✅ Zero risque financier
- ⚠️ Peut avoir des différences vs live (slippage, etc.)

### Mode Live (production)
- ⚠️ **Argent réel** !
- ⚠️ Vérifier **TOUS** les paramètres avant --execute
- ⚠️ Commencer avec petit capital ($1,000-$10,000)
- ⚠️ Tester plusieurs jours en paper avant

### Limitations connues
1. **Alpaca API limits** :
   - 200 req/min pour market data
   - 200 req/min pour trading
   - → Analyse 12K peut prendre 2-4h

2. **Cash négatif possible** :
   - Si trop d'ordres en attente vs cash
   - → PortfolioManager handle gracefully

3. **Fractional shares** :
   - Alpaca supporte, mais pas tous les symboles
   - → Script utilise `notional` pour investir montant fixe

4. **Market hours** :
   - Ordres market exécutés uniquement pendant heures ouverture
   - → Workflow lancé à 09:30 ET (juste après ouverture)

---

## 🐛 Troubleshooting

### Erreur "place_order not found"
**Problème** : Méthode Alpaca API changée

**Solution** : Utiliser `submit_order()` à la place
```python
# Ancien
adapter.place_order(...)

# Nouveau
adapter.submit_order(...)
```

### Cash négatif
**Problème** : Trop d'ordres vs cash disponible

**Solution** :
- Réduire `--max-positions`
- Réduire `--max-investment`
- Annuler ordres en attente manuellement

### Analyse timeout
**Problème** : Analyse > 4h

**Solution** :
- Réduire `--limit` (ex: 6000 au lieu de 12000)
- Vérifier connexion internet
- Vérifier rate limits API

### Symboles "Plus dans top"
**Comportement normal** : Randomisation quotidienne change les symboles

**Si trop de SELL** :
- Augmenter `--limit` (plus de symboles analysés)
- Réduire `--max-positions` (top plus exclusif)
- Ajuster `--hold-threshold` (conserver positions moyennes)

---

## 📚 Exemples d'utilisation

### Test rapide (100 symboles, dry-run)
```bash
python scripts/run_daily_portfolio_management.py \
  --limit 100 \
  --max-positions 20 \
  --max-investment 50
```

### Production (12K symboles, exécution réelle)
```bash
python scripts/run_daily_portfolio_management.py \
  --limit 12000 \
  --max-positions 200 \
  --max-investment 1000 \
  --hold-threshold 0.2 \
  --execute
```

### Stratégie conservatrice
```bash
python scripts/run_daily_portfolio_management.py \
  --limit 12000 \
  --max-positions 50 \
  --max-investment 500 \
  --hold-threshold 0.3 \
  --execute
```

### Stratégie agressive
```bash
python scripts/run_daily_portfolio_management.py \
  --limit 12000 \
  --max-positions 300 \
  --max-investment 2000 \
  --hold-threshold 0.0 \
  --execute
```

---

## 🎯 Prochaines améliorations

### Court terme
- [ ] Intégrer `rebalancer.py` pour rebalancement périodique
- [ ] Ajouter stop-loss automatique
- [ ] Dashboard temps réel (Streamlit)

### Moyen terme
- [ ] ML pour prédire meilleur timing d'exécution
- [ ] Gestion multi-comptes (diversification)
- [ ] Backtesting du portfolio management

### Long terme
- [ ] Options trading
- [ ] Crypto integration
- [ ] Alertes Telegram/Discord

---

## 📞 Support

- **Documentation code** : Voir docstrings dans chaque module
- **Logs** : `logs/` pour debugging
- **Tests** : `tests/test_portfolio/` pour validation
- **GitHub Issues** : Reporter bugs ou demander features

---

**✅ Système 100% opérationnel et prêt pour production !**

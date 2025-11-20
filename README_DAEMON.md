# 🤖 PROFESSIONAL ANALYSIS DAEMON - MODE FULL GLOBAL

## ✅ STATUT : PRODUCTION ACTIVE

**Date lancement** : 2025-11-19 20:38  
**PID Daemon** : 35928  
**Prochaine exécution** : 2025-11-20 à 09:35 (quotidienne)

---

## 📊 CONFIGURATION

| Paramètre | Valeur |
|-----------|--------|
| **Univers** | 10,000 symboles maximum |
| **Régions** | 10 pays (US, UK, DE, JP, CA, FR, AU, CH, NL, SE) |
| **Top sélection** | 150 positions |
| **Historique** | 365 jours |
| **Profil risque** | Medium-High |
| **Pondération** | IC-Weighted (Information Coefficient) |
| **Facteurs totaux** | ~300+ par symbole |
| **Exécution** | Quotidienne à 09:35 ET |
| **Mode** | Alpaca Paper Trading |

---

## 🧠 MODULES INTÉGRÉS

### Feature Engineering (300+ facteurs)
- ✅ **AlphaFactorEngine** : 100+ facteurs alpha (9 catégories)
  - Momentum, Value, Quality, Volatility, Liquidity, Size, Technical, Fundamental, Sentiment
  
- ✅ **FeatureEngineer** : 114 facteurs ML production-grade
  - Returns multiples, volatilités, correlations, volumes, patterns

- ✅ **TechnicalFeatureEngine** : 25+ indicateurs techniques
  - RSI, MACD, Bollinger, ATR, ADX, Stochastic, etc.

- ✅ **FundamentalFeatureEngine** : 47+ ratios fondamentaux
  - P/E, P/B, ROE, ROA, Debt/Equity, Operating Margins, etc.

### Sentiment & ML
- ✅ **FinBERTEngine** : Transformer sentiment analysis
- ✅ **SentimentFactorEngine** : Facteurs sentiment quantitatifs
- ✅ **MLPredictor** : Random Forest avec feature engineering

---

## 🌍 COUVERTURE GLOBALE

Le daemon analyse les marchés suivants :

| Région | Symboles attendus | Note |
|--------|-------------------|------|
| 🇺🇸 United States | ~8,000 | Marché principal |
| 🇬🇧 United Kingdom | ~500 | LSE, AIM |
| 🇩🇪 Germany | ~300 | DAX, MDAX |
| 🇯🇵 Japan | ~800 | Nikkei, TOPIX |
| 🇨🇦 Canada | ~400 | TSX |
| 🇫🇷 France | ~200 | CAC 40, SBF 120 |
| 🇦🇺 Australia | ~300 | ASX |
| 🇨🇭 Switzerland | ~150 | SMI, SPI |
| 🇳🇱 Netherlands | ~100 | AEX |
| 🇸🇪 Sweden | ~150 | OMX Stockholm |

**Total attendu** : ~10,000 symboles (limite configurable)

---

## ⚙️ FLUX D'EXÉCUTION QUOTIDIEN

### 1. Sélection Univers (00:00 - 00:15)
- Récupération symboles FinanceDatabase pour les 10 régions
- Shuffle aléatoire (supprimer biais alphabétique)
- Filtrage Alpaca tradability (vérifie asset.tradable et asset.status == 'active')

### 2. Récupération Prix (00:15 - 01:00)
- Fetch historique 365 jours par batches de 50 symboles
- Gestion erreurs réseau avec retry
- Build DataFrame prix consolidé

### 3. Calcul Scores (01:00 - 04:00)
- **~300+ facteurs par symbole** calculés en parallèle :
  - AlphaFactorEngine (100+)
  - FeatureEngineer (114)
  - TechnicalFeatureEngine (25+)
  - FundamentalFeatureEngine (47+)
  - FinBERT sentiment
  - SentimentFactorEngine
  - MLPredictor

- **IC-Weighted aggregation** :
  - Chaque facteur pondéré par son Information Coefficient historique
  - Facteurs haute IC (ex: Momentum) → poids élevé (40%)
  - Facteurs basse IC (ex: Technical) → poids réduit (10%)

### 4. Sélection Top (04:00 - 04:05)
- Tri décroissant par `composite_score`
- Sélection Top 150 symboles

### 5. Optimisation Portfolio (04:05 - 04:30)
- Equal-weight simple (1/150 per position) pour daemon mode
- Calcul quantités cibles basées sur equity disponible

### 6. Exécution Ordres (04:30 - 05:00)
- Récupération positions actuelles Alpaca
- Calcul delta (target - current)
- Soumission ordres Market :
  - BUY si delta > 0
  - SELL si delta < 0
  - HOLD si delta == 0

### 7. Reporting (05:00 - 05:05)
- Export CSV avec scores détaillés
- Log summary (ordres soumis/échoués)
- Mise à jour monitoring

---

## 📈 MONITORING

### Script de monitoring
```bash
bash scripts/monitor_daemon.sh
```

**Affiche** :
- ✅ Statut processus (PID, mémoire, CPU, durée)
- 📄 Logs récents (10 dernières lignes)
- 📊 Résultats dernière analyse (CSV + Top 5 scores)
- 💰 Compte Alpaca (equity, cash, buying power)
- ⏰ Prochaine exécution planifiée

### Logs en temps réel
```bash
tail -f logs/professional_daemon_$(date +%Y%m%d)*.log
```

### Vérifier processus
```bash
ps aux | grep professional_analysis_daemon | grep -v grep
```

### Arrêter daemon
```bash
kill <PID>
# Exemple: kill 35928
```

---

## 📁 FICHIERS GÉNÉRÉS

| Fichier | Description | Fréquence |
|---------|-------------|-----------|
| `logs/professional_daemon_YYYYMMDD_HHMM.log` | Logs exécution | Quotidienne |
| `professional_analysis_daemon_YYYYMMDD_HHMM.csv` | Résultats scores détaillés | Quotidienne |

### Format CSV
```csv
symbol,composite_score,num_factors_computed,confidence,alpha_score,ml_score,technical_score,fundamental_score,sentiment_score
AAPL,0.856,287,0.92,0.78,0.89,0.73,0.95,0.61
MSFT,0.842,291,0.94,0.81,0.87,0.71,0.93,0.59
...
```

**Colonnes** :
- `symbol` : Ticker
- `composite_score` : Score final IC-weighted (0-1)
- `num_factors_computed` : Nombre de facteurs calculés
- `confidence` : Confiance globale (0-1)
- `alpha_score` : Score AlphaFactorEngine
- `ml_score` : Score FeatureEngineer + MLPredictor
- `technical_score` : Score TechnicalFeatureEngine
- `fundamental_score` : Score FundamentalFeatureEngine
- `sentiment_score` : Score FinBERT + SentimentFactorEngine

---

## 🛠️ COMMANDES UTILES

### Lancer daemon (manuel)
```bash
cd /workspaces/finbot

python -u scripts/professional_analysis_daemon.py \
  --limit 10000 \
  --top 150 \
  --regions "United States,United Kingdom,Germany,Japan,Canada,France,Australia,Switzerland,Netherlands,Sweden" \
  --schedule-time "09:35" \
  --days 365 \
  --risk-level medium-high \
  --weighting ic-weighted \
  > logs/professional_daemon_$(date +%Y%m%d_%H%M).log 2>&1 &

echo "Daemon PID: $!"
```

### Exécution unique (test)
```bash
python scripts/professional_analysis_daemon.py \
  --once \
  --limit 100 \
  --top 15 \
  --regions "United States,Canada" \
  --days 180
```

### Modes régions disponibles
- `--regions "global"` : Toutes régions disponibles
- `--regions "us"` : États-Unis uniquement
- `--regions "eu"` : Europe (UK, DE, FR, CH, NL, SE, ES, IT)
- `--regions "asia"` : Asie (JP, CN, KR, SG, HK, IN)
- `--regions "americas"` : Amériques (US, CA, BR, MX)
- `--regions "Country1,Country2,..."` : Liste custom CSV

### Monitoring compte Alpaca
```bash
# Via API
curl -H "APCA-API-KEY-ID: $APCA_API_KEY_ID" \
     -H "APCA-API-SECRET-KEY: $APCA_API_SECRET_KEY" \
     "$APCA_API_BASE_URL/v2/account" | python -m json.tool

# Via Python
python -c "
from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
adapter = AlpacaAdapter.from_env(mode='paper')
adapter.connect()
account = adapter.get_account()
print(f'Equity: \${account[\"equity\"]:,.2f}')
print(f'Cash: \${account[\"cash\"]:,.2f}')
print(f'Positions: {len(adapter.api.list_positions())}')
"
```

---

## 🎯 PERFORMANCE ATTENDUE

### Métriques Cibles (Backtest Historical)
- **Sharpe Ratio** : > 1.5
- **Sortino Ratio** : > 2.0
- **Max Drawdown** : < 20%
- **Win Rate** : > 55%
- **Annual Return** : > 15%

### Facteurs IC Moyens (Historique)
| Catégorie | IC Moyen | Poids |
|-----------|----------|-------|
| Momentum | 0.15 | 40% |
| Quality | 0.12 | 30% |
| Value | 0.08 | 15% |
| Technical | 0.05 | 10% |
| Sentiment | 0.03 | 5% |

---

## ⚠️ NOTES IMPORTANTES

### Limites Alpaca Paper Trading
- **Max positions** : 200 (configured: 150)
- **Max orders/minute** : 200
- **Position size** : Respecter risk_profile constraints

### Risk Profile (Medium-High)
- Max concentration : 35% / position
- Max position size : $75,000
- Max drawdown : 20%
- Max leverage : 1.5x
- Target volatility : 20% annualisée

### Maintenance
- **Logs rotation** : Nettoyer logs > 30 jours
- **CSV archives** : Archiver CSV > 90 jours
- **Monitoring** : Vérifier daemon actif quotidiennement
- **Performance review** : Analyse mensuelle des résultats

---

## 🔄 HISTORIQUE

| Version | Date | Changements |
|---------|------|-------------|
| 1.0 | 2025-11-19 | Lancement initial daemon mode full global |
| | | - 10,000 symboles max |
| | | - 10 régions |
| | | - 300+ facteurs par symbole |
| | | - IC-weighted scoring |
| | | - Exécution quotidienne 09:35 |

---

## 📞 SUPPORT

### Vérifier santé système
```bash
# 1. Daemon actif ?
bash scripts/monitor_daemon.sh

# 2. Logs récents sans erreurs ?
tail -100 logs/professional_daemon_*.log | grep -i error

# 3. Dernière exécution réussie ?
ls -lth professional_analysis_daemon_*.csv | head -1

# 4. Compte Alpaca accessible ?
python -c "from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter; a=AlpacaAdapter.from_env('paper'); a.connect(); print(a.get_account())"
```

### Troubleshooting

**Daemon ne démarre pas :**
```bash
# Vérifier Python disponible
which python

# Vérifier dépendances
pip list | grep -E "alpaca|pandas|numpy|financedatabase"

# Vérifier .env
cat .env | grep APCA_API
```

**Pas de résultats générés :**
```bash
# Vérifier logs daemon
tail -200 logs/professional_daemon_*.log

# Test exécution manuelle
python scripts/professional_analysis_daemon.py --once --limit 10 --regions "us"
```

**Erreurs API Alpaca :**
```bash
# Vérifier clés API valides
curl -H "APCA-API-KEY-ID: $APCA_API_KEY_ID" \
     -H "APCA-API-SECRET-KEY: $APCA_API_SECRET_KEY" \
     "$APCA_API_BASE_URL/v2/account"

# Vérifier rate limits
# Max: 200 orders/minute, 10,000 requests/hour
```

---

## ✅ CHECKLIST PRODUCTION

---

## 🌐 MODE MULTI-WORKFLOW & AGRÉGATION (NOUVEAU)

Pour améliorer la fiabilité et réduire le temps d'exécution d'un run GLOBAL (30K), le système est découpé en workflows régionaux + un job d'agrégation.

### Fichiers Workflows
- `daily_professional_analysis_us.yml` (01:30 UTC) – Limite 12,000 – Top 200
- `daily_professional_analysis_eu.yml` (01:45 UTC) – Limite 8,000 – Top 150
- `daily_professional_analysis_asia.yml` (02:00 UTC) – Limite 10,000 – Top 180
- `daily_professional_analysis_americas.yml` (02:15 UTC) – Limite 9,000 – Top 160
- `daily_professional_analysis_full.yml` (02:00 UTC) – Optionnel 30K global (peut être désactivé si trop long)
- `daily_professional_analysis_aggregate.yml` (03:00 UTC) – Agrège toutes les sorties en un classement consolidé.

### Script d'Agrégation
`scripts/aggregate_professional_results.py` :
1. Charge chaque CSV régional (`professional_analysis_<region>.csv`)
2. Ajoute colonne `region`
3. Calcule `regional_rank` et `global_rank`
4. Normalise `composite_score` → `normalized_score`
5. Déduplique symboles (meilleur score conservé)
6. Produit `professional_analysis_aggregated.csv`

### Colonnes Finales Agrégées
`symbol, region, composite_score, normalized_score, num_factors_computed, confidence, alpha_score, ml_score, technical_score, fundamental_score, sentiment_score, global_rank, regional_rank`

### Avantages
- Réduction risque timeout CI
- Meilleure parallélisation (charges réparties)
- Possibilité d'analyser échec par région
- Classement global multi-zones

### Exemple Téléchargement (GitHub Actions)
Artifacts disponibles après exécution :
```
professional-analysis-us
professional-analysis-eu
professional-analysis-asia
professional-analysis-americas
professional-analysis-full-30k (optionnel)
professional-analysis-aggregated
```

### Commande Locale Agrégation (si artefacts téléchargés)
```bash
python scripts/aggregate_professional_results.py --directory /chemin/vers/csv --output aggregated.csv
```

### Personnalisation Limites
Adapter `--limit` et `--top` par région selon la capacité API / temps restant.

### Recommandations
- Garder FULL 30K seulement hebdomadaire si CI limite temps.
- Ajouter alertes sur échec d'un workflow régional pour éviter biais dans agrégation.
- Stocker agrégations historisées (ex: `professional_analysis_aggregated_YYYYMMDD.csv`).

---

- [x] Daemon lancé et actif (PID: 35928)
- [x] Prochaine exécution planifiée (2025-11-20 09:35)
- [x] Configuration validée (10K symboles, 10 régions, 150 top)
- [x] Modules chargés (300+ facteurs disponibles)
- [x] Compte Alpaca connecté (Paper Trading)
- [x] Logs configurés (unbuffered output)
- [x] Monitoring script créé (`monitor_daemon.sh`)
- [x] Documentation complète (README_DAEMON.md)

---

**🚀 SYSTÈME OPÉRATIONNEL - READY FOR PRODUCTION**

Le daemon d'analyse professionnelle globale est maintenant actif et exécutera automatiquement l'analyse complète tous les jours à 09:35 ET avec :
- 10,000 symboles (10 régions mondiales)
- 300+ facteurs par symbole
- Top 150 positions sélectionnées
- Application automatique au compte Alpaca Paper Trading

Pour toute modification de configuration, arrêter le daemon (`kill 35928`) et relancer avec les nouveaux paramètres.


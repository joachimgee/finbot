# 🚀 FINBOT - STATUT DÉPLOIEMENT PRODUCTION

**Date**: 2025-11-20  
**Statut**: ✅ ACTIF

---

## 📊 SYSTÈME ACTUEL DÉPLOYÉ

### Daemon Quotidien Local (Codespaces)
- **PID**: 8677
- **Commande**: `professional_analysis_daemon.py --limit 12000 --top 200 --regions global`
- **Planification**: Chaque jour à 09:00 (automatique)
- **Univers**: 12,000 symboles mondiaux (toutes régions)
- **Top sélection**: 200 positions
- **Historique**: 365 jours
- **Profil risque**: Medium-High
- **Pondération**: IC-Weighted (~300 facteurs)
- **Output**: `professional_daily_global.csv`
- **Logs**: `logs/daemon_global_12k_YYYYMMDD.log`
- **Prochaine exécution**: 2025-11-21 à 09:00

### ⚠️ Limitation Codespaces
Le daemon local ne fonctionnera que si Codespaces est actif. Pour une exécution garantie même ordinateur éteint, utiliser les workflows GitHub Actions ci-dessous.

---

## ☁️ WORKFLOWS GITHUB ACTIONS (Persistants)

### 1. Workflow Global Quotidien 12K
**Fichier**: `.github/workflows/daily_professional_analysis_global_12k.yml`
- **Planification**: Quotidienne à 09:00 ET (14:00 UTC)
- **Univers**: 12,000 symboles globaux
- **Top**: 200 positions
- **Durée estimée**: 2-3 heures
- **Artifact**: `professional-analysis-global-12k`

### 2. Workflows Régionaux (Optionnels)
**Fichiers**:
- `daily_professional_analysis_us.yml` (01:30 UTC) - 12K US - Top 200
- `daily_professional_analysis_eu.yml` (01:45 UTC) - 8K EU - Top 150
- `daily_professional_analysis_asia.yml` (02:00 UTC) - 10K ASIA - Top 180
- `daily_professional_analysis_americas.yml` (02:15 UTC) - 9K AMERICAS - Top 160

### 3. Workflow Agrégation
**Fichier**: `daily_professional_analysis_aggregate.yml`
- **Planification**: 03:00 UTC (après workflows régionaux)
- **Fonction**: Fusionne tous les CSV régionaux en classement global
- **Script**: `scripts/aggregate_professional_results.py`
- **Output**: `professional_analysis_aggregated.csv`
- **Colonnes**: symbol, region, composite_score, normalized_score, global_rank, regional_rank, etc.

---

## 🧹 MAINTENANCE AUTOMATIQUE

### Nettoyage des Logs
**Script**: `scripts/cleanup_old_logs.sh`
- **Fonction**: Supprime logs/CSV > 7 jours
- **Exécution**: Manuelle ou via cron
```bash
bash scripts/cleanup_old_logs.sh
```

**Planification recommandée (cron)**:
```bash
# Chaque dimanche à 02:00
0 2 * * 0 cd /workspaces/finbot && bash scripts/cleanup_old_logs.sh
```

---

## 🔑 CONFIGURATION REQUISE

### Secrets GitHub Actions (à définir)
Dans Settings → Secrets and Variables → Actions:
- `APCA_API_BASE_URL`: https://paper-api.alpaca.markets
- `APCA_API_KEY_ID`: Votre clé Alpaca
- `APCA_API_SECRET_KEY`: Votre secret Alpaca
- `FMP_API_KEY`: Clé Financial Modeling Prep
- `ALPHAVANTAGE_API_KEY`: Clé Alpha Vantage
- `NEWSAPI_KEY`: Clé NewsAPI (optionnel)

### Variables d'Environnement Locales
Fichier `.env` contient déjà les clés (⚠️ ne jamais commiter ce fichier)

---

## 📈 MODULES INTÉGRÉS (300+ Facteurs)

### Feature Engineering
- ✅ **AlphaFactorEngine**: 100+ facteurs (Momentum, Value, Quality, Volatility, etc.)
- ✅ **FeatureEngineer**: 114 facteurs ML production-grade
- ✅ **TechnicalFeatureEngine**: 25+ indicateurs (RSI, MACD, Bollinger, ATR, etc.)
- ✅ **FundamentalFeatureEngine**: 47+ ratios (P/E, ROE, Debt/Equity, margins, etc.)

### Sentiment & ML
- ✅ **FinBERTEngine**: Analyse sentiment transformer
- ✅ **SentimentFactorEngine**: Facteurs sentiment quantitatifs
- ✅ **MLPredictor**: Random Forest avec feature engineering

### Pondération
- **IC-Weighted**: Information Coefficient (méthode bancaire professionnelle)
- Facteurs haute IC (Momentum) → poids élevé (40%)
- Facteurs basse IC (Technical) → poids réduit (10%)

---

## 📊 RÉSULTATS ATTENDUS

### Format CSV
```csv
symbol,composite_score,num_factors_computed,confidence,alpha_score,ml_score,technical_score,fundamental_score,sentiment_score
AAPL,0.856,287,0.92,0.78,0.89,0.73,0.95,0.61
MSFT,0.842,291,0.94,0.81,0.87,0.71,0.93,0.59
...
```

### Métriques Clés
- **composite_score**: Score final IC-weighted (0-1)
- **num_factors_computed**: Nombre de facteurs calculés (~300)
- **confidence**: Confiance globale (0-1)
- **Scores catégoriels**: alpha, ml, technical, fundamental, sentiment

---

## 🔍 MONITORING

### Vérifier Daemon Local
```bash
ps aux | grep professional_analysis_daemon | grep -v grep
```

### Logs en Temps Réel
```bash
tail -f logs/daemon_global_12k_$(date +%Y%m%d).log
```

### Monitoring Complet
```bash
bash scripts/monitor_daemon.sh
```

### Derniers Résultats
```bash
ls -lth professional_*.csv | head -5
```

---

## 🛠️ COMMANDES UTILES

### Lancer Analyse Unique (Test)
```bash
python -u scripts/professional_analysis_daemon.py \
  --once \
  --limit 500 \
  --top 20 \
  --regions global \
  --days 180 \
  --output test_run.csv
```

### Arrêter Daemon
```bash
kill 8677
# ou
pkill -f professional_analysis_daemon
```

### Relancer Daemon
```bash
nohup python -u scripts/professional_analysis_daemon.py \
  --limit 12000 \
  --top 200 \
  --regions "global" \
  --schedule-time "09:00" \
  --days 365 \
  --risk-level medium-high \
  --weighting ic-weighted \
  --output professional_daily_global.csv \
  > logs/daemon_global_12k_$(date +%Y%m%d).log 2>&1 &
```

### Agréger Résultats Régionaux (Local)
```bash
python scripts/aggregate_professional_results.py \
  --directory . \
  --output aggregated.csv
```

---

## 📋 CHECKLIST PRODUCTION

- [x] Daemon local lancé (PID 8677)
- [x] Planification quotidienne 09:00 configurée
- [x] Workflows GitHub Actions créés (6 fichiers)
- [x] Script agrégation implémenté
- [x] Script nettoyage logs créé
- [x] Instrumentation progression (prints 1000/2000 symboles)
- [x] Documentation complète (README_DAEMON.md)
- [ ] Secrets GitHub Actions configurés (à faire par utilisateur)
- [ ] Test workflow GitHub Actions (déclencher manuellement via workflow_dispatch)
- [ ] Configuration cron nettoyage logs (optionnel)

---

## 🎯 PROCHAINES ÉTAPES RECOMMANDÉES

1. **Configurer Secrets GitHub** (prioritaire pour workflows cloud)
   - Aller dans Settings → Secrets → Actions
   - Ajouter les 6 secrets listés ci-dessus

2. **Tester Workflow GitHub Actions**
   - Aller dans Actions → Daily Professional Analysis Global 12K
   - Cliquer "Run workflow" → "Run workflow"
   - Vérifier exécution et artifact généré

3. **Décider Stratégie**
   - Option A: Daemon local seulement (nécessite Codespaces actif)
   - Option B: Workflows GitHub Actions seulement (recommandé - persistant)
   - Option C: Hybride (local + workflows pour backup)

4. **Monitoring Premier Run**
   - Attendre 2025-11-21 09:00 pour premier run automatique
   - Vérifier génération `professional_daily_global.csv`
   - Valider présence ~300 facteurs par symbole

5. **Optimisations Futures** (optionnel)
   - Ajouter alertes email sur échec workflow
   - Historiser résultats (archive S3 ou artifact long terme)
   - Dashboard visualisation (Grafana / Streamlit)
   - Backtesting automatique des top selections

---

## 📞 SUPPORT & DÉPANNAGE

### Daemon Ne Démarre Pas
```bash
# Vérifier Python disponible
which python

# Vérifier dépendances
pip list | grep -E "alpaca|pandas|financedatabase"

# Tester connexion Alpaca
python -c "from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter; a=AlpacaAdapter.from_env('paper'); a.connect(); print('OK')"
```

### Pas de Résultats Générés
```bash
# Vérifier logs complets
cat logs/daemon_global_12k_$(date +%Y%m%d).log

# Test run manuel minimal
python scripts/professional_analysis_daemon.py --once --limit 10 --regions us --output test.csv
```

### Workflows GitHub Actions Échouent
- Vérifier secrets correctement configurés
- Consulter logs détaillés dans Actions tab
- Vérifier rate limits APIs (Alpaca: 200 req/min)

---

## ✅ STATUT FINAL

**Système OPÉRATIONNEL et PRÊT pour production quotidienne automatique.**

- Daemon local actif (PID 8677) planifié chaque jour 09:00
- Workflows GitHub Actions prêts (nécessitent configuration secrets)
- 300+ facteurs par symbole intégrés
- Analyse globale 12K symboles mondiaux
- Maintenance automatique (nettoyage logs)
- Documentation complète disponible

**Prochaine exécution automatique**: 2025-11-21 à 09:00

Pour activer workflows cloud persistants → configurer secrets GitHub puis tester manuellement.

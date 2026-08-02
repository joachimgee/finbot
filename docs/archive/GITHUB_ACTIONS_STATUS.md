# ✅ Configuration GitHub Actions - Daily Analysis

## 📅 Planification Quotidienne

### Workflows Activés

#### 1. **Daily Professional Analysis Global 12K**
- **Fichier**: `.github/workflows/daily_professional_analysis_global_12k.yml`
- **Horaire**: 
  - DST (Mars-Nov): 09:35 ET = 13:35 UTC → `35 13 * * 1-5`
  - Standard (Nov-Mars): 09:35 ET = 14:35 UTC → `35 14 * * 1-5`
- **Symboles**: 12,000 globaux
- **Script**: `scripts/professional_analysis_daemon.py`
- **Statut**: ✅ Activé

#### 2. **Daily Portfolio Workflow (Complete)**
- **Fichier**: `.github/workflows/daily_run.yml`
- **Horaire**: 09:35 ET = 14:35 UTC → `35 14 * * 1-5`
- **Symboles**: 12,000 globaux
- **Script**: `scripts/professional_analysis_daemon.py`
- **Statut**: ✅ Activé

#### 3. **Test Daily Complete** (manuel)
- **Fichier**: `.github/workflows/test_daily_complete.yml`
- **Déclenchement**: Manuel via `workflow_dispatch`
- **Usage**: Tests avec 50 symboles
- **Statut**: ✅ Disponible

## 🔧 Modules Intégrés (16 modules)

### Core Modules
1. ✅ **Portfolio Learning** - `PortfolioLearner`
2. ✅ **Universe Selection** - `UniverseSelector`
3. ✅ **Daily Preanalysis** - Drift + Options
4. ✅ **Risk Analysis** - `RiskGuard` + `AccountMonitor`

### Signal Generation
5. ✅ **Signal Fusion Engine** - Multi-source fusion
6. ✅ **Weighting Engine** - Evidence-based weights
7. ✅ **RL Signals** - Reinforcement Learning
8. ✅ **ML Signals** - Machine Learning predictions
9. ✅ **Sentiment Analysis** - Market sentiment

### Portfolio Construction
10. ✅ **Master Orchestrator** - Central orchestration
11. ✅ **Portfolio Optimizer** - Mean-Variance, HRP, etc.
12. ✅ **Performance Attribution** - Returns decomposition
13. ✅ **Portfolio Rebalancer** - Periodic rebalancing

### Analytics & Reporting
14. ✅ **Analytics Engine** - Performance analysis
15. ✅ **Report Generator** - PDF/HTML reports
16. ✅ **Backtesting Engine** - Strategy validation

## 📊 Status Modules par Catégorie

```python
modules_status = {
    'core': True,              # Master orchestrator
    'perf_attr': Available,    # Performance attribution
    'rebalancer': Available,   # Portfolio rebalancer
    'analytics': Available,    # Analytics engine
    'reports': Available,      # Report generator
    'universe': Available,     # Universe selector
    'risk': True,             # Risk guard + monitor
    'backtest': Available,    # Backtesting engine
}
```

## 🚀 Déclenchement Manuel

### Via GitHub Web UI
1. Aller sur `Actions` tab
2. Sélectionner workflow
3. Cliquer `Run workflow`
4. Ajuster paramètres (limit, regions)

### Via GitHub CLI
```bash
# Workflow de test (50 symboles)
gh workflow run test_daily_complete.yml -f limit=50

# Workflow complet (12K symboles)
gh workflow run daily_professional_analysis_global_12k.yml -f limit=12000 -f regions=global

# Daily run standard
gh workflow run daily_run.yml -f limit=12000 -f mode=paper
```

## 📝 Secrets Requis

Configurés dans GitHub Settings → Secrets and variables → Actions:

```
APCA_API_KEY_ID              # Alpaca API key
APCA_API_SECRET_KEY          # Alpaca secret
APCA_API_BASE_URL            # https://paper-api.alpaca.markets
FINANCIAL_MODELING_PREP_API_KEY  # FMP API (optional)
ALPHA_VANTAGE_API_KEY        # Alpha Vantage (optional)
NEWS_API_KEY                 # News API (optional)
```

## ⏰ Prochaine Exécution

Pour vérifier la prochaine exécution planifiée:
```bash
# Calculer prochaine exécution (09:35 ET en semaine)
date -d "tomorrow 09:35 America/New_York" -u
```

## 🔍 Monitoring

### Vérifier dernières exécutions
```bash
gh run list --workflow=daily_professional_analysis_global_12k.yml --limit 5
gh run list --workflow=daily_run.yml --limit 5
```

### Voir logs d'une exécution
```bash
gh run view <RUN_ID> --log
```

### Télécharger artifacts
```bash
gh run download <RUN_ID>
```

## ✅ Validation Locale

Test complet avant push:
```bash
python scripts/professional_analysis_daemon.py \
  --once \
  --limit 100 \
  --top 20 \
  --days 90 \
  --regions us \
  --weighting ic-weighted \
  --output /tmp/test.csv
```

## 🐛 Troubleshooting

### Workflow ne s'exécute pas automatiquement
- ✅ Vérifier que le workflow est dans `main` branch
- ✅ Vérifier syntaxe cron (doit être valide)
- ✅ GitHub nécessite activité récente dans le repo
- ✅ Workflows peuvent être désactivés automatiquement après 60 jours d'inactivité

### Solution: Commit réguliers ou exécution manuelle mensuelle
```bash
# Forcer une exécution mensuelle pour garder workflow actif
gh workflow run daily_run.yml
```

## 📈 Métriques Attendues

Résultats typiques pour 12K symboles:
- **Durée**: 2-4 heures
- **Symboles tradables**: ~1,500-3,000
- **Top sélectionnés**: 200
- **Ordres générés**: 50-150
- **Taille CSV**: 50-200 KB
- **Artifacts**: CSV + logs (~5-10 MB)

## 🎯 Prochaines Améliorations

- [ ] Notification Slack/Email en cas d'échec
- [ ] Dashboard GitHub Pages avec résultats
- [ ] Cache des données historiques
- [ ] Parallélisation fetch symbols
- [ ] Compression artifacts pour réduire coûts

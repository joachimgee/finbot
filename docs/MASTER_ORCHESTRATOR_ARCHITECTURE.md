# Architecture Complète - FinBot Master Orchestrator

## 🎯 Vue d'ensemble

Le **MasterOrchestrator** est le hub central qui coordonne TOUS les modules FinBot sans duplication.

## 📐 Architecture en 4 Phases

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      MASTER ORCHESTRATOR                                │
│                    (analysis/master_orchestrator.py)                    │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐          ┌───────────────┐          ┌───────────────┐
│   PHASE 1     │          │   PHASE 2     │          │   PHASE 3     │
│ PRE-ANALYSIS  │ ────────▶│    SIGNALS    │ ────────▶│  PORTFOLIO    │
│               │          │  GENERATION   │          │ CONSTRUCTION  │
└───────────────┘          └───────────────┘          └───────────────┘
        │                           │                           │
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────────────────────────────────────────────────────────────┐
│                           PHASE 4                                     │
│                  RISK VALIDATION & EXECUTION                          │
└───────────────────────────────────────────────────────────────────────┘
```

---

## 📋 Phase 1: Portfolio Pre-Analysis

**Objectif:** Analyser le portfolio EXISTANT avant toute nouvelle décision.

### Modules Utilisés (RÉUTILISATION)

1. **`learning/portfolio_learner.py`** → `analyze_morning_pre_analysis()`
   - Analyse historique des performances (60 jours)
   - Calcul métriques professionnelles (Sharpe, Sortino, Calmar, etc.)
   - Détection patterns d'erreurs systématiques
   - Génération insights + ajustements bidirectionnels

2. **`preanalysis/daily_preanalysis.py`** → `run_daily_preanalysis()`
   - `check_model_drift()` : Détection drift (3 methods: threshold, t-test, CUSUM)
   - `analyze_options_market()` : ATM pricing, Greeks, hedge ratios
   - Intégration avec `AdaptiveWalkForward` (Priority 4)
   - Intégration avec `Options module` (Priority 5)

3. **`scripts/portfolio_manager.py`** → `make_decisions()`
   - HOLD : Score >= seuil, position valide
   - SELL : Score < seuil, plus dans top opportunités
   - BUY : Nouvelles opportunités détectées
   - CANCEL : Ordres obsolètes

### Output

```python
PreAnalysisResult(
    timestamp=datetime.now(),
    current_portfolio={...},              # État actuel (equity, cash, positions)
    drift_detected=bool,                  # Drift détecté ?
    drift_reason=str,                     # Raison du drift
    options_analysis={...},               # Analyse options (Greeks, hedge ratios)
    portfolio_decisions={                 # Décisions portfolio
        'hold': [...],
        'sell': [...],
        'buy': [...],
        'cancel': [...]
    },
    should_retrain=bool,                  # Besoin retrain ?
    warnings=[...],                       # Avertissements
    learning_insights=[...]               # Insights apprentissage
)
```

---

## 📊 Phase 2: Signal Generation

**Objectif:** Générer signaux de trading à partir de sources multiples.

### Modules Utilisés (RÉUTILISATION)

1. **`pipeline/rl_trading_pipeline.py`** → `RLTradingPipeline`
   - Signaux RL (PPO/DQN/DDPG)
   - Integration avec `TradingEnvironment`
   - Policy actions [-1, 1]

2. **`pipeline/ml_trading_pipeline.py`** → `MLTradingPipeline`
   - Prédictions ML (LSTM, Random Forest, etc.)
   - Features: 150+ indicators (Priority 2)
   - Alpha factors (AlphaFactorEngine)

3. **`sentiment/realtime_pipeline.py`** → `RealtimeSentimentPipeline`
   - Sentiment FinBERT (Priority 2)
   - News scraping
   - Scores [-1, 1]

### Fusion des Signaux

```python
combined_signal = (rl_signal + ml_prediction + sentiment_score) / 3
confidence = 1.0 / (1.0 + std([rl, ml, sentiment]))
```

### Output

```python
SignalGenerationResult(
    timestamp=datetime.now(),
    rl_signals={symbol: float},           # Signaux RL
    ml_predictions={symbol: float},       # Prédictions ML
    sentiment_scores={symbol: float},     # Scores sentiment
    combined_signals={symbol: float},     # Signaux combinés
    confidence_scores={symbol: float}     # Confiances
)
```

---

## 💼 Phase 3: Portfolio Construction

**Objectif:** Construire le portfolio optimal à partir des signaux.

### Modules Utilisés (RÉUTILISATION)

1. **`portfolio/optimizer.py`** → `PortfolioOptimizer`
   - **Mean-Variance** : Markowitz (1952)
   - **Risk Parity** : Equal risk contribution
   - **HRP** : Hierarchical Risk Parity (López de Prado 2016)
   - **Black-Litterman** : Views integration (Black-Litterman 1992)
   - **CVaR** : Conditional Value-at-Risk

2. **`portfolio/constraints.py`** → `PortfolioConstraints`
   - Weight constraints (min/max)
   - Sector constraints
   - Turnover constraints
   - Custom constraints

3. **`portfolio/rebalancer.py`** → `PortfolioRebalancer`
   - Periodic rebalancing (daily, weekly, monthly)
   - Threshold-based rebalancing (15% default)
   - Tax-aware rebalancing

4. **`derivatives/options`** → Options Hedge Overlay
   - Compute portfolio delta
   - Hedge with ATM puts
   - Max 10% allocation in options

### Optimization Methods

| Method           | Description                          | Best For                    |
|------------------|--------------------------------------|-----------------------------|
| Mean-Variance    | Maximize Sharpe ratio                | Balanced portfolios         |
| Risk Parity      | Equal risk contribution              | Risk-adjusted allocation    |
| HRP              | Hierarchical clustering              | Diversification             |
| Black-Litterman  | Bayesian views integration           | Tactical allocation         |
| CVaR             | Tail risk minimization               | Risk-averse strategies      |

### Output

```python
PortfolioConstructionResult(
    timestamp=datetime.now(),
    target_weights=pd.Series,             # Poids cibles [0, 1]
    current_weights=pd.Series,            # Poids actuels
    rebalance_needed=bool,                # Rebalance requis ?
    trades_required=pd.Series,            # Trades requis (delta)
    optimization_method=str,              # Méthode utilisée
    expected_return=float,                # Rendement attendu
    expected_volatility=float,            # Volatilité attendue
    expected_sharpe=float,                # Sharpe attendu
    options_hedge_overlay={...}           # Hedge options (si enabled)
)
```

---

## ⚡ Phase 4: Risk Validation & Execution

**Objectif:** Valider les risques et exécuter les ordres.

### Modules Utilisés (RÉUTILISATION)

1. **`trading/risk_guard.py`** → `RiskGuard`
   - **Circuit Breakers:**
     - Position size limit (20% default)
     - Sector exposure limit (40% default)
     - Daily loss limit (5% default)
   - Pre-trade validation
   - Post-trade monitoring

2. **`trading/broker_adapter.py`** → `AlpacaAdapter` / `IBAdapter`
   - Market data fetching
   - Order submission (market, limit, stop)
   - Order status tracking
   - Account monitoring

3. **`trading/account_monitor.py`** → `AccountMonitor`
   - Real-time P&L tracking
   - Risk metrics monitoring
   - Performance attribution

### Order Execution Flow

```
Target Weights
    ↓
Convert to Orders (qty, side)
    ↓
Risk Validation (circuit breakers)
    ↓
Submit Orders (via broker)
    ↓
Track Execution (fills, rejects)
    ↓
Update Portfolio State
```

### Output

```python
ExecutionResult(
    timestamp=datetime.now(),
    orders_submitted=[...],               # Ordres soumis
    orders_executed=[...],                # Ordres exécutés
    orders_rejected=[...],                # Ordres rejetés
    circuit_breakers_triggered=[...],     # Circuit breakers déclenchés
    portfolio_value_before=float,         # Valeur avant
    portfolio_value_after=float,          # Valeur après
    execution_cost=float                  # Coût exécution
)
```

---

## 🔗 Intégration Complète

### Workflow Type (Morning Routine)

```
09:00 AM : Portfolio Learning Analysis
    ↓
09:05 AM : Model Drift Detection
    ↓
09:10 AM : Options Market Analysis
    ↓
09:15 AM : Portfolio Decisions (HOLD/SELL/BUY)
    ↓
09:20 AM : Signal Generation (RL + ML + Sentiment)
    ↓
09:25 AM : Portfolio Optimization
    ↓
09:30 AM : Options Hedge Overlay
    ↓
09:35 AM : Risk Validation & Execution
```

### Modules Connectés (SANS DOUBLONS)

| Module                          | Phase | Fonction                          |
|---------------------------------|-------|-----------------------------------|
| `learning/portfolio_learner.py` | 1     | Morning learning routine          |
| `preanalysis/daily_preanalysis.py` | 1  | Drift + Options                   |
| `scripts/portfolio_manager.py`  | 1     | HOLD/SELL/BUY decisions           |
| `pipeline/rl_trading_pipeline.py` | 2   | RL signals                        |
| `pipeline/ml_trading_pipeline.py` | 2   | ML predictions                    |
| `sentiment/realtime_pipeline.py` | 2    | Sentiment analysis                |
| `portfolio/optimizer.py`        | 3     | Portfolio optimization            |
| `portfolio/rebalancer.py`       | 3     | Rebalancing logic                 |
| `derivatives/options`           | 3     | Options hedging                   |
| `trading/risk_guard.py`         | 4     | Risk validation                   |
| `trading/broker_adapter.py`     | 4     | Order execution                   |
| `trading/account_monitor.py`    | 4     | Performance tracking              |

---

## 🎯 Utilisation

### Exemple Simple

```python
from financial_analyzer.analysis.master_orchestrator import MasterOrchestrator

# Initialize
orchestrator = MasterOrchestrator(
    symbols=['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'META'],
    mode='paper',
    initial_capital=100_000.0,
    max_positions=200,
)

# Run complete analysis
result = orchestrator.run_complete_analysis(
    start_date='2024-01-01',
    end_date='2024-11-24',
    skip_if_no_drift=True,               # Skip si pas de drift
    use_rl_signals=True,                 # Utiliser RL
    use_ml_signals=True,                 # Utiliser ML
    use_sentiment=True,                  # Utiliser sentiment
    optimization_method='mean_variance', # Méthode d'optimisation
    enable_options_hedge=True,           # Hedge options
    dry_run=False,                       # Exécuter réellement
)

# Check results
print(f"Status: {result.status}")
print(f"Drift detected: {result.pre_analysis.drift_detected}")
print(f"Orders executed: {len(result.execution.orders_executed)}")
```

### Exemple Avancé (Skip Logic)

```python
# Skip analysis if no drift detected
result = orchestrator.run_complete_analysis(
    start_date='2024-01-01',
    end_date='2024-11-24',
    skip_if_no_drift=True,  # ✅ Skip si pas de drift
)

if result.status == 'skipped':
    print("No drift detected, analysis skipped")
elif result.status == 'success':
    print("Analysis complete, orders executed")
else:
    print("Analysis failed")
```

---

## 📊 Tests & Validation

### Tests Existants

- **Priority 1** : Ensemble RL (30/30 tests) ✅
- **Priority 2** : Sentiment Pipeline ✅
- **Priority 3** : SHAP Explainability (30/30 tests) ✅
- **Priority 4** : Adaptive Walk-Forward (31/31 tests) ✅
- **Priority 5** : Options Module (53/53 tests) ✅

**Total : 144/144 tests passing ✅**

### Tests d'Intégration

```bash
# Test pre-analysis
pytest tests/test_preanalysis/ -v

# Test portfolio optimizer
pytest tests/test_portfolio/test_optimizer.py -v

# Test rebalancer
pytest tests/test_portfolio/test_rebalancer.py -v

# Test options integration
pytest tests/test_derivatives/test_options.py -v

# Test adaptive walk-forward
pytest tests/test_backtest/test_adaptive_walk_forward.py -v
```

---

## 🚀 Production Deployment

### Configuration

```bash
# Set environment variables
export ALPACA_API_KEY="your_key"
export ALPACA_API_SECRET="your_secret"
export ALPACA_MODE="paper"  # or "live"

# Run orchestrator
python examples/master_orchestrator_example.py
```

### Scheduling (Cron)

```bash
# Run daily at 9:00 AM ET
0 9 * * 1-5 cd /path/to/finbot && python examples/master_orchestrator_example.py >> logs/orchestrator.log 2>&1
```

---

## 📚 References

- **Markowitz (1952)** : Portfolio Selection Theory
- **Black-Litterman (1992)** : Global Portfolio Optimization
- **López de Prado (2016)** : Building Diversified Portfolios that Outperform Out-of-Sample
- **Sharpe (1966)** : Mutual Fund Performance
- **Sortino (1994)** : Performance Measurement in a Downside Risk Framework

---

## ✅ Avantages

1. **SANS DOUBLONS** : Réutilise tous les modules existants
2. **MODULAIRE** : Chaque phase indépendante, testable séparément
3. **FLEXIBLE** : Options configurables (skip_if_no_drift, dry_run, etc.)
4. **PRODUCTION-READY** : Circuit breakers, logging, monitoring
5. **ACADÉMIQUE** : Références solides, méthodes éprouvées

---

## 🎯 Prochaines Étapes

1. **Tests d'Intégration** : Créer tests pour `master_orchestrator.py` (50+ tests)
2. **Dashboard** : Streamlit dashboard pour visualiser workflow
3. **Monitoring** : Prometheus metrics pour production
4. **Documentation** : API reference complète
5. **Examples** : Cas d'usage avancés (multi-strategy, multi-timeframe, etc.)

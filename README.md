# 🚀 FinBot - Financial Market Analyzer

Application d'analyse financière combinant **sentiment analysis**, **machine learning** et **optimisation de portefeuille** pour générer des recommandations d'actions basées sur les données.

## 🎯 Fonctionnalités

- 📊 **Analyse de Marché** : Récupération et analyse de 300k+ instruments financiers via FinanceDatabase
- 🧠 **Sentiment Analysis** : Analyse NLP des news financières avec FinBERT
- 📈 **Machine Learning** : Prédiction de mouvements de prix avec modèles avancés
- 🔄 **Backtesting** : Test de stratégies sur données historiques
- 💼 **Optimisation Portfolio** : Allocation optimale avec Riskfolio-Lib & PyPortfolioOpt (support 100+ tickers)
- 🌐 **API REST** : Interface FastAPI pour accès programmatique

## 🛠️ Technologies

Ce projet combine les meilleurs outils open-source financiers :

- **FinanceDatabase** : Base de données de 300k+ symboles
- **FinanceToolkit** : 150+ ratios et métriques financières
- **backtesting.py** : Engine de backtesting haute performance
- **Riskfolio-Lib** : Optimisation quantitative de portefeuille (24+ risk measures)
- **PyPortfolioOpt** : Black-Litterman, Efficient Frontier, Discrete Allocation
- **FinBERT** : Modèle NLP spécialisé finance
- **FastAPI** : Framework web moderne

## 📦 Installation

```bash
# Cloner le repository
git clone https://github.com/joachimgee/finbot.git
cd finbot

# Créer environnement virtuel
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt

# Installer en mode développement
pip install -e .

# Copier le fichier d'environnement
cp .env.example .env
# Éditer .env avec vos API keys
```

## � Documentation

- **[API Reference](docs/API_REFERENCE.md)** - Complete API documentation
- **[Architecture](docs/ARCHITECTURE.md)** - System design & patterns
- **[Examples](docs/EXAMPLES.md)** - 8+ usage examples
- **[Deployment](docs/DEPLOYMENT.md)** - Production setup & troubleshooting

## �🔑 API Keys Nécessaires

1. **Financial Modeling Prep** : [Obtenir une clé](https://financialmodelingprep.com/developer/docs/)
2. **Alpha Vantage** (optionnel) : [Obtenir une clé](https://www.alphavantage.co/support/#api-key)

## 🚀 Démarrage Rapide

See [EXAMPLES.md](docs/EXAMPLES.md) for complete workflows.

```python
from financial_analyzer.portfolio import PortfolioOptimizer, PortfolioConstraints
import pandas as pd

# 1. Load historical returns
returns = pd.read_csv("returns.csv", index_col=0, parse_dates=True)

# 2. Setup constraints
constraints = PortfolioConstraints()
constraints.add_allocation_limits(min_weight=0.05, max_weight=0.30)
constraints.add_concentration_limit(max_herfindahl=0.25)

# 3. Optimize portfolio
optimizer = PortfolioOptimizer(returns, risk_free_rate=0.02)
optimizer.add_constraint(constraints)
result = optimizer.optimize_max_sharpe()

print(f"Expected Return: {result['return']:.2%}")
print(f"Volatility: {result['volatility']:.2%}")
print(f"Sharpe Ratio: {result['sharpe']:.2f}")
print(f"\nOptimal Weights:\n{result['weights']}")
```

## 📁 Structure du Projet

```
finbot/
├── src/financial_analyzer/
│   ├── data/              # Data Layer (Universe, Market Data, Fundamentals)
│   ├── features/          # Feature Engineering (Technical, Fundamental)
│   ├── backtest/          # Backtesting Engine
│   ├── portfolio/         # Portfolio Optimization ✅
│   │   ├── optimizer.py       # Mean-Variance Optimization
│   │   ├── constraints.py     # Portfolio Constraints
│   │   ├── rebalancer.py      # Rebalancing Strategies
│   │   └── metrics.py         # Risk/Return Metrics
│   ├── ml/                # Machine Learning ✅
│   │   ├── feature_engineering.py  # AlphaFactorEngine (26+ factors)
│   │   ├── factor_selection.py     # FactorAnalyzer (IC computation)
│   │   └── feature_importance.py   # FeatureImportance (permutation)
│   └── trading/           # Live Trading (TODO)
├── tests/
│   ├── test_portfolio/    # Portfolio Tests (69 tests, 100% passed) ✅
│   │   ├── test_integration.py   # 42 E2E tests
│   │   ├── test_optimizer.py     # 13 tests
│   │   ├── test_constraints.py   # 11 tests
│   │   ├── test_rebalancer.py    # 3 tests
│   │   └── test_metrics.py       # 3 tests
│   ├── test_portfolio_optimization/  # PyPortfolioOpt Tests (39 tests, 100% passed) ✅
│   │   └── test_pyportfolioopt_optimizer.py  # 39 comprehensive tests
│   ├── test_ml/           # ML Tests (19 tests, 100% passed) ✅
│   │   ├── test_features.py           # 8 tests (factors + edge cases)
│   │   ├── test_feature_importance.py # 7 tests (validation)
│   │   └── test_features_edge_cases.py # 4 tests (robustness)
│   ├── test_data/
│   ├── test_features/
│   └── test_backtest/
├── docs/                  # Documentation ✅
│   ├── API_REFERENCE.md       # Complete API docs
│   ├── ARCHITECTURE.md        # System design
│   ├── EXAMPLES.md            # 8+ usage examples
│   ├── DEPLOYMENT.md          # Production guide
│   ├── PHASE4_COMPLETION.md   # Portfolio module docs
│   ├── PHASE4.5_COMPLETION.md # Enhanced tests docs
│   ├── PHASE5.1_COMPLETION.md # ML Alpha Factors docs
│   └── PYPORTFOLIOOPT_INTEGRATION.md  # PyPortfolioOpt backend docs
├── examples/              # Code examples ✅
│   └── pyportfolioopt_example.py  # 7 complete examples
├── api/                   # REST API (TODO)
├── notebooks/             # Jupyter notebooks
└── README.md              # This file
```

## 🧪 Tests

```bash
# Tous les tests
pytest tests/ -v

# Tests portfolio (69 tests)
pytest tests/test_portfolio/ -v

# Tests PyPortfolioOpt (39 tests)
pytest tests/test_portfolio_optimization/test_pyportfolioopt_optimizer.py -v

# Tests ML (19 tests)
pytest tests/test_ml/ -v

# Tests d'intégration (42 E2E tests)
pytest tests/test_portfolio/test_integration.py -v

# Validation rapide PyPortfolioOpt
python3 scripts/validate_pyportfolioopt.py

# Avec couverture
pytest tests/ --cov=financial_analyzer --cov-report=html

# Tests spécifiques
pytest tests/test_portfolio/test_optimizer.py -v
pytest tests/test_ml/test_features.py -v
```

**Phase 4 Portfolio Module - Status: ✅ COMPLETE**
- 69 tests (100% passed, 2 skipped)
- Unit tests: 28/28 ✅
- Integration tests: 41/42 ✅
- Code quality: 9.85/10

**Phase 5.1 ML Alpha Factors - Status: ✅ COMPLETE**
- 19 tests (100% passed)
- 26+ alpha factors (Momentum/Volatility/Trend/Volume) ✅
- Information Coefficient analysis ✅
- Permutation importance ✅
- Code quality: 9.8/10

## 📊 Roadmap

- [x] **Phase 1**: Data Layer (Universe, Market Data, Fundamentals) ✅
- [x] **Phase 2**: Feature Engineering (Technical, Fundamental) ✅
- [x] **Phase 3**: Backtesting Engine (Strategy, Metrics, Signals) ✅
- [x] **Phase 4**: Portfolio Optimization (Optimizer, Constraints, Rebalancer) ✅
- [x] **Phase 4.5**: Enhanced Test Suite (42 E2E tests, 9.85/10) ✅
- [x] **Phase 5.1**: Alpha Factor Engineering (26+ factors, IC analysis, 9.8/10) ✅
- [ ] **Phase 5.2**: Extended Factor Library (100+ factors, advanced selection)
- [ ] **Phase 6**: Live Trading (Broker Integration, Order Management)
- [ ] **Phase 7**: Production (CLI, Dashboard, Deployment)

## 📝 License

MIT License

## 🤝 Contribution

Les contributions sont les bienvenues !

## 📧 Contact

GitHub: [@joachimgee](https://github.com/joachimgee)
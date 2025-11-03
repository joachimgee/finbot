# 🚀 FinBot - Financial Market Analyzer

Application d'analyse financière combinant **sentiment analysis**, **machine learning** et **optimisation de portefeuille** pour générer des recommandations d'actions basées sur les données.

## 🎯 Fonctionnalités

- 📊 **Analyse de Marché** : Récupération et analyse de 300k+ instruments financiers
- 🧠 **Sentiment Analysis** : Analyse NLP des news financières avec FinBERT
- 📈 **Machine Learning** : Prédiction de mouvements de prix avec modèles avancés
- 🔄 **Backtesting** : Test de stratégies sur données historiques
- 💼 **Optimisation Portfolio** : Allocation optimale avec Riskfolio-Lib & PyPortfolioOpt
- 🌐 **API REST** : Interface FastAPI pour accès programmatique

## 🛠️ Technologies

Ce projet combine les meilleurs outils open-source financiers :

- **FinanceDatabase** : Base de données de 300k+ symboles
- **FinanceToolkit** : 150+ ratios et métriques financières
- **backtesting.py** : Engine de backtesting haute performance
- **Riskfolio-Lib** : Optimisation quantitative de portefeuille
- **PyPortfolioOpt** : Efficient frontier et optimisation
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

## 🔑 API Keys Nécessaires

1. **Financial Modeling Prep** : [Obtenir une clé](https://financialmodelingprep.com/developer/docs/)
2. **Alpha Vantage** (optionnel) : [Obtenir une clé](https://www.alphavantage.co/support/#api-key)

## 🚀 Démarrage Rapide

```python
from financial_analyzer.data import MarketDataFetcher
from financial_analyzer.sentiment import FinancialSentimentAnalyzer
from financial_analyzer.recommendations import PortfolioRecommendationEngine

# 1. Récupérer les données
fetcher = MarketDataFetcher(api_key="YOUR_API_KEY")
data = fetcher.get_stock_history("AAPL", period="1y")

# 2. Analyser le sentiment
analyzer = FinancialSentimentAnalyzer()
news = fetcher.scrape_news("AAPL")
sentiment = analyzer.analyze_batch(news['headline'].tolist())

# 3. Générer recommandations
recommender = PortfolioRecommendationEngine(["AAPL", "MSFT", "GOOGL"], data)
allocations = recommender.optimize_with_sentiment(sentiment)
```

## 📁 Structure du Projet

```
finbot/
├── src/financial_analyzer/
│   ├── data/              # Module récupération données
│   ├── sentiment/         # Module analyse sentiment
│   ├── analysis/          # Module analyse technique & ML
│   └── recommendations/   # Module recommandations
├── api/                   # API REST FastAPI
├── notebooks/             # Jupyter notebooks
├── tests/                 # Tests unitaires
└── docs/                  # Documentation
```

## 🧪 Tests

```bash
# Tous les tests
pytest tests/ -v

# Avec couverture
pytest tests/ --cov=financial_analyzer --cov-report=html

# Tests spécifiques
pytest tests/test_sentiment.py -v
```

## 📊 Roadmap

- [x] Setup initial du projet
- [ ] Semaine 1 : Module Data
- [ ] Semaine 2 : Module Sentiment
- [ ] Semaine 3 : Module Analysis & Backtesting
- [ ] Semaine 4 : Module Recommendations
- [ ] API REST complète
- [ ] Dashboard web interactif

## 📝 License

MIT License

## 🤝 Contribution

Les contributions sont les bienvenues !

## 📧 Contact

GitHub: [@joachimgee](https://github.com/joachimgee)
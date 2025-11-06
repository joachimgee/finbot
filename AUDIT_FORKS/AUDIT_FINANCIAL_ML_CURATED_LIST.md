# 📚 AUDIT TECHNIQUE - FINANCIAL MACHINE LEARNING (CURATED LIST)

================================================================================
**FORK** : financial-machine-learning (firmai)
**BUT** : Curated List of Financial ML/DL Resources
**REPO** : https://github.com/firmai/financial-machine-learning
**LICENSE** : MIT
**TYPE** : Knowledge Base / Curated List (Wiki-based)
**UPDATES** : Daily automated status checks
**STARS** : 5K+
================================================================================

## 1. INTRODUCTION

**financial-machine-learning** est une **liste curée et maintenue automatiquement** de ressources (repos GitHub, papers, tools) pour le Machine Learning appliqué à la finance et au trading algorithmique.

### Caractéristiques Uniques

✅ **Auto-updated daily** : GitHub Actions vérifient le status de tous les repos quotidiennement
✅ **Wiki dynamique** : Génération automatique de pages wiki avec stats complètes
✅ **Status tracking** : Dernier commit, star count, repo actif/inactif
✅ **Rating system** : 3-5 stars basé sur popularité et maintenance
✅ **Catégories organisées** : 20+ sections thématiques
✅ **Repository Search** : Recherche automatisée de nouveaux repos
✅ **Main README** : Top 15 repos par section
✅ **Wiki pages** : Liste complète dans chaque page wiki

### Statistiques

- **Repos référencés** : 200+
- **Catégories** : 20+
- **Papers** : 100+
- **Star count total** : ~150K+ (agrégé)
- **GitHub Actions** : 3 workflows (repo status, wiki gen, repo search)
- **Update frequency** : Daily
- **Last major update** : 2024

---

## 2. STRUCTURE DU DÉPÔT

```
financial-machine-learning-master/
├── README.md                       # Main page avec top 15 de chaque catégorie
├── generated_wiki/                 # Pages wiki auto-générées
│   ├── deep_learning_and_reinforcement_learning.md
│   ├── other_models.md
│   ├── data_sources.md
│   ├── backtesting.md
│   ├── portfolio_optimization.md
│   ├── risk_management.md
│   ├── factor_investing.md
│   ├── nlp_alternative_data.md
│   ├── market_microstructure.md
│   ├── visualization.md
│   ├── research_tools.md
│   ├── education.md
│   └── ...
├── raw_data/                       # Données brutes des repos
├── conf.py                         # Configuration
├── wiki_gen.py                     # Script de génération wiki
├── git_search.py                   # Script de recherche de nouveaux repos
├── git_status.py                   # Script de vérification status
├── git_util.py                     # Utilitaires git
├── requirements.txt                # Dependencies
└── .github/
    └── workflows/
        ├── repo_status.yml         # Daily status check
        ├── wiki_gen.yml            # Wiki generation
        └── repo_search.yml         # New repos search
```

---

## 3. CATÉGORIES PRINCIPALES

### 3.1. Trading - Deep Learning & Reinforcement Learning

**Top 5 Repos** :

1. **FinRL-Library** (9.7K stars) ⭐⭐⭐⭐⭐
   - End-to-end DRL library for automated trading
   - Columbia University Engineering project
   - DQN, DDQN, DDPG, PPO, A2C implementations
   - PyTorch + OpenAI Gym
   - Backtesting avec pyfolio
   - **Active** : Last commit 2024-09-28

2. **Stock-Prediction-Models** (7.9K stars) ⭐⭐⭐⭐⭐
   - Curated notebooks : DL + RL models
   - Outlier detection, sentiment analysis (BERT)
   - Monte Carlo simulations
   - Overbought/oversold study
   - **Inactive** : Last commit 2021-01-05

3. **AI Trading** (borisbanushev) (4.1K stars) ⭐⭐⭐⭐⭐
   - AI to predict stock market movements
   - **Inactive** : Last commit 2019-02-11

4. **Bulbea** (Deep Learning IV) (2K stars) ⭐⭐⭐⭐⭐
   - Deep Learning based Python Library
   - **Inactive** : Last commit 2017-03-19

5. **RLTrader** (notadamking) (1.7K stars) ⭐⭐⭐⭐⭐
   - Predecessor to TensorTrade
   - OpenAI Gym integration
   - LSTM, Bayesian optimization (Optuna)
   - Real-time matplotlib rendering
   - **Inactive** : Last commit 2019-10-17

**Autres repos notables** :
- **Deep-Trading** (Rachnog) : 1.4K stars
- **Personae** (Ceruleanacg) : 1.3K stars, DDPG/DDQN
- **RL Trading Colab** : 25+ RL strategies
- **deepstock** (keon) : 470 stars
- **trading-bot** (pskrunner14) : DQN avec TensorFlow/Keras
- **crypto-rl** (sadighian) : LOB data from Coinbase/Bitfinex + Arctic DB

### 3.2. Trading - Other Models

**Top 5 Repos** :

1. **Microservices-Based-Algorithmic-Trading-System** (443 stars) ⭐⭐⭐⭐⭐
   - Docker-based platform
   - **Stack complet** :
     * Backtrader : Backtesting
     * MLflow : ML model lifecycle
     * Airflow : Workflow management
     * Superset : Data visualization (Tableau-like)
     * MinIO : Object storage
     * PostgreSQL : Security master + OHLC data
   - Cloud deployment instructions
   - **Active** : Last commit 2024-04-08

2. **Awesome-Quant-Machine-Learning-Trading** (2.7K stars) ⭐⭐⭐⭐⭐
   - Curated list : Books, courses, videos, blogs, papers, code
   - **Inactive** : Last commit 2020-10-08

3. **Hands-On-Machine-Learning-for-Algorithmic-Trading** (1.4K stars) ⭐⭐⭐⭐⭐
   - Repo for [Packt book](https://www.packtpub.com/product/hands-on-machine-learning-for-algorithmic-trading/9781789346411)
   - Topics : Data, unsupervised learning, NLP, RNN/CNN, RL
   - Uses : Zipline, Alphalens, sklearn, OpenAI Gym
   - **Active** : Last commit 2023-01-18

4. **fin-ml** (tatsath) (846 stars) ⭐⭐⭐⭐
   - Materials for book [Machine Learning and Data Science Blueprints for Finance](https://www.amazon.com/Machine-Learning-Science-Blueprints-Finance/dp/1492073059)
   - Topics : NLP, RL, supervised/unsupervised
   - Special topics : Robo-advisors, fraud detection, loan default, derivative pricing, yield curve
   - **Active** : Last commit 2023-01-26

5. **Machine-Learning-for-Algorithmic-Trading-Second-Edition** (1.2K stars) ⭐⭐⭐⭐
   - Official repo for [Stefan Jansen book](https://www.amazon.com/Machine-Learning-Algorithmic-Trading-alternative/dp/1839217715)
   - Backtesting, boosting, NLP, deep/RL learning
   - Uses : Backtrader, Zipline, TA-Lib
   - **Active** : Last commit 2023-01-18

**Autres repos notables** :
- **AlphaPy** (ScottfreeLLC) : ML framework, sklearn/pandas, 1.1K stars

### 3.3. Data Sources

Repos pour acquisition de données financières :
- **yfinance** : Yahoo Finance API
- **pandas-datareader** : Multiple data sources
- **alpha_vantage** : Alpha Vantage API
- **Quandl** : Quandl data platform
- **IEX Cloud** : IEX Cloud API
- **Financial Modeling Prep** : FMP API

### 3.4. Backtesting

Frameworks de backtesting :
- **Zipline** : Quantopian backtesting engine
- **Backtrader** : Python backtesting library
- **backtesting.py** : Modern backtesting library (audité dans ce projet)
- **bt** : Flexible backtesting framework
- **PyAlgoTrade** : Event-driven backtesting
- **Quantlib** : C++ library with Python bindings

### 3.5. Portfolio Optimization

Librairies d'optimisation de portefeuille :
- **PyPortfolioOpt** (audité dans ce projet)
- **Riskfolio-Lib** (audité dans ce projet)
- **cvxpy** : Convex optimization
- **cvxopt** : Convex optimization tools
- **scipy.optimize** : SciPy optimization module

### 3.6. Risk Management

Tools de gestion de risque :
- **QuantLib** : Quantitative finance library
- **pyfolio** : Performance and risk analysis
- **empyrical** : Financial risk metrics
- **ffn** : Financial functions for Python

### 3.7. Factor Investing

Librairies pour factor investing :
- **Alphalens** : Performance analysis of alpha factors
- **PyFactorModel** : Factor model construction
- **Quantopian Research** : Factor analysis tools

### 3.8. NLP & Alternative Data

Traitement de données textuelles :
- **BERT** (Google) : Text embeddings
- **FinBERT** : BERT for financial text
- **StockTwits API** : Social sentiment data
- **News API** : News articles aggregation
- **PRAW** : Reddit API wrapper
- **Tweepy** : Twitter API

### 3.9. Market Microstructure

Analyse de microstructure :
- **Arctic** (Man Group) : Timeseries database
- **LOB analysis** : Limit Order Book tools
- **LOBSTER** : Limit Order Book data

### 3.10. Visualization

Tools de visualisation :
- **Plotly** : Interactive plots
- **Bokeh** : Interactive visualizations
- **matplotlib** : Basic plotting
- **seaborn** : Statistical visualizations
- **Dash** : Web dashboards
- **Streamlit** : Data apps

### 3.11. Research Tools

Outils de recherche quantitative :
- **Jupyter** : Interactive notebooks
- **JupyterLab** : Next-gen Jupyter
- **Weights & Biases** : Experiment tracking
- **MLflow** : ML lifecycle management
- **DVC** : Data version control

### 3.12. Education

Ressources éducatives :
- **Coursera** : Online courses
- **edX** : University courses
- **QuantConnect** : Learn algorithmic trading
- **WorldQuant University** : MSc in Financial Engineering

---

## 4. FORMAT DES ENTRÉES

Chaque entrée dans les listes contient :

```markdown
| repo | comment | created_at | last_commit | star_count | repo_status | rating |
|------|---------|------------|-------------|------------|-------------|--------|
```

**Exemple** :

```markdown
| [FinRL-Library](https://github.com/AI4Finance-LLC/FinRL-Library) | 
  Started by Columbia university engineering students and designed as an 
  end to end deep reinforcement learning library for automated trading platform. 
  Implementation of DQN DDQN DDPG etc using PyTorch and gym | 
  2020-07-26 13:18:16 | 
  2024-09-28 02:56:03 | 
  9697.0 | 
  :heavy_check_mark: | 
  :star:x5 |
```

**Fields** :
- **repo** : Nom + lien GitHub
- **comment** : Description détaillée
- **created_at** : Date de création du repo
- **last_commit** : Date du dernier commit
- **star_count** : Nombre d'étoiles GitHub
- **repo_status** : ✅ (actif si commit < 6 mois) ou ❌ (inactif)
- **rating** : ⭐x3, ⭐x4, ou ⭐x5 basé sur stars + maintenance

---

## 5. SCRIPTS AUTOMATISÉS

### 5.1. repo_status.yml (GitHub Actions)

```yaml
name: Repo-Updater
on:
  schedule:
    - cron: '0 0 * * *'  # Daily at midnight
  workflow_dispatch:

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.8
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run status check
        run: python git_status.py
      - name: Commit changes
        run: |
          git config --global user.name 'GitHub Actions'
          git config --global user.email 'actions@github.com'
          git add .
          git commit -m "Update repo status"
          git push
```

### 5.2. wiki_gen.py

Génère les pages wiki à partir des données brutes.

```python
def generate_wiki_page(category, repos):
    """
    Generate wiki page for a category.
    
    Args:
        category (str): Category name
        repos (list): List of repo dictionaries
    
    Returns:
        str: Markdown content for wiki page
    """
    # Sort by star count + rating
    sorted_repos = sorted(repos, key=lambda x: (x['rating'], x['star_count']), reverse=True)
    
    # Generate markdown table
    md = f"# {category}\n\n"
    md += "| repo | comment | created_at | last_commit | star_count | repo_status | rating |\n"
    md += "|------|---------|------------|-------------|------------|-------------|--------|\n"
    
    for repo in sorted_repos:
        md += f"| {repo['link']} | {repo['comment']} | {repo['created_at']} | "
        md += f"{repo['last_commit']} | {repo['star_count']} | {repo['status']} | "
        md += f"{repo['rating']} |\n"
    
    return md
```

### 5.3. git_search.py

Recherche automatique de nouveaux repos GitHub.

```python
def search_repos(query, min_stars=50):
    """
    Search GitHub for repos matching query.
    
    Args:
        query (str): Search query
        min_stars (int): Minimum star count
    
    Returns:
        list: List of repo dictionaries
    """
    from github import Github
    
    g = Github(os.getenv('GITHUB_TOKEN'))
    
    results = g.search_repositories(query=query, sort='stars', order='desc')
    
    repos = []
    for repo in results[:100]:
        if repo.stargazers_count >= min_stars:
            repos.append({
                'name': repo.name,
                'url': repo.html_url,
                'stars': repo.stargazers_count,
                'description': repo.description,
                'last_commit': repo.updated_at,
                'created_at': repo.created_at
            })
    
    return repos
```

### 5.4. git_util.py

Utilitaires pour interagir avec l'API GitHub.

```python
def get_repo_status(repo_url):
    """
    Get status of a GitHub repo.
    
    Args:
        repo_url (str): GitHub repo URL
    
    Returns:
        dict: Repo status information
    """
    from github import Github
    import datetime
    
    g = Github(os.getenv('GITHUB_TOKEN'))
    repo = g.get_repo(repo_url.replace('https://github.com/', ''))
    
    last_commit = repo.get_commits()[0].commit.author.date
    now = datetime.datetime.now(datetime.timezone.utc)
    days_since_commit = (now - last_commit).days
    
    status = {
        'last_commit': last_commit.isoformat(),
        'star_count': repo.stargazers_count,
        'is_active': days_since_commit < 180,  # Active if commit < 6 months
        'days_since_commit': days_since_commit
    }
    
    return status
```

---

## 6. CATÉGORIES COMPLÈTES (20+)

### Trading

1. **Deep Learning & Reinforcement Learning** ([Wiki](https://github.com/firmai/financial-machine-learning/wiki/deep_learning_and_reinforcement_learning))
   - DQN, DDPG, PPO, A2C, LSTM, GAN, Transformer
   - 15+ repos (FinRL, Stock-Prediction-Models, AI Trading, Bulbea, RLTrader, etc.)

2. **Other Models** ([Wiki](https://github.com/firmai/financial-machine-learning/wiki/other_models))
   - Microservices, Books, Curated Lists
   - 15+ repos (Microservices-Based, Awesome-Quant-ML, Hands-On-ML, etc.)

3. **Backtesting** ([Wiki](https://github.com/firmai/financial-machine-learning/wiki/backtesting))
   - Zipline, Backtrader, backtesting.py, bt, PyAlgoTrade
   - 10+ repos

4. **Portfolio Optimization** ([Wiki](https://github.com/firmai/financial-machine-learning/wiki/portfolio_optimization))
   - PyPortfolioOpt, Riskfolio-Lib, cvxpy
   - 10+ repos

5. **Factor Investing** ([Wiki](https://github.com/firmai/financial-machine-learning/wiki/factor_investing))
   - Alphalens, PyFactorModel
   - 5+ repos

### Data & Infrastructure

6. **Data Sources** ([Wiki](https://github.com/firmai/financial-machine-learning/wiki/data_sources))
   - yfinance, Quandl, Alpha Vantage, IEX Cloud, FMP
   - 20+ sources

7. **Alternative Data** ([Wiki](https://github.com/firmai/financial-machine-learning/wiki/alternative_data))
   - News, social media, satellite, web scraping
   - 10+ repos

8. **Data Storage** ([Wiki](https://github.com/firmai/financial-machine-learning/wiki/data_storage))
   - Arctic, InfluxDB, TimescaleDB
   - 5+ solutions

9. **Market Microstructure** ([Wiki](https://github.com/firmai/financial-machine-learning/wiki/market_microstructure))
   - LOB analysis, LOBSTER, HFT
   - 5+ repos

### Risk & Performance

10. **Risk Management** ([Wiki](https://github.com/firmai/financial-machine-learning/wiki/risk_management))
    - QuantLib, pyfolio, empyrical, ffn
    - 10+ repos

11. **Performance Analysis** ([Wiki](https://github.com/firmai/financial-machine-learning/wiki/performance_analysis))
    - pyfolio, Quantstats, ffn
    - 5+ repos

### NLP & Sentiment

12. **NLP for Finance** ([Wiki](https://github.com/firmai/financial-machine-learning/wiki/nlp))
    - BERT, FinBERT, sentiment analysis
    - 15+ repos

13. **News & Social Media** ([Wiki](https://github.com/firmai/financial-machine-learning/wiki/news_social))
    - News API, StockTwits, Reddit, Twitter
    - 10+ repos

### Tools & Platforms

14. **Visualization** ([Wiki](https://github.com/firmai/financial-machine-learning/wiki/visualization))
    - Plotly, Bokeh, Dash, Streamlit
    - 10+ tools

15. **Research Tools** ([Wiki](https://github.com/firmai/financial-machine-learning/wiki/research_tools))
    - Jupyter, MLflow, W&B, DVC
    - 10+ tools

16. **Execution Platforms** ([Wiki](https://github.com/firmai/financial-machine-learning/wiki/execution))
    - IB API, Alpaca, CCXT (crypto)
    - 10+ platforms

### Education & Community

17. **Courses & Books** ([Wiki](https://github.com/firmai/financial-machine-learning/wiki/education))
    - Coursera, edX, QuantConnect
    - 50+ resources

18. **Papers & Research** ([Wiki](https://github.com/firmai/financial-machine-learning/wiki/papers))
    - Academic papers, whitepapers
    - 100+ papers

19. **Community & Forums** ([Wiki](https://github.com/firmai/financial-machine-learning/wiki/community))
    - Reddit, Discord, Slack channels
    - 10+ communities

20. **Competitions** ([Wiki](https://github.com/firmai/financial-machine-learning/wiki/competitions))
    - Kaggle, Quantopian contests, Numerai
    - 5+ platforms

---

## 7. EXEMPLES DE REPOS PAR THÈME

### Machine Learning Models

**Classification** :
- Random Forests, XGBoost, LightGBM, CatBoost
- Logistic Regression, SVM
- Neural Networks

**Time Series** :
- ARIMA, SARIMA, Prophet
- LSTM, GRU, Transformer
- State Space Models

**Clustering** :
- K-Means, DBSCAN, Hierarchical
- PCA, t-SNE, UMAP

### Reinforcement Learning

**Value-Based** :
- DQN (Deep Q-Network)
- DDQN (Double DQN)
- Dueling DQN

**Policy-Based** :
- PPO (Proximal Policy Optimization)
- A2C (Advantage Actor-Critic)
- A3C (Asynchronous A3C)

**Actor-Critic** :
- DDPG (Deep Deterministic Policy Gradient)
- TD3 (Twin Delayed DDPG)
- SAC (Soft Actor-Critic)

### NLP Techniques

**Classical** :
- Bag of Words, TF-IDF
- N-grams, Word2Vec

**Modern** :
- BERT, RoBERTa, DistilBERT
- GPT-2, GPT-3
- Transformers

---

## 8. UTILISATION

### Rechercher un repo

1. **Main README** : Top 15 de chaque catégorie
   ```bash
   # Ouvrir README.md
   cat README.md | grep "FinRL"
   ```

2. **Wiki pages** : Liste complète
   ```bash
   # Naviguer vers Wiki
   # https://github.com/firmai/financial-machine-learning/wiki/deep_learning_and_reinforcement_learning
   ```

3. **Search GitHub** : Utiliser GitHub search dans le repo
   ```bash
   # Sur GitHub.com
   # Repo search: "reinforcement learning"
   ```

### Filtrer par status

- **Active repos** : ✅ (commit < 6 mois)
- **Inactive repos** : ❌ (commit > 6 mois)

### Filtrer par rating

- ⭐⭐⭐⭐⭐ (5 stars) : 1000+ stars, très populaire
- ⭐⭐⭐⭐ (4 stars) : 500-1000 stars
- ⭐⭐⭐ (3 stars) : 100-500 stars

---

## 9. MAINTENANCE & CONTRIBUTION

### Daily Updates

GitHub Actions runs daily pour :
1. Vérifier le status de tous les repos
2. Mettre à jour last_commit date
3. Mettre à jour star_count
4. Re-générer les pages wiki
5. Commit les changements

### Ajouter un nouveau repo

1. Fork le repo
2. Éditer `raw_data/` avec nouveau repo
3. Run `python wiki_gen.py`
4. Create Pull Request

### Format d'ajout

```json
{
  "name": "new-repo",
  "url": "https://github.com/user/new-repo",
  "category": "deep_learning_and_reinforcement_learning",
  "comment": "Description détaillée du repo",
  "rating": 4
}
```

---

## 10. POINTS FORTS & LIMITATIONS

### ✅ Points Forts

1. **Maintenance automatique** : Daily updates via GitHub Actions
2. **Comprehensive** : 200+ repos, 20+ catégories
3. **Status tracking** : Active/inactive repos clairement identifiés
4. **Rating system** : Stars + maintenance = rating
5. **Wiki organization** : Full list dans pages wiki dédiées
6. **Community-driven** : Open to contributions
7. **Search functionality** : Automated search for new repos
8. **Historical data** : Tracking de l'évolution des repos

### ⚠️ Limitations

1. **Pas de testing** : Repos non testés, juste listés
2. **Qualité variable** : Certains repos peu maintenus
3. **Pas de benchmarks** : Pas de comparaisons de performance
4. **Documentation externe** : Lien vers repos, pas de docs intégrées
5. **GitHub only** : Uniquement repos GitHub (pas GitLab, Bitbucket)
6. **English only** : Descriptions en anglais uniquement
7. **Bias vers popularité** : Stars ≠ qualité nécessairement
8. **Maintenance gaps** : Certains repos actifs non listés

### 💡 Cas d'Usage Idéaux

- **Research** : Découvrir nouveaux repos et techniques
- **Learning** : Trouver resources éducatives
- **Benchmarking** : Comparer différentes approches
- **Tool discovery** : Identifier outils pour tâches spécifiques
- **Community** : Connecter avec projets similaires
- **Inspiration** : Idées pour nouveaux projets

---

## 11. RESSOURCES COMPLÉMENTAIRES

### Sites Web

- **ML-Quant.com** : Daily ML/Quant research by firmai (Sov.ai)
- **QuantStart** : Algorithmic trading tutorials
- **Quantopian** : Community (discontinued but resources live on)

### Books Mentioned

- "Hands-On Machine Learning for Algorithmic Trading" (Packt)
- "Machine Learning for Algorithmic Trading" (Stefan Jansen, 2nd Ed)
- "Machine Learning and Data Science Blueprints for Finance" (O'Reilly)
- "Advances in Financial Machine Learning" (Marcos López de Prado)

### Papers

Top papers referenced :
- López de Prado : "Building Diversified Portfolios that Outperform Out of Sample"
- Markowitz : "Portfolio Selection" (1952)
- Black & Litterman : "Global Portfolio Optimization" (1992)
- Rockafellar & Uryasev : "Optimization of Conditional Value-at-Risk" (2000)

### Courses

- Coursera : Machine Learning for Trading (Georgia Tech)
- edX : Computational Investing (Georgia Tech)
- QuantConnect : Algorithmic Trading Bootcamp
- WorldQuant University : MSc in Financial Engineering

---

## 12. COMMENT UTILISER CETTE RESSOURCE

### Pour débuter

1. **Commencer par Education** : Courses & Books wiki
2. **Explorer Backtesting** : Zipline, Backtrader, backtesting.py
3. **Apprendre ML basics** : Stock-Prediction-Models notebooks
4. **Essayer RL** : FinRL-Library

### Pour un projet spécifique

**Projet : Portfolio Optimization**
→ PyPortfolioOpt + Riskfolio-Lib wikis

**Projet : HFT / Market Making**
→ Market Microstructure + Arctic DB

**Projet : Sentiment Trading**
→ NLP wiki + News/Social Media wiki

**Projet : Factor Investing**
→ Factor Investing wiki + Alphalens

**Projet : Crypto Trading**
→ crypto-rl + CCXT repos

### Pour la recherche

1. **Papers wiki** : Academic research
2. **Deep Learning wiki** : State-of-the-art models
3. **Alternative Data wiki** : Novel data sources
4. **Research Tools wiki** : MLflow, W&B, DVC

---

## 13. CONTACT & CONTRIBUTION

### Maintainer

- **firmai** (Sov.ai)
- **Email** : research@sov.ai
- **Website** : https://ml-quant.com

### Contributing

```bash
# Fork the repo
git clone https://github.com/YOUR_USERNAME/financial-machine-learning
cd financial-machine-learning

# Create feature branch
git checkout -b add-new-repo

# Add your repo to raw_data/
# Edit raw_data/repos.json

# Generate wiki
python wiki_gen.py

# Commit & push
git add .
git commit -m "Add new repo: XYZ"
git push origin add-new-repo

# Create Pull Request on GitHub
```

### Reporting Issues

- **GitHub Issues** : https://github.com/firmai/financial-machine-learning/issues
- **Gitter Chat** : https://gitter.im/financial-machine-learning/community

================================================================================
FIN DE L'AUDIT - FINANCIAL MACHINE LEARNING (CURATED LIST)
================================================================================

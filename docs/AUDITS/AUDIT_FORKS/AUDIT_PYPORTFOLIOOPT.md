# 📊 AUDIT TECHNIQUE - PYPORTFOLIOOPT

================================================================================
**FORK** : PyPortfolioOpt (robertmartin8)
**BUT** : Portfolio optimization using Modern Portfolio Theory
**REPO** : https://github.com/robertmartin8/PyPortfolioOpt
**LICENSE** : MIT
**VERSION** : 1.5.6
**PYPI** : https://pypi.org/project/PyPortfolioOpt/
**DOCS** : https://pyportfolioopt.readthedocs.io/
**PUBLIÉ** : Journal of Open Source Software (2021)
================================================================================

## 1. INTRODUCTION

**PyPortfolioOpt** est une librairie Python complète pour l'optimisation de portefeuille, implémentant :
- Mean-Variance Optimization (Markowitz 1952)
- Black-Litterman allocation
- Hierarchical Risk Parity (HRP)
- Critical Line Algorithm (CLA)
- Multiple risk measures (Variance, Semi-variance, CVaR, CDaR)
- Expected returns estimation methods
- Covariance matrix estimation with shrinkage

### Points Forts

✅ **Extensible** : API modulaire facile à étendre
✅ **Production-ready** : Utilisé par investisseurs pros et algos traders
✅ **Documentation excellente** : ReadTheDocs + Cookbook complet
✅ **Testing** : 95%+ code coverage
✅ **Peer-reviewed** : Publié dans JOSS
✅ **Active maintenance** : Régulièrement mis à jour

### Statistiques

- **Modules Python** : 12 fichiers principaux
- **Tests** : 17 fichiers de tests
- **Classes principales** : 10+ optimizers
- **Méthodes d'expected returns** : 6+
- **Modèles de risque** : 8+
- **Objective functions** : 20+
- **Downloads PyPI** : 500K+
- **GitHub Stars** : 4K+

---

## 2. STRUCTURE DU DÉPÔT

```
PyPortfolioOpt-master/
├── pypfopt/                        # Package principal
│   ├── __init__.py                 # Exports principaux
│   ├── base_optimizer.py           # Classes abstraites
│   ├── efficient_frontier/         # Mean-variance optimization
│   │   ├── efficient_frontier.py   # EfficientFrontier class
│   │   ├── efficient_cvar.py       # CVaR optimization
│   │   ├── efficient_semivariance.py # Semivariance optimization
│   │   └── efficient_cdar.py       # CDaR optimization
│   ├── black_litterman.py          # Black-Litterman model
│   ├── hierarchical_portfolio.py   # HRP, HERC
│   ├── cla.py                      # Critical Line Algorithm
│   ├── expected_returns.py         # Expected returns models
│   ├── risk_models.py              # Covariance estimation
│   ├── objective_functions.py      # Custom objectives
│   ├── discrete_allocation.py      # Convert weights to shares
│   ├── plotting.py                 # Visualizations
│   └── exceptions.py               # Custom exceptions
├── tests/                          # Suite de tests complète
├── cookbook/                       # Jupyter notebooks exemples
├── docs/                           # Documentation Sphinx
├── example/                        # Exemples de code
├── requirements.txt                # Dependencies
├── pyproject.toml                  # Poetry config
└── README.md
```

---

## 3. WORKFLOW CONCEPTUEL

```
1. DATA PREPARATION
   ↓
   Prices DataFrame (OHLCV)
   
2. EXPECTED RETURNS
   ↓
   expected_returns.py
   - mean_historical_return()
   - ema_historical_return()
   - capm_return()
   - james_stein_shrinkage()
   
3. RISK MODEL
   ↓
   risk_models.py
   - sample_cov()
   - semicovariance()
   - exp_cov()
   - ledoit_wolf_shrinkage()
   - oracle_approximating_shrinkage()
   
4. OPTIMIZATION
   ↓
   EfficientFrontier / HRPOpt / CLA / BlackLittermanModel
   
5. PORTFOLIO WEIGHTS
   ↓
   {"AAPL": 0.25, "MSFT": 0.20, ...}
   
6. DISCRETE ALLOCATION
   ↓
   DiscreteAllocation
   {"AAPL": 10 shares, "MSFT": 8 shares, ...}
```

---

## 4. MODULES PRINCIPAUX

### 4.1. base_optimizer.py

Classes abstraites dont héritent tous les optimizers.

#### Classes

```python
class BaseOptimizer:
    """
    Base class pour tous les optimizers.
    Définit l'interface commune.
    """
    def __init__(self, n_assets, tickers=None):
        pass
    
    def set_weights(self, weights):
        """Définir manuellement les poids."""
        pass
    
    def clean_weights(self, cutoff=0.0001, rounding=5):
        """Nettoyer les poids (remove dust, round)."""
        pass
    
    def portfolio_performance(self, verbose=False, risk_free_rate=0.02):
        """Calculer expected return, volatility, Sharpe ratio."""
        pass

class BaseConvexOptimizer(BaseOptimizer):
    """
    Base class pour optimizers utilisant cvxpy.
    Gère les contraintes et la minimisation.
    """
    def __init__(self, n_assets, tickers=None, weight_bounds=(0, 1)):
        pass
    
    def add_constraint(self, constraint):
        """Ajouter une contrainte custom."""
        pass
    
    def add_sector_constraints(self, sector_mapper, sector_lower, sector_upper):
        """Contraintes par secteur."""
        pass
    
    def add_objective(self, new_objective):
        """Ajouter un terme à l'objective function."""
        pass
```

### 4.2. efficient_frontier/efficient_frontier.py

**Mean-Variance Optimization** : Implémentation du modèle de Markowitz.

#### Class EfficientFrontier

```python
class EfficientFrontier(BaseConvexOptimizer):
    """
    Generate optimal portfolios on the efficient frontier.
    
    Parameters:
    -----------
    expected_returns : pd.Series or array-like
        Expected returns for each asset
    cov_matrix : pd.DataFrame or np.ndarray
        Covariance matrix of asset returns
    weight_bounds : tuple(float, float), default (0, 1)
        Min and max weight for each asset
    gamma : float, default 0
        L2 regularization parameter
    """
    
    def __init__(
        self,
        expected_returns,
        cov_matrix,
        weight_bounds=(0, 1),
        solver=None,
        verbose=False,
        solver_options=None,
        gamma=0,
    ):
        pass
```

#### Méthodes principales

```python
def max_sharpe(self, risk_free_rate=0.02):
    """
    Maximize Sharpe ratio = (return - rf) / volatility
    
    Formule :
    maximize: (μᵀw - rf) / √(wᵀΣw)
    subject to: Σw = 1, w ≥ 0
    
    Returns:
    --------
    weights : dict
        Portfolio weights
    """
    pass

def min_volatility():
    """
    Minimize portfolio volatility.
    
    Formule :
    minimize: √(wᵀΣw)
    subject to: Σw = 1, w ≥ 0
    
    Returns:
    --------
    weights : dict
    """
    pass

def max_quadratic_utility(risk_aversion=1):
    """
    Maximize quadratic utility = return - λ * variance
    
    Formule :
    maximize: μᵀw - λ * wᵀΣw
    subject to: Σw = 1, w ≥ 0
    
    Parameters:
    -----------
    risk_aversion : float, default 1
        Risk aversion parameter λ
    """
    pass

def efficient_risk(target_volatility, market_neutral=False):
    """
    Maximize return for a given risk level.
    
    Formule :
    maximize: μᵀw
    subject to: √(wᵀΣw) ≤ target_volatility
                Σw = 1, w ≥ 0
    """
    pass

def efficient_return(target_return, market_neutral=False):
    """
    Minimize risk for a given return level.
    
    Formule :
    minimize: wᵀΣw
    subject to: μᵀw ≥ target_return
                Σw = 1, w ≥ 0
    """
    pass
```

### 4.3. efficient_frontier/efficient_cvar.py

Optimisation avec **Conditional Value at Risk (CVaR)** comme mesure de risque.

```python
class EfficientCVaR(BaseConvexOptimizer):
    """
    Optimize portfolio using CVaR (tail risk) instead of variance.
    
    CVaR = Expected loss beyond VaR threshold
    
    Parameters:
    -----------
    returns : pd.DataFrame
        Historical returns for each asset
    beta : float, default 0.95
        Confidence level (e.g., 0.95 for 95% CVaR)
    """
    
    def min_cvar(self):
        """
        Minimize CVaR.
        
        Formule :
        CVaR_α = E[Loss | Loss > VaR_α]
        
        où VaR_α est le α-quantile des pertes.
        """
        pass
    
    def max_return_cvar(self, target_cvar):
        """Maximize return given max CVaR."""
        pass
```

### 4.4. efficient_frontier/efficient_semivariance.py

Optimisation avec **Semivariance** (risque downside uniquement).

```python
class EfficientSemivariance(BaseConvexOptimizer):
    """
    Optimize portfolio using semivariance (downside risk only).
    
    Semivariance = variance of returns below a threshold
    
    Parameters:
    -----------
    returns : pd.DataFrame
        Historical returns
    benchmark : float, default 0
        Benchmark return (typically 0 or risk-free rate)
    """
    
    def min_semivariance(self):
        """
        Minimize semivariance.
        
        Formule :
        Semivariance = E[min(r - benchmark, 0)²]
        """
        pass
    
    def efficient_return_semivariance(self, target_return):
        """Minimize semivariance for target return."""
        pass
```

### 4.5. efficient_frontier/efficient_cdar.py

Optimisation avec **Conditional Drawdown at Risk (CDaR)**.

```python
class EfficientCDaR(BaseConvexOptimizer):
    """
    Optimize using CDaR (average of worst drawdowns).
    
    Drawdown = Peak-to-trough decline
    CDaR = Average of worst α% drawdowns
    """
    
    def min_cdar(self):
        """Minimize CDaR."""
        pass
```

### 4.6. hierarchical_portfolio.py

Méthodes **hierarchical clustering** pour diversification.

#### Class HRPOpt

```python
class HRPOpt(BaseOptimizer):
    """
    Hierarchical Risk Parity optimization.
    
    Algorithme :
    1. Compute distance matrix from correlation
    2. Hierarchical clustering (tree structure)
    3. Quasi-diagonalize covariance matrix
    4. Recursive bisection allocation
    
    Avantages vs Markowitz :
    - No need to invert covariance matrix (numerical stability)
    - More diversified portfolios
    - Better out-of-sample performance
    
    Reference: López de Prado (2016)
    """
    
    def __init__(self, returns=None, cov_matrix=None):
        pass
    
    def optimize(self):
        """
        Run HRP algorithm.
        
        Returns:
        --------
        weights : dict
            HRP portfolio weights
        """
        pass
```

#### Class HERCOpt

```python
class HERCOpt(HRPOpt):
    """
    Hierarchical Equal Risk Contribution.
    
    Extension of HRP: allocate weights such that each cluster
    contributes equally to portfolio risk.
    """
    pass
```

### 4.7. black_litterman.py

Modèle **Black-Litterman** pour combiner views et équilibre de marché.

```python
class BlackLittermanModel(BaseOptimizer):
    """
    Black-Litterman model for incorporating investor views.
    
    Formule principale :
    Posterior returns = [(τΣ)⁻¹ + PᵀΩ⁻¹P]⁻¹ [(τΣ)⁻¹π + PᵀΩ⁻¹Q]
    
    où :
    - π = market equilibrium returns (CAPM)
    - Σ = covariance matrix
    - τ = scaling factor (typically 0.01-0.05)
    - P = picking matrix (which assets are in which view)
    - Q = view returns
    - Ω = uncertainty in views
    
    Parameters:
    -----------
    cov_matrix : pd.DataFrame
        Covariance matrix
    pi : pd.Series, "market" or "equal"
        Prior estimate of returns
    market_caps : pd.Series, optional
        Market capitalizations for market-implied returns
    risk_aversion : float, default 1
        Risk aversion parameter δ
    tau : float, default 0.05
        Scaling factor for covariance
    """
    
    def __init__(
        self,
        cov_matrix,
        pi="market",
        market_caps=None,
        risk_aversion=1,
        tau=0.05,
        **kwargs,
    ):
        pass
    
    def bl_weights(self, risk_aversion=None):
        """
        Compute Black-Litterman posterior weights.
        
        Returns:
        --------
        weights : dict
            Optimal portfolio weights
        """
        pass
```

#### Définir des views

```python
# Absolute views
viewdict = {
    "AAPL": 0.20,  # AAPL will return 20%
    "MSFT": 0.15,  # MSFT will return 15%
}
bl.bl_views(viewdict)

# Relative views
viewdict = {
    ("AAPL", "MSFT"): 0.05,  # AAPL will outperform MSFT by 5%
}
bl.bl_views(viewdict)
```

### 4.8. cla.py

**Critical Line Algorithm** : Méthode analytique pour efficient frontier.

```python
class CLA(BaseOptimizer):
    """
    Critical Line Algorithm for mean-variance optimization.
    
    Avantages vs EfficientFrontier :
    - Analytically exact (no numerical optimization)
    - Very fast for computing entire efficient frontier
    - Guaranteed to find global optimum
    
    Désavantages :
    - Only works for quadratic objectives
    - No support for custom constraints
    
    Reference: Markowitz (1987)
    """
    
    def __init__(self, expected_returns, cov_matrix, weight_bounds=(0, 1)):
        pass
    
    def max_sharpe(self):
        """Find max Sharpe portfolio using CLA."""
        pass
    
    def min_volatility(self):
        """Find min volatility portfolio using CLA."""
        pass
    
    def efficient_frontier(self, points=100):
        """
        Compute entire efficient frontier.
        
        Returns:
        --------
        frontier : list of (return, volatility, weights) tuples
        """
        pass
```

### 4.9. expected_returns.py

**6 méthodes** pour estimer les returns attendus.

```python
def mean_historical_return(prices, returns_data=False, compounding=True, frequency=252, log_returns=False):
    """
    Calcule le return moyen historique (annualisé).
    
    Formules :
    - Simple : μ = (1/T) Σ rᵢ
    - Compound : μ = [(1+r₁)(1+r₂)...(1+rₜ)]^(252/T) - 1
    - Log : μ = exp((1/T) Σ ln(1+rᵢ)) - 1
    
    Parameters:
    -----------
    prices : pd.DataFrame
        Prix historiques
    compounding : bool, default True
        Use compound returns
    frequency : int, default 252
        Nombre de périodes de trading par an
    
    Returns:
    --------
    expected_returns : pd.Series
        Expected annual return for each asset
    """
    pass

def ema_historical_return(prices, returns_data=False, compounding=True, span=500, frequency=252, log_returns=False):
    """
    Exponential moving average of historical returns.
    
    Donne plus de poids aux observations récentes.
    
    Formule :
    EMA_t = α * r_t + (1-α) * EMA_(t-1)
    où α = 2 / (span + 1)
    """
    pass

def capm_return(prices, market_prices=None, returns_data=False, risk_free_rate=0.02, compounding=True, frequency=252, log_returns=False):
    """
    Compute expected returns using CAPM.
    
    Formule :
    E[rᵢ] = rf + βᵢ * (E[rₘ] - rf)
    
    où :
    - rf = risk-free rate
    - βᵢ = cov(rᵢ, rₘ) / var(rₘ)
    - E[rₘ] = expected market return
    
    Parameters:
    -----------
    prices : pd.DataFrame
        Asset prices
    market_prices : pd.DataFrame
        Market index prices (e.g., S&P500)
    risk_free_rate : float, default 0.02
        Annual risk-free rate
    """
    pass

def james_stein_shrinkage(prices, returns_data=False, risk_free_rate=0.02, frequency=252, log_returns=False):
    """
    James-Stein shrinkage estimator.
    
    Shrink sample means towards grand mean to reduce estimation error.
    
    Formule :
    μ̂ᵢ = (1 - δ) * μᵢ + δ * μ_grand
    
    où δ est calculé optimalement pour minimiser l'erreur MSE.
    """
    pass

def returns_from_prices(prices, log_returns=False):
    """
    Calculer les returns à partir des prix.
    
    Formules :
    - Simple : rₜ = (Pₜ - Pₜ₋₁) / Pₜ₋₁
    - Log : rₜ = ln(Pₜ / Pₜ₋₁)
    """
    pass

def prices_from_returns(returns, log_returns=False):
    """Reconstruire les prix à partir des returns."""
    pass
```

### 4.10. risk_models.py

**8+ méthodes** pour estimer la matrice de covariance.

```python
def sample_cov(prices, returns_data=False, frequency=252, log_returns=False, **kwargs):
    """
    Covariance matrix empirique (sample covariance).
    
    Formule :
    Σᵢⱼ = (1/T) Σₜ (rᵢₜ - μᵢ)(rⱼₜ - μⱼ)
    
    Problème : Mauvaise estimation quand T < N (curse of dimensionality)
    """
    pass

def semicovariance(prices, returns_data=False, benchmark=0, frequency=252, log_returns=False):
    """
    Covariance des returns négatifs uniquement (downside risk).
    
    Formule :
    Σᵢⱼ⁻ = (1/T) Σₜ min(rᵢₜ - μᵢ, 0) * min(rⱼₜ - μⱼ, 0)
    """
    pass

def exp_cov(prices, returns_data=False, span=180, frequency=252, log_returns=False, **kwargs):
    """
    Exponentially-weighted covariance matrix.
    
    Donne plus de poids aux observations récentes.
    
    Formule :
    Σᵢⱼ = Σₜ wₜ * (rᵢₜ - μᵢ)(rⱼₜ - μⱼ)
    où wₜ = (1-λ) * λᵗ / (1-λᵀ)
    et λ = 1 - 2/(span+1)
    """
    pass

def ledoit_wolf_shrinkage(prices, returns_data=False, frequency=252, log_returns=False):
    """
    Ledoit-Wolf optimal shrinkage covariance.
    
    Shrink sample covariance towards constant correlation matrix.
    
    Formule :
    Σ̂ = δ * F + (1-δ) * S
    
    où :
    - S = sample covariance
    - F = shrinkage target (constant correlation)
    - δ = optimal shrinkage intensity (analytically computed)
    
    Reference : Ledoit & Wolf (2004)
    """
    pass

def oracle_approximating_shrinkage(prices, returns_data=False, frequency=252, log_returns=False):
    """
    Oracle Approximating Shrinkage (OAS).
    
    Better estimation of optimal shrinkage than Ledoit-Wolf.
    
    Reference : Chen et al. (2010)
    """
    pass
```

#### Class CovarianceShrinkage

```python
class CovarianceShrinkage:
    """
    Shrinkage estimators pour covariance matrices.
    
    Multiple shrinkage targets :
    - Constant correlation
    - Diagonal (no correlation)
    - Single factor model
    - Custom target
    """
    
    def __init__(self, prices, returns_data=False, frequency=252, log_returns=False):
        pass
    
    def ledoit_wolf(self, shrinkage_target="constant_correlation"):
        """Ledoit-Wolf shrinkage avec différentes cibles."""
        pass
    
    def oracle_approximating(self):
        """OAS shrinkage."""
        pass
    
    def shrunk_covariance(self, delta=0.5):
        """Shrinkage manuel avec delta spécifié."""
        pass
```

### 4.11. objective_functions.py

**Custom objective functions** pour optimisation avancée.

```python
def L2_reg(weights, gamma=1):
    """
    L2 regularization term : γ * ||w||²
    
    Encourage plus de diversification.
    """
    pass

def quadratic_utility(weights, expected_returns, cov_matrix, risk_aversion=1, market_neutral=False):
    """
    Quadratic utility : μᵀw - λ * wᵀΣw
    
    Parameters:
    -----------
    risk_aversion : float
        Risk aversion parameter λ
    """
    pass

def sharpe_ratio(weights, expected_returns, cov_matrix, risk_free_rate=0.02):
    """
    Sharpe ratio : (μᵀw - rf) / √(wᵀΣw)
    """
    pass

def transaction_cost(weights, prev_weights, k=0.001):
    """
    Transaction cost : k * Σ|wᵢ - wᵢ_prev|
    
    Parameters:
    -----------
    k : float
        Transaction cost coefficient
    """
    pass

def ex_ante_tracking_error(weights, cov_matrix, benchmark_weights):
    """
    Tracking error vs benchmark.
    
    TE = √((w - w_b)ᵀ Σ (w - w_b))
    """
    pass

def ex_post_tracking_error(weights, returns, benchmark_returns):
    """
    Realized tracking error.
    
    TE = std(rₚ - r_b)
    """
    pass
```

### 4.12. discrete_allocation.py

Convertir **poids continus → nombre d'actions entières**.

```python
class DiscreteAllocation:
    """
    Allocate portfolio weights to discrete shares.
    
    Problème : Continuous weights (0.23456) → discrete shares (integer)
    Contrainte : Total cost ≤ budget
    
    Algorithms :
    - Greedy (LP relaxation)
    - Integer programming
    """
    
    def __init__(self, weights, latest_prices, total_portfolio_value=10000, short_ratio=None):
        """
        Parameters:
        -----------
        weights : dict
            Continuous weights {ticker: weight}
        latest_prices : dict
            Current prices {ticker: price}
        total_portfolio_value : float, default 10000
            Total cash available
        short_ratio : float, optional
            If market-neutral, ratio of shorts to longs
        """
        pass
    
    def greedy_portfolio(self, reinvest=False):
        """
        Greedy algorithm : allocate largest weights first.
        
        Returns:
        --------
        allocation : dict
            {ticker: num_shares}
        leftover : float
            Remaining cash
        """
        pass
    
    def lp_portfolio(self):
        """
        Linear programming approach (more optimal but slower).
        
        Formulation :
        maximize: Σ pᵢ * nᵢ
        subject to: Σ pᵢ * nᵢ ≤ budget
                    nᵢ ∈ ℤ⁺
        """
        pass
```

### 4.13. plotting.py

Visualisations interactives.

```python
def plot_covariance(cov_matrix, plot_correlation=False, show_tickers=True, filename=None):
    """
    Plot heatmap of covariance/correlation matrix.
    
    Uses seaborn heatmap.
    """
    pass

def plot_dendrogram(hrp, showfig=True, filename=None):
    """
    Plot hierarchical clustering dendrogram for HRP.
    
    Uses scipy.cluster.hierarchy.
    """
    pass

def plot_efficient_frontier(ef, ef_param="return", ef_param_range=None, points=100, show_assets=True, filename=None):
    """
    Plot efficient frontier curve.
    
    Parameters:
    -----------
    ef : EfficientFrontier
        Fitted optimizer
    ef_param : str, "return" or "risk"
        Which parameter to vary
    ef_param_range : tuple
        (min, max) range for parameter
    points : int
        Number of points on curve
    show_assets : bool
        Show individual assets on plot
    """
    pass

def plot_weights(weights, filename=None):
    """
    Bar plot of portfolio weights.
    """
    pass
```

---

## 5. EXEMPLES D'UTILISATION

### 5.1. Basic Mean-Variance Optimization

```python
import pandas as pd
from pypfopt import EfficientFrontier, risk_models, expected_returns

# 1. Load price data
df = pd.read_csv("stock_prices.csv", parse_dates=True, index_col="date")

# 2. Calculate expected returns and covariance
mu = expected_returns.mean_historical_return(df)
S = risk_models.sample_cov(df)

# 3. Optimize for max Sharpe ratio
ef = EfficientFrontier(mu, S)
weights = ef.max_sharpe()
cleaned_weights = ef.clean_weights()

print(cleaned_weights)
# {'AAPL': 0.25, 'MSFT': 0.20, 'AMZN': 0.18, ...}

# 4. Portfolio performance
performance = ef.portfolio_performance(verbose=True)
# Expected annual return: 21.5%
# Annual volatility: 15.3%
# Sharpe Ratio: 1.35
```

### 5.2. Risk Parity with Constraints

```python
from pypfopt import EfficientFrontier, risk_models, expected_returns

mu = expected_returns.ema_historical_return(df, span=500)
S = risk_models.exp_cov(df, span=180)

ef = EfficientFrontier(mu, S, weight_bounds=(0.05, 0.30))

# Add sector constraints
sector_mapper = {
    "AAPL": "Tech", "MSFT": "Tech", "AMZN": "Tech",
    "JPM": "Finance", "BAC": "Finance",
    "XOM": "Energy", "CVX": "Energy",
}
sector_lower = {"Tech": 0.3}  # At least 30% in Tech
sector_upper = {"Tech": 0.6, "Finance": 0.3}  # At most 60% Tech, 30% Finance

ef.add_sector_constraints(sector_mapper, sector_lower, sector_upper)

# Optimize
weights = ef.max_sharpe()
print(ef.portfolio_performance())
```

### 5.3. Black-Litterman with Views

```python
from pypfopt import BlackLittermanModel, risk_models
from pypfopt import EfficientFrontier

# Market data
S = risk_models.sample_cov(df)
market_caps = {"AAPL": 2.5e12, "MSFT": 2.2e12, "AMZN": 1.7e12}

# Initialize Black-Litterman
bl = BlackLittermanModel(S, pi="market", market_caps=market_caps)

# Define views
viewdict = {
    "AAPL": 0.20,  # Absolute: AAPL will return 20%
    ("MSFT", "AMZN"): 0.03,  # Relative: MSFT will outperform AMZN by 3%
}
bl.bl_views(viewdict)

# Get posterior expected returns
posterior_returns = bl.bl_returns()

# Optimize
ef = EfficientFrontier(posterior_returns, S)
weights = ef.max_sharpe()
print(weights)
```

### 5.4. Hierarchical Risk Parity (HRP)

```python
from pypfopt import HRPOpt, risk_models

# Calculate returns
returns = df.pct_change().dropna()

# HRP optimization
hrp = HRPOpt(returns)
weights = hrp.optimize()

print(weights)
# {'AAPL': 0.12, 'MSFT': 0.11, 'AMZN': 0.09, ...}

# Plot dendrogram
from pypfopt import plotting
plotting.plot_dendrogram(hrp)
```

### 5.5. CVaR Optimization

```python
from pypfopt import EfficientCVaR, expected_returns

# Calculate returns
returns = df.pct_change().dropna()

# Optimize for minimum CVaR
ef_cvar = EfficientCVaR(returns, beta=0.95)  # 95% CVaR
weights = ef_cvar.min_cvar()

print(weights)
```

### 5.6. Discrete Allocation

```python
from pypfopt import DiscreteAllocation

# Get continuous weights from optimization
weights = {'AAPL': 0.25, 'MSFT': 0.20, 'AMZN': 0.18, 'GOOGL': 0.15, 'FB': 0.12, 'TSLA': 0.10}

# Latest prices
latest_prices = {
    'AAPL': 175.00,
    'MSFT': 330.00,
    'AMZN': 140.00,
    'GOOGL': 130.00,
    'FB': 310.00,
    'TSLA': 240.00
}

# Allocate $100,000
da = DiscreteAllocation(weights, latest_prices, total_portfolio_value=100000)

allocation, leftover = da.greedy_portfolio()

print(allocation)
# {'AAPL': 142, 'MSFT': 60, 'AMZN': 128, 'GOOGL': 115, 'FB': 38, 'TSLA': 41}

print(f"Funds remaining: ${leftover:.2f}")
# Funds remaining: $423.00
```

### 5.7. Custom Objective Function

```python
from pypfopt import EfficientFrontier, objective_functions

ef = EfficientFrontier(mu, S)

# Add L2 regularization (encourage diversification)
ef.add_objective(objective_functions.L2_reg, gamma=0.1)

# Add transaction cost
prev_weights = {'AAPL': 0.30, 'MSFT': 0.25, ...}
ef.add_objective(objective_functions.transaction_cost, prev_weights=prev_weights, k=0.001)

# Optimize
weights = ef.max_sharpe()
```

### 5.8. Plotting Efficient Frontier

```python
from pypfopt import plotting
import matplotlib.pyplot as plt

# Create efficient frontier
ef = EfficientFrontier(mu, S)

# Plot
fig, ax = plt.subplots()
plotting.plot_efficient_frontier(ef, ax=ax, show_assets=True)

# Find max Sharpe and plot
ef_max_sharpe = EfficientFrontier(mu, S)
ef_max_sharpe.max_sharpe()
ret, std, _ = ef_max_sharpe.portfolio_performance()
ax.scatter(std, ret, marker="*", s=200, c="r", label="Max Sharpe")

# Find min volatility and plot
ef_min_vol = EfficientFrontier(mu, S)
ef_min_vol.min_volatility()
ret, std, _ = ef_min_vol.portfolio_performance()
ax.scatter(std, ret, marker="*", s=200, c="g", label="Min Volatility")

ax.legend()
plt.tight_layout()
plt.show()
```

---

## 6. FORMULES MATHÉMATIQUES PRINCIPALES

### 6.1. Mean-Variance Optimization

**Sharpe Ratio Maximization**

$$
\begin{aligned}
\text{maximize} \quad & \frac{\mu^T w - r_f}{\sqrt{w^T \Sigma w}} \\
\text{subject to} \quad & \sum_i w_i = 1 \\
& w_i \geq 0 \quad \forall i
\end{aligned}
$$

**Minimum Volatility**

$$
\begin{aligned}
\text{minimize} \quad & w^T \Sigma w \\
\text{subject to} \quad & \sum_i w_i = 1 \\
& w_i \geq 0 \quad \forall i
\end{aligned}
$$

**Quadratic Utility**

$$
\begin{aligned}
\text{maximize} \quad & \mu^T w - \frac{\lambda}{2} w^T \Sigma w \\
\text{subject to} \quad & \sum_i w_i = 1 \\
& w_i \geq 0 \quad \forall i
\end{aligned}
$$

où $\lambda$ est le coefficient d'aversion au risque.

### 6.2. Black-Litterman

**Prior (Market Equilibrium)**

$$
\pi = \delta \Sigma w_{market}
$$

où $\delta$ est l'aversion au risque du marché et $w_{market}$ les poids market-cap.

**Posterior Returns**

$$
E[R] = [(\tau \Sigma)^{-1} + P^T \Omega^{-1} P]^{-1} [(\tau \Sigma)^{-1} \pi + P^T \Omega^{-1} Q]
$$

**Posterior Covariance**

$$
\text{Cov}[R] = \Sigma + [(\tau \Sigma)^{-1} + P^T \Omega^{-1} P]^{-1}
$$

où :
- $\pi$ = prior returns (market equilibrium)
- $\Sigma$ = covariance matrix
- $\tau$ = scaling factor (confidence in prior)
- $P$ = picking matrix (views)
- $Q$ = view returns
- $\Omega$ = uncertainty in views

### 6.3. CVaR (Conditional Value at Risk)

**VaR (Value at Risk)**

$$
\text{VaR}_\alpha = \inf\{x \in \mathbb{R} : P(L > x) \leq 1 - \alpha\}
$$

où $L$ est la perte du portefeuille.

**CVaR**

$$
\text{CVaR}_\alpha = \mathbb{E}[L \mid L > \text{VaR}_\alpha]
$$

CVaR est la perte moyenne au-delà du seuil VaR.

### 6.4. Semivariance

$$
\text{Semivariance} = \frac{1}{T} \sum_{t=1}^T \min(r_t - \text{benchmark}, 0)^2
$$

Ne considère que les returns inférieurs au benchmark (downside risk).

### 6.5. Hierarchical Risk Parity

**Distance Matrix**

$$
d_{ij} = \sqrt{\frac{1 - \rho_{ij}}{2}}
$$

où $\rho_{ij}$ est la corrélation entre actifs $i$ et $j$.

**Recursive Bisection**

$$
w_i^{cluster} = w_{cluster} \times \frac{\sigma_i^{-1}}{\sum_{j \in cluster} \sigma_j^{-1}}
$$

Alloue inversement proportionnel à la volatilité au sein de chaque cluster.

### 6.6. Shrinkage Estimators

**Ledoit-Wolf Shrinkage**

$$
\hat{\Sigma} = \delta F + (1 - \delta) S
$$

où :
- $S$ = sample covariance
- $F$ = shrinkage target (constant correlation matrix)
- $\delta$ = optimal shrinkage intensity

$$
\delta^* = \frac{\sum_{i \neq j} \text{Var}(s_{ij})}{\sum_{i \neq j} (s_{ij} - f_{ij})^2}
$$

### 6.7. Performance Metrics

**Sharpe Ratio**

$$
\text{Sharpe} = \frac{E[R_p] - r_f}{\sigma_p}
$$

**Sortino Ratio** (downside deviation)

$$
\text{Sortino} = \frac{E[R_p] - r_f}{\sigma_{downside}}
$$

**Calmar Ratio**

$$
\text{Calmar} = \frac{E[R_p]}{\text{Max Drawdown}}
$$

---

## 7. INSTALLATION & DÉPENDANCES

### requirements.txt

```
numpy>=1.16.5
pandas>=0.24
matplotlib>=3.0
cvxpy>=1.1.10
scipy>=1.3
scikit-learn>=0.21
```

### Installation

```bash
# Via pip
pip install PyPortfolioOpt

# Via poetry
poetry add PyPortfolioOpt

# From source
git clone https://github.com/robertmartin8/PyPortfolioOpt
cd PyPortfolioOpt
python setup.py install
```

### Docker

```bash
# Build image
docker build -f docker/Dockerfile . -t pypfopt

# Run iPython
docker run -it pypfopt poetry run ipython

# Run Jupyter
docker run -it -p 8888:8888 pypfopt poetry run jupyter notebook --allow-root --no-browser --ip 0.0.0.0

# Run tests
docker run -t pypfopt poetry run pytest
```

---

## 8. TESTS

Suite de tests complète avec **95%+ code coverage**.

```bash
# Run all tests
pytest

# Run specific test file
pytest tests/test_efficient_frontier.py

# Run with coverage
pytest --cov=pypfopt tests/

# Run in Docker
docker run -t pypfopt poetry run pytest
```

### Test Files

```
tests/
├── test_efficient_frontier.py      # Mean-variance optimization
├── test_efficient_cvar.py          # CVaR optimization
├── test_efficient_semivariance.py  # Semivariance optimization
├── test_efficient_cdar.py          # CDaR optimization
├── test_hrp.py                     # Hierarchical Risk Parity
├── test_cla.py                     # Critical Line Algorithm
├── test_black_litterman.py         # Black-Litterman model
├── test_expected_returns.py        # Expected returns methods
├── test_risk_models.py             # Covariance estimation
├── test_objective_functions.py     # Custom objectives
├── test_discrete_allocation.py     # Discrete allocation
├── test_base_optimizer.py          # Base classes
├── test_plotting.py                # Plotting functions
├── test_imports.py                 # Import checks
└── utilities_for_tests.py          # Test utilities
```

---

## 9. POINTS FORTS & LIMITATIONS

### ✅ Points Forts

1. **API claire et intuitive** : 3-4 lignes pour un portfolio optimal
2. **Extensible** : Facile d'ajouter custom objectives et contraintes
3. **Multiple optimizers** : Mean-variance, CVaR, HRP, Black-Litterman
4. **Production-ready** : Utilisé par hedge funds et quant teams
5. **Bien documenté** : ReadTheDocs complet + Cookbook Jupyter
6. **Tests exhaustifs** : 95%+ coverage
7. **Peer-reviewed** : Publié dans Journal of Open Source Software
8. **Active maintenance** : Updates réguliers
9. **Shrinkage methods** : Ledoit-Wolf, OAS pour estimation robuste
10. **Discrete allocation** : Convertir poids → actions entières

### ⚠️ Limitations

1. **Suppose stationnarité** : Expected returns et covariance statiques
2. **Pas de transaction costs intégrés** : Doit ajouter manuellement via objective functions
3. **Pas de rebalancing automatique** : À implémenter soi-même
4. **Optimisation single-period** : Pas de dynamic programming
5. **Pas de contraintes de turnover** : Doit ajouter custom
6. **Requiert cvxpy** : Peut être difficile à installer sur certains systèmes
7. **Black-Litterman complexe** : Requiert expertise pour définir views
8. **HRP pas toujours optimal** : Peut sous-performer en sample (vs out-of-sample)
9. **Pas de gestion de données** : Utilisateur doit fournir prix nettoyés
10. **Python uniquement** : Pas de bindings pour autres langages

### 💡 Cas d'Usage Idéaux

- **Long-only portfolios** : Actions US/Europe
- **Multi-asset allocation** : Stocks + Bonds + Commodities
- **Algorithmic trading** : Combiner alpha signals optimalement
- **Fundamental investing** : Portfolio construction à partir de stock picks
- **Risk management** : Minimiser CVaR, Max Drawdown
- **Research & prototyping** : Tester différentes allocation strategies

---

## 10. RESSOURCES

### Documentation

- **ReadTheDocs** : https://pyportfolioopt.readthedocs.io/
- **Cookbook** : https://github.com/robertmartin8/PyPortfolioOpt/tree/master/cookbook
- **Examples** : https://github.com/robertmartin8/PyPortfolioOpt/tree/master/example

### Paper

- **JOSS Publication** : https://joss.theoj.org/papers/10.21105/joss.03066

### Community

- **GitHub** : https://github.com/robertmartin8/PyPortfolioOpt
- **Issues** : https://github.com/robertmartin8/PyPortfolioOpt/issues
- **Discussions** : https://github.com/robertmartin8/PyPortfolioOpt/discussions

### Installation

- **PyPI** : https://pypi.org/project/PyPortfolioOpt/
- **Docker Hub** : https://hub.docker.com/r/robertmartin8/pypfopt

### References

- **Markowitz (1952)** : "Portfolio Selection"
- **Black & Litterman (1992)** : "Global Portfolio Optimization"
- **López de Prado (2016)** : "Building Diversified Portfolios that Outperform Out of Sample"
- **Ledoit & Wolf (2004)** : "Honey, I Shrunk the Sample Covariance Matrix"

================================================================================
FIN DE L'AUDIT - PYPORTFOLIOOPT
================================================================================

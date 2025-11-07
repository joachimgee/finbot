# 📊 AUDIT TECHNIQUE - RISKFOLIO-LIB

================================================================================
**FORK** : Riskfolio-Lib (dcajasn)
**BUT** : Quantitative Strategic Asset Allocation, Easy for Everyone
**REPO** : https://github.com/dcajasn/Riskfolio-Lib
**LICENSE** : BSD-3-Clause & XL (commercial)
**VERSION** : 6.3.0+ 
**PYPI** : https://pypi.org/project/Riskfolio-Lib/
**DOCS** : https://riskfolio-lib.readthedocs.io/
**ORIGINE** : Made in Peru 🇵🇪
================================================================================

## 1. INTRODUCTION

**Riskfolio-Lib** est une librairie Python avancée pour l'allocation stratégique d'actifs et l'optimisation de portefeuille. Elle se distingue par la **richesse de ses mesures de risque** (24 convexes + 35 pour HRP) et sa **flexibilité** exceptionnelle.

### Points Forts Majeurs

✅ **24 mesures de risque convexes** : Variance, CVaR, CDaR, EVaR, RLVaR, etc.
✅ **35 mesures pour HRP/HERC** : Clustering hiérarchique avec tous types de risque
✅ **Kelly Criterion** : Logarithmic Mean Risk optimization
✅ **Black-Litterman** : Integration avancée avec views
✅ **Risk Factors** : Factor models et risk contributions
✅ **Nested Clustered Optimization (NCO)** : Combine HRP + mean-variance
✅ **Worst Case optimization** : Robust portfolio avec uncertainty sets
✅ **Constraints avancées** : Tracking error, turnover, graph-based, asset classes
✅ **Reporting** : Export Excel et Jupyter notebooks
✅ **Commercial solvers** : Support MOSEK et GUROBI pour large scale

### Statistiques Clés

- **Modules Python** : 12 fichiers principaux
- **Classes** : 2 principales (Portfolio, HCPortfolio)
- **Mesures de risque** : 24 convexes + 35 pour HRP = 59 total
- **Objective functions** : 4 (Min Risk, Max Return, Max Utility, Max Risk-Adjusted Ratio)
- **Optimization models** : 5 (Classic, Black-Litterman, Factor Model, BL-FM, Augmented BL)
- **GitHub Stars** : 3K+
- **Downloads PyPI** : 100K+/month

### Comparaison avec PyPortfolioOpt

| Feature | Riskfolio-Lib | PyPortfolioOpt |
|---------|---------------|----------------|
| Risk measures | 24 convexes | 4 (Variance, Semi-variance, CVaR, CDaR) |
| HRP risk measures | 35 | 1 (Variance) |
| Kelly Criterion | ✅ | ❌ |
| Factor Models | ✅ | ❌ |
| NCO (HRP+MV) | ✅ | ❌ |
| Worst Case | ✅ | ❌ |
| OWA | ✅ | ❌ |
| Risk contributions | ✅ (per asset & factor) | ❌ |
| Reporting | ✅ (Excel + Jupyter) | ❌ |
| Ease of use | Medium | Easy |

---

## 2. STRUCTURE DU DÉPÔT

```
Riskfolio-Lib-master/
├── riskfolio/                      # Package principal
│   ├── __init__.py                 
│   ├── src/                        # Modules core
│   │   ├── Portfolio.py            # Main Portfolio class
│   │   ├── HCPortfolio.py          # Hierarchical Clustering Portfolio
│   │   ├── ParamsEstimation.py     # Expected returns & covariance
│   │   ├── RiskFunctions.py        # 24+ risk measures calculations
│   │   ├── AuxFunctions.py         # Utility functions
│   │   ├── ConstraintsFunctions.py # Building constraints
│   │   ├── PlotFunctions.py        # Visualizations
│   │   ├── Reports.py              # Excel and Jupyter reports
│   │   ├── GerberStatistic.py      # Gerber correlation
│   │   ├── DBHT.py                 # Distance-based hierarchical trees
│   │   ├── OwaWeights.py           # OWA optimization weights
│   │   └── __init__.py
│   └── external/                   # External functions
├── docs/                           # Documentation Sphinx
├── examples/                       # Jupyter notebooks examples (30+)
├── tests/                          # Test suite
├── requirements.txt                # Dependencies
├── pyproject.toml                  # Modern Python packaging
└── README.md
```

---

## 3. CLASSES PRINCIPALES

### 3.1. Portfolio (class Portfolio)

**La classe centrale** pour tous les types d'optimisation de portefeuille.

```python
class Portfolio(object):
    """
    Class that creates a portfolio object with all properties needed to
    calculate optimal portfolios.
    
    Parameters:
    -----------
    returns : pd.DataFrame
        A dataframe that containts the returns of the assets.
    sht : bool, default False
        Allow short positions (True) or not (False).
    uppersht : float, default 1
        Maximum leverage ratio (only if sht=True).
    w_max : float, default 1
        Maximum weight for each asset.
    nea : int, optional
        Number of effective assets (cardinality constraint).
    """
    
    def __init__(self, returns=None, sht=False, uppersht=1, upperlng=1, w_max=1, w_min=0, nea=None):
        pass
```

#### Attributs principaux

```python
self.returns          # pd.DataFrame : Returns historiques
self.mu               # pd.Series : Expected returns
self.cov              # pd.DataFrame : Covariance matrix
self.mu_bl            # pd.Series : Black-Litterman returns
self.cov_bl           # pd.DataFrame : BL covariance
self.mu_f             # pd.Series : Factor model returns
self.cov_f            # pd.DataFrame : Factor covariance
self.loadings         # pd.DataFrame : Factor loadings matrix
self.factors          # pd.DataFrame : Factor returns
self.factors_stats    # pd.DataFrame : Factor statistics

# Constraints
self.ainequality      # Inequality constraints matrix A
self.binequality      # Inequality constraints vector b
self.constraints      # Liste de contraintes spéciales
self.z                # Benchmark weights
self.w_max            # Max weight per asset
self.w_min            # Min weight per asset
self.sht              # Allow short positions
self.nea              # Number of effective assets
```

### 3.2. HCPortfolio (class HCPortfolio)

**Optimisation par clustering hiérarchique** : HRP, HERC, NCO.

```python
class HCPortfolio(object):
    """
    Class for Hierarchical Clustering Portfolio optimization.
    
    Supports:
    - HRP (Hierarchical Risk Parity)
    - HERC (Hierarchical Equal Risk Contribution)
    - NCO (Nested Clustered Optimization)
    
    Parameters:
    -----------
    returns : pd.DataFrame
        Assets returns.
    alpha_tail : float, default 0.05
        Confidence level for tail risk measures (VaR, CVaR, CDaR, EDaR).
    """
    
    def __init__(self, returns=None, alpha_tail=0.05, ...):
        pass
```

---

## 4. MÉTHODES D'OPTIMISATION (Portfolio class)

### 4.1. optimization() - Mean Risk / Kelly Criterion

```python
def optimization(self, model="Classic", rm="MV", obj="Sharpe", kelly=None, rf=0, l=2, hist=True):
    """
    Mean Risk or Logarithmic Mean Risk (Kelly Criterion) Portfolio Optimization.
    
    Parameters:
    -----------
    model : str, {'Classic', 'BL', 'FM', 'BLFM', 'BL_FM', 'ABL'}
        Optimization model:
        - 'Classic': Historical data (mu, cov)
        - 'BL': Black-Litterman
        - 'FM': Factor Model
        - 'BLFM' or 'BL_FM': Black-Litterman with Factor Model
        - 'ABL': Augmented Black-Litterman
    
    rm : str, default 'MV'
        Risk measure. 24 options disponibles :
        
        **Dispersion Measures (9):**
        - 'MV' : Variance (Standard Deviation²)
        - 'KT' : Square Root Kurtosis
        - 'MAD' : Mean Absolute Deviation
        - 'GMD' : Gini Mean Difference
        - 'RG' : Range
        - 'CVRG' : CVaR Range
        - 'TG' : Tail Gini Range
        - 'EVaRG' : EVaR Range
        - 'RLVaRG' : RLVaR Range
        
        **Downside Measures (9):**
        - 'MSV' : Semi Variance (Downside Deviation²)
        - 'SKT' : Square Root Semi Kurtosis
        - 'FLPM' : First Lower Partial Moment (Omega Ratio)
        - 'SLPM' : Second Lower Partial Moment (Sortino Ratio)
        - 'CVaR' : Conditional Value at Risk
        - 'TG' : Tail Gini
        - 'EVaR' : Entropic Value at Risk
        - 'RLVaR' : Relativistic Value at Risk
        - 'WR' : Worst Realization (Minimax)
        
        **Drawdown Measures (6):**
        - 'ADD' : Average Drawdown
        - 'UCI' : Ulcer Index
        - 'CDaR' : Conditional Drawdown at Risk
        - 'EDaR' : Entropic Drawdown at Risk
        - 'RLDaR' : Relativistic Drawdown at Risk
        - 'MDD' : Maximum Drawdown
    
    obj : str, {'MinRisk', 'Sharpe', 'Utility', 'MaxRet'}
        Objective function:
        - 'MinRisk' : Minimize risk
        - 'Sharpe' : Maximize Sharpe ratio (return/risk)
        - 'Utility' : Maximize utility function (return - l*risk)
        - 'MaxRet' : Maximize return
    
    kelly : str, optional, {'approx', 'exact'}
        Use Kelly Criterion (Logarithmic Mean Risk):
        - None : Standard mean-risk optimization
        - 'approx' : Approximate Kelly (use log returns)
        - 'exact' : Exact Kelly (maximize log of wealth)
    
    rf : float, default 0
        Risk-free rate (annual).
    
    l : float, default 2
        Risk aversion parameter for 'Utility' objective.
    
    hist : bool, default True
        Use historical scenarios (True) or estimated parameters (False).
    
    Returns:
    --------
    w : pd.DataFrame
        Portfolio weights.
    """
    pass
```

#### Exemple d'utilisation

```python
import riskfolio as rp

# Create portfolio
port = rp.Portfolio(returns=df)

# Estimate parameters
port.assets_stats(method_mu='hist', method_cov='ledoit')

# Optimize for max Sharpe with CVaR
w = port.optimization(model='Classic', rm='CVaR', obj='Sharpe', rf=0.02, hist=True)

print(w)
```

### 4.2. rp_optimization() - Risk Parity

```python
def rp_optimization(self, model="Classic", rm="MV", rf=0, b=None, b_f=None, hist=True):
    """
    Risk Parity Portfolio Optimization.
    
    Allocate assets such that each contributes equally to total risk.
    
    Parameters:
    -----------
    rm : str
        Risk measure. 20 options disponibles (subset of optimization()).
    
    b : pd.Series, optional
        Risk contribution target for each asset.
        Default: equal contribution (1/n for each asset).
    
    b_f : pd.Series, optional
        Risk contribution target for each risk factor (if model='FM').
    
    Returns:
    --------
    w : pd.DataFrame
        Risk parity weights.
    """
    pass
```

#### Formulation mathématique

**Risk Parity Constraint:**

$$
\frac{\partial R(w)}{\partial w_i} \cdot w_i = b_i \cdot R(w) \quad \forall i
$$

où $R(w)$ est la mesure de risque (variance, CVaR, etc.) et $b_i$ est la contribution cible de l'actif $i$.

**Equal Risk Contribution (ERC):** $b_i = 1/n$ pour tous les actifs.

### 4.3. rrp_optimization() - Relaxed Risk Parity

```python
def rrp_optimization(self, model="Classic", version="A", l=1, b=None, hist=True):
    """
    Relaxed Risk Parity Portfolio Optimization.
    
    Combines risk parity with expected returns.
    
    Parameters:
    -----------
    version : str, {'A', 'B', 'C'}
        Relaxation version:
        - 'A': Version with return-to-risk ratio
        - 'B': Version with linear returns
        - 'C': Version with quadratic penalty
    
    l : float, default 1
        Trade-off parameter between risk parity and returns.
    """
    pass
```

### 4.4. wc_optimization() - Worst Case

```python
def wc_optimization(self, obj="Sharpe", rf=0, l=2, Umu="box", Ucov="box", box_mu=None, box_cov=None, ellip_mu=None, ellip_cov=None, ...):
    """
    Worst Case Mean Variance Portfolio Optimization.
    
    Robust optimization considering uncertainty in mu and Sigma.
    
    Parameters:
    -----------
    Umu : str, {'box', 'ellip', None}
        Uncertainty set for expected returns:
        - 'box': Box uncertainty (mu ± delta)
        - 'ellip': Ellipsoidal uncertainty
        - None: No uncertainty
    
    Ucov : str, {'box', 'ellip', None}
        Uncertainty set for covariance matrix.
    
    box_mu : float
        Size of box uncertainty for mu.
    
    box_cov : float
        Size of box uncertainty for Sigma.
    
    Returns:
    --------
    w : pd.DataFrame
        Robust portfolio weights.
    """
    pass
```

#### Formulation mathématique

**Box Uncertainty:**

$$
\begin{aligned}
\text{maximize} \quad & \min_{\mu \in \mathcal{U}_\mu, \Sigma \in \mathcal{U}_\Sigma} \frac{\mu^T w}{\sqrt{w^T \Sigma w}} \\
\text{where} \quad & \mathcal{U}_\mu = \{\mu : \|\mu - \hat{\mu}\|_\infty \leq \delta_\mu\} \\
& \mathcal{U}_\Sigma = \{\Sigma : \|\Sigma - \hat{\Sigma}\|_\infty \leq \delta_\Sigma\}
\end{aligned}
$$

### 4.5. owa_optimization() - OWA

```python
def owa_optimization(self, obj="Sharpe", owa_w=None, kelly=None, rf=0, l=2, hist=True):
    """
    Ordered Weighted Averaging (OWA) Portfolio Optimization.
    
    Generalization of CVaR, EVaR, etc. using OWA weights.
    
    Parameters:
    -----------
    owa_w : np.ndarray
        OWA weights vector (length T).
        Must be non-negative and sum to 1.
    
    obj : str
        Objective function ('Sharpe', 'Utility', etc.).
    
    Returns:
    --------
    w : pd.DataFrame
        OWA-optimized weights.
    """
    pass
```

**OWA Risk Measure:**

$$
R_{OWA}(X) = \sum_{i=1}^T \omega_i X_{(i)}
$$

où $X_{(1)} \leq X_{(2)} \leq \ldots \leq X_{(T)}$ sont les losses triés et $\omega$ les poids OWA.

**CVaR comme cas spécial:**

$$
\omega_i = \begin{cases}
\frac{1}{\alpha T} & \text{if } i \leq \alpha T \\
0 & \text{otherwise}
\end{cases}
$$

---

## 5. HIERARCHICAL CLUSTERING (HCPortfolio class)

### 5.1. optimization() - HRP / HERC

```python
def optimization(self, model="HRP", codependence="pearson", rm="MV", rf=0, linkage="single", k=None, max_k=10, bins_info="KN", alpha_tail=0.05, leaf_order=True):
    """
    Hierarchical Clustering Portfolio Optimization.
    
    Parameters:
    -----------
    model : str, {'HRP', 'HERC', 'NCO'}
        - 'HRP' : Hierarchical Risk Parity
        - 'HERC' : Hierarchical Equal Risk Contribution
        - 'NCO' : Nested Clustered Optimization
    
    codependence : str, {'pearson', 'spearman', 'abs_pearson', 'abs_spearman', 'distance', 'mutual_info', 'tail'}
        Codependence measure for clustering:
        - 'pearson': Pearson correlation
        - 'spearman': Spearman correlation
        - 'abs_pearson': |Pearson correlation|
        - 'abs_spearman': |Spearman correlation|
        - 'distance': Distance correlation
        - 'mutual_info': Mutual information
        - 'tail': Lower tail dependence
    
    rm : str
        Risk measure. 35 options pour HRP/HERC :
        
        **Dispersion (11):**
        'MV', 'MAD', 'GMD', 'MSV', 'VaR', 'CVaR', 'TG', 'EVaR', 'RLVaR', 'WR', 'RG', 'CVRG', 'TGRG', 'EVaRG', 'RLVaRG'
        
        **Drawdown (14):**
        'ADD', 'UCI', 'CDaR', 'EDaR', 'RLDaR', 'MDD' (compounded + uncompounded = 12)
        'DaR' : Drawdown at Risk
    
    linkage : str, {'single', 'complete', 'average', 'weighted', 'ward'}
        Linkage method for hierarchical clustering.
    
    k : int, optional
        Number of clusters (if specified).
    
    max_k : int, default 10
        Max number of clusters to try (if k not specified).
    
    leaf_order : bool, default True
        Optimize leaf order in dendrogram.
    
    Returns:
    --------
    w : pd.DataFrame
        HRP/HERC portfolio weights.
    """
    pass
```

#### Algorithme HRP (López de Prado 2016)

**Étape 1 : Tree Clustering**

```python
# 1. Compute distance matrix from correlation
distance = np.sqrt((1 - correlation) / 2)

# 2. Hierarchical clustering
linkage_matrix = hierarchy.linkage(distance, method='single')

# 3. Quasi-diagonalize covariance matrix
sorted_order = hierarchy.dendrogram(linkage_matrix)['leaves']
cov_quasi_diag = cov.iloc[sorted_order, sorted_order]
```

**Étape 2 : Recursive Bisection**

```python
def hrp_weights(cov_matrix):
    # Initialize
    weights = pd.Series(1, index=cov_matrix.index)
    
    # Recursive bisection
    clusters = [cov_matrix.columns.tolist()]
    while len(clusters) > 0:
        clusters = [cluster[:len(cluster)//2], cluster[len(cluster)//2:] 
                   for cluster in clusters if len(cluster) > 1]
        
        for i in range(0, len(clusters), 2):
            cluster1 = clusters[i]
            cluster2 = clusters[i+1]
            
            # Inverse variance allocation
            var1 = get_cluster_var(cov_matrix.loc[cluster1, cluster1])
            var2 = get_cluster_var(cov_matrix.loc[cluster2, cluster2])
            
            alpha = 1 - var1 / (var1 + var2)
            
            weights[cluster1] *= alpha
            weights[cluster2] *= (1 - alpha)
    
    return weights
```

### 5.2. NCO (Nested Clustered Optimization)

```python
def optimization(self, model="NCO", obj="Sharpe", rm_i="MV", rm_o="MV", ...):
    """
    Nested Clustered Optimization.
    
    Combine HRP (intra-cluster) with mean-variance (inter-cluster).
    
    Parameters:
    -----------
    rm_i : str
        Risk measure for intra-cluster optimization (within clusters).
    
    rm_o : str
        Risk measure for inter-cluster optimization (between clusters).
    
    obj : str, {'MinRisk', 'Sharpe', 'Utility', 'ERC'}
        Objective function for inter-cluster optimization.
    
    Algorithm:
    ----------
    1. Hierarchical clustering to identify clusters
    2. Within each cluster: HRP allocation
    3. Across clusters: Mean-variance optimization
    """
    pass
```

---

## 6. MESURES DE RISQUE (24 CONVEXES)

### 6.1. Dispersion Risk Measures

#### Variance (MV)

$$
\sigma^2(w) = w^T \Sigma w
$$

#### Mean Absolute Deviation (MAD)

$$
\text{MAD}(w) = \mathbb{E}[|r_p - \mathbb{E}[r_p]|] = \frac{1}{T} \sum_{t=1}^T |r_{p,t} - \mu_p|
$$

#### Gini Mean Difference (GMD)

$$
\text{GMD}(w) = \frac{1}{T^2} \sum_{i=1}^T \sum_{j=1}^T |r_{p,i} - r_{p,j}|
$$

#### Square Root Kurtosis (KT)

$$
\text{KT}(w) = \sqrt{\frac{\mathbb{E}[(r_p - \mu_p)^4]}{\sigma^4} - 1} \cdot \sigma
$$

### 6.2. Downside Risk Measures

#### Semi-Variance (MSV)

$$
\sigma^2_{downside}(w) = \mathbb{E}[\min(r_p - \text{benchmark}, 0)^2]
$$

#### Conditional Value at Risk (CVaR)

$$
\text{CVaR}_\alpha(w) = \mathbb{E}[L | L > \text{VaR}_\alpha]
$$

où $L = -r_p$ est la perte.

**Formulation linéaire (Rockafellar & Uryasev):**

$$
\begin{aligned}
\text{CVaR}_\alpha = \min_{z,u} \quad & z + \frac{1}{\alpha T} \sum_{t=1}^T u_t \\
\text{subject to} \quad & u_t \geq -r_{p,t} - z \\
& u_t \geq 0
\end{aligned}
$$

#### Entropic Value at Risk (EVaR)

$$
\text{EVaR}_\alpha(w) = \inf_{z > 0} \left\{ z \ln\left(\frac{1}{\alpha}\right) + z \ln\left(\mathbb{E}[e^{-L/z}]\right) \right\}
$$

EVaR est une relaxation convexe de CVaR.

#### Relativistic Value at Risk (RLVaR)

$$
\text{RLVaR}_\alpha(w, \kappa) = \inf_{\theta} \left\{ \theta + \kappa \ln\left(\frac{1}{\alpha} \mathbb{E}[\cosh(\frac{L - \theta}{\kappa})]\right) \right\}
$$

### 6.3. Drawdown Risk Measures

#### Maximum Drawdown (MDD)

$$
\text{MDD}(w) = \max_{t \in [0,T]} \left[ \max_{s \in [0,t]} V_s - V_t \right]
$$

où $V_t$ est la valeur du portefeuille au temps $t$.

#### Conditional Drawdown at Risk (CDaR)

$$
\text{CDaR}_\alpha(w) = \mathbb{E}[DD | DD > \text{DaR}_\alpha]
$$

où $DD$ est le drawdown et $\text{DaR}_\alpha$ est le Drawdown at Risk (α-quantile).

#### Entropic Drawdown at Risk (EDaR)

$$
\text{EDaR}_\alpha(w) = \inf_{z > 0} \left\{ z \ln\left(\frac{1}{\alpha}\right) + z \ln\left(\mathbb{E}[e^{DD/z}]\right) \right\}
$$

#### Ulcer Index (UCI)

$$
\text{UCI}(w) = \sqrt{\frac{1}{T} \sum_{t=1}^T DD_t^2}
$$

---

## 7. BLACK-LITTERMAN & FACTOR MODELS

### 7.1. Black-Litterman Views

```python
# Define views on assets
view1 = ["AAPL", "MSFT", "GOOGL"]  # Assets in view
factor1 = [0.5, -0.3, -0.2]  # Coefficients (AAPL outperforms)
q1 = 0.03  # Expected outperformance: 3%

port.views = [view1, view2, ...]
port.factors = [factor1, factor2, ...]
port.Q = np.array([q1, q2, ...])

# Estimate Black-Litterman parameters
port.blacklitterman(P=P, Q=Q, tau=0.05, delta=2.5, eq=True)

# Optimize with BL returns
w = port.optimization(model='BL', rm='CVaR', obj='Sharpe')
```

### 7.2. Factor Models

```python
# Load factor returns (e.g., Fama-French 5 factors)
factors = pd.read_csv("factors.csv", index_col=0)

# Estimate loadings via regression
port.factors = factors
port.factors_stats(method_cov='ledoit')

# Optimize with factor model
w = port.optimization(model='FM', rm='CVaR', obj='Sharpe')
```

---

## 8. CONSTRAINTS & UTILITIES

### 8.1. Building Constraints

```python
from riskfolio import ConstraintsFunctions as cf

# Asset class constraints
asset_classes = {'Tech': ['AAPL', 'MSFT', 'GOOGL'],
                 'Finance': ['JPM', 'BAC', 'GS'],
                 'Energy': ['XOM', 'CVX']}

# Min/max weights per class
A, B = cf.assets_constraints(port, asset_classes, 
                              lower={'Tech': 0.3, 'Finance': 0.1},
                              upper={'Tech': 0.6, 'Finance': 0.3})

port.ainequality = A
port.binequality = B

# Tracking error constraint
A_te, B_te = cf.tracking_error_constraint(port, benchmark_weights, max_te=0.05)

# Turnover constraint
A_to, B_to = cf.turnover_constraint(port, prev_weights, max_turnover=0.20)

# Graph-based constraints (network analysis)
A_graph, B_graph = cf.network_constraints(port, adjacency_matrix, max_network_risk=0.1)
```

### 8.2. Risk Contributions

```python
# Calculate risk contributions per asset
risk_contrib = rp.RiskFunctions.Risk_Contribution(weights, cov, rm='CVaR')

print(risk_contrib)
# Asset   Risk_Contribution
# AAPL    0.32
# MSFT    0.28
# GOOGL   0.25
# ...

# Per factor
factor_contrib = rp.RiskFunctions.Factor_Risk_Contribution(weights, loadings, factors_cov, rm='MV')
```

---

## 9. REPORTING

### 9.1. Excel Report

```python
from riskfolio import Reports as rp_reports

# Create Excel report
rp_reports.excel_report(returns, weights, 
                        rf=0.02,
                        alpha=0.05,
                        name="Portfolio_Report.xlsx")
```

**Report includes:**
- Summary statistics (return, volatility, Sharpe, Sortino, Calmar)
- Risk measures (VaR, CVaR, Max Drawdown, Ulcer Index)
- Weights pie chart
- Cumulative returns plot
- Drawdown plot
- Rolling returns
- Correlation matrix
- Risk contributions

### 9.2. Jupyter Report

```python
# Display comprehensive report in Jupyter
rp_reports.jupyter_report(returns, weights, 
                          benchmark=None,
                          rf=0.02,
                          alpha=0.05,
                          others=0.05)
```

---

## 10. VISUALIZATIONS

```python
from riskfolio import PlotFunctions as plf

# 1. Correlation matrix
plf.plot_table(port.cov, cmap="YlGn", size=(12, 10))

# 2. Dendrogram (HRP)
plf.plot_dendrogram(port.returns, codependence='pearson', linkage='ward')

# 3. Efficient frontier
mu_range = np.linspace(0.10, 0.30, 50)
ws = []
for mu_target in mu_range:
    w = port.optimization(model='Classic', rm='MV', obj='Sharpe')
    ws.append(w)

plf.plot_frontier(ws, port.returns, rm='MV')

# 4. Risk contributions pie chart
plf.plot_pie(weights=weights, title="Portfolio Allocation", others=0.05)

# 5. Histogram of returns
plf.plot_hist(port.returns, bins=50, alpha=0.7)

# 6. Cumulative returns
plf.plot_series(returns=returns, weights=weights, log_scale=False)

# 7. Drawdown plot
plf.plot_drawdown(returns=returns, weights=weights)

# 8. Risk contribution bar chart
plf.plot_risk_con(weights, cov, rm='CVaR', title="CVaR Contributions")
```

---

## 11. EXEMPLES D'UTILISATION

### 11.1. Basic Mean-CVaR Optimization

```python
import riskfolio as rp
import pandas as pd

# Load data
df = pd.read_csv("prices.csv", index_col=0, parse_dates=True)
returns = df.pct_change().dropna()

# Create portfolio
port = rp.Portfolio(returns=returns)

# Estimate parameters
port.assets_stats(method_mu='hist', method_cov='ledoit')

# Optimize for max Sharpe with CVaR
w = port.optimization(model='Classic', 
                      rm='CVaR',  # Use CVaR instead of variance
                      obj='Sharpe',
                      rf=0.02,
                      hist=True)

print(w.T)
```

### 11.2. HRP with Tail Dependence

```python
# HRP with tail dependence clustering
port_hrp = rp.HCPortfolio(returns=returns, alpha_tail=0.05)

w_hrp = port_hrp.optimization(model='HRP',
                               codependence='tail',  # Tail dependence
                               rm='CDaR',  # Conditional Drawdown at Risk
                               linkage='ward',
                               leaf_order=True)

print(w_hrp.T)
```

### 11.3. Black-Litterman with Views

```python
# Market equilibrium
port = rp.Portfolio(returns=returns)
port.assets_stats(method_mu='hist', method_cov='ledoit')

# Define views
views = [
    ["AAPL", "MSFT"],  # View 1: AAPL vs MSFT
    ["GOOGL", "AMZN", "FB"]  # View 2: GOOGL vs others
]
factors = [
    [1, -1],  # AAPL will outperform MSFT
    [0.5, -0.3, -0.2]  # GOOGL will outperform weighted avg
]
Q = np.array([0.03, 0.02])  # Expected outperformance

# Estimate BL
port.blacklitterman(P=factors, Q=Q, delta=2.5, eq=True, tau=0.05)

# Optimize
w_bl = port.optimization(model='BL', rm='MV', obj='Sharpe')
```

### 11.4. Worst Case Robust Optimization

```python
# Robust optimization with box uncertainty
w_robust = port.wc_optimization(obj='Sharpe',
                                  rf=0.02,
                                  Umu='box',  # Box uncertainty for mu
                                  Ucov='box',  # Box uncertainty for Sigma
                                  box_mu=0.05,  # ±5% uncertainty
                                  box_cov=0.10)  # ±10% uncertainty
```

### 11.5. NCO (Nested Clustered Optimization)

```python
port_nco = rp.HCPortfolio(returns=returns)

w_nco = port_nco.optimization(model='NCO',
                               obj='Sharpe',
                               rm_i='MV',  # Within clusters: Variance
                               rm_o='CVaR',  # Between clusters: CVaR
                               rf=0.02)
```

### 11.6. Risk Parity with Factor Model

```python
# Load factors (e.g., Fama-French)
factors = pd.read_csv("factors.csv", index_col=0, parse_dates=True)

port = rp.Portfolio(returns=returns)
port.factors = factors
port.factors_stats(method_cov='ledoit')

# Risk parity with factor contributions
w_rp = port.rp_optimization(model='FM',
                             rm='MV',
                             b_f=None)  # Equal factor contributions
```

### 11.7. Kelly Criterion (Logarithmic Optimization)

```python
# Maximize log wealth (Kelly Criterion)
w_kelly = port.optimization(model='Classic',
                             rm='MV',
                             obj='Sharpe',
                             kelly='exact',  # Exact Kelly
                             rf=0.02)
```

---

## 12. FORMULES MATHÉMATIQUES COMPLÈTES

### 12.1. CVaR Optimization Problem

$$
\begin{aligned}
\min_{w, z, u} \quad & z + \frac{1}{\alpha T} \sum_{t=1}^T u_t \\
\text{subject to} \quad & u_t \geq -r_{p,t} - z \quad \forall t \\
& u_t \geq 0 \quad \forall t \\
& \sum_i w_i = 1 \\
& w_i \geq 0 \quad \forall i
\end{aligned}
$$

### 12.2. Risk Parity (Variance)

$$
\frac{\partial}{\partial w_i} (w^T \Sigma w) \cdot w_i = \frac{1}{n} \cdot w^T \Sigma w \quad \forall i
$$

Simplifié :

$$
(\Sigma w)_i \cdot w_i = \frac{1}{n} \cdot w^T \Sigma w \quad \forall i
$$

### 12.3. NCO Algorithm

**Step 1: Hierarchical Clustering**

$$
d_{ij} = \sqrt{\frac{1 - \rho_{ij}}{2}}
$$

**Step 2: Intra-cluster allocation (HRP)**

Pour chaque cluster $C_k$:

$$
w_i^{(k)} = \frac{\sigma_i^{-1}}{\sum_{j \in C_k} \sigma_j^{-1}} \quad \forall i \in C_k
$$

**Step 3: Inter-cluster optimization (Mean-Variance)**

$$
\begin{aligned}
\max_{w^{cluster}} \quad & \frac{\mu_{cluster}^T w^{cluster}}{\sqrt{(w^{cluster})^T \Sigma_{cluster} w^{cluster}}} \\
\text{subject to} \quad & \sum_k w_k^{cluster} = 1 \\
& w_k^{cluster} \geq 0 \quad \forall k
\end{aligned}
$$

**Final weights:**

$$
w_i^{final} = w_{C(i)}^{cluster} \cdot w_i^{(C(i))}
$$

où $C(i)$ est le cluster de l'actif $i$.

### 12.4. Worst Case (Box Uncertainty)

$$
\begin{aligned}
\max_w \min_{\mu, \Sigma} \quad & \frac{\mu^T w - r_f}{\sqrt{w^T \Sigma w}} \\
\text{subject to} \quad & \|\mu - \hat{\mu}\|_\infty \leq \delta_\mu \\
& \|\Sigma - \hat{\Sigma}\|_\infty \leq \delta_\Sigma \\
& \sum_i w_i = 1, \quad w_i \geq 0
\end{aligned}
$$

---

## 13. INSTALLATION & DÉPENDANCES

### requirements.txt

```
numpy>=1.21.0
scipy>=1.6.3
pandas>=1.2.0
matplotlib>=3.3.0
cvxpy>=1.1.15
scikit-learn>=1.0.2
statsmodels>=0.13.0
astropy>=4.3.1
networkx>=2.5.1
```

### Installation

```bash
# Via pip
pip install riskfolio-lib

# Avec MOSEK (commercial solver)
pip install riskfolio-lib[mosek]

# Avec GUROBI (commercial solver)
pip install riskfolio-lib[gurobi]

# From source
git clone https://github.com/dcajasn/Riskfolio-Lib
cd Riskfolio-Lib
pip install -e .
```

---

## 14. POINTS FORTS & LIMITATIONS

### ✅ Points Forts

1. **24 mesures de risque convexes** : Le plus complet disponible
2. **Kelly Criterion** : Logarithmic optimization unique
3. **NCO** : Combine HRP et mean-variance intelligemment
4. **Worst Case** : Robust optimization avec uncertainty sets
5. **Factor Models** : Risk contributions per factor
6. **Reporting** : Excel et Jupyter exports automatiques
7. **Risk Parity avancé** : 20 mesures de risque pour RP
8. **Constraints flexibles** : Tracking error, turnover, graph-based, asset classes
9. **Commercial solvers** : MOSEK et GUROBI pour large scale
10. **Documentation excellente** : 30+ examples Jupyter

### ⚠️ Limitations

1. **Complexité** : Courbe d'apprentissage plus raide que PyPortfolioOpt
2. **Performance** : Plus lent pour large portfolios (sauf avec MOSEK/GUROBI)
3. **Data prep** : Nécessite nettoyage manuel des données
4. **Pas de discrete allocation** : Pas de conversion poids → actions
5. **Python only** : Pas de bindings autres langages
6. **Dependencies lourdes** : cvxpy, statsmodels, astropy
7. **Documentation dispersée** : Certaines features peu documentées
8. **Pas de rebalancing auto** : À implémenter soi-même
9. **Black-Litterman views complexes** : Syntaxe P, Q pas intuitive
10. **Commercial license** : XL license pour usage commercial

### 💡 Cas d'Usage Idéaux

- **Institutions financières** : Banks, hedge funds, asset managers
- **Risk management** : Focus sur CVaR, CDaR, tail risk
- **Multi-asset allocation** : Stocks, bonds, commodities, alternatives
- **Factor investing** : Risk parity per factor
- **Robust portfolios** : Worst case optimization avec incertitude
- **Research** : Tester différentes risk measures
- **Hierarchical approaches** : HRP, HERC, NCO pour grande diversification

---

## 15. RESSOURCES

### Documentation

- **ReadTheDocs** : https://riskfolio-lib.readthedocs.io/
- **Examples** : https://riskfolio-lib.readthedocs.io/en/latest/examples.html
- **Jupyter Notebooks** : 30+ examples dans `/examples`

### Publications

- **López de Prado (2016)** : "Building Diversified Portfolios that Outperform Out of Sample"
- **Rockafellar & Uryasev (2000)** : "Optimization of Conditional Value-at-Risk"

### Community

- **GitHub** : https://github.com/dcajasn/Riskfolio-Lib
- **Issues** : https://github.com/dcajasn/Riskfolio-Lib/issues

### Installation

- **PyPI** : https://pypi.org/project/Riskfolio-Lib/
- **Conda** : `conda install -c conda-forge riskfolio-lib`

================================================================================
FIN DE L'AUDIT - RISKFOLIO-LIB
================================================================================

# DOSSIER D'AUDIT TECHNIQUE - BACKTESTING.PY

================================================================================

## 🎯 NOM DU FORK / PROJET
**backtesting.py** - Python framework for data-driven algorithmic trading

## 📋 INTRODUCTION & BUT DU PROJET

**Titre officiel** : Backtesting.py - Backtest trading strategies with Python

**Description** : Framework Python pour backtester des stratégies de trading de manière simple et user-friendly. Permet de tester des stratégies algorithmiques avec des données OHLCV historiques.

**Objectif principal** : 
- Fournir un framework simple d'utilisation pour backtester des stratégies de trading
- Permettre l'optimisation de paramètres de stratégies
- Générer des visualisations interactives des résultats
- Calculer automatiquement 30+ métriques de performance

**Auteur/Organisation** : kernc (Keryn Knight)

**License** : AGPL-3.0

**Langage principal** : Python

**Site web** : https://kernc.github.io/backtesting.py/

---

## 📂 STRUCTURE DU DÉPÔT

### Arborescence principale

```
backtesting.py-master/
├── backtesting/              # Package principal
│   ├── __init__.py          # Exports: Backtest, Strategy
│   ├── backtesting.py       # Classes core (1764 lignes)
│   ├── lib.py               # Bibliothèque d'helpers (647 lignes)
│   ├── _stats.py            # Calculs de statistiques (213 lignes)
│   ├── _plotting.py         # Génération de graphiques Bokeh
│   ├── _util.py             # Utilitaires internes
│   ├── autoscale_cb.js      # Callback JavaScript pour plots
│   └── test/                # Tests unitaires
│       ├── __init__.py
│       ├── __main__.py
│       └── _test.py
├── doc/                      # Documentation & exemples
│   ├── examples/            # Notebooks d'exemples
│   └── scripts/             # Scripts de génération
├── requirements.txt          # Dépendances
├── setup.py                  # Installation
├── pyproject.toml           # Configuration moderne
├── setup.cfg                # Configuration setuptools
├── MANIFEST.in              # Fichiers à inclure
└── README.md                # Documentation principale
```

---

## 🔧 FICHIERS CLÉS & FONCTIONNALITÉS

### 1. **backtesting/backtesting.py** (1764 lignes)

**Rôle** : Fichier core contenant les classes principales du framework

#### Classes principales :

##### **A. Class `Strategy` (metaclass=ABCMeta)**

**But** : Classe de base abstraite pour définir des stratégies de trading

**Méthodes principales** :

```python
def __init__(self, broker, data, params):
    """
    Initialise la stratégie avec:
    - broker: gestionnaire d'ordres
    - data: données OHLCV
    - params: paramètres de la stratégie
    """
    self._indicators = []
    self._broker = broker
    self._data = data
    self._params = params
```

```python
def I(self, func: Callable, *args, name=None, plot=True, 
      overlay=None, color=None, scatter=False, **kwargs) -> np.ndarray:
    """
    MÉTHODE CRITIQUE : Déclare un indicateur technique
    
    Arguments:
    - func: fonction retournant l'indicateur (ex: SMA, EMA)
    - *args, **kwargs: arguments passés à func
    - name: nom de l'indicateur dans le plot
    - plot: afficher ou non (True par défaut)
    - overlay: superposer sur chandelier ou séparé
    - color: couleur (hex ou nom X11)
    - scatter: points ou ligne
    
    Retourne: np.ndarray de valeurs d'indicateur
    
    Note IMPORTANTE: Les indicateurs à fenêtre glissante peuvent 
    front-pad avec des NaNs. Le backtest commence seulement 
    quand tous les indicateurs ont des valeurs non-NaN.
    """
```

```python
@abstractmethod
def init(self):
    """
    À surcharger: initialisation de la stratégie.
    Déclarer ici les indicateurs avec self.I()
    Précomputer ce qui peut l'être vectoriellement
    """
    pass

@abstractmethod  
def next(self):
    """
    À surcharger: logique principale exécutée à chaque barre.
    Appelée pour chaque nouvelle ligne de données.
    Prendre ici les décisions de trading.
    """
    pass
```

```python
def buy(self, *, size: float = _FULL_EQUITY, limit: Optional[float] = None,
        stop: Optional[float] = None, sl: Optional[float] = None,
        tp: Optional[float] = None, tag: object = None) -> 'Order':
    """
    Place un ordre LONG
    
    Paramètres:
    - size: fraction d'equity (0<size<1) ou nombre d'unités (≥1)
    - limit: prix limite (None = ordre au marché)
    - stop: prix stop
    - sl: stop-loss
    - tp: take-profit
    - tag: tag personnalisé pour identifier l'ordre
    
    Retourne: objet Order
    
    Note: Ordres de marché remplis à l'ouverture de la barre suivante
          (sauf si trade_on_close=True)
          Ordres limite/stop remplis quand conditions remplies
    """
```

```python
def sell(self, *, size: float = _FULL_EQUITY, limit: Optional[float] = None,
         stop: Optional[float] = None, sl: Optional[float] = None,
         tp: Optional[float] = None, tag: object = None) -> 'Order':
    """
    Place un ordre SHORT
    
    ATTENTION: self.sell(size=.1) ne ferme PAS un trade 
    self.buy(size=.1) existant sauf si:
    - exclusive_orders=True
    - prix égal et spread=commission=0
    
    Utiliser Trade.close() ou Position.close() pour fermer explicitement
    """
```

**Propriétés exposées** :

```python
@property
def equity(self) -> float:
    """Equity actuel du compte (cash + actifs)"""
    return self._broker.equity

@property
def data(self) -> _Data:
    """
    Données de prix OHLCV
    
    Particularités:
    - N'est PAS un DataFrame mais structure custom avec numpy arrays
    - Dans init(): arrays complets (pour précalculs)
    - Dans next(): arrays partiels jusqu'à barre actuelle
    - data.Close[-1] = valeur la plus récente
    - data.Close.s = pandas Series
    - data.df = DataFrame complet
    - data.pip = plus petit changement de prix
    """
```

##### **B. Class `Order`**

**But** : Représente un ordre de trading (buy/sell)

**Propriétés** :
- `size` : taille de l'ordre (+ pour long, - pour short)
- `limit` : prix limite
- `stop` : prix stop
- `sl` : stop-loss
- `tp` : take-profit
- `parent_trade` : trade parent si c'est un ordre de fermeture

**Méthodes** :
```python
def cancel(self):
    """Annule l'ordre s'il n'est pas encore exécuté"""

def is_long(self) -> bool:
    """True si ordre long"""
    
def is_short(self) -> bool:
    """True si ordre short"""
```

##### **C. Class `Position`**

**But** : Représente la position actuelle (ensemble des trades ouverts)

**Propriétés principales** :
```python
@property
def size(self) -> float:
    """Taille de la position (+ long, - short, 0 flat)"""

@property
def pl(self) -> float:
    """Profit/Loss non réalisé de la position"""
    
@property  
def pl_pct(self) -> float:
    """P/L en pourcentage"""

@property
def is_long(self) -> bool:
    """True si position longue"""

@property
def is_short(self) -> bool:
    """True si position courte"""
```

**Méthode de fermeture** :
```python
def close(self, portion: float = 1.):
    """
    Ferme une portion de la position
    portion=1. ferme tout (défaut)
    portion=0.5 ferme la moitié
    """
```

##### **D. Class `Trade`**

**But** : Représente un trade individuel (entré et éventuellement sorti)

**Propriétés** :
```python
@property
def size(self) -> float:
    """Taille du trade"""

@property
def entry_price(self) -> float:
    """Prix d'entrée"""

@property
def exit_price(self) -> Optional[float]:
    """Prix de sortie (None si encore ouvert)"""

@property
def entry_time(self) -> datetime:
    """Timestamp d'entrée"""

@property
def exit_time(self) -> Optional[datetime]:
    """Timestamp de sortie"""

@property
def pl(self) -> float:
    """Profit/Loss du trade"""

@property
def pl_pct(self) -> float:
    """P/L en pourcentage"""

@property
def value(self) -> float:
    """Valeur du trade (taille * prix)"""
```

##### **E. Class `Backtest`**

**But** : Classe principale pour exécuter un backtest

**Signature d'initialisation** :
```python
def __init__(self,
             data: pd.DataFrame,
             strategy: Type[Strategy],
             *,
             cash: float = 10_000,
             commission: float = 0.,
             margin: float = 1.,
             trade_on_close=False,
             hedging=False,
             exclusive_orders=False,
             spread: float = 0.):
    """
    Arguments:
    - data: DataFrame OHLCV avec DatetimeIndex
    - strategy: classe Strategy (pas instance!)
    - cash: capital initial (défaut 10000)
    - commission: commission par trade (0.002 = 0.2%)
    - margin: marge requise (1. = pas de levier, 0.5 = 2x)
    - trade_on_close: exécuter sur close au lieu d'open suivant
    - hedging: autoriser positions long ET short simultanées
    - exclusive_orders: nouvel ordre annule automatiquement opposé
    - spread: spread bid-ask (0.002 = 0.2%)
    """
```

**Méthode principale d'exécution** :
```python
def run(self, **params) -> pd.Series:
    """
    Exécute le backtest avec paramètres donnés
    
    Args:
        **params: paramètres de stratégie à surcharger
        
    Returns:
        pd.Series contenant:
        - Start/End/Duration
        - Exposure Time [%]
        - Equity Final/Peak [$]
        - Return [%]
        - Buy & Hold Return [%]
        - Return (Ann.) [%]
        - Volatility (Ann.) [%]
        - CAGR [%]
        - Sharpe Ratio
        - Sortino Ratio
        - Calmar Ratio
        - Alpha [%]
        - Beta
        - Max. Drawdown [%]
        - Avg. Drawdown [%]
        - Max. Drawdown Duration
        - Avg. Drawdown Duration
        - # Trades
        - Win Rate [%]
        - Best/Worst/Avg. Trade [%]
        - Max/Avg. Trade Duration
        - Profit Factor
        - Expectancy [%]
        - SQN (System Quality Number)
        - Kelly Criterion
        - _strategy: instance de stratégie
        - _equity_curve: DataFrame avec Equity/Drawdown
        - _trades: DataFrame des trades
    """
```

**Méthode d'optimisation** :
```python
def optimize(self,
             *,
             maximize: Union[str, Callable[[pd.Series], float]] = 'SQN',
             method: str = 'grid',
             max_tries: Optional[int] = None,
             constraint: Optional[Callable[[dict], bool]] = None,
             return_heatmap: bool = False,
             return_optimization: bool = False,
             random_state: Optional[int] = None,
             **params) -> Union[pd.Series, Tuple]:
    """
    Optimise les paramètres de la stratégie
    
    Args:
        maximize: métrique à maximiser ('SQN', 'Sharpe Ratio', etc.)
                 ou fonction custom
        method: 'grid' (exhaustif) ou 'skopt' (Bayesian)
        max_tries: nombre max d'essais (grid uniquement)
        constraint: fonction de contrainte sur params
        return_heatmap: retourner heatmap des résultats
        return_optimization: retourner objet d'optimisation
        **params: ranges de paramètres (iterable ou range/slice)
        
    Returns:
        Meilleurs stats ou (stats, heatmap, optimization)
        
    Exemple:
        stats = bt.optimize(
            n1=range(5, 30, 5),
            n2=range(10, 70, 5),
            maximize='Sharpe Ratio',
            constraint=lambda p: p.n1 < p.n2
        )
    """
```

**Méthode de visualisation** :
```python
def plot(self, *,
         results: pd.Series = None,
         filename: str = '',
         plot_width: int = None,
         plot_equity: bool = True,
         plot_return: bool = False,
         plot_pl: bool = True,
         plot_volume: bool = True,
         plot_drawdown: bool = False,
         smooth_equity: bool = False,
         relative_equity: bool = True,
         superimpose: Union[bool, str] = True,
         resample: Union[bool, str] = True,
         reverse_indicators: bool = False,
         show_legend: bool = True,
         open_browser: bool = True) -> Bokeh figure:
    """
    Génère un graphique interactif Bokeh
    
    Features du plot:
    - Chandelier OHLC avec indicateurs
    - Marqueurs d'entrée/sortie de trades
    - Courbe d'equity
    - Profit/Loss
    - Volume
    - Drawdown
    - Interactivité: zoom, pan, hover tooltips
    """
```

---

### 2. **backtesting/lib.py** (647 lignes)

**Rôle** : Bibliothèque d'utilitaires, indicateurs et stratégies composables

#### Constantes d'agrégation :

```python
OHLCV_AGG = OrderedDict((
    ('Open', 'first'),
    ('High', 'max'),
    ('Low', 'min'),
    ('Close', 'last'),
    ('Volume', 'sum'),
))
# Pour resampler: df.resample('4H').agg(OHLCV_AGG).dropna()

TRADES_AGG = OrderedDict((
    ('Size', 'sum'),
    ('EntryBar', 'first'),
    ('ExitBar', 'last'),
    ('EntryPrice', 'mean'),
    ('ExitPrice', 'mean'),
    ('PnL', 'sum'),
    ('ReturnPct', 'mean'),
    ('EntryTime', 'first'),
    ('ExitTime', 'last'),
    ('Duration', 'sum'),
))
# Pour agréger trades: stats._trades.resample('1D', on='ExitTime').agg(TRADES_AGG)
```

#### Fonctions utilitaires de signal :

```python
def barssince(condition: Sequence[bool], default=np.inf) -> int:
    """
    Nombre de barres depuis la dernière fois que condition était True
    
    Exemple:
        >>> barssince(self.data.Close > self.data.Open)
        3  # Il y a 3 barres, Close était > Open
    """
    return next(compress(range(len(condition)), reversed(condition)), default)


def cross(series1: Sequence, series2: Sequence) -> bool:
    """
    True si series1 et series2 viennent de se croiser (dans n'importe quel sens)
    
    Exemple:
        >>> cross(self.data.Close, self.sma)
        True  # Close vient de croiser SMA
    """
    return crossover(series1, series2) or crossover(series2, series1)


def crossover(series1: Sequence, series2: Sequence) -> bool:
    """
    True si series1 vient de croiser AU-DESSUS de series2
    
    Formule: series1[-2] < series2[-2] AND series1[-1] > series2[-1]
    
    Exemple:
        >>> crossover(self.ma_fast, self.ma_slow)
        True  # MA rapide vient de croiser au-dessus de MA lente
    """
    series1 = (
        series1.values if isinstance(series1, pd.Series) else
        (series1, series1) if isinstance(series1, Number) else
        series1)
    series2 = (
        series2.values if isinstance(series2, pd.Series) else
        (series2, series2) if isinstance(series2, Number) else
        series2)
    try:
        return series1[-2] < series2[-2] and series1[-1] > series2[-1]
    except IndexError:
        return False


def quantile(series: Sequence, quantile: Union[None, float] = None):
    """
    Si quantile=None: retourne le rang quantile de la dernière valeur
    Si quantile entre 0-1: retourne la valeur à ce quantile
    
    Exemples:
        >>> quantile(self.data.Close[-20:], .1)
        162.130  # Valeur au 10ème percentile des 20 derniers Close
        
        >>> quantile(self.data.Close)
        0.13  # Close actuel est au 13ème percentile de l'historique
    """
    if quantile is None:
        try:
            last, series = series[-1], series[:-1]
            return np.mean(series < last)
        except IndexError:
            return np.nan
    assert 0 <= quantile <= 1
    return np.nanpercentile(series, quantile * 100)
```

#### Fonction de resampling multi-timeframe :

```python
def resample_apply(rule: str,
                   func: Optional[Callable[..., Sequence]],
                   series: Union[pd.Series, pd.DataFrame],
                   *args,
                   agg: Optional[Union[str, dict]] = None,
                   **kwargs):
    """
    Applique un indicateur sur une série resampleée à un timeframe différent
    
    UTILISATION CRITIQUE pour stratégies multi-timeframes
    
    Args:
        rule: timeframe Pandas ('D', 'W', '4H', etc.)
        func: fonction indicateur à appliquer
        series: série de données (self.data.Close, etc.)
        agg: fonction d'agrégation ('last', 'max', 'first', etc.)
        *args, **kwargs: passés à func
        
    Exemple - SMA(10) sur timeframe journalier avec données horaires:
        class System(Strategy):
            def init(self):
                self.sma_daily = resample_apply(
                    'D', SMA, self.data.Close, 10, plot=False)
                    
    Note: équivalent à:
        1. Resampler la série au timeframe voulu
        2. Appliquer l'indicateur
        3. Reindexer au timeframe original (forward-fill)
    """
```

#### Fonctions de visualisation :

```python
def plot_heatmaps(heatmap: pd.Series,
                  agg: Union[str, Callable] = 'max',
                  *,
                  ncols: int = 3,
                  plot_width: int = 1200,
                  filename: str = '',
                  open_browser: bool = True):
    """
    Génère une grille de heatmaps pour chaque paire de paramètres
    
    Args:
        heatmap: Series retournée par Backtest.optimize(return_heatmap=True)
        agg: fonction d'agrégation quand n_dimensions > 2 ('max', 'mean', etc.)
        ncols: nombre de colonnes dans la grille
        
    Utilisation typique:
        stats, heatmap = bt.optimize(
            n1=range(5, 30, 5),
            n2=range(10, 70, 5),
            n3=range(20, 100, 10),
            return_heatmap=True
        )
        plot_heatmaps(heatmap, agg='max')
    """
```

#### Fonction de recalcul de statistiques :

```python
def compute_stats(*,
                  stats: pd.Series,
                  data: pd.DataFrame,
                  trades: pd.DataFrame = None,
                  risk_free_rate: float = 0.) -> pd.Series:
    """
    Recalcule les métriques de performance pour un sous-ensemble de trades
    
    Cas d'usage:
    - Analyser séparément trades longs vs shorts
    - Analyser performance par période
    - Filtrer trades par tag ou autre critère
    
    Exemple - statistiques des trades longs uniquement:
        >>> stats = Backtest(GOOG, MyStrategy).run()
        >>> only_long = stats._trades[stats._trades.Size > 0]
        >>> long_stats = compute_stats(
        ...     stats=stats,
        ...     trades=only_long,
        ...     data=GOOG,
        ...     risk_free_rate=.02
        ... )
    """
```

#### Classes de stratégies composables :

```python
class SignalStrategy(Strategy):
    """
    Stratégie abstraite basée sur un signal long/short
    
    À surcharger: définir self.signal_long et self.signal_short
    dans init() comme arrays booléens
    
    Exemple:
        class MySignal(SignalStrategy):
            def init(self):
                self.signal_long = self.data.Close > self.sma
                self.signal_short = self.data.Close < self.sma
    """

class TrailingStrategy(Strategy):
    """
    Stratégie abstraite avec trailing stops dynamiques
    
    À surcharger: définir self.set_trailing_sl() pour stops adaptatifs
    
    Features:
    - Stops loss ajustables dynamiquement
    - Position sizing dynamique
    """
```

---

### 3. **backtesting/_stats.py** (213 lignes)

**Rôle** : Calculs de toutes les métriques de performance

#### Fonctions de calcul :

```python
def compute_drawdown_duration_peaks(dd: pd.Series) -> Tuple[pd.Series, pd.Series]:
    """
    Calcule la durée et les pics de drawdown
    
    Args:
        dd: série de drawdown (1 - equity / cummax(equity))
        
    Returns:
        (duration_series, peak_dd_series)
        
    Formule drawdown:
        DD(t) = 1 - Equity(t) / max(Equity[0:t])
    """


def geometric_mean(returns: pd.Series) -> float:
    """
    Moyenne géométrique des retours
    
    Formule:
        GM = exp(mean(log(1 + returns))) - 1
        
    Utilisé pour: Return (Ann.), CAGR
    """
    returns = returns.fillna(0) + 1
    if np.any(returns <= 0):
        return 0
    return np.exp(np.log(returns).sum() / (len(returns) or np.nan)) - 1


def compute_stats(trades: List[Trade],
                  equity: np.ndarray,
                  ohlc_data: pd.DataFrame,
                  strategy_instance: Strategy,
                  risk_free_rate: float = 0) -> pd.Series:
    """
    FONCTION CENTRALE : Calcule toutes les statistiques de performance
    
    Métriques calculées (30+):
    
    TEMPORELLES:
    - Start: date de début
    - End: date de fin  
    - Duration: durée totale
    
    RENDEMENT:
    - Equity Final [$]: capital final
    - Equity Peak [$]: capital maximum atteint
    - Return [%]: rendement total
    - Buy & Hold Return [%]: rendement si acheté et gardé
    - Return (Ann.) [%]: rendement annualisé
        Formule: (1 + total_return)^(365/days) - 1
    - CAGR [%]: Compound Annual Growth Rate
        Formule: (final_equity / initial_equity)^(1/years) - 1
    
    RISQUE:
    - Volatility (Ann.) [%]: volatilité annualisée des returns
        Formule: std(returns) * sqrt(252)
    - Max. Drawdown [%]: pire baisse depuis un pic
        Formule: max(1 - equity / cummax(equity))
    - Avg. Drawdown [%]: drawdown moyen
    - Max. Drawdown Duration: durée du plus long drawdown
    - Avg. Drawdown Duration: durée moyenne des drawdowns
    
    RATIOS RISQUE/RENDEMENT:
    - Sharpe Ratio: (return - rf) / volatility
        Formule: (mean(returns) - risk_free_rate) / std(returns) * sqrt(252)
    - Sortino Ratio: comme Sharpe mais downside deviation seulement
        Formule: (mean(returns) - rf) / std(returns[returns<0]) * sqrt(252)
    - Calmar Ratio: return / max_drawdown
        Formule: CAGR / abs(max_drawdown)
    
    EXPOSITION:
    - Exposure Time [%]: % temps en position
        Formule: sum(position != 0) / total_bars * 100
    
    MODÈLE DE MARCHÉ:
    - Alpha [%]: excès de rendement vs marché
    - Beta: sensibilité au marché (régression vs buy-hold)
    
    TRADES:
    - # Trades: nombre total de trades
    - Win Rate [%]: % de trades gagnants
        Formule: count(pnl > 0) / count(trades) * 100
    - Best Trade [%]: meilleur trade
    - Worst Trade [%]: pire trade
    - Avg. Trade [%]: trade moyen
    - Max. Trade Duration: plus long trade
    - Avg. Trade Duration: durée moyenne
    - Profit Factor: gains / pertes
        Formule: sum(pnl[pnl>0]) / abs(sum(pnl[pnl<0]))
    - Expectancy [%]: espérance de gain par trade
        Formule: mean(returns_pct)
    - SQN: System Quality Number
        Formule: sqrt(n_trades) * mean(pnl) / std(pnl)
    - Kelly Criterion: fraction optimale de capital à risquer
        Formule: win_rate - (1-win_rate)/(avg_win/avg_loss)
        
    OBJETS INTERNES:
    - _strategy: instance de Strategy
    - _equity_curve: DataFrame(Equity, DrawdownPct, DrawdownDuration)
    - _trades: DataFrame détaillé des trades
    """
```

---

### 4. **backtesting/_plotting.py**

**Rôle** : Génération de graphiques interactifs avec Bokeh

**Fonctionnalités** :
- Génère des plots HTML interactifs
- Chandelier OHLC avec zoom/pan
- Overlay d'indicateurs techniques
- Marqueurs de trades (entry/exit)
- Sous-plots pour volume, equity, P/L, drawdown
- Hover tooltips avec détails
- Légendes cliquables pour show/hide

---

### 5. **backtesting/_util.py**

**Rôle** : Utilitaires internes

**Classes principales** :

```python
class _Indicator(np.ndarray):
    """
    Wrapper numpy array pour indicateurs
    Ajoute propriétés .name, .plot, .overlay, .color, .scatter
    Permet accès .s pour pandas Series et .df pour DataFrame
    """

class _Data:
    """
    Wrapper pour données OHLCV
    Expose Open, High, Low, Close, Volume comme arrays
    Dans next(): arrays tronqués à la barre actuelle
    Propriétés .index, .pip, .s (Series), .df (DataFrame)
    """

class _Broker:
    """
    Gestionnaire d'ordres interne
    Gère positions, margin, equity, commissions
    Exécute ordres au marché, limite, stop
    """
```

**Fonctions** :
```python
def _indicator_warmup_nbars(indicator) -> int:
    """Calcule le nombre de barres de warm-up d'un indicateur (avant non-NaN)"""

def _strategy_indicators(strategy: Strategy) -> List:
    """Récupère tous les indicateurs déclarés dans une stratégie"""
```

---

## 📊 EXEMPLES DE CODE CONCRETS

### Exemple 1 : Stratégie SMA Crossover simple

```python
from backtesting import Backtest, Strategy
from backtesting.lib import crossover
from backtesting.test import SMA, GOOG


class SmaCross(Strategy):
    # Paramètres de stratégie (optimisables)
    n1 = 10  # Période MA rapide
    n2 = 20  # Période MA lente
    
    def init(self):
        # Déclarer les indicateurs
        price = self.data.Close
        self.ma1 = self.I(SMA, price, self.n1)
        self.ma2 = self.I(SMA, price, self.n2)
    
    def next(self):
        # Logique de trading
        if crossover(self.ma1, self.ma2):
            # MA rapide croise au-dessus de MA lente => Signal achat
            self.buy()
        elif crossover(self.ma2, self.ma1):
            # MA lente croise au-dessus de MA rapide => Signal vente
            self.sell()


# Exécution
bt = Backtest(GOOG, SmaCross, commission=.002, exclusive_orders=True)
stats = bt.run()
print(stats)
bt.plot()
```

**Output attendu** :
```
Start                     2004-08-19 00:00:00
End                       2013-03-01 00:00:00
Duration                   3116 days 00:00:00
Exposure Time [%]                       94.27
Equity Final [$]                     68935.12
Equity Peak [$]                      68991.22
Return [%]                             589.35
Buy & Hold Return [%]                  703.46
Return (Ann.) [%]                       25.42
Volatility (Ann.) [%]                   38.43
CAGR [%]                                16.80
Sharpe Ratio                             0.66
Sortino Ratio                            1.30
Calmar Ratio                             0.77
Alpha [%]                              450.62
Beta                                     0.02
Max. Drawdown [%]                      -33.08
Avg. Drawdown [%]                       -5.58
Max. Drawdown Duration      688 days 00:00:00
Avg. Drawdown Duration       41 days 00:00:00
# Trades                                   93
Win Rate [%]                            53.76
Best Trade [%]                          57.12
Worst Trade [%]                        -16.63
Avg. Trade [%]                           1.96
Max. Trade Duration         121 days 00:00:00
Avg. Trade Duration          32 days 00:00:00
Profit Factor                            2.13
Expectancy [%]                           6.91
SQN                                      1.78
Kelly Criterion                        0.6134
_strategy              SmaCross(n1=10, n2=20)
```

### Exemple 2 : Optimisation de paramètres

```python
# Optimisation grid search
stats = bt.optimize(
    n1=range(5, 30, 5),      # MA rapide: 5, 10, 15, 20, 25
    n2=range(10, 70, 5),     # MA lente: 10, 15, 20, ..., 65
    maximize='Sharpe Ratio',
    constraint=lambda p: p.n1 < p.n2  # MA rapide < MA lente
)

print(f'Meilleurs paramètres: n1={stats._strategy.n1}, n2={stats._strategy.n2}')
print(f'Sharpe Ratio: {stats["Sharpe Ratio"]:.2f}')
```

### Exemple 3 : Stratégie avec stop-loss et take-profit

```python
class SmaCrossWithStops(Strategy):
    n1 = 10
    n2 = 20
    stop_loss_pct = 0.02    # 2% stop loss
    take_profit_pct = 0.05  # 5% take profit
    
    def init(self):
        self.ma1 = self.I(SMA, self.data.Close, self.n1)
        self.ma2 = self.I(SMA, self.data.Close, self.n2)
    
    def next(self):
        price = self.data.Close[-1]
        
        if crossover(self.ma1, self.ma2):
            # Calculer prix de SL et TP
            sl_price = price * (1 - self.stop_loss_pct)
            tp_price = price * (1 + self.take_profit_pct)
            # Placer ordre avec SL/TP
            self.buy(sl=sl_price, tp=tp_price)
            
        elif crossover(self.ma2, self.ma1):
            sl_price = price * (1 + self.stop_loss_pct)
            tp_price = price * (1 - self.take_profit_pct)
            self.sell(sl=sl_price, tp=tp_price)
```

### Exemple 4 : Stratégie multi-indicateurs avec RSI

```python
from backtesting.test import SMA
# Supposons que nous avons un RSI défini ailleurs

class MultiIndicatorStrategy(Strategy):
    sma_period = 20
    rsi_period = 14
    rsi_overbought = 70
    rsi_oversold = 30
    
    def init(self):
        self.sma = self.I(SMA, self.data.Close, self.sma_period)
        self.rsi = self.I(RSI, self.data.Close, self.rsi_period)
    
    def next(self):
        price = self.data.Close[-1]
        
        # Condition d'achat: prix > SMA ET RSI < oversold
        if price > self.sma[-1] and self.rsi[-1] < self.rsi_oversold:
            if not self.position:  # Pas déjà en position
                self.buy()
        
        # Condition de vente: prix < SMA OU RSI > overbought
        elif price < self.sma[-1] or self.rsi[-1] > self.rsi_overbought:
            if self.position.is_long:
                self.position.close()
```

### Exemple 5 : Position sizing dynamique

```python
class DynamicSizeStrategy(Strategy):
    risk_per_trade = 0.02  # Risquer 2% du capital par trade
    n1 = 10
    n2 = 20
    
    def init(self):
        self.ma1 = self.I(SMA, self.data.Close, self.n1)
        self.ma2 = self.I(SMA, self.data.Close, self.n2)
    
    def next(self):
        if crossover(self.ma1, self.ma2):
            price = self.data.Close[-1]
            # Stop loss à 2% sous le prix
            sl_price = price * 0.98
            # Calculer taille de position basée sur risque
            risk_per_unit = price - sl_price
            units = (self.equity * self.risk_per_trade) / risk_per_unit
            self.buy(size=units, sl=sl_price)
```

### Exemple 6 : Stratégie multi-timeframe

```python
from backtesting.lib import resample_apply
from backtesting.test import SMA

class MultiTimeframeStrategy(Strategy):
    def init(self):
        # SMA court terme sur données natives (ex: horaires)
        self.sma_short = self.I(SMA, self.data.Close, 20)
        
        # SMA long terme sur timeframe journalier
        self.sma_daily = resample_apply(
            'D',                    # Timeframe journalier
            SMA,                    # Indicateur
            self.data.Close,        # Série
            50,                     # Paramètre: période 50
            plot=True,
            overlay=True
        )
    
    def next(self):
        # Trader seulement si tendance daily est haussière
        if self.data.Close[-1] > self.sma_daily[-1]:
            # Et si signal court terme
            if crossover(self.data.Close, self.sma_short):
                self.buy()
        elif self.position:
            self.position.close()
```

### Exemple 7 : Accès aux trades et calcul custom

```python
# Après exécution
stats = bt.run()

# DataFrame de tous les trades
trades = stats._trades
print(f"Nombre de trades: {len(trades)}")

# Filtrer trades gagnants
winning_trades = trades[trades['PnL'] > 0]
print(f"Win rate: {len(winning_trades)/len(trades)*100:.1f}%")

# Analyser par période
import pandas as pd
trades_by_month = trades.resample('M', on='ExitTime')['PnL'].sum()
print(trades_by_month)

# Courbe d'equity
equity_curve = stats._equity_curve
equity_curve.plot()

# Statistiques séparées pour longs et shorts
long_trades = trades[trades['Size'] > 0]
short_trades = trades[trades['Size'] < 0]

from backtesting.lib import compute_stats
long_stats = compute_stats(
    stats=stats, 
    trades=long_trades, 
    data=GOOG
)
print(f"Long only Sharpe: {long_stats['Sharpe Ratio']:.2f}")
```

---

## 🎨 EXEMPLES D'UTILISATION EN LIGNE DE COMMANDE

### Installation
```bash
pip install backtesting

# Avec dépendances optionnelles
pip install backtesting[doc]  # Pour générer documentation
```

### Exécution d'un script
```bash
python my_strategy.py
```

### Tests unitaires
```bash
python -m backtesting.test
# ou
pytest
```

---

## 📈 INDICATEURS TECHNIQUES DISPONIBLES

Le framework ne fournit PAS d'indicateurs built-in (par design).
Il est conçu pour utiliser des bibliothèques tierces:

**Bibliothèques recommandées** :

### TA-Lib
```python
import talib

class TALibStrategy(Strategy):
    def init(self):
        self.rsi = self.I(talib.RSI, self.data.Close, timeperiod=14)
        self.macd, self.signal, self.hist = self.I(
            talib.MACD, 
            self.data.Close,
            fastperiod=12,
            slowperiod=26, 
            signalperiod=9
        )
        self.bbands_upper, self.bbands_middle, self.bbands_lower = self.I(
            talib.BBANDS,
            self.data.Close,
            timeperiod=20
        )
```

**Indicateurs TA-Lib supportés** (150+) :
- Overlap Studies: SMA, EMA, DEMA, TEMA, WMA, KAMA, MAMA, T3, BBANDS, etc.
- Momentum: RSI, STOCH, MACD, ADX, CCI, MFI, Williams %R, ROC, etc.
- Volume: AD, ADOSC, OBV
- Volatility: ATR, NATR, TRANGE
- Price Transform: AVGPRICE, MEDPRICE, TYPPRICE, WCLPRICE
- Cycle: HT_DCPERIOD, HT_DCPHASE, HT_PHASOR, HT_SINE, HT_TRENDMODE
- Pattern Recognition: 60+ candlestick patterns

### Pandas-TA
```python
import pandas_ta as ta

class PandasTAStrategy(Strategy):
    def init(self):
        close_series = pd.Series(self.data.Close)
        self.sma = self.I(ta.sma, close_series, length=20)
        self.rsi = self.I(ta.rsi, close_series, length=14)
```

### Indicators custom
```python
def custom_indicator(close, period):
    """Indicateur personnalisé"""
    # Doit retourner array de même longueur que close
    return np.array([...])

class CustomStrategy(Strategy):
    def init(self):
        self.custom = self.I(custom_indicator, self.data.Close, 20)
```

---

## 🔬 FORMULES MATHÉMATIQUES CLÉS

### 1. Simple Moving Average (SMA)
```
SMA(n) = (P₁ + P₂ + ... + Pₙ) / n

où P = prix (généralement Close)
    n = période
```

### 2. Exponential Moving Average (EMA)
```
EMA(t) = Price(t) × α + EMA(t-1) × (1 - α)

où α = 2 / (n + 1)  # smoothing factor
    n = période
```

### 3. Relative Strength Index (RSI)
```
RSI = 100 - (100 / (1 + RS))

où RS = Average Gain / Average Loss
    Average Gain = EMA(gains, n)
    Average Loss = EMA(losses, n)
    n = période (généralement 14)
```

### 4. Bollinger Bands
```
Middle Band = SMA(close, n)
Upper Band = Middle Band + (k × σ)
Lower Band = Middle Band - (k × σ)

où σ = std(close, n)  # écart-type
    n = période (généralement 20)
    k = nombre d'écarts-types (généralement 2)
```

### 5. MACD (Moving Average Convergence Divergence)
```
MACD Line = EMA(close, fast) - EMA(close, slow)
Signal Line = EMA(MACD Line, signal)
Histogram = MACD Line - Signal Line

Paramètres standard: fast=12, slow=26, signal=9
```

### 6. Sharpe Ratio
```
Sharpe = (R̄ₚ - Rₖ) / σₚ × √T

où R̄ₚ = rendement moyen du portefeuille
    Rₖ = taux sans risque
    σₚ = écart-type des rendements
    T = périodes par an (252 pour daily)
```

### 7. Sortino Ratio
```
Sortino = (R̄ₚ - Rₖ) / σ_downside × √T

où σ_downside = std(returns[returns < 0])
    (seulement la volatilité négative)
```

### 8. Calmar Ratio
```
Calmar = CAGR / |Max Drawdown|

CAGR = (Equity_final / Equity_initial)^(1/years) - 1
Max DD = max(1 - Equity(t) / max(Equity[0:t]))
```

### 9. Profit Factor
```
Profit Factor = Sum(Winning Trades) / |Sum(Losing Trades)|

Interprétation:
> 2.0 : Excellent
> 1.5 : Bon
> 1.0 : Break-even
< 1.0 : Perdant
```

### 10. System Quality Number (SQN)
```
SQN = √n × (Mean(R) / Std(R))

où n = nombre de trades
    R = distribution des returns par trade
    
Interprétation Van Tharp:
> 7.0 : Holy Grail
> 5.0 : Excellent
> 3.0 : Bon
> 2.0 : Moyen
< 1.0 : Médiocre
```

### 11. Kelly Criterion
```
Kelly % = W - ((1 - W) / R)

où W = win rate (probabilité de gain)
    R = win/loss ratio (avg_win / avg_loss)
    
Exemple: W=0.6, R=2.0
Kelly = 0.6 - (0.4/2.0) = 0.4 = 40% du capital
```

### 12. Average True Range (ATR)
```
TR = max(High - Low, |High - Close_prev|, |Low - Close_prev|)
ATR = EMA(TR, n)

où n = période (généralement 14)
```

---

## 📚 DOCUMENTATION & RESSOURCES

### Documentation officielle
- **Site web** : https://kernc.github.io/backtesting.py/
- **API Reference** : https://kernc.github.io/backtesting.py/doc/backtesting/
- **Examples** : https://kernc.github.io/backtesting.py/doc/examples/

### Exemples inclus dans doc/examples/

1. **Quick Start User Guide.py**
   - Introduction de base
   - Première stratégie
   - Run et plot
   
2. **Trading with Machine Learning.py**
   - Intégration scikit-learn
   - Features engineering
   - Train/test split
   - Prédictions en streaming

3. **Strategies Library.py**
   - Collection de stratégies prêtes à l'emploi
   - SMA crossover, RSI, Bollinger, etc.
   
4. **Parameter Heatmap & Optimization.py**
   - Grid search
   - Heatmaps de performance
   - Contraintes d'optimisation
   - Bayesian optimization avec skopt

5. **Multiple Time Frames.py**
   - Stratégies multi-timeframes
   - Resampling
   - Alignement de signaux

### Dépendances
```
numpy>=1.17.0
pandas>=1.1.0
bokeh>=2.0.0,<3.0.0
```

Optionnelles:
```
scikit-optimize  # Pour méthode='skopt' dans optimize()
```

---

## 🎯 POINTS FORTS & CARACTÉRISTIQUES

### ✅ Avantages majeurs

1. **Simplicité d'utilisation**
   - API épurée : 2 classes principales (Backtest, Strategy)
   - Syntaxe intuitive
   - 10 lignes de code pour un backtest fonctionnel

2. **Performance**
   - Vectorisation numpy
   - Optimisation Cython optionnelle
   - Gère millions de barres

3. **Visualisation**
   - Graphiques interactifs HTML
   - Bokeh plots publication-ready
   - Heatmaps d'optimisation

4. **Flexibilité**
   - Compatible avec n'importe quel indicateur (TA-Lib, pandas-ta, custom)
   - Multi-timeframes natif
   - Extensible (classes composables)

5. **Métriques complètes**
   - 30+ métriques automatiques
   - Sharpe, Sortino, Calmar, SQN, Kelly, etc.
   - Statistiques par trade

6. **Optimisation intégrée**
   - Grid search
   - Bayesian optimization (skopt)
   - Contraintes custom
   - Heatmaps automatiques

### 🎨 Design patterns utilisés

- **Strategy Pattern** : Stratégies comme classes héritant de Strategy
- **Template Method** : init() et next() à surcharger
- **Decorator** : self.I() pour wrapper indicateurs
- **Composition** : Stratégies composables (lib.py)

### 🔍 Cas d'usage typiques

1. **Développement de stratégies**
   - Prototypage rapide
   - Test d'idées
   - Validation de concepts

2. **Recherche quantitative**
   - Backtests académiques
   - Comparaison de modèles
   - Walk-forward analysis

3. **Optimisation**
   - Parameter tuning
   - Recherche d'hyperparamètres
   - Robustness testing

4. **Éducation**
   - Apprentissage du trading algorithmique
   - Enseignement universitaire
   - Démonstrations

---

## ⚠️ LIMITATIONS & CONTRAINTES

### Limitations connues

1. **Pas de trading intraday sophistiqué**
   - Un ordre par barre
   - Pas de book limit order complet
   - Slippage simplifié

2. **Pas de data sourcing**
   - Ne télécharge pas les données
   - Nécessite données préparées (pandas DataFrame)

3. **Single-asset focus**
   - Un instrument à la fois
   - Pas de portfolio multi-assets natif

4. **Exécution simplifiée**
   - Market orders remplis au open suivant (sauf trade_on_close=True)
   - Pas de partial fills
   - Pas de market impact

5. **Pas de live trading**
   - Uniquement backtest historique
   - Pas de connexion broker

### Workarounds

- **Multi-assets** : Exécuter plusieurs Backtest et combiner résultats
- **Data sourcing** : Utiliser yfinance, pandas-datareader, etc. en amont
- **Live trading** : Réutiliser stratégie avec framework live (ex: bt, zipline-live)

---

## 🔬 ANNEXE - TESTS UNITAIRES

Le framework inclut une suite de tests complète dans `backtesting/test/`

### Tests couverts

```python
# _test.py contient tests pour:

# Test 1: Exécution basique
def test_run():
    """Vérifie qu'un backtest s'exécute sans erreur"""

# Test 2: Ordres
def test_orders():
    """Vérifie market, limit, stop orders"""

# Test 3: Position management
def test_position():
    """Vérifie long, short, close, size"""

# Test 4: Stop-loss / Take-profit
def test_sl_tp():
    """Vérifie triggers SL/TP"""

# Test 5: Commissions
def test_commission():
    """Vérifie calcul commissions"""

# Test 6: Indicateurs
def test_indicators():
    """Vérifie déclaration et accès indicateurs"""

# Test 7: Optimisation
def test_optimization():
    """Vérifie grid search et skopt"""

# Test 8: Plotting
def test_plotting():
    """Vérifie génération plots"""

# Test 9: Statistiques
def test_stats():
    """Vérifie calcul métriques"""

# Test 10: Multi-timeframe
def test_resample():
    """Vérifie resample_apply()"""
```

### Lancer les tests
```bash
python -m backtesting.test
# ou
pytest backtesting/
```

---

## 💡 SNIPPETS UTILES

### 1. Charger données depuis CSV
```python
import pandas as pd

df = pd.read_csv('data.csv', index_col='Date', parse_dates=True)
df = df[['Open', 'High', 'Low', 'Close', 'Volume']]

bt = Backtest(df, MyStrategy)
stats = bt.run()
```

### 2. Données depuis Yahoo Finance
```python
import yfinance as yf

df = yf.download('AAPL', start='2020-01-01', end='2023-01-01')
df = df[['Open', 'High', 'Low', 'Close', 'Volume']]

bt = Backtest(df, MyStrategy)
```

### 3. Walk-forward analysis
```python
import pandas as pd

results = []
window_size = 252  # 1 an
test_size = 63     # 3 mois

for i in range(0, len(data) - window_size - test_size, test_size):
    train_data = data.iloc[i:i+window_size]
    test_data = data.iloc[i+window_size:i+window_size+test_size]
    
    # Optimiser sur train
    bt_train = Backtest(train_data, MyStrategy)
    stats_train = bt_train.optimize(
        param1=range(10, 50, 5),
        param2=range(20, 100, 10),
        maximize='Sharpe Ratio'
    )
    
    # Tester sur test
    bt_test = Backtest(test_data, MyStrategy)
    stats_test = bt_test.run(
        param1=stats_train._strategy.param1,
        param2=stats_train._strategy.param2
    )
    
    results.append(stats_test)

# Analyser résultats
walk_forward_returns = [s['Return [%]'] for s in results]
```

### 4. Sauvegarder résultats
```python
# Sauvegarder statistiques
stats.to_csv('stats.csv')

# Sauvegarder trades
stats._trades.to_csv('trades.csv')

# Sauvegarder equity curve
stats._equity_curve.to_csv('equity.csv')

# Sauvegarder plot HTML
bt.plot(filename='backtest.html', open_browser=False)
```

### 5. Comparer stratégies
```python
strategies = {
    'SMA10-20': (MyStrategy, {'n1': 10, 'n2': 20}),
    'SMA20-50': (MyStrategy, {'n1': 20, 'n2': 50}),
    'SMA50-200': (MyStrategy, {'n1': 50, 'n2': 200}),
}

results = {}
for name, (strat_class, params) in strategies.items():
    bt = Backtest(data, strat_class)
    stats = bt.run(**params)
    results[name] = stats

# Comparer
comparison = pd.DataFrame({
    name: stats[['Return [%]', 'Sharpe Ratio', 'Max. Drawdown [%]', '# Trades']]
    for name, stats in results.items()
}).T
print(comparison)
```

---

## 📊 MÉTRIQUES DE PERFORMANCE - RÉFÉRENCE COMPLÈTE

| Métrique | Formule | Interprétation |
|----------|---------|----------------|
| **Return [%]** | (Final Equity - Initial Equity) / Initial Equity × 100 | Rendement total brut |
| **Return (Ann.) [%]** | ((1 + Return)^(365/days) - 1) × 100 | Rendement annualisé |
| **CAGR [%]** | ((Final/Initial)^(1/years) - 1) × 100 | Taux croissance composé annuel |
| **Volatility (Ann.) [%]** | std(daily_returns) × √252 × 100 | Volatilité annualisée |
| **Sharpe Ratio** | (Return_ann - RF) / Volatility_ann | > 1 Bon, > 2 Excellent |
| **Sortino Ratio** | (Return_ann - RF) / Downside_Vol | Sharpe avec vol négative |
| **Calmar Ratio** | CAGR / abs(Max_DD) | > 3 Bon, > 5 Excellent |
| **Max Drawdown [%]** | max(Peak - Trough) / Peak × 100 | Pire baisse depuis pic |
| **Avg Drawdown [%]** | mean(all_drawdowns) | Drawdown moyen |
| **Win Rate [%]** | Winning_Trades / Total_Trades × 100 | % trades gagnants |
| **Profit Factor** | Sum(Wins) / abs(Sum(Losses)) | > 1.5 Bon, > 2 Excellent |
| **Expectancy [%]** | mean(trade_returns_pct) | Gain moyen par trade |
| **SQN** | √n × mean(R) / std(R) | > 3 Bon, > 5 Excellent |
| **Kelly Criterion** | WinRate - (1-WinRate)/(AvgWin/AvgLoss) | Fraction optimale à risquer |

---

## 🎓 CONCLUSION

**backtesting.py** est un framework Python mature, performant et user-friendly pour:
- ✅ Backtester des stratégies de trading algorithmiques
- ✅ Optimiser des paramètres de stratégies
- ✅ Calculer automatiquement 30+ métriques de performance
- ✅ Générer des visualisations interactives
- ✅ Prototyper rapidement des idées de trading

**Points forts** :
- API simple et intuitive
- Documentation excellente
- Performance (vectorisation numpy)
- Extensibilité
- Visualisations publication-ready

**Limitations** :
- Single-asset (pas de portfolio multi-assets natif)
- Pas de live trading
- Exécution simplifiée (pas de partial fills, market impact, etc.)

**Cas d'usage idéaux** :
- Développement et test de stratégies
- Recherche quantitative
- Enseignement
- Prototypage rapide

================================================================================
FIN DU DOSSIER D'AUDIT - BACKTESTING.PY
================================================================================

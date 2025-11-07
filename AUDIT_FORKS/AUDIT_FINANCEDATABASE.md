# DOSSIER D'AUDIT TECHNIQUE - FINANCEDATABASE

================================================================================

## 🎯 NOM DU FORK / PROJET
**FinanceDatabase** - Comprehensive Financial Products Database (300,000+ symbols)

## 📋 INTRODUCTION & BUT DU PROJET

**Titre officiel** : FinanceDatabase - Financial Products Categorization Database

**Description** : Base de données Python de 300,000+ symboles financiers couvrant Equities, ETFs, Funds, Indices, Currencies, Cryptocurrencies et Money Markets avec catégorisation complète par secteur/industrie/pays.

**Objectif principal** :
- Fournir accès à une base complète de produits financiers mondiaux
- Catégoriser selon standards GICS (sectors/industries)
- Permettre filtrage multi-critères avancé
- Offrir metadata complètes (ISIN, CUSIP, FIGI, etc.)
- Alternative gratuite et open-source aux bases payantes

**Auteur** : JerBouma (Jeroen Bouma)

**License** : MIT

**Site web** : https://www.jeroenbouma.com/projects/financedatabase

**GitHub** : https://github.com/JerBouma/FinanceDatabase

---

## 📊 STATISTIQUES DE LA DATABASE

| Produit Type     | Quantité | Secteurs | Industries | Pays | Exchanges |
|------------------|----------|----------|------------|------|-----------|
| **Equities**     | 158,429  | 12       | 63         | 111  | 83        |
| **ETFs**         | 36,786   | 295      | 22         | 111  | 53        |
| **Funds**        | 57,881   | 1,541    | 52         | 111  | 34        |
| **Currencies**   | 2,556    | 175 Currencies |        |      |           |
| **Cryptocurrencies** | 3,367 | 352 Cryptos |          |      |           |
| **Indices**      | 91,183   | 64 Exchanges |          |      |           |
| **Money Markets**| 1,367    | 3 Exchanges  |          |      |           |

**TOTAL** : **300,000+ produits financiers**

---

## 📂 STRUCTURE DU DÉPÔT

```
FinanceDatabase-main/
├── README.md                    # Documentation complète
├── CONTRIBUTING.md              # Guide de contribution
├── pyproject.toml               # Configuration Python
├── LICENSE                      # Licence MIT
│
├── financedatabase/            # Package principal
│   ├── __init__.py             # Exports publics
│   ├── helpers.py              # Classes de base
│   ├── Equities.py             # Module Actions (291 lignes)
│   ├── ETFs.py                 # Module ETFs
│   ├── Funds.py                # Module Fonds
│   ├── Indices.py              # Module Indices
│   ├── Currencies.py           # Module Devises
│   ├── Cryptos.py              # Module Cryptos
│   └── Moneymarkets.py         # Module Money Markets
│
├── database/                    # Données compressées (.bz2)
│   ├── equities.bz2            # 158K actions
│   ├── etfs.bz2                # 36K ETFs
│   ├── funds.bz2               # 57K fonds
│   ├── indices.bz2             # 91K indices
│   ├── currencies.bz2          # 2.5K devises
│   ├── cryptos.bz2             # 3.3K cryptos
│   └── moneymarkets.bz2        # 1.3K money markets
│
├── compression/                 # Scripts de compression
├── parsers/                     # Parsers de données
├── examples/                    # Notebooks d'exemples
└── tests/                       # Tests unitaires
```

---

## 🔧 CLASSES PRINCIPALES & API

### 1. **Classe `Equities`** (Actions)

**Rôle** : Interroger la base de 158,429 actions mondiales

```python
from financedatabase import Equities

# Initialisation (charge data une seule fois)
equities = Equities()

# Sélection de base - Toutes les actions
all_equities = equities.select()
# Returns: DataFrame avec 158,429 lignes

# Filtrage par pays
us_equities = equities.select(country="United States")
# Returns: Actions US uniquement (~8,000)

# Filtrage par secteur GICS
tech_equities = equities.select(sector="Information Technology")
# Returns: Toutes actions tech mondiale

# Filtrage multi-critères
us_tech_large_cap = equities.select(
    country="United States",
    sector="Information Technology",
    market_cap="Large Cap"  # > $10B
)
# Returns: AAPL, MSFT, GOOGL, etc.

# Filtrage par industry (plus granulaire)
software_stocks = equities.select(
    industry="Software"
)

# Filtrage par exchange
nasdaq_stocks = equities.select(
    exchange="NMS"  # NASDAQ Global Select
)

# Primary listings uniquement (éviter duplicates)
primary_only = equities.select(
    country="United States",
    only_primary_listing=True
)
```

**Colonnes retournées** :
```python
columns = [
    'symbol',           # Ticker (ex: AAPL)
    'name',             # Nom complet
    'currency',         # Devise de cotation (USD, EUR, etc.)
    'sector',           # Secteur GICS
    'industry_group',   # Groupe industrie GICS
    'industry',         # Industrie GICS
    'exchange',         # Code exchange
    'market',           # Nom du marché
    'country',          # Pays
    'state',            # État (US)
    'city',             # Ville du siège
    'zipcode',          # Code postal
    'website',          # Site web
    'market_cap',       # Catégorie: Mega/Large/Mid/Small/Micro Cap
    'isin',             # Code ISIN
    'cusip',            # Code CUSIP
    'figi',             # Code FIGI
    'composite_figi',   # FIGI Composite
    'shareclass_figi'   # FIGI Share Class
]
```

**Secteurs GICS disponibles** (12) :
```python
sectors = [
    'Energy',
    'Materials',
    'Industrials',
    'Consumer Discretionary',
    'Consumer Staples',
    'Health Care',
    'Financials',
    'Information Technology',
    'Communication Services',
    'Utilities',
    'Real Estate',
    'Unknown'
]
```

**Exemple d'output** :
```
     symbol  name                    sector      industry        country    market_cap
0    AAPL    Apple Inc.              Info Tech   Hardware        US         Mega Cap
1    MSFT    Microsoft Corporation   Info Tech   Software        US         Mega Cap
2    GOOGL   Alphabet Inc.           Comm Svc    Internet        US         Mega Cap
```

---

### 2. **Classe `ETFs`** (Exchange-Traded Funds)

**Rôle** : Interroger 36,786 ETFs mondiaux

```python
from financedatabase import ETFs

etfs = ETFs()

# Tous les ETFs
all_etfs = etfs.select()

# ETFs par catégorie
equity_etfs = etfs.select(category="Equity")
bond_etfs = etfs.select(category="Fixed Income")
commodity_etfs = etfs.select(category="Commodities")

# ETFs par famille (provider)
vanguard_etfs = etfs.select(family="Vanguard")
ishares_etfs = etfs.select(family="iShares")
spdr_etfs = etfs.select(family="SPDR")

# ETFs par region
europe_etfs = etfs.select(category_group="Europe Equity")
asia_etfs = etfs.select(category_group="Asia Equity")

# Combinaisons
us_large_cap_etfs = etfs.select(
    category="Large Cap Equity",
    country="United States"
)
```

**295 catégories d'ETFs** incluant :
- Equity (Large/Mid/Small Cap, Growth/Value, Sectors)
- Fixed Income (Government, Corporate, High Yield)
- Commodities (Gold, Oil, Agriculture)
- Alternative (Real Estate, Currencies, Volatility)
- Multi-Asset (Balanced, Target Date)

---

### 3. **Classe `Funds`** (Mutual Funds)

**Rôle** : Interroger 57,881 fonds mutuels

```python
from financedatabase import Funds

funds = Funds()

# Fonds par catégorie
equity_funds = funds.select(category="Equity")
bond_funds = funds.select(category="Bond")
balanced_funds = funds.select(category="Allocation")

# Fonds par famille
fidelity_funds = funds.select(family="Fidelity")
vanguard_funds = funds.select(family="Vanguard")
```

**1,541 catégories de fonds** couvrant toutes stratégies d'investissement

---

### 4. **Classe `Indices`** (Indices Boursiers)

**Rôle** : Interroger 91,183 indices mondiaux

```python
from financedatabase import Indices

indices = Indices()

# Tous les indices
all_indices = indices.select()

# Indices par exchange
sp_indices = indices.select(market="S&P")  # S&P 500, S&P 400, etc.
msci_indices = indices.select(market="MSCI")  # MSCI World, MSCI EM, etc.
ftse_indices = indices.select(market="FTSE")  # FTSE 100, FTSE 250, etc.

# Indices par catégorie
equity_indices = indices.select(category="Equity")
bond_indices = indices.select(category="Bond")
commodity_indices = indices.select(category="Commodity")
```

**64 exchanges d'indices** incluant S&P, MSCI, FTSE, DAX, CAC, Nikkei, etc.

---

### 5. **Classe `Currencies`** (Devises)

**Rôle** : Interroger 2,556 paires de devises

```python
from financedatabase import Currencies

currencies = Currencies()

# Toutes les paires
all_pairs = currencies.select()

# Paires par base currency
usd_pairs = currencies.select(base="USD")  # USD/EUR, USD/JPY, etc.
eur_pairs = currencies.select(base="EUR")  # EUR/USD, EUR/GBP, etc.

# Paires par quote currency
to_usd = currencies.select(quote="USD")  # EUR/USD, GBP/USD, JPY/USD, etc.
```

**175 devises** couvrant monnaies majeures, mineures et exotiques

---

### 6. **Classe `Cryptos`** (Cryptocurrencies)

**Rôle** : Interroger 3,367 cryptomonnaies

```python
from financedatabase import Cryptos

cryptos = Cryptos()

# Toutes les cryptos
all_cryptos = cryptos.select()

# Cryptos par quote currency
btc_pairs = cryptos.select(quote="BTC")  # ETH/BTC, XRP/BTC, etc.
usdt_pairs = cryptos.select(quote="USDT")  # BTC/USDT, ETH/USDT, etc.
```

**352 cryptomonnaies** incluant Bitcoin, Ethereum, altcoins, stablecoins

---

### 7. **Classe `Moneymarkets`** (Money Markets)

**Rôle** : Interroger 1,367 instruments money market

```python
from financedatabase import Moneymarkets

moneymarkets = Moneymarkets()

# Tous les instruments
all_mm = moneymarkets.select()

# Par exchange
nyse_mm = moneymarkets.select(exchange="NYS")
```

---

## 🎨 MÉTHODES UTILITAIRES

### `show_options()` - Voir toutes les options de filtrage

```python
from financedatabase import Equities

equities = Equities()

# Voir tous les secteurs disponibles
sectors = equities.show_options(selection='sector')
print(sectors)
# ['Energy', 'Materials', 'Industrials', ...]

# Voir toutes les industries
industries = equities.show_options(selection='industry')
print(len(industries))  # 63 industries

# Voir tous les pays
countries = equities.show_options(selection='country')
print(len(countries))  # 111 pays

# Voir tous les exchanges
exchanges = equities.show_options(selection='exchange')
print(len(exchanges))  # 83 exchanges

# Voir toutes les catégories de market cap
market_caps = equities.show_options(selection='market_cap')
# ['Mega Cap', 'Large Cap', 'Mid Cap', 'Small Cap', 'Micro Cap', 'Nano Cap']
```

### `search()` - Recherche par mot-clé

```python
# Rechercher "Apple" dans les noms
apple_stocks = equities.search(name='Apple')
# Returns: AAPL, AAPL.MX, AAPL.SW, etc. (tous les listings)

# Rechercher par ticker
msft = equities.search(symbol='MSFT')

# Recherche partielle avec regex
tech_names = equities.search(name='.*Tech.*', regex=True)
```

---

## 💡 EXEMPLES D'UTILISATION PRATIQUES

### Exemple 1 : Screener d'actions tech US large cap

```python
from financedatabase import Equities

equities = Equities()

# Filtrer actions tech US > $10B
us_tech_large = equities.select(
    country="United States",
    sector="Information Technology",
    market_cap=["Large Cap", "Mega Cap"],
    only_primary_listing=True
)

print(f"Trouvé {len(us_tech_large)} actions")
print(us_tech_large[['symbol', 'name', 'industry', 'market_cap']].head(10))

# Output exemple:
#    symbol  name                    industry        market_cap
# 0  AAPL    Apple Inc.              Hardware        Mega Cap
# 1  MSFT    Microsoft Corporation   Software        Mega Cap
# 2  NVDA    NVIDIA Corporation      Semiconductors  Mega Cap
# ...
```

### Exemple 2 : Tous les ETFs Vanguard low-cost

```python
from financedatabase import ETFs

etfs = ETFs()

# ETFs Vanguard aux US
vanguard_us = etfs.select(
    family="Vanguard",
    country="United States"
)

print(f"Nombre d'ETFs Vanguard US: {len(vanguard_us)}")
# Résultat: ~400 ETFs

# Extraire les tickers pour usage avec yfinance
tickers = vanguard_us.index.tolist()
# ['VTI', 'VOO', 'VEA', 'VWO', 'BND', ...]
```

### Exemple 3 : Analyse sectorielle globale

```python
from financedatabase import Equities
import pandas as pd

equities = Equities()

# Compter actions par secteur et pays
all_equities = equities.select()

sector_country = all_equities.groupby(['sector', 'country']).size().reset_index(name='count')
sector_country = sector_country.sort_values('count', ascending=False)

print(sector_country.head(20))

# Concentration par secteur
sector_counts = all_equities['sector'].value_counts()
print("\nDistribution sectorielle:")
print(sector_counts)
```

### Exemple 4 : Combiner avec yfinance pour données en temps réel

```python
import financedatabase as fd
import yfinance as yf

# 1. Obtenir universe d'actions
equities = fd.Equities()
healthcare = equities.select(
    sector="Health Care",
    country="United States",
    market_cap="Large Cap",
    only_primary_listing=True
)

# 2. Extraire tickers
tickers = healthcare.index.tolist()[:10]  # Top 10
print(f"Analysing: {tickers}")

# 3. Télécharger données historiques
data = yf.download(tickers, start="2020-01-01", end="2024-01-01")['Adj Close']

# 4. Calculer performance
returns = data.pct_change().mean() * 252  # Annualized
volatility = data.pct_change().std() * np.sqrt(252)
sharpe = returns / volatility

print("\nPerformance:")
print(pd.DataFrame({'Return': returns, 'Volatility': volatility, 'Sharpe': sharpe}).sort_values('Sharpe', ascending=False))
```

### Exemple 5 : Créer un screener custom multi-critères

```python
from financedatabase import Equities

def custom_screener(
    sectors=None,
    countries=None, 
    min_market_cap='Mid Cap',
    exchanges=None
):
    """
    Screener personnalisé avec critères multiples
    """
    equities = Equities()
    
    # Market cap hierarchy
    cap_hierarchy = ['Nano Cap', 'Micro Cap', 'Small Cap', 'Mid Cap', 'Large Cap', 'Mega Cap']
    min_cap_index = cap_hierarchy.index(min_market_cap)
    allowed_caps = cap_hierarchy[min_cap_index:]
    
    # Apply filters
    results = equities.select(
        sector=sectors,
        country=countries,
        market_cap=allowed_caps,
        exchange=exchanges,
        only_primary_listing=True
    )
    
    return results

# Usage
emerging_tech = custom_screener(
    sectors=['Information Technology', 'Communication Services'],
    countries=['United States', 'China', 'India'],
    min_market_cap='Mid Cap'
)

print(f"Found {len(emerging_tech)} stocks matching criteria")
```

---

## 📊 STRUCTURE DES DONNÉES

### Schéma type pour Equities

```python
{
    'symbol': 'AAPL',                          # Ticker
    'name': 'Apple Inc.',                       # Nom complet
    'currency': 'USD',                          # Devise
    'sector': 'Information Technology',         # Secteur GICS niveau 1
    'industry_group': 'Technology Hardware',    # GICS niveau 2
    'industry': 'Technology Hardware',          # GICS niveau 3
    'exchange': 'NMS',                          # Code exchange
    'market': 'NASDAQ Global Select',           # Nom marché
    'country': 'United States',                 # Pays
    'state': 'CA',                              # État
    'city': 'Cupertino',                        # Ville
    'zipcode': '95014',                         # Code postal
    'website': 'http://www.apple.com',          # Site web
    'market_cap': 'Mega Cap',                   # Catégorie cap
    'isin': 'US0378331005',                     # Code ISIN
    'cusip': '037833100',                       # Code CUSIP
    'figi': 'BBG000B9XRY4',                     # Code FIGI
    'composite_figi': 'BBG000B9XRY4',          # FIGI composite
    'shareclass_figi': 'BBG001S5N8V8'          # FIGI share class
}
```

---

## 🚀 INSTALLATION & UTILISATION

### Installation
```bash
pip install financedatabase -U
```

### Import
```python
import financedatabase as fd

# Ou imports spécifiques
from financedatabase import Equities, ETFs, Funds
```

### Usage basique complet
```python
import financedatabase as fd

# 1. Initialiser (une fois)
equities = fd.Equities()
etfs = fd.ETFs()
funds = fd.Funds()

# 2. Explorer options disponibles
print("Secteurs:", fd.show_options("equities", "sector"))
print("Pays:", fd.show_options("equities", "country"))

# 3. Filtrer
us_tech = equities.select(
    country="United States",
    sector="Information Technology"
)

# 4. Exporter
us_tech.to_csv("us_tech_stocks.csv")
```

---

## 🎯 POINTS FORTS

1. **Comprehensive** : 300K+ produits financiers
2. **Gratuit & Open-Source** : Alternative aux Bloomberg/Reuters
3. **Bien structuré** : Classification GICS standard
4. **Metadata riches** : ISIN, CUSIP, FIGI inclus
5. **Facile d'utilisation** : API Python simple
6. **Maintenu activement** : Mises à jour régulières
7. **Flexible** : Filtrage multi-critères
8. **Intégration** : Compatible yfinance, FinanceToolkit

---

## ⚠️ LIMITATIONS

1. **Pas de données de prix** : Uniquement metadata (utiliser yfinance pour prix)
2. **Pas de fondamentaux** : Pas de P/E, revenus, etc. (utiliser FinanceToolkit)
3. **Snapshots statiques** : Base mise à jour périodiquement (pas temps réel)
4. **Duplicates possibles** : Même ticker sur plusieurs exchanges (utiliser only_primary_listing=True)

---

## 📚 RESSOURCES

- **Documentation** : https://www.jeroenbouma.com/projects/financedatabase
- **GitHub** : https://github.com/JerBouma/FinanceDatabase
- **PyPI** : https://pypi.org/project/financedatabase/
- **Contributing** : https://github.com/JerBouma/FinanceDatabase/blob/main/CONTRIBUTING.md

---

## 🔗 COMPLÉMENTARITÉ AVEC AUTRES OUTILS

### Workflow typique :

1. **FinanceDatabase** → Trouver symboles/universe
2. **yfinance** → Télécharger prix historiques
3. **FinanceToolkit** → Calculer ratios/fondamentaux
4. **backtesting.py** → Backtester stratégies
5. **PyPortfolioOpt** → Optimiser allocation

```python
# Exemple de workflow complet
import financedatabase as fd
import yfinance as yf
from financetoolkit import Toolkit

# 1. Sélectionner universe
equities = fd.Equities()
tech_stocks = equities.select(
    sector="Information Technology",
    country="United States",
    market_cap=["Large Cap", "Mega Cap"]
)
tickers = tech_stocks.index.tolist()[:20]

# 2. Télécharger données
data = yf.download(tickers, period="1y")

# 3. Analyser fondamentaux
toolkit = Toolkit(tickers, api_key="YOUR_KEY")
ratios = toolkit.ratios.collect_all_ratios()

# 4. Continuer avec backtesting, optimization, etc.
```

================================================================================
FIN DU DOSSIER D'AUDIT - FINANCEDATABASE
================================================================================

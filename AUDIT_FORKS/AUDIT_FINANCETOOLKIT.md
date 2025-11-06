# DOSSIER D'AUDIT TECHNIQUE - FINANCETOOLKIT

================================================================================
**NOTE : Framework Python complet avec 78 fichiers pour analyse financière**
**150+ ratios, 40+ modèles, intégration complète FMP API**
================================================================================

## 🎯 NOM DU FORK / PROJET
**FinanceToolkit** - Comprehensive Financial Analysis Framework (150+ Ratios)

## 📋 INTRODUCTION & BUT DU PROJET

**Titre officiel** : FinanceToolkit - Open Source Financial Analysis & Metrics

**Description** : Framework Python open-source complet fournissant 150+ ratios financiers, 40+ modèles d'évaluation, analyse de performance, gestion de risque, et données de marché/fondamentales avec transparence totale sur les formules de calcul.

**Objectif principal** :
- Résoudre le problème des métriques incohérentes entre providers
- Fournir transparence totale sur méthodes de calcul (code source visible)
- Offrir 30+ années de données financières (via FMP API)
- Supporter Equities, Options, Currencies, Cryptos, ETFs, Funds, Indices
- Workflow ML4T complet : Data → Features → Models → Backtest

**Auteur** : JerBouma (Jeroen Bouma)

**License** : MIT

**Site web** : https://www.jeroenbouma.com/projects/financetoolkit

**GitHub** : https://github.com/JerBouma/FinanceToolkit

---

## 📊 STATISTIQUES GLOBALES

- **Total fichiers Python** : 78 fichiers
- **Ratios financiers** : 150+
- **Modèles d'évaluation** : 40+
- **Modules principaux** : 12
- **Métriques performance** : 50+
- **Mesures de risque** : 30+
- **Historique données** : 30+ ans
- **Assets supportés** : Stocks, Options, Currencies, Cryptos, ETFs, Funds, Indices

---

## 📂 STRUCTURE DU DÉPÔT

```
FinanceToolkit-main/
├── README.md (3314 lignes)         # Documentation exhaustive
├── CONTRIBUTING.md                  # Guide de contribution
├── LICENSE.txt                      # Licence MIT
├── pyproject.toml                   # Configuration Python
│
├── financetoolkit/                 # Package principal (78 fichiers)
│   │
│   ├── __init__.py                 # Exports principaux
│   ├── toolkit_controller.py      # Classe Toolkit principale
│   │
│   ├── DATA ACQUISITION
│   ├── fmp_model.py               # Financial Modeling Prep API
│   ├── yfinance_model.py          # Yahoo Finance fallback
│   ├── historical_model.py        # Données historiques OHLCV
│   ├── fundamentals_model.py      # États financiers
│   ├── currencies_model.py        # Données devises/crypto
│   │
│   ├── RATIOS & METRICS (150+)
│   ├── ratios/
│   │   ├── efficiency_model.py    # Ratios d'efficacité
│   │   ├── liquidity_model.py     # Ratios de liquidité
│   │   ├── profitability_model.py # Ratios de profitabilité
│   │   ├── solvency_model.py      # Ratios de solvabilité
│   │   └── valuation_model.py     # Ratios de valorisation
│   │
│   ├── MODELS D'ÉVALUATION (40+)
│   ├── models/
│   │   ├── dupont_model.py        # Analyse DuPont
│   │   ├── enterprise_model.py    # Valuation enterprise
│   │   ├── growth_model.py        # Modèles de croissance
│   │   ├── intrinsic_model.py     # Valeur intrinsèque
│   │   ├── wacc_model.py          # WACC calculation
│   │   └── ...
│   │
│   ├── OPTIONS
│   ├── options/
│   │   ├── options_controller.py  # Options trading & Greeks
│   │   ├── black_scholes.py       # Modèle Black-Scholes
│   │   ├── binomial.py            # Modèle binomial
│   │   └── greeks.py              # Delta, Gamma, Theta, Vega, Rho
│   │
│   ├── PERFORMANCE
│   ├── performance/
│   │   ├── performance_controller.py
│   │   ├── performance_model.py   # Métriques performance
│   │   └── factor_model.py        # Factor analysis
│   │
│   ├── RISK MANAGEMENT
│   ├── risk/
│   │   ├── risk_controller.py
│   │   ├── risk_model.py          # VaR, CVaR, drawdowns
│   │   ├── var_model.py           # Value at Risk
│   │   └── cvar_model.py          # Conditional VaR
│   │
│   ├── TECHNICAL INDICATORS
│   ├── technicals/
│   │   ├── momentum_model.py      # RSI, MACD, Stochastic
│   │   ├── overlap_model.py       # SMA, EMA, Bollinger
│   │   ├── volatility_model.py    # ATR, Bollinger Width
│   │   └── volume_model.py        # OBV, CMF
│   │
│   ├── ECONOMICS & MACRO
│   ├── economics/
│   │   ├── economics_controller.py
│   │   ├── fred_model.py          # Federal Reserve data
│   │   └── macro_model.py         # Macro indicators
│   │
│   ├── PORTFOLIO MANAGEMENT
│   ├── portfolio/
│   │   ├── portfolio_controller.py
│   │   ├── allocation_model.py    # Asset allocation
│   │   └── optimization_model.py  # Portfolio optimization
│   │
│   ├── FIXED INCOME
│   ├── fixedincome/
│   │   ├── bonds_model.py         # Bond pricing & yields
│   │   └── duration_model.py      # Duration & convexity
│   │
│   ├── DISCOVERY & SCREENING
│   ├── discovery/
│   │   ├── discovery_controller.py
│   │   ├── screener_model.py      # Stock screening
│   │   └── correlation_model.py   # Correlation analysis
│   │
│   ├── NORMALIZATION & HELPERS
│   ├── normalization/             # Normalisation données
│   ├── normalization_model.py
│   ├── helpers.py                 # Fonctions utilitaires
│   └── utilities/
│
├── examples/                       # Jupyter notebooks
│   ├── Getting Started.ipynb
│   ├── Ratios.ipynb
│   ├── Models.ipynb
│   ├── Options.ipynb
│   ├── Performance.ipynb
│   └── ... (20+ notebooks)
│
└── tests/                          # Tests unitaires
    └── ... (Tests complets)
```

---

## 🔧 CLASSE PRINCIPALE - `Toolkit`

### Initialisation

```python
from financetoolkit import Toolkit

companies = Toolkit(
    tickers=['AAPL', 'MSFT', 'GOOGL'],
    api_key="FMP_API_KEY",              # Financial Modeling Prep
    start_date="2020-01-01",
    end_date="2024-01-01",
    quarterly=False,                     # Annual par défaut
    risk_free_rate=0.04,                # 4% taux sans risque
    historical_period="1y",              # Période données historiques
    historical_interval="1d",            # Daily, 1h, 5m, etc.
    
    # Options avancées
    convert_currency='USD',              # Convertir toutes devises en USD
    normalize=True,                      # Normaliser données
    source='FinancialModelingPrep',      # Ou 'YahooFinance'
    enforce_source=False                 # Fallback automatique
)
```

**Sources de données** :
1. **Primary** : Financial Modeling Prep (FMP) - 30+ ans d'historique
2. **Fallback** : Yahoo Finance - Gratuit mais limité à 5 ans

**API Key FMP** :
- Free plan : 250 requêtes/jour, 5 ans de données, US exchanges
- Premium plans : Illimité, 30+ ans, global exchanges
- S'inscrire : https://www.jeroenbouma.com/fmp (15% discount avec lien affiliate)

---

## 📈 MODULE 1 : DONNÉES HISTORIQUES (Historical)

### Récupération OHLCV

```python
# Données historiques de prix
historical_data = companies.get_historical_data()

# Returns: DataFrame multi-index
#           AAPL                    MSFT                    GOOGL
#           Open  High  Low  Close  Open  High  Low  Close  Open  High  Low  Close
# 2020-01-02  ...   ...   ...  ...   ...   ...   ...  ...   ...   ...   ...  ...
# 2020-01-03  ...   ...   ...  ...   ...   ...   ...  ...   ...   ...   ...  ...

# Données spécifiques
close_prices = companies.get_historical_data()['Close']
volumes = companies.get_historical_data()['Volume']

# Statistiques descriptives
stats = companies.get_historical_statistics()
# Returns: mean, std, min, max, skew, kurtosis pour chaque ticker
```

### Returns & Volatility

```python
# Simple returns
returns = companies.get_returns()
# Returns: (Close[t] - Close[t-1]) / Close[t-1]

# Log returns
log_returns = companies.get_log_returns()
# Returns: ln(Close[t] / Close[t-1])

# Cumulative returns
cum_returns = companies.get_cumulative_returns()
# Returns: (1 + r1) * (1 + r2) * ... - 1

# Volatilité historique (annualisée)
volatility = companies.get_volatility()
# Returns: std(returns) * sqrt(252)
```

---

## 📊 MODULE 2 : ÉTATS FINANCIERS (Fundamentals)

### Income Statement (Compte de résultat)

```python
# Récupérer tous les income statements
income_statement = companies.get_income_statement()

# Contient (30+ lignes) :
revenues = income_statement.loc['revenue']
cost_of_revenue = income_statement.loc['cost_of_revenue']
gross_profit = income_statement.loc['gross_profit']
rd_expenses = income_statement.loc['research_and_development_expenses']
sga_expenses = income_statement.loc['selling_general_and_administrative_expenses']
operating_income = income_statement.loc['operating_income']
interest_expense = income_statement.loc['interest_expense']
income_before_tax = income_statement.loc['income_before_tax']
income_tax_expense = income_statement.loc['income_tax_expense']
net_income = income_statement.loc['net_income']
eps_basic = income_statement.loc['eps']
eps_diluted = income_statement.loc['eps_diluted']
weighted_avg_shares = income_statement.loc['weighted_average_shares_outstanding']
weighted_avg_shares_diluted = income_statement.loc['weighted_average_shares_outstanding_diluted']

# Multi-periods, multi-tickers
# Shape: (metric, year, ticker)
```

### Balance Sheet (Bilan)

```python
# Récupérer tous les balance sheets
balance_sheet = companies.get_balance_sheet()

# ACTIFS
total_assets = balance_sheet.loc['total_assets']
current_assets = balance_sheet.loc['total_current_assets']
cash = balance_sheet.loc['cash_and_cash_equivalents']
short_term_investments = balance_sheet.loc['short_term_investments']
accounts_receivable = balance_sheet.loc['net_receivables']
inventory = balance_sheet.loc['inventory']
prepaid_expenses = balance_sheet.loc['other_current_assets']

non_current_assets = balance_sheet.loc['total_non_current_assets']
property_plant_equipment = balance_sheet.loc['property_plant_equipment_net']
goodwill = balance_sheet.loc['goodwill']
intangible_assets = balance_sheet.loc['intangible_assets']

# PASSIFS
total_liabilities = balance_sheet.loc['total_liabilities']
current_liabilities = balance_sheet.loc['total_current_liabilities']
accounts_payable = balance_sheet.loc['account_payables']
short_term_debt = balance_sheet.loc['short_term_debt']
current_portion_long_term_debt = balance_sheet.loc['current_long_term_debt']

non_current_liabilities = balance_sheet.loc['total_non_current_liabilities']
long_term_debt = balance_sheet.loc['long_term_debt']
deferred_revenue = balance_sheet.loc['deferred_revenue_non_current']

# CAPITAUX PROPRES
total_equity = balance_sheet.loc['total_stockholders_equity']
common_stock = balance_sheet.loc['common_stock']
retained_earnings = balance_sheet.loc['retained_earnings']
accumulated_other_comprehensive_income = balance_sheet.loc['accumulated_other_comprehensive_income_loss']
```

### Cash Flow Statement (Tableau de flux)

```python
# Récupérer tous les cash flow statements
cash_flow = companies.get_cash_flow_statement()

# OPERATING CASH FLOW
operating_cash_flow = cash_flow.loc['operating_cash_flow']
net_income_cf = cash_flow.loc['net_income']
depreciation_amortization = cash_flow.loc['depreciation_and_amortization']
stock_based_compensation = cash_flow.loc['stock_based_compensation']
change_working_capital = cash_flow.loc['change_in_working_capital']
change_receivables = cash_flow.loc['accounts_receivables']
change_inventory = cash_flow.loc['inventory']
change_payables = cash_flow.loc['accounts_payables']

# INVESTING CASH FLOW
investing_cash_flow = cash_flow.loc['net_cash_used_for_investing_activities']
capex = cash_flow.loc['capital_expenditure']
acquisitions = cash_flow.loc['acquisitions_net']
purchases_investments = cash_flow.loc['purchases_of_investments']
sales_investments = cash_flow.loc['sales_maturities_of_investments']

# FINANCING CASH FLOW
financing_cash_flow = cash_flow.loc['net_cash_used_provided_by_financing_activities']
debt_repayment = cash_flow.loc['debt_repayment']
common_stock_issued = cash_flow.loc['common_stock_issued']
common_stock_repurchased = cash_flow.loc['common_stock_repurchased']
dividends_paid = cash_flow.loc['dividends_paid']

# FREE CASH FLOW
free_cash_flow = cash_flow.loc['free_cash_flow']
# FCF = Operating CF - CapEx
```

---

## 💰 MODULE 3 : RATIOS FINANCIERS (150+)

### A. PROFITABILITY RATIOS (Ratios de rentabilité)

```python
profitability = companies.ratios.collect_profitability_ratios()

# Contient tous ces ratios:

# 1. GROSS PROFIT MARGIN
gross_margin = companies.ratios.get_gross_margin()
# Formule: Gross Profit / Revenue
# Interprétation: % de revenus après coûts directs

# 2. OPERATING PROFIT MARGIN
operating_margin = companies.ratios.get_operating_margin()
# Formule: Operating Income / Revenue
# Interprétation: % de revenus après coûts opérationnels

# 3. NET PROFIT MARGIN
net_margin = companies.ratios.get_net_profit_margin()
# Formule: Net Income / Revenue
# Interprétation: % de revenus en profit net

# 4. ROA (Return on Assets)
roa = companies.ratios.get_return_on_assets()
# Formule: Net Income / Total Assets
# Interprétation: Efficacité utilisation des actifs

# 5. ROE (Return on Equity)
roe = companies.ratios.get_return_on_equity()
# Formule: Net Income / Shareholders' Equity
# Interprétation: Rendement des capitaux propres

# 6. ROIC (Return on Invested Capital)
roic = companies.ratios.get_return_on_invested_capital()
# Formule: NOPAT / Invested Capital
# Où: NOPAT = Operating Income × (1 - Tax Rate)
#     Invested Capital = Total Assets - Current Liabilities

# 7. ROCE (Return on Capital Employed)
roce = companies.ratios.get_return_on_capital_employed()
# Formule: EBIT / Capital Employed
# Où: Capital Employed = Total Assets - Current Liabilities

# 8. ROT (Return on Tangible Assets)
rot = companies.ratios.get_return_on_tangible_assets()
# Formule: Net Income / Tangible Assets
# Où: Tangible Assets = Total Assets - Intangible Assets - Goodwill

# 9. EARNINGS PER SHARE (EPS)
eps = companies.ratios.get_earnings_per_share()
# Formule: Net Income / Weighted Average Shares Outstanding

# 10. DILUTED EPS
eps_diluted = companies.ratios.get_earnings_per_share_diluted()
# Formule: Net Income / Diluted Shares Outstanding

# 11. FREE CASH FLOW PER SHARE
fcf_per_share = companies.ratios.get_free_cash_flow_per_share()
# Formule: Free Cash Flow / Shares Outstanding

# 12. BOOK VALUE PER SHARE
book_value = companies.ratios.get_book_value_per_share()
# Formule: Total Equity / Shares Outstanding

# 13. TANGIBLE BOOK VALUE PER SHARE
tangible_book_value = companies.ratios.get_tangible_book_value_per_share()
# Formule: (Total Equity - Intangibles - Goodwill) / Shares
```

### B. LIQUIDITY RATIOS (Ratios de liquidité)

```python
liquidity = companies.ratios.collect_liquidity_ratios()

# 1. CURRENT RATIO
current_ratio = companies.ratios.get_current_ratio()
# Formule: Current Assets / Current Liabilities
# Interprétation: > 1 = peut payer dettes court terme
# Idéal: 1.5 - 3.0

# 2. QUICK RATIO (Acid Test)
quick_ratio = companies.ratios.get_quick_ratio()
# Formule: (Current Assets - Inventory) / Current Liabilities
# Interprétation: Liquidité immédiate (sans vendre inventaire)
# Idéal: > 1.0

# 3. CASH RATIO
cash_ratio = companies.ratios.get_cash_ratio()
# Formule: (Cash + Cash Equivalents) / Current Liabilities
# Interprétation: Liquidité ultra-conservatrice
# Idéal: > 0.5

# 4. WORKING CAPITAL
working_capital = companies.ratios.get_working_capital()
# Formule: Current Assets - Current Liabilities
# Interprétation: Cushion opérationnel en $

# 5. OPERATING CASH FLOW RATIO
ocf_ratio = companies.ratios.get_operating_cash_flow_ratio()
# Formule: Operating Cash Flow / Current Liabilities
# Interprétation: Capacité à générer cash vs dettes CT
```

### C. SOLVENCY RATIOS (Ratios de solvabilité)

```python
solvency = companies.ratios.collect_solvency_ratios()

# 1. DEBT-TO-ASSETS RATIO
debt_to_assets = companies.ratios.get_debt_to_assets_ratio()
# Formule: Total Debt / Total Assets
# Interprétation: % actifs financés par dette
# Idéal: < 0.5 (50%)

# 2. DEBT-TO-EQUITY RATIO
debt_to_equity = companies.ratios.get_debt_to_equity_ratio()
# Formule: Total Debt / Total Equity
# Interprétation: Levier financier
# Idéal: < 2.0 (varie selon industrie)

# 3. INTEREST COVERAGE RATIO
interest_coverage = companies.ratios.get_interest_coverage_ratio()
# Formule: EBIT / Interest Expense
# Interprétation: Capacité à payer intérêts
# Idéal: > 3.0

# 4. DEBT SERVICE COVERAGE RATIO
debt_service_coverage = companies.ratios.get_debt_service_coverage_ratio()
# Formule: Operating Income / Total Debt Service
# Interprétation: Capacité à couvrir dette totale

# 5. EQUITY MULTIPLIER
equity_multiplier = companies.ratios.get_equity_multiplier()
# Formule: Total Assets / Total Equity
# Interprétation: Levier financier
# Plus élevé = plus de dette

# 6. CASH FLOW TO DEBT RATIO
cf_to_debt = companies.ratios.get_cash_flow_to_debt_ratio()
# Formule: Operating Cash Flow / Total Debt
# Interprétation: Années pour rembourser dette avec OCF
```

### D. EFFICIENCY RATIOS (Ratios d'efficacité)

```python
efficiency = companies.ratios.collect_efficiency_ratios()

# 1. ASSET TURNOVER
asset_turnover = companies.ratios.get_asset_turnover_ratio()
# Formule: Revenue / Average Total Assets
# Interprétation: Revenus générés par $ d'actifs
# Plus élevé = meilleur

# 2. INVENTORY TURNOVER
inventory_turnover = companies.ratios.get_inventory_turnover_ratio()
# Formule: Cost of Goods Sold / Average Inventory
# Interprétation: Nombre de fois inventaire vendu/an
# Plus élevé = efficace

# 3. DAYS INVENTORY OUTSTANDING (DIO)
dio = companies.ratios.get_days_of_inventory_outstanding()
# Formule: 365 / Inventory Turnover
# Interprétation: Jours pour vendre inventaire
# Plus bas = meilleur

# 4. RECEIVABLES TURNOVER
receivables_turnover = companies.ratios.get_receivables_turnover()
# Formule: Revenue / Average Accounts Receivable
# Interprétation: Efficacité collection créances

# 5. DAYS SALES OUTSTANDING (DSO)
dso = companies.ratios.get_days_of_sales_outstanding()
# Formule: 365 / Receivables Turnover
# Interprétation: Jours pour collecter créances
# Plus bas = meilleur

# 6. PAYABLES TURNOVER
payables_turnover = companies.ratios.get_payables_turnover()
# Formule: Cost of Goods Sold / Average Accounts Payable
# Interprétation: Vitesse paiement fournisseurs

# 7. DAYS PAYABLES OUTSTANDING (DPO)
dpo = companies.ratios.get_days_of_payables_outstanding()
# Formule: 365 / Payables Turnover
# Interprétation: Jours avant payer fournisseurs
# Plus élevé = garde cash plus longtemps

# 8. CASH CONVERSION CYCLE (CCC)
ccc = companies.ratios.get_cash_conversion_cycle()
# Formule: DIO + DSO - DPO
# Interprétation: Jours pour convertir inventaire en cash
# Plus bas = meilleur (cash plus vite disponible)
```

### E. VALUATION RATIOS (Ratios de valorisation)

```python
valuation = companies.ratios.collect_valuation_ratios()

# 1. PRICE-TO-EARNINGS RATIO (P/E)
pe_ratio = companies.ratios.get_price_earnings_ratio()
# Formule: Share Price / Earnings Per Share
# Interprétation: $ payés pour $1 de profit
# Tech: 20-40, Value: 10-15

# 2. FORWARD P/E
forward_pe = companies.ratios.get_forward_price_earnings_ratio()
# Formule: Share Price / Forward EPS
# Basé sur estimations futures

# 3. PEG RATIO (P/E to Growth)
peg_ratio = companies.ratios.get_peg_ratio()
# Formule: P/E Ratio / EPS Growth Rate
# Interprétation: < 1 = sous-évalué, > 1 = sur-évalué
# Ajuste P/E pour croissance

# 4. PRICE-TO-BOOK RATIO (P/B)
pb_ratio = companies.ratios.get_price_to_book_ratio()
# Formule: Share Price / Book Value Per Share
# Interprétation: < 1 = trade en-dessous valeur comptable

# 5. PRICE-TO-TANGIBLE-BOOK RATIO
ptb_ratio = companies.ratios.get_price_to_tangible_book_ratio()
# Formule: Share Price / Tangible Book Value Per Share
# Exclut goodwill et intangibles

# 6. PRICE-TO-SALES RATIO (P/S)
ps_ratio = companies.ratios.get_price_to_sales_ratio()
# Formule: Market Cap / Total Revenue
# Interprétation: Valorisation vs revenus
# Utile pour sociétés non-profitables

# 7. PRICE-TO-FREE-CASH-FLOW RATIO
p_fcf_ratio = companies.ratios.get_price_to_free_cash_flow_ratio()
# Formule: Market Cap / Free Cash Flow
# Interprétation: Valorisation vs génération cash

# 8. ENTERPRISE VALUE (EV)
enterprise_value = companies.ratios.get_enterprise_value()
# Formule: Market Cap + Total Debt - Cash
# Valeur totale de l'entreprise

# 9. EV/EBITDA
ev_ebitda = companies.ratios.get_ev_to_ebitda_ratio()
# Formule: Enterprise Value / EBITDA
# Interprétation: Multiple d'acquisition
# Comparaison inter-secteurs

# 10. EV/SALES
ev_sales = companies.ratios.get_ev_to_sales_ratio()
# Formule: Enterprise Value / Revenue

# 11. DIVIDEND YIELD
div_yield = companies.ratios.get_dividend_yield()
# Formule: Annual Dividends Per Share / Share Price
# Interprétation: % rendement dividende

# 12. DIVIDEND PAYOUT RATIO
payout_ratio = companies.ratios.get_dividend_payout_ratio()
# Formule: Dividends / Net Income
# Interprétation: % profits distribués
# Growth stocks: 0-40%, Mature: 40-60%
```

---

## 🎯 MODULE 4 : MODÈLES D'ÉVALUATION (40+)

### A. DUPONT ANALYSIS (Décomposition ROE)

```python
# Analyse DuPont à 3 facteurs
dupont_3 = companies.models.get_dupont_analysis()
# ROE = Net Margin × Asset Turnover × Equity Multiplier
# ROE = (Net Income / Revenue) × (Revenue / Assets) × (Assets / Equity)

# Analyse DuPont à 5 facteurs (Extended)
dupont_5 = companies.models.get_extended_dupont_analysis()
# ROE = Tax Burden × Interest Burden × EBIT Margin × Asset Turnover × Equity Multiplier
```

### B. ENTERPRISE VALUE MODELS

```python
# Enterprise Value
ev = companies.models.get_enterprise_value()
# EV = Market Cap + Total Debt + Preferred Equity + Minority Interest - Cash

# Enterprise Value to EBITDA
ev_ebitda = companies.models.get_ev_to_ebitda()
# Standard valuation multiple

# Enterprise Value to Sales
ev_sales = companies.models.get_ev_to_sales()
```

### C. GROWTH MODELS

```python
# Revenue Growth
revenue_growth = companies.models.get_revenue_growth()
# (Revenue[t] - Revenue[t-1]) / Revenue[t-1]

# EPS Growth
eps_growth = companies.models.get_earnings_growth()

# Free Cash Flow Growth
fcf_growth = companies.models.get_fcf_growth()

# CAGR (Compound Annual Growth Rate)
revenue_cagr = companies.models.get_revenue_cagr(years=5)
# (Final / Initial)^(1/years) - 1
```

### D. INTRINSIC VALUE MODELS

```python
# Discounted Cash Flow (DCF)
dcf_value = companies.models.get_intrinsic_value_dcf(
    growth_rate=0.05,       # 5% perpetual growth
    wacc=0.10,              # 10% WACC
    terminal_growth=0.03    # 3% terminal growth
)
# PV = sum(FCF[t] / (1+WACC)^t) + Terminal Value

# Dividend Discount Model (DDM)
ddm_value = companies.models.get_intrinsic_value_ddm(
    dividend_growth=0.04,
    required_return=0.10
)
# Value = D1 / (r - g)
```

### E. WACC (Weighted Average Cost of Capital)

```python
wacc = companies.models.get_wacc()
# WACC = (E/V × Re) + (D/V × Rd × (1-T))
# Où:
#   E = Market Value of Equity
#   D = Market Value of Debt
#   V = E + D
#   Re = Cost of Equity (CAPM)
#   Rd = Cost of Debt
#   T = Tax Rate
```

---

## ⚙️ MODULE 5 : OPTIONS

### Black-Scholes Model

```python
options = companies.options

# Calculer prix d'option (Call/Put)
option_price = options.get_black_scholes(
    strike_price=150,
    time_to_expiration=30/365,  # 30 jours
    volatility=0.25,             # 25% vol implicite
    dividend_yield=0.01,         # 1% dividend yield
    option_type='call'           # 'call' ou 'put'
)

# Tous les Greeks en une fois
all_greeks = options.collect_all_greeks(
    expiration_time_range=180  # Options expirant dans 180 jours
)
# Returns: Delta, Gamma, Theta, Vega, Rho pour toutes les strikes/expirations
```

### Greeks (Sensibilités)

```python
# Delta (Δ) - Sensibilité au prix sous-jacent
delta = options.get_delta()
# ∂Option/∂Stock
# Call: 0 to 1, Put: -1 to 0

# Gamma (Γ) - Taux de changement de Delta
gamma = options.get_gamma()
# ∂²Option/∂Stock²
# Toujours positif

# Theta (Θ) - Decay temporel
theta = options.get_theta()
# ∂Option/∂Time
# Généralement négatif (perte valeur temps)

# Vega (ν) - Sensibilité à la volatilité
vega = options.get_vega()
# ∂Option/∂Volatility
# Toujours positif

# Rho (ρ) - Sensibilité aux taux d'intérêt
rho = options.get_rho()
# ∂Option/∂Interest Rate
```

---

## 📊 MODULE 6 : PERFORMANCE

### Métriques de rendement

```python
performance = companies.performance

# Total Return
total_return = performance.get_total_return(period='1y')

# Annualized Return
annualized_return = performance.get_annualized_return()
# (1 + Total Return)^(365/days) - 1

# Cumulative Return
cumulative = performance.get_cumulative_return()

# Logarithmic Return
log_return = performance.get_log_return()
```

### Ratios risque/rendement

```python
# Sharpe Ratio
sharpe = performance.get_sharpe_ratio(risk_free_rate=0.04)
# (Return - RF) / Std Dev

# Sortino Ratio
sortino = performance.get_sortino_ratio(risk_free_rate=0.04)
# (Return - RF) / Downside Deviation

# Treynor Ratio
treynor = performance.get_treynor_ratio(risk_free_rate=0.04)
# (Return - RF) / Beta

# Information Ratio
info_ratio = performance.get_information_ratio(benchmark='SPY')
# (Return - Benchmark) / Tracking Error

# Calmar Ratio
calmar = performance.get_calmar_ratio()
# CAGR / Max Drawdown
```

### Factor Analysis

```python
# Alpha et Beta vs benchmark
alpha_beta = performance.get_alpha_beta(benchmark='SPY')

# Factor correlations (Fama-French)
factor_corr = performance.get_factor_asset_correlations(period='quarterly')
```

---

## ⚠️ MODULE 7 : RISK MANAGEMENT

### Value at Risk (VaR)

```python
risk = companies.risk

# Historical VaR
var_hist = risk.get_var_historical(confidence_level=0.95)
# 95% chance perte < VaR

# Parametric VaR
var_param = risk.get_var_parametric(confidence_level=0.95)
# Assume distribution normale

# Conditional VaR (CVaR / Expected Shortfall)
cvar = risk.get_cvar(confidence_level=0.95)
# Perte moyenne si dépasse VaR
```

### Drawdown Analysis

```python
# Maximum Drawdown
max_dd = risk.get_max_drawdown()
# Pire baisse depuis pic

# Drawdown Duration
dd_duration = risk.get_drawdown_duration()
# Temps pour récupérer

# Calmar Ratio
calmar = risk.get_calmar_ratio()
```

### Volatility Measures

```python
# Historical Volatility
vol_hist = risk.get_historical_volatility()

# Exponentially Weighted Volatility
vol_ewma = risk.get_ewma_volatility(lambda_param=0.94)

# Downside Deviation
downside_dev = risk.get_downside_deviation()
# Std dev des returns négatifs seulement
```

---

## 📈 MODULE 8 : TECHNICAL INDICATORS

### Momentum Indicators

```python
technicals = companies.technicals

# RSI (Relative Strength Index)
rsi = technicals.get_rsi(period=14)

# MACD
macd, signal, histogram = technicals.get_macd()

# Stochastic Oscillator
slowk, slowd = technicals.get_stochastic()

# Williams %R
willr = technicals.get_williams_r(period=14)
```

### Overlap Indicators

```python
# Simple Moving Average
sma = technicals.get_sma(period=20)

# Exponential Moving Average
ema = technicals.get_ema(period=12)

# Bollinger Bands
upper, middle, lower = technicals.get_bollinger_bands(period=20, std=2)
```

### Volume Indicators

```python
# On-Balance Volume
obv = technicals.get_obv()

# Chaikin Money Flow
cmf = technicals.get_chaikin_money_flow()
```

---

## 🌍 MODULE 9 : ECONOMICS & MACRO

### FRED Data (Federal Reserve)

```python
economics = companies.economics

# GDP Growth
gdp = economics.get_gdp_growth()

# Unemployment Rate
unemployment = economics.get_unemployment_rate()

# Inflation (CPI)
cpi = economics.get_cpi()

# Interest Rates
fed_funds = economics.get_fed_funds_rate()

# Treasury Yields
treasury_10y = economics.get_treasury_yield(maturity='10Y')
```

---

## 💼 MODULE 10 : PORTFOLIO MANAGEMENT

### Asset Allocation

```python
portfolio = companies.portfolio

# Equal Weight Allocation
equal_weight = portfolio.get_equal_weight_allocation()

# Market Cap Weighted
market_cap_weight = portfolio.get_market_cap_weighted_allocation()

# Risk Parity
risk_parity = portfolio.get_risk_parity_allocation()
```

### Optimization

```python
# Maximum Sharpe Ratio
max_sharpe = portfolio.optimize_sharpe_ratio(risk_free_rate=0.04)

# Minimum Volatility
min_vol = portfolio.optimize_minimum_volatility()

# Efficient Frontier
efficient_frontier = portfolio.get_efficient_frontier(
    num_portfolios=10000
)
```

---

## 🎯 EXEMPLES D'UTILISATION COMPLETS

### Exemple 1 : Analyse complète d'une action

```python
from financetoolkit import Toolkit

# 1. Initialiser
company = Toolkit(['AAPL'], api_key=API_KEY, start_date='2020-01-01')

# 2. Données historiques
hist = company.get_historical_data()
returns = company.get_returns()

# 3. États financiers
income = company.get_income_statement()
balance = company.get_balance_sheet()
cashflow = company.get_cash_flow_statement()

# 4. Tous les ratios
ratios = company.ratios.collect_all_ratios()

# 5. Valorisation
pe = company.ratios.get_price_earnings_ratio()
pb = company.ratios.get_price_to_book_ratio()
ps = company.ratios.get_price_to_sales_ratio()

# 6. Performance
sharpe = company.performance.get_sharpe_ratio()
sortino = company.performance.get_sortino_ratio()

# 7. Risque
var = company.risk.get_var_historical(confidence_level=0.95)
max_dd = company.risk.get_max_drawdown()

# 8. Export
ratios.to_excel('AAPL_analysis.xlsx')
```

### Exemple 2 : Comparaison sectorielle

```python
# Tech giants
tech = Toolkit(
    ['AAPL', 'MSFT', 'GOOGL', 'META', 'NVDA'],
    api_key=API_KEY
)

# Comparer ratios de profitabilité
prof_ratios = tech.ratios.collect_profitability_ratios()

# Visualiser
import matplotlib.pyplot as plt
prof_ratios.loc['return_on_equity'].plot(kind='bar')
plt.title('ROE Comparison - Tech Giants')
plt.ylabel('ROE (%)')
plt.show()

# Meilleur ROE
best_roe = prof_ratios.loc['return_on_equity'].idxmax()
print(f"Highest ROE: {best_roe}")
```

### Exemple 3 : Screening avec FinanceDatabase

```python
import financedatabase as fd
from financetoolkit import Toolkit

# 1. Obtenir universe
equities = fd.Equities()
tech_us = equities.select(
    sector='Information Technology',
    country='United States',
    market_cap=['Large Cap', 'Mega Cap']
)
tickers = tech_us.index.tolist()[:20]

# 2. Analyser avec FinanceToolkit
companies = Toolkit(tickers, api_key=API_KEY)

# 3. Calculer ratios
pe = companies.ratios.get_price_earnings_ratio()
peg = companies.ratios.get_peg_ratio()
roe = companies.ratios.get_return_on_equity()

# 4. Screener custom
import pandas as pd
screen = pd.DataFrame({
    'P/E': pe.iloc[-1],
    'PEG': peg.iloc[-1],
    'ROE': roe.iloc[-1]
})

# Filtrer : P/E < 25, PEG < 2, ROE > 15%
filtered = screen[(screen['P/E'] < 25) & 
                  (screen['PEG'] < 2) & 
                  (screen['ROE'] > 0.15)]
print(filtered.sort_values('PEG'))
```

---

## 🎯 POINTS FORTS

1. **Transparence totale** : Code source visible pour toutes formules
2. **Comprehensive** : 150+ ratios, 40+ modèles
3. **Données riches** : 30+ ans via FMP API
4. **Multi-assets** : Stocks, Options, Currencies, Cryptos
5. **Intégré** : Fonctionne avec FinanceDatabase
6. **Performance** : Vectorisation pandas/numpy
7. **Flexible** : API simple et intuitive
8. **Bien documenté** : 3314 lignes de README + notebooks

---

## ⚠️ LIMITATIONS

1. **API Key requise** : FMP API (250 req/jour gratuit)
2. **US-centric** : Free plan limité aux exchanges US
3. **Pas de live trading** : Analyse seulement
4. **Pas de backtesting intégré** : Utiliser avec backtesting.py

---

## 📚 RESSOURCES

- **Documentation** : https://www.jeroenbouma.com/projects/financetoolkit/docs
- **GitHub** : https://github.com/JerBouma/FinanceToolkit
- **PyPI** : https://pypi.org/project/financetoolkit/
- **FMP API** : https://www.jeroenbouma.com/fmp (15% discount)

================================================================================
FIN DU DOSSIER D'AUDIT - FINANCETOOLKIT
================================================================================

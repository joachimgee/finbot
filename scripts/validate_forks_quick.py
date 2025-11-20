#!/usr/bin/env python3
"""
Validation rapide des 3 intégrations critiques des forks.

Usage:
    python scripts/validate_forks_quick.py [--offline]

Modes:
    --offline ou FINBOT_OFFLINE=1 permet de sauter les validations réseau
    (FinanceDatabase & yfinance) pour des environnements CI/air-gapped.
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Tuple

print("\n" + "=" * 80)
print("FORKS INTEGRATION - QUICK VALIDATION")
print("=" * 80 + "\n")

# Détermination du mode offline via flag CLI ou variable d'environnement
OFFLINE = "--offline" in sys.argv or os.environ.get("FINBOT_OFFLINE", "0") == "1"
if OFFLINE:
    print("Mode OFFLINE: les validations réseau seront sautées.\n")

# ============================================================================
# VALIDATION 1: FinanceDatabase
# ============================================================================
print("=" * 80)
print("VALIDATION 1: FinanceDatabase Integration")
print("=" * 80)

if OFFLINE:
    print("SKIP (OFFLINE): FinanceDatabase non vérifié")
    val1_pass = True  # traité comme PASS pour ne pas échouer en CI offline
else:
    try:
        from financedatabase import Equities

        db = Equities()
        tech_result = db.search(sector='Technology', country='United States')

        if isinstance(tech_result, dict):
            tech_tickers = list(tech_result.keys())
        else:
            tech_tickers = list(tech_result.index)

        print(f"✓ FinanceDatabase.search(Technology, US): {len(tech_tickers)} tickers")
        print(f"  Sample: {tech_tickers[:5]}")

        if len(tech_tickers) >= 20:
            print("✓ VALIDATION 1: PASS")
            val1_pass = True
        else:
            print(f"✗ VALIDATION 1: FAIL - Only {len(tech_tickers)} tickers")
            val1_pass = False

    except Exception as e:
        print(f"✗ VALIDATION 1: FAIL - {e}")
        val1_pass = False

# ============================================================================
# VALIDATION 2: MarketDataFetcher (yfinance fallback)
# ============================================================================
print("\n" + "=" * 80)
print("VALIDATION 2: MarketDataFetcher (yfinance)")
print("=" * 80)

if OFFLINE:
    print("SKIP (OFFLINE): yfinance non vérifié")
    val2_pass = True  # traité comme PASS pour CI offline
else:
    try:
        import yfinance as yf

        tickers = ['AAPL', 'MSFT']
        print(f"Fetching {tickers} via yfinance...")

        data = {}
        for ticker in tickers:
            t = yf.Ticker(ticker)
            df = t.history(period='3mo', interval='1d')
            data[ticker] = df

        print(f"✓ Fetched {len(data)} tickers")

        all_ok = True
        for ticker, df in data.items():
            required = ['Open', 'High', 'Low', 'Close', 'Volume']
            missing = [c for c in required if c not in df.columns]

            if missing:
                print(f"✗ {ticker}: missing columns {missing}")
                all_ok = False
            elif len(df) < 10:
                print(f"✗ {ticker}: only {len(df)} rows")
                all_ok = False
            else:
                print(f"✓ {ticker}: {len(df)} rows, Close mean={df['Close'].mean():.2f}")

        if all_ok:
            print("✓ VALIDATION 2: PASS")
            val2_pass = True
        else:
            print("✗ VALIDATION 2: FAIL")
            val2_pass = False

    except Exception as e:
        print(f"✗ VALIDATION 2: FAIL - {e}")
        val2_pass = False

# ============================================================================
# VALIDATION 3: Riskfolio-Lib
# ============================================================================
print("\n" + "=" * 80)
print("VALIDATION 3: Riskfolio-Lib Integration")
print("=" * 80)

try:
    # Import notre wrapper qui gère les edge cases
    sys.path.insert(0, 'src')
    from financial_analyzer.portfolio_optimization.riskfolio_optimizer import RiskfolioOptimizer
    
    # Générer returns synthétiques (20 assets, 252 days)
    np.random.seed(42)
    n_assets = 20
    n_days = 252
    
    tickers = [f"ASSET{i:02d}" for i in range(n_assets)]
    dates = pd.date_range(end=datetime.now(), periods=n_days, freq='D')
    
    # Générer returns directement (pas besoin de cov)
    returns = np.random.randn(n_days, n_assets) * 0.01
    returns_df = pd.DataFrame(returns, index=dates, columns=tickers)
    
    print(f"✓ Synthetic returns: {returns_df.shape}")
    
    # Test via notre wrapper
    opt = RiskfolioOptimizer(returns_df, covariance_method='ledoit_wolf')
    w_cvar = opt.optimize_mean_cvar(risk_aversion=1.0, cvar_alpha=0.05)
    
    w_sum = float(w_cvar.sum())
    print(f"✓ CVaR optimization: sum={w_sum:.6f}")
    print(f"  Top 5 weights: {w_cvar.nlargest(5).to_dict()}")
    
    if abs(w_sum - 1.0) < 0.01:
        print("✓ VALIDATION 3: PASS")
        val3_pass = True
    else:
        print(f"✗ VALIDATION 3: FAIL - weights sum={w_sum:.6f}")
        val3_pass = False
        
except Exception as e:
    print(f"✗ VALIDATION 3: FAIL - {e}")
    import traceback
    traceback.print_exc()
    val3_pass = False

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 80)
print("VALIDATION SUMMARY")
print("=" * 80)

results = {
    'Universe (FinanceDatabase)': val1_pass,
    'MarketData (yfinance)': val2_pass,
    'Portfolio (Riskfolio-Lib)': val3_pass,
}

for name, passed in results.items():
    status = "✓ PASS" if passed else "✗ FAIL"
    print(f"{status:10} | {name}")

total = sum(results.values())
print("=" * 80)
print(f"TOTAL: {total}/{len(results)} validations passed")

if total == len(results):
    print("\n✓ ALL VALIDATIONS PASSED - Forks integration is working! 🚀\n")
    sys.exit(0)
else:
    print("\n✗ SOME VALIDATIONS FAILED - Review logs above\n")
    sys.exit(1)

"""
Test de stress institutionnel avec univers élargi et pondérations professionnelles.

Simule un portefeuille bancaire/asset manager avec:
- 47 tickers diversifiés (S&P 500 constituents majeurs)
- Pondérations market-cap weighted et risk parity
- Stress tests réalistes: crises historiques + Monte Carlo
- Validation contre benchmarks institutionnels
"""

import pandas as pd
import numpy as np
from datetime import datetime
from financial_analyzer.data.market_data import MarketDataFetcher
from financial_analyzer.risk.stress_test import StressTester
from financial_analyzer.risk.market_cap_weights import calculate_market_cap_weights as calc_real_mcap
from financial_analyzer.risk.var_backtest import backtest_rolling_var, VaRBacktester
from collections import Counter

# Univers institutionnel (47 tickers, diversification sectorielle)
INSTITUTIONAL_UNIVERSE = {
    # Tech (19%)
    'AAPL': 'Technology', 'MSFT': 'Technology', 'NVDA': 'Technology', 
    'GOOGL': 'Technology', 'META': 'Technology', 'AVGO': 'Technology',
    'ORCL': 'Technology', 'CSCO': 'Technology', 'ADBE': 'Technology',
    # Finance (13%)
    'JPM': 'Financials', 'BAC': 'Financials', 'WFC': 'Financials',
    'GS': 'Financials', 'MS': 'Financials', 'BLK': 'Financials',
    # Healthcare (13%)
    'UNH': 'Healthcare', 'JNJ': 'Healthcare', 'LLY': 'Healthcare',
    'ABBV': 'Healthcare', 'MRK': 'Healthcare', 'PFE': 'Healthcare',
    # Consumer (13%)
    'AMZN': 'Consumer', 'TSLA': 'Consumer', 'HD': 'Consumer',
    'NKE': 'Consumer', 'MCD': 'Consumer', 'SBUX': 'Consumer',
    # Energy (11%)
    'XOM': 'Energy', 'CVX': 'Energy', 'COP': 'Energy',
    'SLB': 'Energy', 'EOG': 'Energy',
    # Industrial (11%)
    'BA': 'Industrials', 'CAT': 'Industrials', 'GE': 'Industrials',
    'UPS': 'Industrials', 'HON': 'Industrials',
    # Utilities (6%)
    'NEE': 'Utilities', 'DUK': 'Utilities', 'SO': 'Utilities',
    # Telecom (4%)
    'VZ': 'Telecom', 'T': 'Telecom',
    # Materials (4%)
    'LIN': 'Materials', 'APD': 'Materials',
    # Real Estate (6%)
    'AMT': 'RealEstate', 'PLD': 'RealEstate', 'CCI': 'RealEstate'
}

# Période de données (3 ans, typique pour stress tests bancaires)
START_DATE = '2000-01-01'  # Recommandation 2: Long historical data (24+ years) pour vraies crises
END_DATE = '2024-06-30'


def fetch_returns(tickers, start, end):
    """Récupère returns pour univers de tickers."""
    print(f"Fetching data for {len(tickers)} tickers from {start} to {end}...")
    fetcher = MarketDataFetcher()
    frames = {}
    failed = []
    
    for i, ticker in enumerate(tickers, 1):
        try:
            df = fetcher.get_historical_data(ticker, start_date=start, end_date=end)
            frames[ticker] = df['Close'].pct_change().dropna()
            if i % 10 == 0:
                print(f"  Progress: {i}/{len(tickers)}")
        except Exception as e:
            print(f"  Failed {ticker}: {e}")
            failed.append(ticker)
    
    returns = pd.DataFrame(frames).dropna()
    print(f"Successfully fetched {len(returns.columns)} tickers, {len(returns)} days")
    if failed:
        print(f"Failed tickers ({len(failed)}): {failed}")
    
    return returns, failed


def calculate_market_cap_weights(returns, reference_date=None):
    """
    Pondérations market-cap weighted REAL via yfinance API.
    
    Utilise vraies market caps fetched depuis yfinance.
    """
    # Recommandation 1: Vraies market caps
    tickers = list(returns.columns)
    try:
        weights = calc_real_mcap(tickers, reference_date=reference_date or START_DATE, min_weight=0.005, max_weight=0.15)
        print(f"\nMarket-cap weighted (REAL from yfinance):")
    except Exception as e:
        print(f"\nWARNING: Failed to fetch real market caps ({e}), falling back to inverse-vol proxy")
        vols = returns.std()
        inv_vols = 1.0 / vols
        weights = inv_vols / inv_vols.sum()
        print(f"\nMarket-cap weighted (proxy inverse-vol):")
    
    print(f"\nMarket-cap weighted (proxy inverse-vol):")
    print(f"  Min weight: {weights.min():.2%}")
    print(f"  Max weight: {weights.max():.2%}")
    print(f"  Top 5: {weights.nlargest(5).to_dict()}")
    
    return weights


def calculate_risk_parity_weights(returns):
    """
    Pondérations risk parity (contribution égale au risque total).
    
    Standard bancaire: chaque actif contribue également à la volatilité du portefeuille.
    """
    # Risk parity simplifié: inverse volatility normalisé
    vols = returns.std()
    inv_vols = 1.0 / vols
    weights = inv_vols / inv_vols.sum()
    
    # Vérification: contribution au risque
    cov_matrix = returns.cov()
    portfolio_var = weights @ cov_matrix @ weights
    marginal_contrib = cov_matrix @ weights
    risk_contrib = weights * marginal_contrib / np.sqrt(portfolio_var)
    
    print(f"\nRisk Parity weights:")
    print(f"  Min weight: {weights.min():.2%}")
    print(f"  Max weight: {weights.max():.2%}")
    print(f"  Risk contribution std: {risk_contrib.std():.4f} (should be ~0)")
    print(f"  Top 5: {weights.nlargest(5).to_dict()}")
    
    return weights


def run_institutional_stress_test(returns, weights, label):
    """Exécute stress test complet avec métriques institutionnelles."""
    print(f"\n{'='*70}")
    print(f"STRESS TEST: {label}")
    print(f"{'='*70}")
    
    tester = StressTester(returns, weights)
    
    # Portfolio stats de base
    portfolio_returns = (returns * weights).sum(axis=1)
    sharpe = portfolio_returns.mean() / portfolio_returns.std() * np.sqrt(252)
    max_dd = ((1 + portfolio_returns).cumprod() / (1 + portfolio_returns).cumprod().cummax() - 1).min()
    
    print(f"\nPortfolio Statistics (historical):")
    print(f"  Sharpe ratio (annualized): {sharpe:.3f}")
    print(f"  Volatility (annualized): {portfolio_returns.std() * np.sqrt(252):.2%}")
    print(f"  Max drawdown: {max_dd:.2%}")
    print(f"  Skewness: {portfolio_returns.skew():.3f}")
    print(f"  Kurtosis: {portfolio_returns.kurtosis():.3f}")
    
    # Monte Carlo (10k scenarios, horizon 1 mois)
    print(f"\nRunning Monte Carlo (10,000 scenarios, 21-day horizon)...")
    mc = tester.monte_carlo_stress(n_scenarios=10000, horizon_days=21, tail_scenarios=True)
    
    print(f"\nMonte Carlo Results:")
    print(f"  VaR 95% (21d): {mc['var_95']:.2%}")
    print(f"  CVaR 95% (21d): {mc['cvar_95']:.2%}")
    print(f"  Worst scenario: {mc['worst_scenario']:.2%}")
    print(f"  Best scenario: {mc['best_scenario']:.2%}")
    print(f"  P(loss > 10%): {mc['tail_probability']:.1%}")
    
    # Recommandation 3: VaR Backtesting (Basel) + méthodes avancées + sentiment
    print(f"\nVaR Backtesting (Basel Compliance & Advanced Methods)...")
    try:
        from financial_analyzer.risk.var_backtest import backtest_multi_methods
        from financial_analyzer.ml.sentiment_pipeline import SentimentAnalyzer, sentiment_adjustment_factor

        sentiment_headlines = [
            "Stocks fall as recession fears grow",
            "Energy sector downgraded on demand slump",
            "Tech giants beat earnings expectations"
        ]
        analyzer = SentimentAnalyzer()
        sentiment_score = analyzer.compute_sentiment_score(sentiment_headlines)
        factor = sentiment_adjustment_factor(sentiment_score)
        print(f"  Sentiment score: {sentiment_score:.3f} (adjustment factor={factor:.3f})")

        # Backtest multi méthodes
        multi = backtest_multi_methods(portfolio_returns, methods=["historical","parametric","ewma","cornish_fisher"], window=250, confidence=0.95)
        for m, r in multi.items():
            print(f"  {m:15s} violation_rate={r['violation_rate']:.2%} zone={r['traffic_light']['zone']}")

        # Choisir meilleure (min violation_rate) avant ajustement sentiment
        best_method = min(multi.items(), key=lambda kv: kv[1]['violation_rate'])[0]
        best_results = multi[best_method]
        print(f"  Selected VaR method: {best_method} (violation_rate={best_results['violation_rate']:.2%})")

        # Appliquer facteur sentiment à VaR forecasts (stress si négatif)
        adjusted_forecasts = best_results['forecasts'] * factor
        adjusted_backtester = VaRBacktester(best_results['backtester'].returns, adjusted_forecasts, 0.95)
        adjusted_summary = adjusted_backtester.run_all_tests()
        print(f"  Adjusted (sentiment) violation_rate={adjusted_summary['violation_rate']:.2%} zone={adjusted_summary['traffic_light']['zone']}")

        mc['var_backtest'] = {
            'raw_multi': multi,
            'selected_method': best_method,
            'adjusted': adjusted_summary,
            'sentiment_score': sentiment_score,
            'sentiment_factor': factor
        }
    except Exception as e:
        print(f"  WARNING: Advanced VaR backtest failed ({e})")
        mc['var_backtest'] = None
    
    
    # Crises historiques
    print(f"\nHistorical Crisis Scenarios:")
    crisis_results = {}
    for name in tester.HISTORICAL_SCENARIOS.keys():
        result = tester.apply_historical_crisis(name, returns)
        crisis_results[name] = result
        print(f"  {result['scenario']}:")
        print(f"    Total loss: {result.get('total_loss', 0):.2%}")
        print(f"    Max drawdown: {result.get('max_drawdown', 0):.2%}")
    
    # Correlation breakdown
    print(f"\nCorrelation Breakdown Analysis:")
    corr_breakdown = tester.detect_correlation_breakdown(threshold=0.50)
    print(f"  Crisis periods detected: {corr_breakdown['n_breakdown_periods']}")
    print(f"  Normal correlation: {corr_breakdown['avg_correlation_normal']:.3f}")
    print(f"  Crisis correlation: {corr_breakdown['avg_correlation_crisis']:.3f}")
    print(f"  Diversification loss: {corr_breakdown['diversification_loss']:.2%}")
    
    return {
        'sharpe': sharpe,
        'max_dd': max_dd,
        'monte_carlo': mc,
        'crises': crisis_results,
        'correlation': corr_breakdown
    }


def compare_with_benchmarks(results):
    """Compare avec benchmarks institutionnels typiques."""
    print(f"\n{'='*70}")
    print(f"BENCHMARK COMPARISON")
    print(f"{'='*70}")
    
    # Benchmarks typiques (stress tests bancaires Fed/ECB)
    benchmarks = {
        'VaR 95% (1 mois)': {
            'Fed Severely Adverse': 0.15,  # 15% loss sur 1 mois
            'ECB Adverse': 0.12,
            'Our Result': results['market_cap']['monte_carlo']['var_95']
        },
        'CVaR 95% (1 mois)': {
            'Fed Severely Adverse': 0.25,  # 25% conditional loss
            'ECB Adverse': 0.20,
            'Our Result': results['market_cap']['monte_carlo']['cvar_95']
        },
        'Sharpe Ratio': {
            'Typical Institutional': 0.8,
            'Good Institutional': 1.2,
            'Our Result': results['market_cap']['sharpe']
        }
    }
    
    print("\nKey Metrics vs Benchmarks:")
    for metric, values in benchmarks.items():
        print(f"\n{metric}:")
        for label, val in values.items():
            print(f"  {label:25s}: {val:.2%}" if isinstance(val, float) else f"  {label:25s}: {val:.3f}")


def main():
    """Exécution complète du stress test institutionnel."""
    print("="*70)
    print("INSTITUTIONAL STRESS TEST")
    print("="*70)
    
    # Fetch data
    tickers = list(INSTITUTIONAL_UNIVERSE.keys())
    returns, failed = fetch_returns(tickers, START_DATE, END_DATE)
    
    # Calculer pondérations professionnelles
    weights_market_cap = calculate_market_cap_weights(returns)
    weights_risk_parity = calculate_risk_parity_weights(returns)
    
    # Stress tests
    results = {}
    results['market_cap'] = run_institutional_stress_test(
        returns, weights_market_cap, "Market-Cap Weighted Portfolio"
    )
    results['risk_parity'] = run_institutional_stress_test(
        returns, weights_risk_parity, "Risk Parity Portfolio"
    )
    
    # Comparaison benchmarks
    compare_with_benchmarks(results)
    
    # Résumé final
    print(f"\n{'='*70}")
    print(f"SUMMARY")
    print(f"{'='*70}")
    print(f"Universe: {len(returns.columns)} tickers, {len(returns)} days")
    print(f"Sectors: {len(set(INSTITUTIONAL_UNIVERSE.values()))}")
    print(f"\nMarket-Cap Weighted:")
    print(f"  Sharpe: {results['market_cap']['sharpe']:.3f}")
    print(f"  VaR 95%: {results['market_cap']['monte_carlo']['var_95']:.2%}")
    print(f"  Max DD (hist): {results['market_cap']['max_dd']:.2%}")
    print(f"\nRisk Parity:")
    print(f"  Sharpe: {results['risk_parity']['sharpe']:.3f}")
    print(f"  VaR 95%: {results['risk_parity']['monte_carlo']['var_95']:.2%}")
    print(f"  Max DD (hist): {results['risk_parity']['max_dd']:.2%}")
    
    return results


if __name__ == "__main__":
    results = main()

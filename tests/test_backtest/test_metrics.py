"""
Tests unitaires pour le module metrics.py.

Ce module teste toutes les fonctions de calcul de métriques de performance,
les fonctions de formatage/export, et les cas limites (edge cases).

Test Coverage:
    - Sharpe Ratio (positive, negative, zero volatility)
    - Sortino Ratio
    - Calmar Ratio
    - Max Drawdown (peak-to-trough, no drawdown)
    - Win Rate (all winners, all losers, mixed)
    - Profit Factor (profitable, unprofitable)
    - Average Trade Duration
    - Exposure Time (always in position, never in position)
    - calculate_all_metrics (intégration complète)
    - format_metrics_report (structure)
    - compare_strategies (multi-stratégies)
    - export_metrics_json
    - export_metrics_csv
"""

import pytest
import numpy as np
import pandas as pd
import json
from pathlib import Path
from datetime import datetime, timedelta

from financial_analyzer.backtest.metrics import (
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_calmar_ratio,
    calculate_max_drawdown,
    calculate_win_rate,
    calculate_profit_factor,
    calculate_avg_trade_duration,
    calculate_exposure_time,
    calculate_all_metrics,
    format_metrics_report,
    compare_strategies,
    export_metrics_json,
    export_metrics_csv,
    _calculate_returns,
    _annualize_return,
    _calculate_downside_deviation
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def mock_returns():
    """Generate mock daily returns (252 trading days)."""
    np.random.seed(42)
    # Moyenne légèrement positive, volatilité réaliste
    returns = np.random.normal(0.001, 0.02, 252)
    dates = pd.date_range(start='2023-01-01', periods=252, freq='D')
    return pd.Series(returns, index=dates)


@pytest.fixture
def mock_equity_curve():
    """Generate mock equity curve starting at $100,000."""
    np.random.seed(42)
    returns = np.random.normal(0.001, 0.02, 252)
    equity = 100000 * (1 + pd.Series(returns)).cumprod()
    dates = pd.date_range(start='2023-01-01', periods=252, freq='D')
    equity.index = dates
    return equity


@pytest.fixture
def mock_trades_df():
    """Generate mock trades DataFrame with realistic data."""
    np.random.seed(42)
    n_trades = 50
    
    entry_times = pd.date_range(start='2023-01-01', periods=n_trades, freq='5D')
    exit_times = entry_times + pd.Timedelta(days=3)
    
    # Mix de trades gagnants et perdants (60% win rate)
    pnls = []
    for i in range(n_trades):
        if i < 30:  # 30 winners
            pnls.append(np.random.uniform(50, 500))
        else:  # 20 losers
            pnls.append(np.random.uniform(-300, -50))
    
    trades_df = pd.DataFrame({
        'EntryTime': entry_times,
        'ExitTime': exit_times,
        'PnL': pnls,
        'Size': [100] * n_trades
    })
    
    return trades_df


@pytest.fixture
def mock_metrics_dict():
    """Generate mock metrics dictionary for testing formatting/export."""
    return {
        'sharpe_ratio': 1.85,
        'sortino_ratio': 2.31,
        'calmar_ratio': 1.42,
        'max_drawdown_pct': -15.3,
        'max_drawdown_duration_days': 45,
        'win_rate_pct': 60.0,
        'profit_factor': 2.15,
        'avg_trade_duration_days': 3.5,
        'exposure_time_pct': 75.2,
        'total_return_pct': 18.5,
        'annual_return_pct': 19.2,
        'total_trades': 50
    }


# ============================================================================
# TESTS: SHARPE RATIO
# ============================================================================

class TestSharpeRatio:
    """Tests pour calculate_sharpe_ratio."""
    
    def test_sharpe_ratio_positive_returns(self, mock_returns):
        """Test Sharpe Ratio avec returns positifs."""
        sharpe = calculate_sharpe_ratio(mock_returns)
        
        assert isinstance(sharpe, float)
        assert not np.isnan(sharpe)
        # Sharpe devrait être positif avec des returns moyens positifs
        assert sharpe > 0
    
    def test_sharpe_ratio_negative_returns(self):
        """Test Sharpe Ratio avec returns négatifs."""
        returns = pd.Series(np.random.normal(-0.001, 0.02, 252))
        sharpe = calculate_sharpe_ratio(returns)
        
        assert isinstance(sharpe, float)
        # Sharpe devrait être négatif avec des returns moyens négatifs
        assert sharpe < 0
    
    def test_sharpe_ratio_zero_volatility(self):
        """Test Sharpe Ratio avec volatilité nulle (returns constants)."""
        returns = pd.Series([0.01] * 252)
        sharpe = calculate_sharpe_ratio(returns)
        
        # Devrait retourner NaN car std = 0
        assert np.isnan(sharpe)
    
    def test_sharpe_ratio_with_risk_free_rate(self, mock_returns):
        """Test Sharpe Ratio avec risk-free rate non nul."""
        sharpe_no_rf = calculate_sharpe_ratio(mock_returns, risk_free_rate=0.0)
        sharpe_with_rf = calculate_sharpe_ratio(mock_returns, risk_free_rate=0.03)
        
        # Sharpe devrait être plus bas avec risk-free rate positif
        assert sharpe_with_rf < sharpe_no_rf
    
    def test_sharpe_ratio_empty_returns(self):
        """Test Sharpe Ratio avec returns vide."""
        empty_returns = pd.Series([], dtype=float)
        
        with pytest.raises(ValueError, match="Returns series cannot be empty"):
            calculate_sharpe_ratio(empty_returns)
    
    def test_sharpe_ratio_invalid_periods(self, mock_returns):
        """Test Sharpe Ratio avec periods_per_year invalide."""
        with pytest.raises(ValueError, match="periods_per_year must be positive"):
            calculate_sharpe_ratio(mock_returns, periods_per_year=0)


# ============================================================================
# TESTS: SORTINO RATIO
# ============================================================================

class TestSortinoRatio:
    """Tests pour calculate_sortino_ratio."""
    
    def test_sortino_ratio_calculation(self, mock_returns):
        """Test calcul Sortino Ratio standard."""
        sortino = calculate_sortino_ratio(mock_returns)
        
        assert isinstance(sortino, float)
        assert not np.isnan(sortino)
        # Sortino devrait être >= Sharpe (pénalise seulement downside)
        sharpe = calculate_sharpe_ratio(mock_returns)
        assert sortino >= sharpe
    
    def test_sortino_ratio_no_downside(self):
        """Test Sortino Ratio avec seulement returns positifs."""
        returns = pd.Series(np.abs(np.random.normal(0.01, 0.01, 252)))
        sortino = calculate_sortino_ratio(returns)
        
        # Devrait retourner NaN car downside dev = 0
        assert np.isnan(sortino)
    
    def test_sortino_ratio_empty_returns(self):
        """Test Sortino Ratio avec returns vide."""
        empty_returns = pd.Series([], dtype=float)
        
        with pytest.raises(ValueError, match="Returns series cannot be empty"):
            calculate_sortino_ratio(empty_returns)


# ============================================================================
# TESTS: CALMAR RATIO
# ============================================================================

class TestCalmarRatio:
    """Tests pour calculate_calmar_ratio."""
    
    def test_calmar_ratio_calculation(self, mock_returns, mock_equity_curve):
        """Test calcul Calmar Ratio standard."""
        calmar = calculate_calmar_ratio(mock_returns, mock_equity_curve)
        
        assert isinstance(calmar, float)
        # Peut être positif ou négatif selon la performance
    
    def test_calmar_ratio_no_drawdown(self):
        """Test Calmar Ratio avec equity monotonique (no drawdown)."""
        # Equity curve strictement croissante
        equity = pd.Series(np.linspace(100000, 120000, 252))
        returns = equity.pct_change().fillna(0)
        
        calmar = calculate_calmar_ratio(returns, equity)
        
        # Devrait retourner NaN car max_dd = 0
        assert np.isnan(calmar)
    
    def test_calmar_ratio_empty_inputs(self):
        """Test Calmar Ratio avec inputs vides."""
        empty_series = pd.Series([], dtype=float)
        
        with pytest.raises(ValueError, match="Returns and equity_curve cannot be empty"):
            calculate_calmar_ratio(empty_series, empty_series)


# ============================================================================
# TESTS: MAX DRAWDOWN
# ============================================================================

class TestMaxDrawdown:
    """Tests pour calculate_max_drawdown."""
    
    def test_max_drawdown_peak_to_trough(self, mock_equity_curve):
        """Test calcul max drawdown avec drawdown réel."""
        max_dd_info = calculate_max_drawdown(mock_equity_curve)
        
        assert isinstance(max_dd_info, dict)
        assert 'max_dd_pct' in max_dd_info
        assert 'max_dd_duration_days' in max_dd_info
        assert 'peak_date' in max_dd_info
        assert 'trough_date' in max_dd_info
        
        # Max DD devrait être négatif
        assert max_dd_info['max_dd_pct'] <= 0
        
        # Durée devrait être >= 0
        assert max_dd_info['max_dd_duration_days'] >= 0
    
    def test_max_drawdown_no_drawdown(self):
        """Test max drawdown avec equity monotonique."""
        # Equity strictement croissante
        equity = pd.Series(np.linspace(100000, 120000, 252))
        dates = pd.date_range(start='2023-01-01', periods=252, freq='D')
        equity.index = dates
        
        max_dd_info = calculate_max_drawdown(equity)
        
        assert max_dd_info['max_dd_pct'] == 0.0
        assert max_dd_info['max_dd_duration_days'] == 0
        assert max_dd_info['peak_date'] is None
        assert max_dd_info['trough_date'] is None
    
    def test_max_drawdown_simple_case(self):
        """Test max drawdown avec un cas simple connu."""
        # Equity: 100 -> 120 -> 80 -> 100
        # Max DD = (80 - 120) / 120 = -33.33%
        equity = pd.Series([100, 120, 80, 100])
        dates = pd.date_range(start='2023-01-01', periods=4, freq='D')
        equity.index = dates
        
        max_dd_info = calculate_max_drawdown(equity)
        
        expected_dd = (80 - 120) / 120
        assert abs(max_dd_info['max_dd_pct'] - expected_dd) < 0.0001
        assert max_dd_info['max_dd_duration_days'] == 1  # De index 1 à 2
    
    def test_max_drawdown_empty_equity(self):
        """Test max drawdown avec equity vide."""
        empty_equity = pd.Series([], dtype=float)
        
        with pytest.raises(ValueError, match="Equity curve cannot be empty"):
            calculate_max_drawdown(empty_equity)


# ============================================================================
# TESTS: WIN RATE
# ============================================================================

class TestWinRate:
    """Tests pour calculate_win_rate."""
    
    def test_win_rate_all_winners(self):
        """Test win rate avec 100% winners."""
        trades_df = pd.DataFrame({
            'PnL': [100, 200, 150, 300]
        })
        
        win_rate = calculate_win_rate(trades_df)
        assert win_rate == 100.0
    
    def test_win_rate_all_losers(self):
        """Test win rate avec 100% losers."""
        trades_df = pd.DataFrame({
            'PnL': [-100, -200, -150, -300]
        })
        
        win_rate = calculate_win_rate(trades_df)
        assert win_rate == 0.0
    
    def test_win_rate_mixed(self, mock_trades_df):
        """Test win rate avec mix winners/losers."""
        win_rate = calculate_win_rate(mock_trades_df)
        
        assert 0 <= win_rate <= 100
        # Mock trades_df a 30 winners / 50 total = 60%
        assert abs(win_rate - 60.0) < 1.0
    
    def test_win_rate_empty_df(self):
        """Test win rate avec DataFrame vide."""
        empty_df = pd.DataFrame(columns=['PnL'])
        
        with pytest.raises(ValueError, match="Trades DataFrame cannot be empty"):
            calculate_win_rate(empty_df)
    
    def test_win_rate_missing_column(self):
        """Test win rate avec colonne PnL manquante."""
        df_no_pnl = pd.DataFrame({'Size': [100, 200]})
        
        with pytest.raises(ValueError, match="must have 'PnL' column"):
            calculate_win_rate(df_no_pnl)


# ============================================================================
# TESTS: PROFIT FACTOR
# ============================================================================

class TestProfitFactor:
    """Tests pour calculate_profit_factor."""
    
    def test_profit_factor_profitable(self, mock_trades_df):
        """Test profit factor avec stratégie profitable."""
        pf = calculate_profit_factor(mock_trades_df)
        
        assert isinstance(pf, float)
        # Devrait être > 1 car mock_trades_df est profitable
        assert pf > 1.0
    
    def test_profit_factor_unprofitable(self):
        """Test profit factor avec stratégie non-profitable."""
        trades_df = pd.DataFrame({
            'PnL': [100, -200, 50, -300]  # Total: -350
        })
        
        pf = calculate_profit_factor(trades_df)
        
        # Total profit = 150, Total loss = 500 -> PF = 0.3
        assert pf < 1.0
    
    def test_profit_factor_no_losses(self):
        """Test profit factor sans pertes (devrait retourner Inf)."""
        trades_df = pd.DataFrame({
            'PnL': [100, 200, 150, 300]
        })
        
        pf = calculate_profit_factor(trades_df)
        
        assert np.isinf(pf)
    
    def test_profit_factor_no_profits(self):
        """Test profit factor sans profits."""
        trades_df = pd.DataFrame({
            'PnL': [-100, -200, -150]
        })
        
        pf = calculate_profit_factor(trades_df)
        
        assert pf == 0.0
    
    def test_profit_factor_empty_df(self):
        """Test profit factor avec DataFrame vide."""
        empty_df = pd.DataFrame(columns=['PnL'])
        
        with pytest.raises(ValueError, match="Trades DataFrame cannot be empty"):
            calculate_profit_factor(empty_df)


# ============================================================================
# TESTS: AVERAGE TRADE DURATION
# ============================================================================

class TestAvgTradeDuration:
    """Tests pour calculate_avg_trade_duration."""
    
    def test_avg_trade_duration(self, mock_trades_df):
        """Test calcul durée moyenne trades."""
        avg_duration = calculate_avg_trade_duration(mock_trades_df)
        
        assert isinstance(avg_duration, float)
        assert avg_duration > 0
        # Mock trades_df a des trades de 3 jours
        assert abs(avg_duration - 3.0) < 0.1
    
    def test_avg_trade_duration_single_day(self):
        """Test durée moyenne avec trades intraday."""
        trades_df = pd.DataFrame({
            'EntryTime': pd.to_datetime(['2023-01-01 09:30', '2023-01-02 10:00']),
            'ExitTime': pd.to_datetime(['2023-01-01 15:00', '2023-01-02 14:30']),
            'PnL': [100, -50]
        })
        
        avg_duration = calculate_avg_trade_duration(trades_df)
        
        # Durées intraday devraient être < 1 jour
        assert avg_duration < 1.0
    
    def test_avg_trade_duration_missing_columns(self):
        """Test durée moyenne avec colonnes manquantes."""
        df_missing = pd.DataFrame({'PnL': [100, 200]})
        
        with pytest.raises(ValueError, match="must have 'EntryTime' and 'ExitTime'"):
            calculate_avg_trade_duration(df_missing)


# ============================================================================
# TESTS: EXPOSURE TIME
# ============================================================================

class TestExposureTime:
    """Tests pour calculate_exposure_time."""
    
    def test_exposure_time_always_in_position(self, mock_equity_curve):
        """Test exposure time avec position toujours ouverte."""
        # Créer trades couvrant toute la période
        trades_df = pd.DataFrame({
            'EntryTime': [mock_equity_curve.index[0]],
            'ExitTime': [mock_equity_curve.index[-1]],
            'PnL': [1000]
        })
        
        exposure = calculate_exposure_time(mock_equity_curve, trades_df)
        
        # Devrait être ~100%
        assert 95 <= exposure <= 100
    
    def test_exposure_time_never_in_position(self, mock_equity_curve):
        """Test exposure time avec trades très courts."""
        # Trades de 1 jour sur 252 jours
        trades_df = pd.DataFrame({
            'EntryTime': [mock_equity_curve.index[10]],
            'ExitTime': [mock_equity_curve.index[11]],
            'PnL': [100]
        })
        
        exposure = calculate_exposure_time(mock_equity_curve, trades_df)
        
        # Devrait être très faible
        assert exposure < 10
    
    def test_exposure_time_no_trades(self, mock_equity_curve):
        """Test exposure time sans trades."""
        empty_trades = pd.DataFrame(columns=['EntryTime', 'ExitTime', 'PnL'])
        
        exposure = calculate_exposure_time(mock_equity_curve, empty_trades)
        
        assert exposure == 0.0
    
    def test_exposure_time_empty_equity(self):
        """Test exposure time avec equity vide."""
        empty_equity = pd.Series([], dtype=float)
        trades_df = pd.DataFrame({
            'EntryTime': [datetime.now()],
            'ExitTime': [datetime.now()],
            'PnL': [100]
        })
        
        with pytest.raises(ValueError, match="Equity curve cannot be empty"):
            calculate_exposure_time(empty_equity, trades_df)


# ============================================================================
# TESTS: CALCULATE ALL METRICS
# ============================================================================

class TestCalculateAllMetrics:
    """Tests pour calculate_all_metrics."""
    
    def test_calculate_all_metrics_complete(
        self, mock_returns, mock_equity_curve, mock_trades_df
    ):
        """Test calcul de toutes les métriques en 1 appel."""
        metrics = calculate_all_metrics(
            mock_returns, mock_equity_curve, mock_trades_df
        )
        
        # Vérifier que toutes les métriques sont présentes
        expected_keys = [
            'sharpe_ratio', 'sortino_ratio', 'calmar_ratio',
            'max_drawdown_pct', 'max_drawdown_duration_days',
            'win_rate_pct', 'profit_factor', 'avg_trade_duration_days',
            'exposure_time_pct', 'total_return_pct', 'annual_return_pct',
            'total_trades'
        ]
        
        for key in expected_keys:
            assert key in metrics
        
        # Vérifier types
        assert isinstance(metrics['sharpe_ratio'], (float, np.floating))
        assert isinstance(metrics['total_trades'], (int, np.integer, float))
    
    def test_calculate_all_metrics_with_risk_free_rate(
        self, mock_returns, mock_equity_curve, mock_trades_df
    ):
        """Test calculate_all_metrics avec risk-free rate."""
        metrics = calculate_all_metrics(
            mock_returns, mock_equity_curve, mock_trades_df,
            risk_free_rate=0.03
        )
        
        assert 'sharpe_ratio' in metrics
        # Sharpe devrait être différent avec risk-free rate
    
    def test_calculate_all_metrics_handles_errors(self):
        """Test que calculate_all_metrics gère les erreurs gracieusement."""
        # Créer des données problématiques
        bad_returns = pd.Series([np.nan, np.nan])
        bad_equity = pd.Series([100, 100])
        bad_trades = pd.DataFrame({'PnL': []})
        
        # Ne devrait pas crash, devrait retourner NaN pour métriques échouées
        metrics = calculate_all_metrics(bad_returns, bad_equity, bad_trades)
        
        assert isinstance(metrics, dict)
        # Certaines métriques peuvent être NaN
        assert 'sharpe_ratio' in metrics


# ============================================================================
# TESTS: FORMAT METRICS REPORT
# ============================================================================

class TestFormatMetricsReport:
    """Tests pour format_metrics_report."""
    
    def test_format_metrics_report_structure(self, mock_metrics_dict):
        """Test structure du rapport formaté."""
        report_df = format_metrics_report(mock_metrics_dict, "TestStrategy")
        
        assert isinstance(report_df, pd.DataFrame)
        assert 'Metric' in report_df.columns
        assert 'Value' in report_df.columns
        
        # Vérifier que toutes les métriques sont présentes
        assert len(report_df) == len(mock_metrics_dict)
    
    def test_format_metrics_report_value_formatting(self, mock_metrics_dict):
        """Test formatage des valeurs."""
        report_df = format_metrics_report(mock_metrics_dict)
        
        # Vérifier que les valeurs sont des strings formatées
        assert all(isinstance(v, str) for v in report_df['Value'])
        
        # Vérifier formatage des nombres entiers
        total_trades_row = report_df[report_df['Metric'] == 'Total Trades']
        assert total_trades_row['Value'].values[0] == "50"
    
    def test_format_metrics_report_handles_nan(self):
        """Test formatage avec valeurs NaN."""
        metrics_with_nan = {
            'sharpe_ratio': np.nan,
            'total_trades': 10
        }
        
        report_df = format_metrics_report(metrics_with_nan)
        
        # NaN devrait être formaté comme "N/A"
        sharpe_row = report_df[report_df['Metric'] == 'Sharpe Ratio']
        assert sharpe_row['Value'].values[0] == "N/A"
    
    def test_format_metrics_report_handles_inf(self):
        """Test formatage avec valeurs infinies."""
        metrics_with_inf = {
            'profit_factor': float('inf'),
            'total_trades': 5
        }
        
        report_df = format_metrics_report(metrics_with_inf)
        
        # Inf devrait être formaté comme "∞"
        pf_row = report_df[report_df['Metric'] == 'Profit Factor']
        assert pf_row['Value'].values[0] == "∞"


# ============================================================================
# TESTS: COMPARE STRATEGIES
# ============================================================================

class TestCompareStrategies:
    """Tests pour compare_strategies."""
    
    def test_compare_strategies_multiple(self, mock_metrics_dict):
        """Test comparaison de plusieurs stratégies."""
        strategies = {
            'Strategy1': mock_metrics_dict.copy(),
            'Strategy2': {**mock_metrics_dict, 'sharpe_ratio': 1.2, 'win_rate_pct': 55.0},
            'Strategy3': {**mock_metrics_dict, 'sharpe_ratio': 2.5, 'win_rate_pct': 70.0}
        }
        
        comparison_df = compare_strategies(strategies)
        
        assert isinstance(comparison_df, pd.DataFrame)
        assert len(comparison_df) == 3  # 3 stratégies
        assert 'sharpe_ratio' in comparison_df.columns
        assert 'win_rate_pct' in comparison_df.columns
    
    def test_compare_strategies_single(self, mock_metrics_dict):
        """Test comparaison avec une seule stratégie."""
        strategies = {'Strategy1': mock_metrics_dict}
        
        comparison_df = compare_strategies(strategies)
        
        assert len(comparison_df) == 1
    
    def test_compare_strategies_empty(self):
        """Test comparaison avec dict vide."""
        with pytest.raises(ValueError, match="strategies_results cannot be empty"):
            compare_strategies({})
    
    def test_compare_strategies_column_order(self, mock_metrics_dict):
        """Test que les colonnes sont ordonnées logiquement."""
        strategies = {'Strategy1': mock_metrics_dict}
        comparison_df = compare_strategies(strategies)
        
        # total_return_pct devrait être la première colonne
        assert comparison_df.columns[0] == 'total_return_pct'


# ============================================================================
# TESTS: EXPORT FUNCTIONS
# ============================================================================

class TestExportFunctions:
    """Tests pour export_metrics_json et export_metrics_csv."""
    
    def test_export_metrics_json(self, mock_metrics_dict, tmp_path):
        """Test export métriques en JSON."""
        filepath = tmp_path / "metrics.json"
        
        export_metrics_json(mock_metrics_dict, str(filepath))
        
        assert filepath.exists()
        
        # Vérifier contenu
        with open(filepath, 'r') as f:
            loaded_metrics = json.load(f)
        
        assert 'sharpe_ratio' in loaded_metrics
        assert loaded_metrics['sharpe_ratio'] == 1.85
    
    def test_export_metrics_json_handles_nan(self, tmp_path):
        """Test export JSON avec valeurs NaN."""
        metrics_with_nan = {
            'sharpe_ratio': np.nan,
            'sortino_ratio': 2.0
        }
        filepath = tmp_path / "metrics_nan.json"
        
        export_metrics_json(metrics_with_nan, str(filepath))
        
        with open(filepath, 'r') as f:
            loaded = json.load(f)
        
        # NaN devrait être converti en null
        assert loaded['sharpe_ratio'] is None
        assert loaded['sortino_ratio'] == 2.0
    
    def test_export_metrics_json_handles_inf(self, tmp_path):
        """Test export JSON avec valeurs infinies."""
        metrics_with_inf = {
            'profit_factor': float('inf'),
            'win_rate_pct': 60.0
        }
        filepath = tmp_path / "metrics_inf.json"
        
        export_metrics_json(metrics_with_inf, str(filepath))
        
        with open(filepath, 'r') as f:
            loaded = json.load(f)
        
        # Inf devrait être converti en string "Infinity"
        assert loaded['profit_factor'] == "Infinity"
    
    def test_export_metrics_json_creates_dirs(self, tmp_path):
        """Test que export crée les répertoires manquants."""
        nested_path = tmp_path / "subdir" / "nested" / "metrics.json"
        
        export_metrics_json({'test': 1.0}, str(nested_path))
        
        assert nested_path.exists()
    
    def test_export_metrics_csv(self, mock_metrics_dict, tmp_path):
        """Test export métriques en CSV."""
        report_df = format_metrics_report(mock_metrics_dict)
        filepath = tmp_path / "metrics.csv"
        
        export_metrics_csv(report_df, str(filepath))
        
        assert filepath.exists()
        
        # Vérifier contenu
        loaded_df = pd.read_csv(filepath, index_col=0)
        assert 'Metric' in loaded_df.columns
        assert 'Value' in loaded_df.columns
        assert len(loaded_df) == len(report_df)
    
    def test_export_metrics_csv_creates_dirs(self, mock_metrics_dict, tmp_path):
        """Test que export CSV crée les répertoires manquants."""
        report_df = format_metrics_report(mock_metrics_dict)
        nested_path = tmp_path / "subdir" / "metrics.csv"
        
        export_metrics_csv(report_df, str(nested_path))
        
        assert nested_path.exists()


# ============================================================================
# TESTS: HELPER FUNCTIONS
# ============================================================================

class TestHelperFunctions:
    """Tests pour les fonctions helper internes."""
    
    def test_calculate_returns(self, mock_equity_curve):
        """Test _calculate_returns."""
        returns = _calculate_returns(mock_equity_curve)
        
        assert isinstance(returns, pd.Series)
        assert len(returns) == len(mock_equity_curve)
        # Premier return devrait être 0 (fillna)
        assert returns.iloc[0] == 0
    
    def test_annualize_return(self):
        """Test _annualize_return."""
        # Return de 10% sur 252 jours
        total_return = 0.10
        annual_return = _annualize_return(total_return, 252, 252)
        
        # Devrait être ~10% (car exactement 1 an)
        assert abs(annual_return - 0.10) < 0.001
        
        # Return de 10% sur 126 jours (0.5 an)
        annual_return_half = _annualize_return(total_return, 126, 252)
        
        # Devrait être > 10% car extrapolé sur 1 an complet
        assert annual_return_half > 0.10
    
    def test_annualize_return_zero_periods(self):
        """Test _annualize_return avec zero periods."""
        annual_return = _annualize_return(0.10, 0, 252)
        assert annual_return == 0.0
    
    def test_calculate_downside_deviation(self):
        """Test _calculate_downside_deviation."""
        returns = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02])
        
        downside_dev = _calculate_downside_deviation(returns, target_return=0.0)
        
        assert isinstance(downside_dev, float)
        assert downside_dev > 0
        
        # Calculer manuellement
        negative_returns = returns[returns < 0]
        expected_dev = negative_returns.std(ddof=1)
        assert abs(downside_dev - expected_dev) < 0.0001
    
    def test_calculate_downside_deviation_no_negative(self):
        """Test downside deviation sans returns négatifs."""
        returns = pd.Series([0.01, 0.02, 0.03, 0.04])
        
        downside_dev = _calculate_downside_deviation(returns)
        
        # Devrait être 0 car aucun return négatif
        assert downside_dev == 0.0


# ============================================================================
# TESTS EDGE CASES ADDITIONNELS
# ============================================================================

class TestEdgeCases:
    """Tests pour cas limites et erreurs."""
    
    def test_sharpe_with_single_return(self):
        """Test Sharpe avec un seul return."""
        returns = pd.Series([0.01])
        
        # Devrait retourner NaN car std impossible avec 1 valeur
        sharpe = calculate_sharpe_ratio(returns)
        assert np.isnan(sharpe)
    
    def test_max_drawdown_with_negative_equity(self):
        """Test max drawdown avec equity négative."""
        # Equity passant en négatif (cas extrême)
        equity = pd.Series([100, 50, -10, -50])
        
        # Ne devrait pas crash
        max_dd_info = calculate_max_drawdown(equity)
        assert isinstance(max_dd_info, dict)
    
    def test_profit_factor_with_zero_pnl(self):
        """Test profit factor avec tous PnL = 0."""
        trades_df = pd.DataFrame({'PnL': [0, 0, 0]})
        
        pf = calculate_profit_factor(trades_df)
        
        # Devrait retourner 0
        assert pf == 0.0
    
    def test_metrics_with_very_short_period(self):
        """Test métriques avec période très courte (5 jours)."""
        returns = pd.Series([0.01, -0.02, 0.03, -0.01, 0.02])
        equity = pd.Series([100, 101, 98.98, 101.95, 100.93, 102.95])
        trades_df = pd.DataFrame({
            'EntryTime': pd.to_datetime(['2023-01-01', '2023-01-03']),
            'ExitTime': pd.to_datetime(['2023-01-02', '2023-01-04']),
            'PnL': [50, -30]
        })
        
        # Ne devrait pas crash
        metrics = calculate_all_metrics(returns, equity, trades_df)
        
        assert isinstance(metrics, dict)
        assert 'sharpe_ratio' in metrics


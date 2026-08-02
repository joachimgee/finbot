"""
Tests pour le module Backtesting.

Author: FinBot Team
Date: 2025-11-06
Version: 2.0.0
"""

from datetime import datetime

import numpy as np
import pandas as pd
import pytest
from backtesting import Strategy

from financial_analyzer.backtest import BacktestRunner, CustomStrategy


# Markers pytest pour tous les tests de ce fichier
pytestmark = [pytest.mark.backtest, pytest.mark.unit]


@pytest.fixture
def mock_features_df():
    """Fixture avec 252 jours de features OHLCV + indicators."""
    dates = pd.date_range('2023-01-01', periods=252, freq='D')
    
    np.random.seed(42)
    
    # Prix avec tendance haussière
    close = 100 + np.cumsum(np.random.normal(0.1, 1, 252))
    open_prices = close + np.random.uniform(-0.5, 0.5, 252)
    high = np.maximum(open_prices, close) + np.random.uniform(0, 1, 252)
    low = np.minimum(open_prices, close) - np.random.uniform(0, 1, 252)
    volume = np.random.randint(1000000, 5000000, 252)
    
    # Features techniques simples
    sma_20 = pd.Series(close).rolling(20).mean().values
    rsi_14 = 50 + np.random.uniform(-20, 20, 252)  # RSI simulé
    
    # Signal simple (buy when RSI < 40, sell when RSI > 60)
    signal = np.where(rsi_14 < 40, 1, np.where(rsi_14 > 60, -1, 0))
    
    df = pd.DataFrame(
        {
            'Open': open_prices,
            'High': high,
            'Low': low,
            'Close': close,
            'Volume': volume,
            'SMA_20': sma_20,
            'RSI_14': rsi_14,
            'Signal': signal,
        },
        index=dates,
    )
    
    # Forward fill NaN des premiers jours (SMA_20)
    df = df.ffill()
    
    return df


@pytest.fixture
def dummy_strategy():
    """Stratégie dummy pour tests (buy/sell alterné sur Signal)."""
    class DummyStrategy(CustomStrategy):
        def init(self):
            """Init: pas d'indicateurs additionnels."""
            pass
        
        def next(self):
            """Logic: buy si Signal=1, sell si Signal=-1."""
            if self.data.Signal[-1] == 1 and not self.position:
                self.buy()
            elif self.data.Signal[-1] == -1 and self.position:
                self.position.close()
    
    return DummyStrategy


class RSIStrategy(CustomStrategy):
    """Classe RSI définie au niveau module pour permettre l'optimisation.

    Définit des attributs `rsi_lower` et `rsi_upper` qui seront modifiés
    par l'optimiseur si nécessaire.
    """
    rsi_lower = 30
    rsi_upper = 70

    def init(self):
        """Init: accès à RSI_14."""
        self.rsi = self.data.RSI_14

    def next(self):
        """Logic: buy si RSI < rsi_lower, sell si RSI > rsi_upper."""
        if self.rsi[-1] < self.rsi_lower and not self.position:
            self.buy()
        elif self.rsi[-1] > self.rsi_upper and self.position:
            self.position.close()


@pytest.fixture
def rsi_strategy():
    """Stratégie RSI pour tests (oversold/overbought)."""
    # Retourne la classe module-level RSIStrategy définie ci-dessous
    return RSIStrategy


class TestBacktestRunnerInit:
    """Tests d'initialisation du BacktestRunner."""
    
    @pytest.mark.unit
    def test_init_valid_features(self, mock_features_df, dummy_strategy):
        """Test initialisation avec features valides."""
        runner = BacktestRunner(mock_features_df, dummy_strategy)
        
        assert runner.features is not None
        assert len(runner.features) == 252
        assert runner.strategy == dummy_strategy
        assert runner.cash == 100_000
        assert runner.commission == 0.002
    
    @pytest.mark.unit
    def test_init_with_custom_params(self, mock_features_df, dummy_strategy):
        """Test initialisation avec paramètres custom."""
        runner = BacktestRunner(
            mock_features_df,
            dummy_strategy,
            cash=50_000,
            commission=0.001
        )
        
        assert runner.cash == 50_000
        assert runner.commission == 0.001
    
    @pytest.mark.unit
    def test_init_invalid_features_not_dataframe(self, dummy_strategy):
        """Test ValueError si features n'est pas DataFrame."""
        with pytest.raises(TypeError, match="features doit être DataFrame"):
            BacktestRunner([1, 2, 3], dummy_strategy)
    
    @pytest.mark.unit
    def test_init_invalid_features_empty(self, dummy_strategy):
        """Test ValueError si features DataFrame vide."""
        empty_df = pd.DataFrame()
        
        with pytest.raises(ValueError, match="ne peut pas être vide"):
            BacktestRunner(empty_df, dummy_strategy)
    
    @pytest.mark.unit
    def test_init_invalid_features_no_datetime_index(self, dummy_strategy):
        """Test ValueError si index pas DatetimeIndex."""
        df = pd.DataFrame(
            {'Open': [100], 'High': [102], 'Low': [99], 'Close': [101], 'Volume': [1000000]},
            index=[0],  # Integer index
        )
        
        with pytest.raises(ValueError, match="index doit être DatetimeIndex"):
            BacktestRunner(df, dummy_strategy)
    
    @pytest.mark.unit
    def test_init_invalid_features_missing_ohlcv(self, dummy_strategy):
        """Test ValueError si colonnes OHLCV manquantes."""
        df = pd.DataFrame(
            {'Close': [100, 101, 102]},
            index=pd.date_range('2023-01-01', periods=3),
        )
        
        with pytest.raises(ValueError, match="Colonnes OHLCV manquantes"):
            BacktestRunner(df, dummy_strategy)
    
    @pytest.mark.unit
    def test_init_invalid_strategy_not_subclass(self, mock_features_df):
        """Test TypeError si strategy pas subclass de Strategy."""
        class NotAStrategy:
            pass
        
        with pytest.raises(TypeError, match="doit être subclass de Strategy"):
            BacktestRunner(mock_features_df, NotAStrategy)


class TestBacktestRunnerRun:
    """Tests de la méthode run()."""
    
    @pytest.mark.unit
    def test_run_default(self, mock_features_df, dummy_strategy):
        """Test run avec paramètres par défaut."""
        runner = BacktestRunner(mock_features_df, dummy_strategy)
        result = runner.run()
        
        # Vérifier résultats retournés
        assert isinstance(result, pd.Series)
        assert 'Return [%]' in result.index
        assert '# Trades' in result.index
    
    @pytest.mark.unit
    @pytest.mark.skip(reason="Bokeh plotting bloque pytest - test manuel")
    def test_run_with_return_plot(self, mock_features_df, dummy_strategy):
        """Test run avec return_plot=True (SKIP - test manuel)."""
        pass
    
    @pytest.mark.unit
    def test_commission_applied(self, mock_features_df, dummy_strategy):
        """Test que commission est appliquée."""
        # Run sans commission
        runner1 = BacktestRunner(
            mock_features_df,
            dummy_strategy,
            commission=0.0
        )
        result1 = runner1.run()
        
        # Run avec commission
        runner2 = BacktestRunner(
            mock_features_df,
            dummy_strategy,
            commission=0.002
        )
        result2 = runner2.run()
        
        # Return devrait être inférieur avec commission
        assert result2['Return [%]'] <= result1['Return [%]']
    
    @pytest.mark.unit
    def test_result_keys_and_metrics(self, mock_features_df, dummy_strategy):
        """Test présence de toutes les métriques clés."""
        runner = BacktestRunner(mock_features_df, dummy_strategy)
        result = runner.run()
        
        # Métriques clés attendues
        expected_keys = [
            'Return [%]',
            'Sharpe Ratio',
            'Max. Drawdown [%]',
            'Win Rate [%]',
            '# Trades',
        ]
        
        for key in expected_keys:
            assert key in result.index, f"Métrique manquante: {key}"


class TestStrategyFeatureAccess:
    """Tests d'accès aux features dans stratégies."""
    
    @pytest.mark.unit
    def test_strategy_access_to_features(self, mock_features_df):
        """Test que stratégie peut accéder aux features."""
        class FeatureAccessStrategy(CustomStrategy):
            def init(self):
                # Accéder aux features
                self.sma = self.data.SMA_20
                self.rsi = self.data.RSI_14
                self.signal = self.data.Signal
            
            def next(self):
                # Vérifier accès aux features
                assert self.sma[-1] is not None
                assert self.rsi[-1] is not None
                assert self.signal[-1] is not None
                
                # Logic simple
                if self.signal[-1] == 1 and not self.position:
                    self.buy()
        
        runner = BacktestRunner(mock_features_df, FeatureAccessStrategy)
        result = runner.run()
        
        # Devrait fonctionner sans erreur
        assert result is not None
    
    @pytest.mark.unit
    def test_custom_signal_rule(self, mock_features_df):
        """Test stratégie avec règle custom."""
        class CustomRuleStrategy(CustomStrategy):
            def init(self):
                self.sma = self.data.SMA_20
                self.close = self.data.Close
            
            def next(self):
                # Règle: buy si Close > SMA, sell si Close < SMA
                if self.close[-1] > self.sma[-1] and not self.position:
                    self.buy()
                elif self.close[-1] < self.sma[-1] and self.position:
                    self.position.close()
        
        runner = BacktestRunner(mock_features_df, CustomRuleStrategy)
        result = runner.run()
        
        # Vérifier trades générés
        assert result['# Trades'] > 0


class TestMetricsCalculation:
    """Tests de calcul des métriques."""
    
    @pytest.mark.unit
    def test_win_rate_calculation(self, mock_features_df, dummy_strategy):
        """Test calcul Win Rate."""
        runner = BacktestRunner(mock_features_df, dummy_strategy)
        result = runner.run()
        
        # Win Rate devrait être entre 0 et 100
        assert 0 <= result['Win Rate [%]'] <= 100
    
    @pytest.mark.unit
    def test_max_drawdown_calculation(self, mock_features_df, dummy_strategy):
        """Test calcul Max Drawdown."""
        runner = BacktestRunner(mock_features_df, dummy_strategy)
        result = runner.run()
        
        # Max Drawdown devrait être négatif (perte)
        assert result['Max. Drawdown [%]'] <= 0
    
    @pytest.mark.unit
    def test_sharpe_ratio_calculation(self, mock_features_df, dummy_strategy):
        """Test calcul Sharpe Ratio."""
        runner = BacktestRunner(mock_features_df, dummy_strategy)
        result = runner.run()
        
        # Sharpe Ratio devrait exister
        assert 'Sharpe Ratio' in result.index


class TestTrades:
    """Tests de gestion des trades."""
    
    @pytest.mark.unit
    def test_buy_and_sell_trades(self, mock_features_df, dummy_strategy):
        """Test exécution buy et sell trades."""
        runner = BacktestRunner(mock_features_df, dummy_strategy)
        result = runner.run()
        
        # Devrait avoir au moins 1 trade
        assert result['# Trades'] > 0
    
    @pytest.mark.unit
    def test_get_trades(self, mock_features_df, dummy_strategy):
        """Test récupération DataFrame trades."""
        runner = BacktestRunner(mock_features_df, dummy_strategy)
        runner.run()
        
        trades = runner.get_trades()
        
        # Vérifier structure DataFrame
        assert isinstance(trades, pd.DataFrame)
        assert len(trades) > 0
        
        # Colonnes attendues
        expected_cols = ['Size', 'EntryBar', 'ExitBar', 'EntryPrice', 'ExitPrice', 'PnL']
        for col in expected_cols:
            assert col in trades.columns, f"Colonne manquante: {col}"
    
    @pytest.mark.unit
    def test_get_trades_before_run(self, mock_features_df, dummy_strategy):
        """Test RuntimeError si get_trades() avant run()."""
        runner = BacktestRunner(mock_features_df, dummy_strategy)
        
        with pytest.raises(RuntimeError, match="Appeler run\\(\\) d'abord"):
            runner.get_trades()


class TestEquityCurve:
    """Tests de courbe equity."""
    
    @pytest.mark.unit
    def test_get_equity_curve(self, mock_features_df, dummy_strategy):
        """Test récupération equity curve."""
        runner = BacktestRunner(mock_features_df, dummy_strategy)
        runner.run()
        
        equity = runner.get_equity_curve()
        
        # Vérifier structure Series
        assert isinstance(equity, pd.Series)
        assert len(equity) > 0
        
        # Equity devrait commencer proche de cash initial
        assert abs(equity.iloc[0] - 100_000) < 1000
    
    @pytest.mark.unit
    def test_get_equity_curve_before_run(self, mock_features_df, dummy_strategy):
        """Test RuntimeError si get_equity_curve() avant run()."""
        runner = BacktestRunner(mock_features_df, dummy_strategy)
        
        with pytest.raises(RuntimeError, match="Appeler run\\(\\) d'abord"):
            runner.get_equity_curve()


class TestStatsDict:
    """Tests de conversion stats en dict."""
    
    @pytest.mark.unit
    def test_get_stats_dict(self, mock_features_df, dummy_strategy):
        """Test conversion stats en dict."""
        runner = BacktestRunner(mock_features_df, dummy_strategy)
        runner.run()
        
        stats_dict = runner.get_stats_dict()
        
        # Vérifier structure dict
        assert isinstance(stats_dict, dict)
        assert len(stats_dict) > 0
        
        # Métriques clés présentes
        assert 'Return [%]' in stats_dict
        assert '# Trades' in stats_dict
    
    @pytest.mark.unit
    def test_get_stats_dict_before_run(self, mock_features_df, dummy_strategy):
        """Test RuntimeError si get_stats_dict() avant run()."""
        runner = BacktestRunner(mock_features_df, dummy_strategy)
        
        with pytest.raises(RuntimeError, match="Appeler run\\(\\) d'abord"):
            runner.get_stats_dict()


class TestEdgeCases:
    """Tests de cas limites."""
    
    @pytest.mark.unit
    def test_with_constant_features(self, dummy_strategy):
        """Test avec features constantes (pas de variation)."""
        dates = pd.date_range('2023-01-01', periods=100, freq='D')
        
        df = pd.DataFrame(
            {
                'Open': [100.0] * 100,
                'High': [101.0] * 100,
                'Low': [99.0] * 100,
                'Close': [100.0] * 100,
                'Volume': [1000000] * 100,
                'Signal': [0] * 100,  # Pas de signaux
            },
            index=dates,
        )
        
        runner = BacktestRunner(df, dummy_strategy)
        result = runner.run()
        
        # Devrait fonctionner, mais pas de trades
        assert result['# Trades'] == 0
        assert result['Return [%]'] == 0.0
    
    @pytest.mark.unit
    def test_single_trade(self, mock_features_df):
        """Test avec stratégie qui génère 1 seul trade."""
        class SingleTradeStrategy(CustomStrategy):
            def init(self):
                self.bought = False
            
            def next(self):
                # Buy seulement au début
                if not self.bought and not self.position:
                    self.buy()
                    self.bought = True
        
        runner = BacktestRunner(mock_features_df, SingleTradeStrategy)
        result = runner.run()
        
        # Devrait avoir exactement 1 trade
        assert result['# Trades'] == 1


class TestOptimize:
    """Tests d'optimisation paramètres."""
    
    @pytest.mark.unit
    def test_optimize_rsi_params(self, mock_features_df, rsi_strategy):
        """Test optimisation paramètres RSI."""
        runner = BacktestRunner(mock_features_df, rsi_strategy)
        
        result = runner.optimize(
            rsi_lower=range(20, 35, 5),
            rsi_upper=range(65, 80, 5),
            maximize='Return [%]',
            method='grid'
        )
        
        # Vérifier résultats
        assert isinstance(result, pd.Series)
        assert 'Return [%]' in result.index
    
    @pytest.mark.unit
    def test_optimize_with_constraint(self, mock_features_df, rsi_strategy):
        """Test optimisation avec constraint."""
        def constraint(params):
            # rsi_upper doit être > rsi_lower + 20
            return params['rsi_upper'] > params['rsi_lower'] + 20
        
        runner = BacktestRunner(mock_features_df, rsi_strategy)
        
        result = runner.optimize(
            rsi_lower=range(20, 40, 10),
            rsi_upper=range(60, 80, 10),
            constraint=constraint,
            maximize='Sharpe Ratio',
            method='grid'
        )
        
        # Devrait fonctionner avec constraint
        assert result is not None


class TestIntegration:
    """Tests d'intégration E2E."""
    
    @pytest.mark.integration
    def test_full_pipeline_to_backtest(self, mock_features_df, dummy_strategy):
        """Test pipeline complet: features → backtest → metrics."""
        # Simuler pipeline features (déjà fait dans fixture)
        features = mock_features_df
        
        # Backtest
        runner = BacktestRunner(features, dummy_strategy)
        result = runner.run()
        
        # Vérifier résultats complets
        assert result['# Trades'] > 0
        assert 'Return [%]' in result.index
        assert 'Sharpe Ratio' in result.index
        
        # Get trades
        trades = runner.get_trades()
        assert len(trades) > 0
        
        # Get equity
        equity = runner.get_equity_curve()
        assert len(equity) > 0
        
        # Get stats dict
        stats = runner.get_stats_dict()
        assert len(stats) > 0

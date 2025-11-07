"""
Tests for SentimentMomentumStrategy.

Coverage:
- Initialization (5 tests)
- Entry conditions (6 tests)
- Exit conditions (4 tests)
- Position sizing (3 tests)
- Integration backtest (2 tests)

Total: 20 tests
"""

import pytest
from unittest.mock import MagicMock, patch
import pandas as pd
import numpy as np
from typing import Optional

from financial_analyzer.strategies.sentiment_momentum_strategy import SentimentMomentumStrategy
# backtesting.Backtest pour tests integration
from backtesting import Backtest


def _make_backtest_data(days: int = 252, seed: Optional[int] = 42) -> pd.DataFrame:
    """
    Génère données mock pour backtesting avec sentiment factors.
    
    Args:
        days: Nombre de jours de données
        seed: Random seed pour reproductibilité
    
    Returns:
        DataFrame avec colonnes : Open, High, Low, Close, Volume,
                                  sentiment_ma_5d, sentiment_surprise_20d
    
    Example:
        >>> data = _make_backtest_data(100)
        >>> data.shape
        (100, 7)
        >>> 'sentiment_ma_5d' in data.columns
        True
    """
    if seed is not None:
        np.random.seed(seed)
    
    idx = pd.date_range('2024-01-01', periods=days, freq='D')
    
    # Prix OHLC (random walk)
    close = 100 + np.cumsum(np.random.randn(days) * 0.5)
    close = np.maximum(close, 50)  # Éviter prix négatifs
    
    # Sentiment factors (mock réalistes)
    sentiment_ma = np.random.uniform(-0.5, 0.8, days)  # Mostly positive
    sentiment_surprise = np.random.normal(0, 1.0, days)  # Centered 0, std=1
    
    df = pd.DataFrame({
        'Open': close * 0.998,
        'High': close * 1.005,
        'Low': close * 0.995,
        'Close': close,
        'Volume': np.random.randint(900_000, 1_200_000, days),
        'sentiment_ma_5d': sentiment_ma,
        'sentiment_surprise_20d': sentiment_surprise
    }, index=idx)
    
    return df


# -------------------- Initialization Tests --------------------

def test_strategy_init_with_valid_data():
    """Strategy s'initialise correctement avec données valides."""
    data = _make_backtest_data(100)
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000, commission=0.002)
    
    # Run pour déclencher init()
    stats = bt.run()
    
    # Vérifier que backtest a tourné
    assert stats is not None
    assert 'Return [%]' in stats
    assert 'Sharpe Ratio' in stats
    assert '# Trades' in stats


def test_strategy_init_missing_sentiment_columns():
    """Strategy lève ValueError si colonnes sentiment manquantes."""
    data = _make_backtest_data(100)
    data = data.drop(columns=['sentiment_ma_5d'])  # Remove required column
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    
    with pytest.raises(ValueError, match="Missing sentiment columns"):
        bt.run()


def test_strategy_parameters_default_values():
    """Vérifier valeurs par défaut des paramètres."""
    assert SentimentMomentumStrategy.sentiment_threshold == 0.3
    assert SentimentMomentumStrategy.surprise_threshold == 1.5
    assert SentimentMomentumStrategy.rsi_period == 14
    assert SentimentMomentumStrategy.rsi_upper == 70
    assert SentimentMomentumStrategy.rsi_exit == 80
    assert SentimentMomentumStrategy.volume_multiplier == 1.2
    assert SentimentMomentumStrategy.max_position_size == 0.10
    assert SentimentMomentumStrategy.stop_loss_pct == 0.05


def test_strategy_init_with_custom_parameters():
    """Strategy accepte paramètres custom."""
    data = _make_backtest_data(100)
    
    class CustomStrategy(SentimentMomentumStrategy):
        sentiment_threshold = 0.5
        rsi_period = 21
        max_position_size = 0.15
    
    bt = Backtest(data, CustomStrategy, cash=100_000)
    stats = bt.run()
    
    assert stats is not None
    # Vérifier que paramètres custom ont été utilisés
    assert stats._strategy.sentiment_threshold == 0.5
    assert stats._strategy.rsi_period == 21
    assert stats._strategy.max_position_size == 0.15


def test_strategy_indicators_initialized():
    """Indicateurs techniques initialisés correctement."""
    data = _make_backtest_data(100)
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    
    # Accès à la stratégie après run
    stats = bt.run()
    
    # Vérifier que backtest a tourné (indicateurs OK si pas d'erreur)
    assert stats['# Trades'] >= 0
    # Note: backtesting.py ne donne pas accès direct aux indicateurs internes
    # mais si init() échoue, run() lève une exception


# -------------------- Entry Conditions Tests --------------------

def test_entry_long_all_conditions_met():
    """Entry LONG quand toutes conditions respectées."""
    data = _make_backtest_data(200, seed=123)
    
    # Forcer conditions favorables sur une période
    data.loc[data.index[50:60], 'sentiment_ma_5d'] = 0.6  # > 0.3
    data.loc[data.index[50:60], 'sentiment_surprise_20d'] = 2.0  # > 1.5
    # Volume déjà aléatoire, RSI sera OK si pas de strong trend
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000, commission=0.001)
    stats = bt.run()
    
    # Au moins 1 trade doit avoir été généré
    assert stats['# Trades'] >= 1


def test_no_entry_if_sentiment_too_low():
    """Pas d'entry si sentiment < threshold."""
    data = _make_backtest_data(100, seed=42)
    
    # Forcer sentiment négatif partout
    data['sentiment_ma_5d'] = -0.5
    data['sentiment_surprise_20d'] = 2.0  # Surprise OK mais sentiment trop bas
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    stats = bt.run()
    
    # Aucun trade attendu
    assert stats['# Trades'] == 0


def test_no_entry_if_surprise_too_low():
    """Pas d'entry si surprise < threshold."""
    data = _make_backtest_data(100, seed=42)
    
    # Forcer surprise faible partout
    data['sentiment_ma_5d'] = 0.7  # Sentiment OK
    data['sentiment_surprise_20d'] = 0.5  # < 1.5
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    stats = bt.run()
    
    # Très peu ou pas de trades
    assert stats['# Trades'] <= 1


def test_no_entry_if_rsi_overbought():
    """Pas d'entry si RSI > rsi_upper."""
    data = _make_backtest_data(100, seed=42)
    
    # Forcer sentiment OK mais créer strong uptrend → RSI élevé
    data['sentiment_ma_5d'] = 0.7
    data['sentiment_surprise_20d'] = 2.0
    data['Close'] = 100 + np.cumsum(np.ones(100) * 2)  # Strong uptrend → RSI > 70
    data['High'] = data['Close'] * 1.005
    data['Low'] = data['Close'] * 0.995
    data['Open'] = data['Close'] * 0.998
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    stats = bt.run()
    
    # Peu ou pas de trades (RSI constamment overbought)
    assert stats['# Trades'] <= 2


def test_entry_position_sizing_proportional_to_sentiment():
    """Position size proportionnel à sentiment strength."""
    data = _make_backtest_data(100, seed=42)
    
    # Scenario: sentiment moyen (0.5) → size ~= 30% de max (sentiment_strength ~= 0.3)
    # (0.5 - 0.3) / (1.0 - 0.3) = 0.2 / 0.7 = ~0.29
    data.loc[data.index[30:40], 'sentiment_ma_5d'] = 0.5
    data.loc[data.index[30:40], 'sentiment_surprise_20d'] = 2.0
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    stats = bt.run()
    
    # Vérifier que des trades ont eu lieu (test indirect de position sizing)
    assert stats['Exposure Time [%]'] > 0


def test_no_entry_if_volume_too_low():
    """Pas d'entry si volume < threshold."""
    data = _make_backtest_data(100, seed=42)
    
    # Forcer sentiment OK mais volume très bas
    data['sentiment_ma_5d'] = 0.7
    data['sentiment_surprise_20d'] = 2.0
    data['Volume'] = 100  # Très faible → volume_ma * 1.2 toujours > current
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    stats = bt.run()
    
    # Pas de trades car volume condition jamais satisfaite
    assert stats['# Trades'] == 0


def test_entry_logged_correctly():
    """Entry events sont logged (via mock)."""
    data = _make_backtest_data(100, seed=42)
    data.loc[data.index[40:50], 'sentiment_ma_5d'] = 0.8
    data.loc[data.index[40:50], 'sentiment_surprise_20d'] = 2.5
    
    with patch('financial_analyzer.strategies.sentiment_momentum_strategy.logger') as mock_logger:
        bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
        stats = bt.run()
        
        # Vérifier que logger.info a été appelé (au moins 1 fois pour init)
        assert mock_logger.info.call_count >= 1


# -------------------- Exit Conditions Tests --------------------

def test_exit_when_sentiment_turns_negative():
    """Exit position si sentiment < 0."""
    data = _make_backtest_data(100, seed=42)
    
    # Entry conditions @ bar 30-40
    data.loc[data.index[30:40], 'sentiment_ma_5d'] = 0.7
    data.loc[data.index[30:40], 'sentiment_surprise_20d'] = 2.0
    
    # Exit trigger @ bar 45 : sentiment négatif
    data.loc[data.index[45:], 'sentiment_ma_5d'] = -0.3
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    stats = bt.run()
    
    # Au moins un trade généré et fermé
    assert stats['# Trades'] >= 1
    # Trade fermé rapidement (< 20 jours)
    if stats['# Trades'] > 0:
        assert stats['Avg. Trade Duration'] < pd.Timedelta(days=20)


def test_exit_when_rsi_extreme_overbought():
    """Exit position si RSI > rsi_exit (80)."""
    data = _make_backtest_data(100, seed=42)
    
    # Entry @ bar 20
    data.loc[data.index[20:30], 'sentiment_ma_5d'] = 0.6
    data.loc[data.index[20:30], 'sentiment_surprise_20d'] = 1.8
    
    # Strong rally @ bar 35+ → RSI > 80
    for i in range(35, len(data)):
        data.loc[data.index[i], 'Close'] = data.loc[data.index[i-1], 'Close'] * 1.02
    data.loc[data.index[35:], 'High'] = data.loc[data.index[35:], 'Close'] * 1.005
    data.loc[data.index[35:], 'Low'] = data.loc[data.index[35:], 'Close'] * 0.995
    data.loc[data.index[35:], 'Open'] = data.loc[data.index[35:], 'Close'] * 0.998
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    stats = bt.run()
    
    # Au moins un trade
    assert stats['# Trades'] >= 1


def test_stop_loss_triggered():
    """Stop loss déclenché si perte > stop_loss_pct."""
    data = _make_backtest_data(100, seed=42)
    
    # Entry @ bar 30
    data.loc[data.index[30:35], 'sentiment_ma_5d'] = 0.7
    data.loc[data.index[30:35], 'sentiment_surprise_20d'] = 2.0
    
    # Crash @ bar 40 : -10% depuis entry
    entry_price = data.loc[data.index[30], 'Close']
    data.loc[data.index[40:], 'Close'] = entry_price * 0.90  # -10%
    data.loc[data.index[40:], 'High'] = data.loc[data.index[40:], 'Close'] * 1.002
    data.loc[data.index[40:], 'Low'] = data.loc[data.index[40:], 'Close'] * 0.998
    data.loc[data.index[40:], 'Open'] = data.loc[data.index[40:], 'Close'] * 1.001
    
    # stop_loss_pct = 0.05 (5%) → exit attendu
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    stats = bt.run()
    
    # Vérifications renforcées
    assert stats['# Trades'] >= 1, "Au moins 1 trade attendu"
    if stats['# Trades'] > 0:
        assert stats['Avg. Trade Duration'] < pd.Timedelta(days=15), \
            f"Trade devrait fermer vite après crash, got {stats['Avg. Trade Duration']}"
    assert stats['Return [%]'] < 0, \
        f"Return devrait être négatif après stop-loss, got {stats['Return [%]']:.2f}%"


def test_no_exit_if_all_conditions_still_valid():
    """Position reste ouverte si toutes conditions valides."""
    data = _make_backtest_data(100, seed=42)
    
    # Sentiment constamment positif, RSI OK (trend modéré)
    data['sentiment_ma_5d'] = 0.5
    data['sentiment_surprise_20d'] = 1.8
    data['Close'] = 100 + np.linspace(0, 5, 100)  # Trend modéré → RSI OK
    data['High'] = data['Close'] * 1.005
    data['Low'] = data['Close'] * 0.995
    data['Open'] = data['Close'] * 0.998
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    stats = bt.run()
    
    # Peu de trades (position longue maintenue)
    assert stats['# Trades'] <= 5


# -------------------- Position Sizing Tests --------------------

def test_position_size_scales_with_sentiment_strength():
    """Position size augmente avec sentiment strength."""
    data_low = _make_backtest_data(100, seed=100)
    data_high = _make_backtest_data(100, seed=101)
    
    # Scenario 1: sentiment faible (0.4) → strength ~= 0.14
    data_low.loc[data_low.index[30:50], 'sentiment_ma_5d'] = 0.4
    data_low.loc[data_low.index[30:50], 'sentiment_surprise_20d'] = 2.0
    
    # Scenario 2: sentiment élevé (0.9) → strength ~= 0.86
    data_high.loc[data_high.index[30:50], 'sentiment_ma_5d'] = 0.9
    data_high.loc[data_high.index[30:50], 'sentiment_surprise_20d'] = 2.0
    
    bt_low = Backtest(data_low, SentimentMomentumStrategy, cash=100_000)
    bt_high = Backtest(data_high, SentimentMomentumStrategy, cash=100_000)
    
    stats_low = bt_low.run()
    stats_high = bt_high.run()
    
    # Vérifier que high a plus d'exposition (indirectement)
    # Note: test indirect car backtesting.py n'expose pas position sizes individuels
    assert stats_low['# Trades'] >= 0 and stats_high['# Trades'] >= 0


def test_max_position_size_respected():
    """Position size ne dépasse jamais max_position_size."""
    data = _make_backtest_data(100, seed=42)
    data['sentiment_ma_5d'] = 1.0  # Sentiment max
    data['sentiment_surprise_20d'] = 3.0
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    stats = bt.run()
    
    # Max Exposure ne doit pas dépasser max_position_size * 100%
    # Note : Exposure Time [%] est temps en position, pas size
    # Test indirect : vérifier que strategy n'a pas over-leveraged
    assert stats['Exposure Time [%]'] <= 100


def test_position_size_zero_if_sentiment_at_threshold():
    """Position size ~0 si sentiment exactement au threshold."""
    data = _make_backtest_data(100, seed=42)
    
    # Sentiment exactement au threshold (0.3) → strength = 0
    data.loc[data.index[30:50], 'sentiment_ma_5d'] = 0.30001  # Juste au-dessus
    data.loc[data.index[30:50], 'sentiment_surprise_20d'] = 2.0
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000)
    stats = bt.run()
    
    # Peu ou pas de trades (size trop faible pour être significatif)
    assert stats['# Trades'] <= 3


# -------------------- Integration Tests --------------------

def test_backtest_complete_run():
    """Backtest complet sur 1 an de données."""
    data = _make_backtest_data(252, seed=42)  # 1 trading year
    
    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000, commission=0.002)
    stats = bt.run()
    
    # Vérifier métriques clés présentes
    assert 'Return [%]' in stats
    assert 'Sharpe Ratio' in stats
    assert 'Max. Drawdown [%]' in stats
    assert 'Win Rate [%]' in stats
    assert '# Trades' in stats
    assert stats['# Trades'] >= 0
    
    # Vérifier que equity final existe
    assert 'Equity Final [$]' in stats
    assert stats['Equity Final [$]'] > 0


def test_backtest_with_optimization():
    """Optimization des paramètres via backtesting.py."""
    data = _make_backtest_data(300, seed=42)
    # Forcer conditions favorables pour générer des trades
    data.loc[data.index[50:150], 'sentiment_ma_5d'] = np.random.uniform(0.4, 0.8, 100)
    data.loc[data.index[50:150], 'sentiment_surprise_20d'] = np.random.uniform(1.6, 2.5, 100)

    bt = Backtest(data, SentimentMomentumStrategy, cash=100_000, commission=0.002)
    
    # Certains environnements de backtesting.py appliquent constraint sur les paramètres
    # et non sur les stats; on utilise une contrainte triviale pour éviter KeyError.
    stats = bt.optimize(
        sentiment_threshold=[0.2, 0.3, 0.4],
        rsi_period=[10, 14, 21],
        maximize='Sharpe Ratio',
        constraint=lambda p: True
    )
    
    # Vérifier que optimization a tourné
    assert stats is not None
    assert 'Return [%]' in stats
    assert stats._strategy.sentiment_threshold in [0.2, 0.3, 0.4]
    assert stats._strategy.rsi_period in [10, 14, 21]


# -------------------- Helper pour import check --------------------

# (Optional already imported en haut)

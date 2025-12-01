import pandas as pd
import numpy as np

from financial_analyzer.integration.weighting_engine import WeightingEngine
from financial_analyzer.integration.signal_fusion_engine import SignalFusionEngine


def generate_history(days: int = 120) -> pd.DataFrame:
    rng = pd.date_range("2025-01-01", periods=days)
    # Technical: strong sharpe
    technical = np.random.normal(0.0012, 0.008, days)
    # Fundamental: moderate
    fundamental = np.random.normal(0.0009, 0.009, days)
    # Sentiment: higher vol, slightly better mean
    sentiment = np.random.normal(0.0011, 0.012, days)
    # LSTM: best mean, moderate vol
    ml_lstm = np.random.normal(0.0015, 0.010, days)
    # ML factor: weaker
    ml_factor = np.random.normal(0.0005, 0.011, days)
    # RL: neutral
    rl = np.random.normal(0.0007, 0.010, days)
    return pd.DataFrame({
        'technical': technical,
        'fundamental': fundamental,
        'sentiment': sentiment,
        'ml_lstm': ml_lstm,
        'ml_factor': ml_factor,
        'rl': rl
    }, index=rng)


def test_weighting_engine_basic():
    history = generate_history()
    engine = WeightingEngine()
    result = engine.compute_weights(history)
    assert result.observations == len(history)
    assert abs(sum(result.weights.values()) - 1.0) < 1e-9
    # LSTM devrait avoir un poids >= technique (meilleur mean) ou proche
    assert result.weights['ml_lstm'] >= result.weights['ml_factor']
    # Poids positifs
    for w in result.weights.values():
        assert w > 0


def test_signal_fusion_engine_reweighting():
    history = generate_history()
    sfe = SignalFusionEngine(weighting_history=history)
    weights = sfe.source_weights
    assert abs(sum(weights.values()) - 1.0) < 1e-9
    # Vérifier qu'au moins un poids diffère des defaults (évidence-based)
    defaults = SignalFusionEngine.DEFAULT_WEIGHTS
    changed = any(abs(weights[k] - defaults[k]/sum(defaults.values())) > 0.05 for k in defaults)
    assert changed


def test_dynamic_update_weights():
    history = generate_history()
    sfe = SignalFusionEngine(weighting_history=history)
    # Simuler nouvelle histoire où ml_factor devient meilleur
    new_history = history.copy()
    new_history['ml_factor'] = np.random.normal(0.0020, 0.009, len(history))
    before = sfe.source_weights['ml_factor']
    sfe.update_weights_from_history(new_history, min_change=0.0)
    after = sfe.source_weights['ml_factor']
    assert after > before  # poids doit augmenter


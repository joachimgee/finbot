import pandas as pd
import numpy as np

from financial_analyzer.integration.weighting_engine import WeightingEngine
from financial_analyzer.integration.signal_fusion_engine import SignalFusionEngine


def generate_history(days: int = 120, seed: int = 7) -> pd.DataFrame:
    # RNG **graine** : le test doit être déterministe. Sans graine, les poids
    # (donc les assertions d'ordre et de positivité) varient d'un run à l'autre.
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2025-01-01", periods=days)
    return pd.DataFrame({
        'technical': rng.normal(0.0012, 0.008, days),   # strong sharpe
        'fundamental': rng.normal(0.0009, 0.009, days),  # moderate
        'sentiment': rng.normal(0.0011, 0.012, days),    # higher vol
        'ml_lstm': rng.normal(0.0015, 0.010, days),      # best mean
        'ml_factor': rng.normal(0.0005, 0.011, days),    # weaker
        'rl': rng.normal(0.0007, 0.010, days),           # neutral
    }, index=idx)


def test_weighting_engine_basic():
    history = generate_history()
    engine = WeightingEngine()
    result = engine.compute_weights(history)
    assert result.observations == len(history)
    assert abs(sum(result.weights.values()) - 1.0) < 1e-9
    # LSTM (meilleur mean) doit peser au moins autant que ml_factor (plus faible).
    assert result.weights['ml_lstm'] >= result.weights['ml_factor']
    # Poids **non négatifs** : par conception, la source la plus faible peut être
    # plancher à 0 (normalisation robuste min-max clippée à [0,1]).
    for w in result.weights.values():
        assert w >= 0


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


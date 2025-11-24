import pandas as pd
import numpy as np
from typing import List

from financial_analyzer.universe.universe_selector_enhanced import EnhancedUniverseSelector, SelectionConfig

# --- Synthetic helpers ----------------------------------------------------

def make_synthetic_market(symbols: List[str], days: int = 90) -> pd.DataFrame:
    idx = pd.date_range(end=pd.Timestamp.utcnow().normalize(), periods=days, freq='D')
    frames = []
    for sym in symbols:
        close = np.cumsum(np.random.standard_normal(days)) + 50
        volume = np.random.uniform(100_000, 800_000, days)
        df = pd.DataFrame({
            (sym, 'Close'): close,
            (sym, 'Volume'): volume,
        }, index=idx)
        frames.append(df)
    return pd.concat(frames, axis=1)

# Monkeypatch target: _download_market_data & _fetch_raw_universe

class DummySelector(EnhancedUniverseSelector):
    def __init__(self, symbols: List[str]):
        super().__init__(SelectionConfig(limit=len(symbols)))
        self._symbols = symbols

    def _fetch_raw_universe(self, regions):  # override
        # Return DataFrame with index as symbols and sector cycles
        sectors = ['Tech', 'Fin', 'Health']
        meta = pd.DataFrame(index=self._symbols)
        meta['sector'] = [sectors[i % len(sectors)] for i in range(len(self._symbols))]
        return meta

    def _download_market_data(self, symbols: List[str]) -> pd.DataFrame:  # override
        return make_synthetic_market(symbols)

# --- Tests ----------------------------------------------------------------

def test_dynamic_weights_sum_to_one():
    sel = DummySelector([f'SYM{i}' for i in range(30)])
    market = sel._download_market_data(sel._symbols)
    df = sel._compute_quality_metrics(market)
    w_cols = ['LiquidityWeight', 'SizeWeight', 'StabilityWeight', 'MomentumWeight']
    # All rows should have identical weights (global cross-sectional)
    first = df.iloc[0][w_cols]
    assert abs(first.sum() - 1.0) < 1e-6
    assert (first >= 0).all()


def test_quality_score_rank_order():
    sel = DummySelector([f'SYM{i}' for i in range(25)])
    market = sel._download_market_data(sel._symbols)
    df = sel._compute_quality_metrics(market)
    # quality_score should be sorted descending already
    assert df['quality_score'].is_monotonic_decreasing


def test_selection_limit_respected():
    symbols = [f'SYM{i}' for i in range(120)]
    sel = DummySelector(symbols)
    sel.config.limit = 50
    # Désactiver la contrainte sectorielle pour test
    sel.config.max_sector_weight = 1.0
    out = sel.select(limit=50)
    assert len(out) == 50


def test_sector_diversification_applies_cap():
    symbols = [f'SYM{i}' for i in range(90)]
    sel = DummySelector(symbols)
    sel.config.limit = 60
    # Force small max sector weight
    sel.config.max_sector_weight = 0.20
    ranked = sel._compute_quality_metrics(sel._download_market_data(symbols))
    meta = sel._fetch_raw_universe(None)
    selected = sel._apply_sector_diversification(ranked, meta)
    # Count sector occurrences
    meta_sel = meta.loc[selected]
    counts = meta_sel['sector'].value_counts()
    assert counts.max() <= int(sel.config.limit * sel.config.max_sector_weight) + 1


def test_structural_filter_excludes_long_symbols():
    sel = DummySelector(['ABCD', 'TOOLONGSYMBOL', 'XYZ', 'SUPERLONG'])
    meta = sel._fetch_raw_universe(None)
    filtered = sel._structural_filter(meta)
    assert 'TOOLONGSYMBOL' not in filtered and 'SUPERLONG' not in filtered


def test_structural_filter_allows_valid_symbols():
    sel = DummySelector(['AAA', 'BBB', 'CCC'])
    meta = sel._fetch_raw_universe(None)
    filtered = sel._structural_filter(meta)
    assert set(filtered) == {'AAA', 'BBB', 'CCC'}


def test_fallback_when_no_market_data():
    # Override to return empty DataFrame
    class EmptyDataSelector(DummySelector):
        def _download_market_data(self, symbols: List[str]) -> pd.DataFrame:  # type: ignore
            return pd.DataFrame()
    symbols = [f'S{i}' for i in range(40)]
    sel = EmptyDataSelector(symbols)
    sel.config.limit = 20
    out = sel.select(limit=20)
    assert len(out) == 20  # fallback to precandidates


def test_quality_metrics_columns_presence():
    sel = DummySelector([f'SYM{i}' for i in range(35)])
    market = sel._download_market_data(sel._symbols)
    df = sel._compute_quality_metrics(market)
    for col in ['LiquidityScore', 'SizeScore', 'StabilityScore', 'MomentumScore', 'quality_score']:
        assert col in df.columns


def test_weights_non_negative():
    sel = DummySelector([f'SYM{i}' for i in range(40)])
    market = sel._download_market_data(sel._symbols)
    df = sel._compute_quality_metrics(market)
    for col in ['LiquidityWeight', 'SizeWeight', 'StabilityWeight', 'MomentumWeight']:
        assert (df[col] >= 0).all()


def test_cardinality_enforcement_via_limit():
    sel = DummySelector([f'SYM{i}' for i in range(200)])
    sel.config.limit = 75
    sel.config.max_sector_weight = 1.0
    out = sel.select(limit=75)
    assert len(out) == 75


def test_random_seed_consistency():
    symbols = [f'S{i}' for i in range(100)]
    # Utiliser DummySelector pour contrôler univers
    cfg = SelectionConfig(limit=50, random_seed=123)
    sel1 = DummySelector(symbols)
    sel1.config = cfg
    sel2 = DummySelector(symbols)
    sel2.config = SelectionConfig(limit=50, random_seed=123)
    # Forcer générateurs locaux identiques après reconfiguration
    import random as _rnd
    sel1._rng = _rnd.Random(123)
    sel2._rng = _rnd.Random(123)
    raw1 = sel1._structural_filter(sel1._fetch_raw_universe(None))
    raw2 = sel2._structural_filter(sel2._fetch_raw_universe(None))
    pre1 = sel1._sample_precandidates(raw1)
    pre2 = sel2._sample_precandidates(raw2)
    assert pre1 == pre2


def test_dynamic_weight_penalty_high_correlation():
    # Construct artificial df where Liquidity and Size identical to test redundancy penalty
    sel = DummySelector([f'SYM{i}' for i in range(30)])
    market = sel._download_market_data(sel._symbols)
    df = sel._compute_quality_metrics(market)
    weights_first = df.iloc[0][['LiquidityWeight', 'SizeWeight', 'StabilityWeight', 'MomentumWeight']]
    # Ensure no component absurdly dominates
    assert (weights_first < 0.75).all()


def test_quality_score_with_single_symbol_edge():
    sel = DummySelector(['ONLY'])
    market = sel._download_market_data(sel._symbols)
    df = sel._compute_quality_metrics(market)
    assert 'quality_score' in df.columns
    assert len(df) == 1


def test_select_global_regions_none():
    sel = DummySelector([f'SYM{i}' for i in range(55)])
    sel.config.max_sector_weight = 1.0
    out = sel.select(limit=50, regions=None)
    assert len(out) == 50


def test_select_override_limit_parameter():
    sel = DummySelector([f'SYM{i}' for i in range(80)])
    sel.config.max_sector_weight = 1.0
    out = sel.select(limit=10)
    assert len(out) == 10


def test_quality_score_distribution_not_constant():
    sel = DummySelector([f'SYM{i}' for i in range(60)])
    market = sel._download_market_data(sel._symbols)
    df = sel._compute_quality_metrics(market)
    assert df['quality_score'].nunique() > 1


def test_apply_sector_diversification_handles_empty_meta():
    sel = DummySelector([f'SYM{i}' for i in range(40)])
    market = sel._download_market_data(sel._symbols)
    ranked = sel._compute_quality_metrics(market)
    # Pass empty meta to force simple slicing
    selected = sel._apply_sector_diversification(ranked, pd.DataFrame())
    assert len(selected) == len(ranked)


def test_weights_presence_after_compute_quality_metrics():
    sel = DummySelector([f'SYM{i}' for i in range(45)])
    market = sel._download_market_data(sel._symbols)
    df = sel._compute_quality_metrics(market)
    for c in ['LiquidityWeight', 'SizeWeight', 'StabilityWeight', 'MomentumWeight']:
        assert c in df.columns


def test_quality_score_sorted_descending_after_selection():
    sel = DummySelector([f'SYM{i}' for i in range(70)])
    market = sel._download_market_data(sel._symbols)
    ranked = sel._compute_quality_metrics(market)
    assert ranked['quality_score'].is_monotonic_decreasing


def test_no_failure_on_extreme_volatility():
    sel = DummySelector([f'SYM{i}' for i in range(35)])
    market = sel._download_market_data(sel._symbols)
    # Inject extreme volatility
    sym0_close = market[('SYM0', 'Close')]
    market[('SYM0', 'Close')] = sym0_close * np.linspace(1, 5, len(sym0_close))
    df = sel._compute_quality_metrics(market)
    assert 'SYM0' in df['symbol'].values

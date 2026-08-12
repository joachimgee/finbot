"""Univers liquide large (Tier 2 bis) — helpers purs (sans réseau)."""
from __future__ import annotations

from financial_analyzer.data.alpaca_universe_liquid import (
    is_probable_fund,
    median_dollar_volume,
    rank_liquid_symbols,
)


def test_fund_names_are_excluded() -> None:
    assert is_probable_fund("SPDR S&P 500 ETF Trust")
    assert is_probable_fund("iShares Core MSCI EAFE")
    assert is_probable_fund("Invesco QQQ Trust")
    assert is_probable_fund("ProShares UltraPro")


def test_common_stock_names_are_kept() -> None:
    assert not is_probable_fund("Apple Inc.")
    assert not is_probable_fund("Microsoft Corporation")
    assert not is_probable_fund("JPMorgan Chase & Co.")
    assert not is_probable_fund("")


def test_median_dollar_volume() -> None:
    bars = [{"c": 10.0, "v": 100}, {"c": 10.0, "v": 300}, {"c": 10.0, "v": 200}]
    assert median_dollar_volume(bars) == 2000.0  # médiane de 1000/3000/2000
    assert median_dollar_volume([]) == 0.0
    # Barres sans volume ignorées.
    assert median_dollar_volume([{"c": 5.0, "v": 0}, {"c": 5.0, "v": 400}]) == 2000.0


def test_rank_keeps_top_n_above_floor() -> None:
    dv = {"A": 9e6, "B": 20e6, "C": 1e6, "D": 50e6, "E": 6e6}
    top = rank_liquid_symbols(dv, n=3, min_dollar=5e6)
    assert top == ["D", "B", "A"]  # C exclu (< plancher), E hors top-3


def test_rank_respects_floor_when_fewer_than_n() -> None:
    dv = {"A": 9e6, "B": 2e6, "C": 1e6}
    assert rank_liquid_symbols(dv, n=10, min_dollar=5e6) == ["A"]

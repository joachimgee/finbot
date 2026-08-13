"""Algorithmes d'exécution — planification d'ordres enfants."""
from __future__ import annotations

import pytest

from financial_analyzer.trading.execution_algos import (
    almgren_chriss_schedule,
    expected_impact_cost,
    pov_schedule,
    twap_schedule,
    vwap_schedule,
)


def test_twap_equal_slices_sum_preserved() -> None:
    s = twap_schedule(100, 4)
    assert sum(s) == 100
    assert s == [25, 25, 25, 25]


def test_twap_handles_remainder() -> None:
    s = twap_schedule(103, 4)
    assert sum(s) == 103
    assert max(s) - min(s) <= 1  # tranches ~égales


def test_vwap_proportional_to_volume() -> None:
    s = vwap_schedule(100, [1, 3])  # 25 % / 75 %
    assert sum(s) == 100
    assert s == [25, 75]


def test_pov_caps_by_participation() -> None:
    # 10 % de participation ; volumes 1000 par intervalle -> 100 max/intervalle.
    s = pov_schedule(250, [1000, 1000, 1000], participation=0.10)
    assert sum(s) == 250
    assert s[0] == 100 and s[1] == 100  # plafonné, puis reste
    assert all(x >= 0 for x in s)


def test_pov_absorbs_unplaceable_remainder_at_end() -> None:
    s = pov_schedule(500, [100, 100], participation=0.10)  # 10/intervalle -> 20 plaçables
    assert sum(s) == 500  # reste ajouté au dernier


def test_almgren_chriss_kappa_zero_is_twap() -> None:
    assert almgren_chriss_schedule(100, 4, kappa=0.0) == twap_schedule(100, 4)


def test_almgren_chriss_is_front_loaded_when_urgent() -> None:
    """Plus κ est grand (urgent), plus la 1re tranche est grosse (front-loaded)."""
    patient = almgren_chriss_schedule(1000, 6, kappa=0.2)
    urgent = almgren_chriss_schedule(1000, 6, kappa=1.5)
    assert sum(patient) == 1000 and sum(urgent) == 1000
    assert urgent[0] > patient[0]
    assert urgent[0] >= urgent[-1]  # décroissant


def test_twap_reduces_impact_vs_single_shot() -> None:
    """Découper en TWAP réduit le coût d'impact temporaire vs tout d'un coup."""
    qty, adv, price = 10000, 100000.0, 50.0
    one_shot = expected_impact_cost([qty], adv, price)
    sliced = expected_impact_cost(twap_schedule(qty, 10), adv, price)
    assert sliced < one_shot


def test_schedules_reject_bad_params() -> None:
    with pytest.raises(ValueError):
        twap_schedule(100, 0)
    with pytest.raises(ValueError):
        pov_schedule(100, [1000], participation=1.5)
    with pytest.raises(ValueError):
        almgren_chriss_schedule(100, 4, kappa=-1.0)
    with pytest.raises(ValueError):
        vwap_schedule(100, [])


def test_impact_cost_zero_for_empty_or_no_adv() -> None:
    assert expected_impact_cost([], 100.0, 10.0) == 0.0
    assert expected_impact_cost([100], 0.0, 10.0) == 0.0

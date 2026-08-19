"""Parité backtest ↔ live du signal d'illiquidité d'Amihud.

Le vrai garde-fou n'est pas « les deux chemins appellent la même fonction » (une
refactorisation peut défaire ça sans bruit) : c'est **« les deux chemins produisent le
même book »**, vérifié sur des données. C'est l'objet de ce fichier.

Contexte : la formule d'Amihud était écrite 5 fois dans le dépôt. Les copies
concordaient, mais les *paramètres* et le *prétraitement* autour d'elles, non — d'où
deux bugs en une journée (bande de non-transaction gelante, horizon d'IC du moniteur).
Cf. ``financial_analyzer/backtest/illiquidity.py``.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.backtest.illiquidity import (
    AMIHUD_SCALE,
    AmihudSpec,
    DEFAULT_SPEC,
    amihud_illiquidity,
    amihud_weights,
    prepare_panels,
)


def _panel(n_dates: int = 220, n_assets: int = 40, seed: int = 7):
    """Panel (close, volume) synthétique avec une vraie dispersion de liquidité."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n_dates, freq="B")
    cols = [f"S{i:02d}" for i in range(n_assets)]
    close = pd.DataFrame(
        100 * np.exp(np.cumsum(rng.normal(0.0002, 0.02, (n_dates, n_assets)), axis=0)),
        index=idx, columns=cols,
    )
    # Volumes très hétérogènes -> les rangs d'illiquidité sont discriminants.
    scale = np.logspace(4, 7, n_assets)
    volume = pd.DataFrame(
        rng.lognormal(0, 0.3, (n_dates, n_assets)) * scale, index=idx, columns=cols,
    )
    return close, volume


# --- La primitive elle-même -------------------------------------------------

def test_illiquidity_is_high_for_thin_volume() -> None:
    """Sens économique : à mouvement égal, moins de volume = plus illiquide."""
    close, volume = _panel()
    illiq = amihud_illiquidity(close, volume).iloc[-1].dropna()
    # Les volumes croissent avec l'indice de colonne -> l'illiquidité doit décroître.
    rank_corr = illiq.reset_index(drop=True).corr(
        pd.Series(range(len(illiq)), dtype=float), method="spearman")
    assert rank_corr < -0.8


def test_scale_is_rank_neutral() -> None:
    """L'échelle est cosmétique : elle ne doit changer aucun poids."""
    close, volume = _panel()
    illiq = amihud_illiquidity(close, volume)
    w_scaled = amihud_weights(illiq.iloc[-1])
    w_raw = amihud_weights(illiq.iloc[-1] / AMIHUD_SCALE)
    pd.testing.assert_series_equal(w_scaled, w_raw)


def test_zero_volume_yields_nan_not_a_fabricated_rank() -> None:
    """Un volume nul ne doit pas produire un rang inventé (0 = 'très liquide')."""
    close, volume = _panel()
    volume.iloc[:, 0] = 0.0
    illiq = amihud_illiquidity(close, volume)
    assert illiq.iloc[-1].isna().iloc[0]


def test_warmup_is_nan() -> None:
    close, volume = _panel()
    illiq = amihud_illiquidity(close, volume, window=60)
    assert illiq.iloc[58].isna().all()
    assert illiq.iloc[-1].notna().any()


def test_abstains_below_min_names() -> None:
    """Trop peu de titres -> book vide (abstention), pas un tri hasardeux."""
    close, volume = _panel(n_assets=8)
    illiq = amihud_illiquidity(close, volume)
    assert amihud_weights(illiq.iloc[-1], min_names=20).empty


def test_book_is_dollar_neutral_and_normalised() -> None:
    close, volume = _panel()
    w = amihud_weights(amihud_illiquidity(close, volume).iloc[-1])
    assert w.sum() == pytest.approx(0.0, abs=1e-9)          # dollar-neutre
    assert w.abs().sum() == pytest.approx(1.0, abs=1e-9)    # normalisé
    assert (w > 0).sum() == (w < 0).sum()                   # jambes symétriques


def test_empty_inputs_do_not_raise() -> None:
    assert amihud_illiquidity(pd.DataFrame(), pd.DataFrame()).empty
    assert prepare_panels(pd.DataFrame(), pd.DataFrame())[0].empty
    assert amihud_weights(pd.Series(dtype=float)).empty


def test_prepare_panels_drops_sparse_names_and_aligns() -> None:
    close, volume = _panel(n_dates=100, n_assets=10)
    close.iloc[:80, 0] = np.nan          # historique trop lacunaire (ffill n'aide pas)
    c, v = prepare_panels(close, volume, min_history_frac=0.6)
    assert "S00" not in c.columns
    assert list(c.columns) == list(v.columns) and c.index.equals(v.index)


# --- LA parité : même book des deux côtés -----------------------------------

def _live_book(close: pd.DataFrame, volume: pd.DataFrame) -> dict:
    """Book produit par le chemin LIVE (``AmihudConstruction``)."""
    from financial_analyzer.trading.framework import AmihudConstruction

    pipeline = MagicMock()
    pipeline.target_vol = None
    pipeline.no_trade_band = 0.0
    pipeline._construct_weights.return_value = {"__FALLBACK__": 1.0}
    layer = AmihudConstruction(pipeline, consolidated_volume=False)
    data = {"prices": {
        s: pd.DataFrame({"close": close[s], "volume": volume[s]}) for s in close.columns
    }}
    return layer.construct({}, data)


def _backtest_book(close: pd.DataFrame, volume: pd.DataFrame) -> dict:
    """Book produit par le chemin BACKTEST (appels directs au module canonique)."""
    c, v = prepare_panels(close, volume)
    w = amihud_weights(amihud_illiquidity(c, v, window=DEFAULT_SPEC.window).iloc[-1])
    return {s: float(x) for s, x in w.items() if abs(x) > 1e-9}


def test_live_and_backtest_produce_the_same_book() -> None:
    """Le test qui compte : mêmes données en entrée → book identique des deux côtés."""
    close, volume = _panel()
    live, back = _live_book(close, volume), _backtest_book(close, volume)
    assert live and "__FALLBACK__" not in live, "le chemin live est tombé en repli"
    assert set(live) == set(back)
    for s in back:
        assert live[s] == pytest.approx(back[s], abs=1e-12)


def test_parity_holds_on_a_messy_panel() -> None:
    """Parité maintenue avec trous, titres lacunaires et volumes nuls."""
    close, volume = _panel(seed=11)
    close.iloc[30:45, 3] = np.nan
    close.iloc[:150, 5] = np.nan      # sera écarté par min_history_frac
    volume.iloc[:, 7] = 0.0           # illiquidité non définie
    live, back = _live_book(close, volume), _backtest_book(close, volume)
    assert live and "__FALLBACK__" not in live
    assert set(live) == set(back)
    for s in back:
        assert live[s] == pytest.approx(back[s], abs=1e-12)


def test_live_defaults_come_from_the_shared_spec() -> None:
    """Le chemin live ne redéfinit pas ses paramètres : il lit la spécification."""
    from financial_analyzer.trading.framework import AmihudConstruction

    layer = AmihudConstruction(MagicMock())
    assert layer.window == DEFAULT_SPEC.window
    assert layer.quantile == DEFAULT_SPEC.quantile
    assert layer.min_names == DEFAULT_SPEC.min_names
    assert layer.min_history_frac == DEFAULT_SPEC.min_history_frac


def test_spec_is_frozen() -> None:
    """La spécification validée ne s'altère pas en place."""
    with pytest.raises(AttributeError):
        DEFAULT_SPEC.window = 999  # type: ignore[misc]


def test_spec_override_flows_through_to_the_live_book() -> None:
    """Surcharger la spécification change bien le book live (le câblage est réel)."""
    from financial_analyzer.trading.framework import AmihudConstruction

    close, volume = _panel()
    pipeline = MagicMock()
    pipeline.target_vol = None
    pipeline.no_trade_band = 0.0
    data = {"prices": {
        s: pd.DataFrame({"close": close[s], "volume": volume[s]}) for s in close.columns
    }}
    wide = AmihudConstruction(pipeline, consolidated_volume=False,
                              spec=AmihudSpec(quantile=0.4)).construct({}, data)
    narrow = AmihudConstruction(pipeline, consolidated_volume=False,
                                spec=AmihudSpec(quantile=0.1)).construct({}, data)
    assert len(wide) > len(narrow)


def test_no_trade_band_is_zero_in_the_validated_spec() -> None:
    """Régression du bug de production : la bande est désactivée par défaut."""
    assert DEFAULT_SPEC.no_trade_band == 0.0


def test_no_duplicate_amihud_formula_in_the_repo() -> None:
    """Aucune ré-implémentation de la formule hors du module canonique.

    Ce test est le garde-fou qui empêche la duplication de revenir par la porte de
    derrière : la formule ``|r| / $volume`` ne doit apparaître que dans
    ``backtest/illiquidity.py``. Sans lui, le prochain script de recherche la
    recopiera — c'est exactement ainsi qu'elle s'était retrouvée écrite 5 fois.
    """
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[2]
    canonical = root / "src/financial_analyzer/backtest/illiquidity.py"
    # La signature de la formule : une valeur absolue de rendement divisée par un
    # volume en dollars, quelle que soit la façon de nommer les variables.
    pattern = re.compile(r"\.abs\(\)\s*/\s*\w*(dollar_vol|dv|dollar_volume)\w*")

    offenders = []
    for path in list((root / "src").rglob("*.py")) + list((root / "scripts").rglob("*.py")):
        if path == canonical or "__pycache__" in path.parts:
            continue
        if pattern.search(path.read_text(encoding="utf-8", errors="ignore")):
            offenders.append(str(path.relative_to(root)))

    assert not offenders, (
        "Formule d'Amihud ré-implémentée hors du module canonique : "
        f"{offenders}. Importer amihud_illiquidity depuis backtest/illiquidity.py."
    )

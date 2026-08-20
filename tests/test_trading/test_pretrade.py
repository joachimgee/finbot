"""Contrôles pré-trade : emprunt (C) et participation au volume (D).

Comme pour la réconciliation de positions, la première chose à vérifier n'est pas que
le contrôle laisse passer, c'est qu'il **refuse quand il doit**. Un garde-fou incapable
de bloquer est pire que pas de garde-fou : il donne l'illusion d'une protection.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from financial_analyzer.trading.pretrade import PretradePolicy, check_tradability


def _asset(shortable=True, easy=True, tradable=True):
    return {"symbol": "AAA", "tradable": tradable, "shortable": shortable,
            "easy_to_borrow": easy, "fractionable": True, "status": "active"}


def _policy(**kw):
    base = {"asset_provider": lambda s: _asset(), "adv_provider": lambda s: 1_000_000.0}
    base.update(kw)
    return PretradePolicy(**base)


# --- (C) Emprunt ------------------------------------------------------------

def test_short_on_non_shortable_is_rejected() -> None:
    pol = _policy(asset_provider=lambda s: _asset(shortable=False))
    d = pol.check("AAA", 10, "sell", price=100.0)
    assert d.action == "reject" and not d.allowed and "shortable" in d.reason


def test_short_on_hard_to_borrow_is_rejected() -> None:
    """`shortable` mais pas `easy_to_borrow` : empruntable cher, et **rappelable**.

    Sur un book tenu 21 jours, un rappel force un rachat au pire moment. Exiger
    `easy_to_borrow` est la position prudente, et c'est configurable.
    """
    pol = _policy(asset_provider=lambda s: _asset(easy=False))
    assert pol.check("AAA", 10, "sell", price=100.0).action == "reject"


def test_hard_to_borrow_can_be_tolerated_explicitly() -> None:
    pol = _policy(asset_provider=lambda s: _asset(easy=False), require_easy_to_borrow=False)
    assert pol.check("AAA", 10, "sell", price=100.0).action == "allow"


def test_buy_is_not_blocked_by_borrow_rules() -> None:
    """Un achat n'emprunte rien : les règles de short ne doivent pas s'y appliquer."""
    pol = _policy(asset_provider=lambda s: _asset(shortable=False, easy=False))
    assert pol.check("AAA", 10, "buy", price=100.0).action == "allow"


def test_sell_closing_a_long_is_not_treated_as_a_short() -> None:
    """Vendre pour solder un long ne doit pas être refusé faute d'emprunt."""
    pol = _policy(asset_provider=lambda s: _asset(shortable=False))
    d = check_tradability("AAA", 10, "sell", 100.0, policy=pol, opening_short=False)
    assert d.action == "allow"


def test_non_tradable_asset_is_rejected_both_ways() -> None:
    pol = _policy(asset_provider=lambda s: _asset(tradable=False))
    assert pol.check("AAA", 10, "buy", price=100.0).action == "reject"
    assert pol.check("AAA", 10, "sell", price=100.0).action == "reject"


# --- (D) Participation ------------------------------------------------------

def test_small_order_passes() -> None:
    """Ordre de 1 000 $ sur 1 M$/jour = 0,1 % — très en deçà de la limite."""
    assert _policy().check("AAA", 10, "buy", price=100.0).action == "allow"


def test_oversized_order_is_resized_not_rejected() -> None:
    """Au-delà de la limite on RÉDUIT : le book se complètera au rééquilibrage suivant.

    Refuser en bloc laisserait une jambe béante ; réduire dégrade proprement.
    """
    pol = _policy(max_participation=0.01)          # 1 % de 1 M$ = 10 000 $
    d = pol.check("AAA", 500, "buy", price=100.0)  # 50 000 $ demandés
    assert d.action == "resize" and d.qty == 100   # 10 000 $ / 100 $
    assert d.allowed


def test_order_too_large_to_resize_to_one_share_is_rejected() -> None:
    """Sous une action entière, réduire donnerait 0 : un faux « exécuté ». On refuse."""
    pol = _policy(max_participation=0.01, adv_provider=lambda s: 1_000.0)  # cap = 10 $
    d = pol.check("AAA", 5, "buy", price=100.0)
    assert d.action == "reject" and d.qty == 0.0


def test_participation_check_skipped_without_price() -> None:
    """Sans prix, on ne fabrique pas un notionnel — on s'abstient de contrôler."""
    assert _policy().check("AAA", 10_000, "buy", price=None).action == "allow"


def test_participation_check_skipped_without_volume() -> None:
    assert _policy(adv_provider=lambda s: None).check("AAA", 10_000, "buy",
                                                      price=100.0).action == "allow"


# --- Dégradation et cache ---------------------------------------------------

def test_no_policy_means_unchanged_behaviour() -> None:
    assert check_tradability("AAA", 10, "sell", 100.0, policy=None).action == "allow"


def test_provider_failure_is_fail_open_by_default() -> None:
    """Une API muette ne doit pas geler la stratégie ; le broker refusera lui-même."""
    def boom(_s):
        raise RuntimeError("API HS")

    assert _policy(asset_provider=boom).check("AAA", 10, "sell", price=100.0).action == "allow"


def test_fail_closed_is_available_for_shorts() -> None:
    pol = _policy(asset_provider=lambda s: None, allow_on_unknown=False)
    assert pol.check("AAA", 10, "sell", price=100.0).action == "reject"


def test_asset_metadata_is_cached_per_symbol() -> None:
    calls = []

    def provider(symbol):
        calls.append(symbol)
        return _asset()

    pol = _policy(asset_provider=provider)
    for _ in range(5):
        pol.check("AAA", 1, "sell", price=100.0)
    assert calls == ["AAA"], "un seul appel réseau par symbole et par run"


# --- Intégration au chokepoint ---------------------------------------------

def _gateway(policy):
    from financial_analyzer.trading.order_gateway import OrderGateway

    broker = MagicMock()
    broker.mode = "paper"
    broker.submit_order.return_value = {"status": "filled", "order_id": "x"}
    risk = MagicMock()
    risk.validate_order.return_value = None
    return OrderGateway(broker, risk, pretrade=policy), broker


def test_gateway_rejects_unborrowable_short() -> None:
    """Le contrôle vit dans le chokepoint : tout chemin d'ordre en hérite."""
    from financial_analyzer.trading.risk_guard import InvalidOrderError

    gw, broker = _gateway(_policy(asset_provider=lambda s: _asset(shortable=False)))
    with pytest.raises(InvalidOrderError, match="Pré-trade"):
        gw.submit("AAA", 10, "sell", price=100.0)
    assert not broker.submit_order.called, "aucun ordre ne doit atteindre le broker"


def test_gateway_resizes_oversized_order_before_submitting() -> None:
    gw, broker = _gateway(_policy(max_participation=0.01))
    gw.submit("AAA", 500, "buy", price=100.0)
    assert broker.submit_order.called
    assert broker.submit_order.call_args.kwargs["qty"] == 100


def test_gateway_without_policy_is_unchanged() -> None:
    gw, broker = _gateway(None)
    gw.submit("AAA", 500, "sell", price=100.0)
    assert broker.submit_order.call_args.kwargs["qty"] == 500

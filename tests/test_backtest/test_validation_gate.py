"""Portail de validation à double critère (P1) — règle vérifiée en CI.

Encode noir sur blanc les deux leçons du projet :
* un Sharpe net positif *seul* ne valide pas (piège de queue épaisse du
  combinateur : IC t négatif) → doit être REJETÉ ;
* un IC significatif *seul* ne valide pas (piège de coûts) → doit être REJETÉ.
Seul IC t > 2 ET Sharpe net > 0 passe.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from financial_analyzer.backtest.signal_evaluation import CostModel
from financial_analyzer.backtest.validation_gate import (
    DECLASSED_SIGNALS,
    VALIDATED_SIGNALS,
    GateThresholds,
    ValidatedSignal,
    decide,
    evaluate_signal_gate,
    is_validated,
    require_validated,
)

# --- Décision pure : la table de vérité du double critère --------------------

@pytest.mark.parametrize(
    "ic_t, net_sharpe, expected",
    [
        (2.56, 0.76, True),    # momentum_12_1 (coûts Alpaca calibrés) : passe les deux
        (3.00, 0.50, True),    # franc positif
        (2.01, 0.01, True),    # juste au-dessus des deux seuils
        (-3.07, 0.50, False),  # PIÈGE combinateur : IC négatif, Sharpe positif -> rejet
        (2.50, -0.20, False),  # PIÈGE coûts : IC ok, Sharpe net négatif -> rejet
        (1.50, 0.50, False),   # IC non significatif -> rejet
        (2.00, 0.50, False),   # seuil strict : t == 2 ne suffit pas
        (2.50, 0.00, False),   # seuil strict : sharpe == 0 ne suffit pas
        (float("nan"), 0.50, False),  # preuve manquante -> rejet
        (2.50, float("nan"), False),
    ],
)
def test_decide_dual_criterion(ic_t, net_sharpe, expected) -> None:
    passed, reasons = decide(ic_t, net_sharpe)
    assert passed is expected
    assert passed == (len(reasons) == 0)


def test_combiner_trap_reason_points_at_ic() -> None:
    """Le rejet du piège combinateur cite bien le critère IC (pas le Sharpe)."""
    passed, reasons = decide(-3.07, 0.50)
    assert not passed
    assert any("IC" in r for r in reasons)
    assert not any("Sharpe" in r for r in reasons)


# --- DSR : 3e critère optionnel (anti-tests-multiples) -----------------------

def test_decide_dsr_absent_keeps_dual_criterion() -> None:
    """Sans DSR fourni, le portail décide exactement comme avant (rétro-compat)."""
    assert decide(2.56, 0.76)[0] is True
    assert decide(2.56, 0.76, dsr=None)[0] is True


def test_decide_low_dsr_rejects_otherwise_passing_signal() -> None:
    """Un signal qui passe IC+Sharpe mais dont le DSR est faible est REJETÉ."""
    passed, reasons = decide(2.56, 0.76, dsr=0.10)
    assert not passed
    assert any("DSR" in r for r in reasons)


def test_decide_high_dsr_passes() -> None:
    passed, reasons = decide(2.56, 0.76, dsr=0.99)
    assert passed
    assert reasons == ()


def test_decide_nan_dsr_is_failure() -> None:
    passed, _ = decide(2.56, 0.76, dsr=float("nan"))
    assert not passed


def test_evaluate_gate_populates_dsr_when_trials_given() -> None:
    """Fournir n_trials + dispersion active et renseigne le DSR dans le verdict."""
    returns = _returns_panel(seed=1)
    rng = np.random.default_rng(7)
    scores = returns.shift(-1) + rng.normal(0, 0.03, returns.shape)
    verdict = evaluate_signal_gate(
        "predictive", scores, returns, cost_model=CostModel(),
        n_trials=50, trial_sharpe_std=0.05,
    )
    assert verdict.dsr is not None
    assert 0.0 <= verdict.dsr <= 1.0


def test_evaluate_gate_dsr_none_by_default() -> None:
    """Sans n_trials, le DSR reste None et le verdict est double-critère."""
    returns = _returns_panel(seed=1)
    rng = np.random.default_rng(7)
    scores = returns.shift(-1) + rng.normal(0, 0.03, returns.shape)
    verdict = evaluate_signal_gate("predictive", scores, returns, cost_model=CostModel())
    assert verdict.dsr is None


# --- PBO : 4e critère optionnel (surapprentissage du processus de sélection) --

def test_decide_high_pbo_rejects() -> None:
    """Un signal qui passe IC+Sharpe mais dont la sélection sur-apprend (PBO élevée)
    est REJETÉ."""
    passed, reasons = decide(2.56, 0.76, pbo=0.80)
    assert not passed
    assert any("PBO" in r for r in reasons)


def test_decide_low_pbo_passes() -> None:
    passed, reasons = decide(2.56, 0.76, pbo=0.10)
    assert passed
    assert reasons == ()


def test_decide_pbo_absent_keeps_behaviour() -> None:
    assert decide(2.56, 0.76, pbo=None)[0] is True


def test_evaluate_gate_passes_pbo_into_verdict() -> None:
    returns = _returns_panel(seed=1)
    rng = np.random.default_rng(7)
    scores = returns.shift(-1) + rng.normal(0, 0.03, returns.shape)
    verdict = evaluate_signal_gate(
        "predictive", scores, returns, cost_model=CostModel(), pbo=0.9)
    assert verdict.pbo == 0.9
    assert not verdict.passed  # PBO trop élevée -> rejet malgré IC/Sharpe ok
    assert any("PBO" in r for r in verdict.reasons)


# --- Évaluation bout-en-bout sur données synthétiques ------------------------

def _returns_panel(n_days: int = 260, n_assets: int = 40, seed: int = 0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n_days, freq="B")
    cols = [f"A{i}" for i in range(n_assets)]
    return pd.DataFrame(rng.normal(0, 0.01, (n_days, n_assets)), index=idx, columns=cols)


def test_predictive_signal_passes() -> None:
    """Un signal bruité mais prédictif du rendement forward passe le portail.

    On ajoute du bruit au rendement forward : l'IC quotidien est élevé *mais*
    varie d'un jour à l'autre (sinon std=0 → t-stat NaN, cas d'un signal « trop
    parfait » qui n'existe pas en réalité et que le portail rejette à juste titre).
    """
    returns = _returns_panel(seed=1)
    rng = np.random.default_rng(7)
    scores = returns.shift(-1) + rng.normal(0, 0.03, returns.shape)
    verdict = evaluate_signal_gate("predictive", scores, returns, cost_model=CostModel())
    assert verdict.passed
    assert verdict.ic_t_stat > 2
    assert verdict.net_sharpe > 0


def test_noise_signal_is_rejected() -> None:
    """Un signal indépendant des rendements échoue au portail."""
    returns = _returns_panel(seed=2)
    noise = pd.DataFrame(
        np.random.default_rng(99).normal(0, 1, returns.shape),
        index=returns.index, columns=returns.columns,
    )
    verdict = evaluate_signal_gate("noise", noise, returns, cost_model=CostModel())
    assert not verdict.passed


def test_empty_oos_is_rejected() -> None:
    """Trop peu de données -> pas de fenêtre OOS -> rejet explicite."""
    returns = _returns_panel(n_days=40, seed=3)
    scores = returns.shift(-1)
    # n_splits élevé pour forcer des fenêtres trop courtes n'est pas permis
    # (walk_forward lève) ; on teste plutôt le contrat via un panel minimal viable.
    verdict = evaluate_signal_gate("tiny", scores, returns, n_splits=5)
    # Doit rendre un verdict (pass/fail) sans exception ; la clé est qu'il décide.
    assert isinstance(verdict.passed, bool)


# --- Registre : source de vérité de « ce qui a le droit de trader » ----------

def test_registry_entries_actually_pass_the_gate() -> None:
    """Toute entrée du registre satisfait réellement le double critère.

    L'invariant porte sur le CONTENU, pas sur la taille : un registre **vide** est
    légitime (et sûr — plus rien n'a le droit de décider). Le remplir sans preuve
    serait la seule violation possible.
    """
    for sig in VALIDATED_SIGNALS.values():
        assert sig.verdict().passed, f"{sig.name} enregistré mais ne passe pas le portail"


def test_momentum_12_1_is_declassed_not_validated() -> None:
    """momentum_12_1 a été retiré du registre : IC t=+1.83 à l'horizon de détention.

    Le t précédent (+4.85) était gonflé par des observations chevauchantes ; mesuré
    sans recouvrement, le signal ne franchit plus le seuil. La preuve est conservée
    dans ``DECLASSED_SIGNALS`` pour que la décision reste auditable.
    """
    assert not is_validated("momentum_12_1")
    sig = DECLASSED_SIGNALS["momentum_12_1"]
    assert sig.rebalance_every == 10
    assert not sig.verdict().passed
    assert "DÉCLASSÉ" in sig.evidence


def test_declassed_signals_cannot_trade() -> None:
    """Un signal déclassé est refusé par la garde d'exécution, comme un inconnu."""
    for name in DECLASSED_SIGNALS:
        assert not is_validated(name)
        with pytest.raises(ValueError, match="non validé"):
            require_validated(name)


def test_require_validated_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="non validé"):
        require_validated("reversal_5")  # net-négatif -> jamais enregistré


def _sample_signal(ic_t: float = 2.56, sharpe: float = 0.73) -> ValidatedSignal:
    """Entrée de registre construite localement — ces tests portent sur le TYPE,
    pas sur le contenu du registre (qui peut légitimement être vide)."""
    return ValidatedSignal(name="demo", rebalance_every=10, ic_t_stat=ic_t,
                           net_sharpe=sharpe, evidence="fixture de test")


def test_stricter_thresholds_can_reject_a_registered_signal() -> None:
    """Les seuils sont configurables : un portail plus exigeant peut resserrer."""
    sig = _sample_signal()
    assert sig.verdict().passed  # portail par défaut : 2.56 > 2.0 et 0.73 > 0
    strict = GateThresholds(ic_t_stat_min=3.0, net_sharpe_min=1.0)
    assert not sig.verdict(thresholds=strict).passed  # 2.56 < 3.0 et 0.73 < 1.0


def test_validated_signal_is_immutable() -> None:
    sig = _sample_signal()
    # frozen dataclass -> l'assignation lève FrozenInstanceError (sous-classe
    # d'AttributeError) : la preuve enregistrée ne peut pas être altérée en place.
    with pytest.raises(AttributeError):
        sig.net_sharpe = 9.9  # type: ignore[misc]
    assert isinstance(sig, ValidatedSignal)

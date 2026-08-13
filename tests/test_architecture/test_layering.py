"""Frontière d'architecture : le chemin *live* n'importe pas la couche *recherche*.

FinBot porte ~11 k LOC de recherche (`ml/`, `rl/`, `deep_learning/`, `derivatives/`)
qui **ne doivent pas** entrer dans le chemin de décision qui trade. La discipline P0
a fait *s'abstenir* les sources non validées ; ce test **verrouille** la frontière :
les modules du chemin live ne doivent contenir *aucun* import direct de la couche
recherche. Il empêche la ré-introduction silencieuse d'un couplage (régression).

Portée : import **direct** dans les fichiers du cœur de décision (statique, robuste
et maintenable — on ne suit pas la fermeture transitive, qui serait fragile).
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[2] / "src" / "financial_analyzer"

# Cœur de décision « live » : de la donnée aux ordres.
_LIVE_GLOBS = (
    "trading/*.py",
    "integration/signal_fusion_engine.py",
    "integration/signal_portfolio_bridge.py",
    "backtest/validation_gate.py",
    "backtest/signal_evaluation.py",
    "backtest/classic_factors.py",
    "backtest/vol_management.py",
    "backtest/robustness.py",
    "backtest/rebalance_gate.py",
    "backtest/cost_calibration.py",
    "portfolio/black_litterman.py",
    "portfolio/constraints.py",
)

# Couche recherche interdite dans le chemin live (\b évite ml_features, etc.).
_FORBIDDEN = re.compile(r"financial_analyzer\.(ml|rl|deep_learning|derivatives)\b")


def _live_files() -> list[Path]:
    files: list[Path] = []
    for g in _LIVE_GLOBS:
        files.extend(sorted(_SRC.glob(g)))
    return files


def test_live_path_files_exist() -> None:
    """Garde-fou : les globs pointent bien sur des fichiers (sinon test vide)."""
    assert len(_live_files()) >= 10


def test_live_path_does_not_import_research_layer() -> None:
    """Aucun fichier du cœur live n'importe ml/rl/deep_learning/derivatives."""
    violations: list[str] = []
    for f in _live_files():
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if ("import" in stripped) and _FORBIDDEN.search(stripped):
                violations.append(f"{f.relative_to(_SRC)}:{i}: {stripped}")
    assert not violations, (
        "Couplage recherche→live détecté (la couche ml/rl/deep_learning/derivatives "
        "ne doit pas entrer dans le chemin de décision) :\n" + "\n".join(violations)
    )


@pytest.mark.parametrize("pkg", ["ml", "rl", "deep_learning", "derivatives"])
def test_forbidden_regex_matches_research_but_not_lookalikes(pkg: str) -> None:
    """Le motif attrape la vraie couche recherche, pas les modules au nom proche."""
    assert _FORBIDDEN.search(f"from financial_analyzer.{pkg}.foo import Bar")
    # Faux positifs à éviter : ml_features, ml_features_advanced.
    assert not _FORBIDDEN.search("from financial_analyzer.ml_features.feature_engineer import X")

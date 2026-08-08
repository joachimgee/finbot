"""Manifeste de run pour la reproductibilité (observabilité P5).

Un run de trading doit être traçable : quel code (commit git), quelles versions
de dépendances clés, quel mode et quelle configuration. :func:`build_run_manifest`
capture cet état ; couplé au journal (:meth:`TradingJournal.record_manifest`), il
laisse une empreinte horodatée permettant de reconstituer les conditions exactes
d'un run — la brique « runs reproductibles / artefacts horodatés » du plan.

Toutes les captures sont *best-effort* : un environnement sans git ou sans un
paquet donné produit ``None`` plutôt qu'une erreur — un manifeste n'est jamais
une raison d'interrompre un run.
"""
from __future__ import annotations

import platform
import subprocess
from datetime import datetime, timezone
from importlib import metadata
from typing import Any

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

__all__ = ["build_run_manifest", "git_commit_sha", "package_versions"]

#: Paquets dont la version conditionne la reproductibilité numérique.
_TRACKED_PACKAGES = ("pandas", "numpy", "scikit-learn", "alpaca-trade-api")


def git_commit_sha() -> str | None:
    """SHA du commit git courant (``None`` si indisponible)."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        sha = out.stdout.strip()
        return sha or None
    except Exception:  # noqa: BLE001 - capture best-effort, ne doit jamais lever
        return None


def package_versions(packages: tuple[str, ...] = _TRACKED_PACKAGES) -> dict[str, str | None]:
    """Versions installées des paquets suivis (``None`` si absent)."""
    versions: dict[str, str | None] = {}
    for pkg in packages:
        try:
            versions[pkg] = metadata.version(pkg)
        except Exception:  # noqa: BLE001 - paquet absent -> None
            versions[pkg] = None
    return versions


def build_run_manifest(**extra: Any) -> dict[str, Any]:
    """Construit le manifeste d'un run.

    Args:
        **extra: champs spécifiques au run (mode, taille d'univers, paramètres…).

    Returns:
        Dict horodaté : ``kind='manifest'``, ``ts``, ``git_sha``,
        ``python_version``, ``platform``, ``packages``, plus ``extra``.
    """
    return {
        "kind": "manifest",
        "ts": datetime.now(timezone.utc).isoformat(),
        "git_sha": git_commit_sha(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "packages": package_versions(),
        **extra,
    }

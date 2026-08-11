"""Cadence de rééquilibrage persistante (P1) — réaliser l'edge net de coûts.

Le daemon canonique tourne quotidiennement, mais le facteur 12-1 validé est
meilleur **espacé** : le sweep OOS (``scripts/run_rebalance_sweep_alpaca.py``)
retient ``rebalance_every=10`` — rééquilibrer chaque jour paie un turnover que
l'edge ne rembourse pas (Sharpe net +0.61 en quotidien vs +0.73 à 10 jours).

Cette garde matérialise cette cadence en production : elle **persiste la date du
dernier rééquilibrage** (fichier d'état JSON, survit aux redémarrages de
conteneur) et n'autorise un nouveau rééquilibrage du book piloté par le momentum
que lorsque ``rebalance_every`` **jours ouvrés** se sont écoulés. Entre deux, le
book est tenu (aucun turnover, aucun coût).

La liquidation pour raison de risque n'est **pas** du ressort de cette garde :
elle ne gate que le déploiement/rééquilibrage piloté par le signal.

Le nombre de périodes vient du registre du portail de validation
(:data:`~financial_analyzer.backtest.validation_gate.VALIDATED_SIGNALS`), source
unique de vérité — pas d'un « 10 » magique.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import numpy as np

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

__all__ = ["RebalanceGate"]


def _as_date(value: date | datetime) -> date:
    return value.date() if isinstance(value, datetime) else value


@dataclass
class RebalanceGate:
    """Garde de cadence : ne laisse rééquilibrer que tous les N jours ouvrés.

    Attributes:
        state_path: fichier JSON d'état (persistant). Créé au premier ``record``.
        rebalance_every: nombre de jours ouvrés minimal entre deux rééquilibrages
            (≥ 1). 1 = pas de gate (rééquilibrage à chaque appel).
    """

    state_path: Path
    rebalance_every: int

    def __post_init__(self) -> None:
        self.state_path = Path(self.state_path)
        self.rebalance_every = max(1, int(self.rebalance_every))

    @classmethod
    def from_validated_signal(
        cls,
        state_path: Path | str,
        name: str = "momentum_12_1",
        default_every: int = 1,
    ) -> RebalanceGate:
        """Construit la garde en lisant ``rebalance_every`` depuis le registre validé.

        Si le signal n'est pas au registre (ou le module indisponible), on retombe
        sur ``default_every`` (pas de gate) plutôt que d'échouer — la cadence est
        une optimisation de coûts, jamais un point de rupture du trading.
        """
        every = default_every
        try:
            from financial_analyzer.backtest.validation_gate import VALIDATED_SIGNALS

            sig = VALIDATED_SIGNALS.get(name)
            if sig is not None:
                every = sig.rebalance_every
        except Exception as e:  # noqa: BLE001  # pragma: no cover - dégradation gracieuse
            logger.warning("Registre de validation indisponible (%s); cadence=%d", e, every)
        return cls(state_path=Path(state_path), rebalance_every=every)

    def _load_last(self) -> date | None:
        """Date du dernier rééquilibrage enregistré, ou None si jamais/illisible."""
        if not self.state_path.exists():
            return None
        try:
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            raw = data.get("last_rebalance")
            return date.fromisoformat(raw) if raw else None
        except Exception as e:  # noqa: BLE001 - un état corrompu ne doit pas bloquer
            logger.warning("État de cadence illisible (%s); rééquilibrage autorisé", e)
            return None

    def sessions_since(self, now: date | datetime | None = None) -> int | None:
        """Jours ouvrés écoulés depuis le dernier rééquilibrage (None si jamais)."""
        last = self._load_last()
        if last is None:
            return None
        now_d = _as_date(now) if now is not None else date.today()  # noqa: DTZ011
        # busday_count compte les jours ouvrés dans [last, now) ; borne à 0 en cas
        # de recul d'horloge.
        return max(0, int(np.busday_count(last.isoformat(), now_d.isoformat())))

    def is_due(self, now: date | datetime | None = None) -> bool:
        """Vrai s'il faut rééquilibrer : jamais rééquilibré, ou N jours ouvrés passés."""
        elapsed = self.sessions_since(now)
        if elapsed is None:
            return True  # première fois -> rééquilibrer
        return elapsed >= self.rebalance_every

    def sessions_until_due(self, now: date | datetime | None = None) -> int:
        """Nombre de jours ouvrés restants avant le prochain rééquilibrage (0 si dû)."""
        elapsed = self.sessions_since(now)
        if elapsed is None:
            return 0
        return max(0, self.rebalance_every - elapsed)

    def record(self, now: date | datetime | None = None) -> None:
        """Persiste la date de ce rééquilibrage (à appeler après soumission)."""
        now_d = _as_date(now) if now is not None else date.today()  # noqa: DTZ011
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_rebalance": now_d.isoformat(),
            "rebalance_every": self.rebalance_every,
            "recorded_at": datetime.now().isoformat(timespec="seconds"),  # noqa: DTZ005
        }
        self.state_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        logger.info("Rééquilibrage enregistré: %s (cadence=%d j ouvrés)",
                    now_d.isoformat(), self.rebalance_every)

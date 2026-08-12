"""Suivi P&L (P4) à partir des snapshots du journal d'exécution.

Le journal (:mod:`financial_analyzer.trading.journal`) persiste des snapshots de
compte (equity/cash/positions) au début et à la fin de chaque run. Ce module en
dérive, **en lecture seule**, une courbe d'equity et les métriques de suivi :
P&L total, rendement, drawdown maximal, nombre de runs. Aucune décision de
trading ici — on observe la piste d'audit, on ne trade pas.

Responsabilité unique : transformer une liste de snapshots en un rapport P&L.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

__all__ = ["PnLReport", "compute_pnl", "load_snapshots"]


@dataclass
class PnLReport:
    """Métriques de suivi P&L dérivées d'une série de snapshots d'equity."""

    n_snapshots: int
    n_runs: int
    start_ts: str | None
    end_ts: str | None
    start_equity: float
    end_equity: float
    total_pnl: float
    total_return_pct: float
    max_drawdown_pct: float
    peak_equity: float
    equity_curve: list[tuple[str, float]] = field(default_factory=list)

    def summary(self) -> str:
        if self.n_snapshots == 0:
            return "P&L: aucun snapshot exploitable."
        return (
            f"P&L: {self.n_runs} runs, {self.n_snapshots} snapshots | "
            f"equity {self.start_equity:,.2f} -> {self.end_equity:,.2f} "
            f"({self.total_pnl:+,.2f}, {self.total_return_pct:+.2f}%) | "
            f"drawdown max {self.max_drawdown_pct:+.2f}% | "
            f"pic {self.peak_equity:,.2f}"
        )


def load_snapshots(paths: list[str | Path]) -> list[dict]:
    """Charge et fusionne les snapshots de plusieurs journaux JSONL, triés par ``ts``.

    Les fichiers absents sont ignorés (best-effort). On ne garde que les
    événements ``kind == "snapshot"`` porteurs d'une equity numérique.
    """
    from financial_analyzer.trading.journal import TradingJournal

    snaps: list[dict] = []
    for p in paths:
        path = Path(p)
        if not path.exists():
            continue
        try:
            snaps.extend(TradingJournal(path).snapshots())
        except Exception as e:  # noqa: BLE001 - un journal illisible ne bloque pas le suivi
            logger.warning("Journal illisible (%s): %s", path, e)
    numeric = [s for s in snaps if isinstance(s.get("equity"), (int, float))]
    return sorted(numeric, key=lambda s: s.get("ts", ""))


def compute_pnl(snapshots: list[dict]) -> PnLReport:
    """Calcule le rapport P&L à partir de snapshots (déjà triés de préférence).

    - equity de départ/fin = premier/dernier snapshot ;
    - drawdown maximal = pire repli pic→creux sur la courbe d'equity ;
    - ``n_runs`` = nombre de snapshots ``event == "run_end"`` (défaut : moitié des
      snapshots si l'événement n'est pas tagué, car un run émet start + end).
    """
    snaps = sorted(
        [s for s in snapshots if isinstance(s.get("equity"), (int, float))],
        key=lambda s: s.get("ts", ""),
    )
    if not snaps:
        return PnLReport(0, 0, None, None, 0.0, 0.0, 0.0, 0.0, 0.0, [])

    curve = [(str(s.get("ts", "")), float(s["equity"])) for s in snaps]
    start_eq = curve[0][1]
    end_eq = curve[-1][1]

    peak = curve[0][1]
    max_dd = 0.0
    for _, eq in curve:
        peak = max(peak, eq)
        if peak > 0:
            dd = (eq - peak) / peak
            max_dd = min(max_dd, dd)

    n_runs = sum(1 for s in snaps if s.get("event") == "run_end")
    if n_runs == 0:
        n_runs = max(1, len(snaps) // 2)

    total_pnl = end_eq - start_eq
    total_return = (end_eq / start_eq - 1.0) * 100.0 if start_eq > 0 else 0.0

    return PnLReport(
        n_snapshots=len(snaps),
        n_runs=n_runs,
        start_ts=curve[0][0],
        end_ts=curve[-1][0],
        start_equity=start_eq,
        end_equity=end_eq,
        total_pnl=total_pnl,
        total_return_pct=total_return,
        max_drawdown_pct=max_dd * 100.0,
        peak_equity=peak,
        equity_curve=curve,
    )

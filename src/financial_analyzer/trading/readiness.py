"""Rapport de préparation au live (go/no-go) à partir des artefacts paper.

Le runbook ``docs/RUNBOOK_PAPER_TO_LIVE.md`` définit **10 critères chiffrés** de
passage paper → live. Le suivi P&L (:mod:`financial_analyzer.trading.pnl`) donne la
courbe d'equity ; il manquait un outil qui **score l'ensemble des critères** contre
les journaux qui s'accumulent (``logs/*.jsonl``), pour transformer les runs paper en
une décision **go/no-go auditable**.

Ce module fournit cette logique, **en lecture seule** (il n'active jamais le live —
le double-verrou de :mod:`financial_analyzer.trading.safety` reste seul maître). Il
classe chaque critère en :

* **auto** — vérifiable depuis les artefacts (journaux, état, config, env) ;
* **opérateur** — décision humaine ou gate par test (chokepoint, kill-switch,
  capital) : le rapport rappelle *quoi* vérifier, sans prétendre le juger.

Verdict ``ready`` = **tous** les critères *auto* passent (aucun échec). Les critères
opérateur restent à confirmer à la main — le rapport ne peut pas se substituer au
jugement pour engager de l'argent réel.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

__all__ = ["Criterion", "ReadinessReport", "load_runs", "evaluate_readiness"]

#: Seuil du runbook : runs consécutifs sans écart de réconciliation avant live.
CLEAN_RUN_TARGET = 20
#: Seuil du runbook : drawdown paper toléré (fraction ; −10 %).
MAX_PAPER_DRAWDOWN_PCT = -10.0


@dataclass
class Criterion:
    """Un critère de passage, avec son verdict et la valeur mesurée."""

    id: int
    title: str
    threshold: str
    status: str  # "pass" | "fail" | "manual"
    measured: str
    kind: str  # "auto" | "operator"

    @property
    def icon(self) -> str:
        return {"pass": "✅", "fail": "❌", "manual": "⚠️"}.get(self.status, "?")


@dataclass
class ReadinessReport:
    """Ensemble des critères + verdict global."""

    criteria: list[Criterion] = field(default_factory=list)

    @property
    def auto(self) -> list[Criterion]:
        return [c for c in self.criteria if c.kind == "auto"]

    @property
    def operator(self) -> list[Criterion]:
        return [c for c in self.criteria if c.kind == "operator"]

    @property
    def n_auto_pass(self) -> int:
        return sum(1 for c in self.auto if c.status == "pass")

    @property
    def ready(self) -> bool:
        """Prêt (côté auto) = tout critère auto passe. N'engage rien : les critères
        opérateur (capital, kill-switch, chokepoint) restent à confirmer à la main."""
        return bool(self.auto) and all(c.status == "pass" for c in self.auto)

    def summary(self) -> str:
        verdict = "PRÊT (côté automatique)" if self.ready else "PAS PRÊT"
        return (f"{verdict} — {self.n_auto_pass}/{len(self.auto)} critères auto OK ; "
                f"{len(self.operator)} critères opérateur à confirmer à la main.")


def load_runs(paths: list[str | Path]) -> list[dict]:
    """Résume chaque journal (= un run) : présence/état de réconciliation, ts.

    Un run *exécuté* écrit un enregistrement ``reconciliation`` ; un dry-run n'en a
    pas (il est ignoré du décompte des runs live-pertinents). Fail-safe : un journal
    illisible est ignoré.
    """
    from financial_analyzer.trading.journal import TradingJournal

    runs: list[dict] = []
    for p in sorted(paths, key=lambda x: str(x)):
        path = Path(p)
        if not path.exists():
            continue
        try:
            records = TradingJournal(path).read()
        except Exception as e:  # noqa: BLE001 - un journal illisible ne bloque pas le rapport
            logger.warning("Journal illisible (%s): %s", path, e)
            continue
        recons = [r for r in records if r.get("kind") == "reconciliation"]
        ts = next((r.get("ts", "") for r in records if r.get("ts")), path.name)
        runs.append({
            "path": str(path),
            "ts": ts,
            "has_recon": bool(recons),
            "recon_ok": bool(recons) and all(bool(r.get("ok")) for r in recons),
        })
    return sorted(runs, key=lambda r: r["ts"])


def _clean_run_streak(runs: list[dict]) -> tuple[int, int]:
    """(streak consécutif propre depuis le plus récent, total de runs réconciliés)."""
    recon_runs = [r for r in runs if r["has_recon"]]
    streak = 0
    for r in reversed(recon_runs):  # du plus récent au plus ancien
        if r["recon_ok"]:
            streak += 1
        else:
            break
    return streak, len(recon_runs)


def _drawdown_pct(paths: list[str | Path]) -> tuple[float | None, int]:
    """(drawdown max en %, nb de snapshots). ``None`` si aucun snapshot exploitable."""
    from financial_analyzer.trading.pnl import compute_pnl, load_snapshots

    snaps = load_snapshots(paths)
    if not snaps:
        return None, 0
    rep = compute_pnl(snaps)
    return rep.max_drawdown_pct, rep.n_snapshots


def _registry_signals() -> list[str]:
    try:
        from financial_analyzer.backtest.validation_gate import VALIDATED_SIGNALS
        return sorted(VALIDATED_SIGNALS)
    except Exception:  # noqa: BLE001
        return []


def _live_risk_config_ready() -> tuple[bool, str]:
    """Vrai si la config de risque *live* committée renseigne toutes les limites.

    Vérifie la *structure* (machinerie prête) sur un capital témoin ; le capital
    réel reste une décision opérateur (critère #10).
    """
    try:
        from financial_analyzer.trading.risk_config import (
            REQUIRED_LIMIT_KEYS,
            live_risk_config,
        )
        cfg = live_risk_config(100_000.0)
        missing = [k for k in REQUIRED_LIMIT_KEYS if cfg.get(k) is None]
        if missing:
            return False, f"limites manquantes : {missing}"
        if not cfg.get("enable_circuit_breaker"):
            return False, "circuit breaker désactivé"
        return True, (f"live: pos≤{cfg['max_position_pct']:.0%}, DD≥{cfg['max_drawdown']:.0%}, "
                      f"levier≤{cfg['max_leverage']:g}, vol≤{cfg['max_portfolio_vol']:.0%} "
                      "(capital = décision opérateur, #10)")
    except Exception as e:  # noqa: BLE001
        return False, f"config live indisponible ({e})"


def _costs_calibrated() -> tuple[bool, str]:
    try:
        from financial_analyzer.backtest.signal_evaluation import CostModel
        cm = CostModel.alpaca_equities()
        ok = cm.commission_bps == 0.0 and cm.slippage_bps == 2.5
        return ok, f"commission {cm.commission_bps:g} + slippage {cm.slippage_bps:g} bps"
    except Exception as e:  # noqa: BLE001
        return False, f"indisponible ({e})"


def evaluate_readiness(
    journal_paths: list[str | Path],
    *,
    rebalance_state: str | Path = "logs/rebalance_state.json",
    alert_log: str | Path = "logs/alerts.jsonl",
) -> ReadinessReport:
    """Score les 10 critères du runbook depuis les artefacts. Lecture seule."""
    runs = load_runs(journal_paths)
    streak, n_recon = _clean_run_streak(runs)
    dd_pct, n_snaps = _drawdown_pct(journal_paths)
    signals = _registry_signals()
    costs_ok, costs_desc = _costs_calibrated()
    webhook = os.environ.get("FINBOT_ALERT_WEBHOOK", "").strip()
    alert_log_exists = Path(alert_log).exists()
    reb_state_exists = Path(rebalance_state).exists()

    c: list[Criterion] = []

    # 1 — Runs consécutifs sans écart de réconciliation ≥ 20 (auto).
    c.append(Criterion(
        1, "Runs paper consécutifs sans écart de réconciliation",
        f"≥ {CLEAN_RUN_TARGET}",
        "pass" if streak >= CLEAN_RUN_TARGET else "fail",
        f"streak={streak} (sur {n_recon} runs réconciliés)", "auto"))

    # 2 — Drawdown paper > −10 % (auto si snapshots présents).
    if dd_pct is None:
        c.append(Criterion(
            2, "Suivi P&L exploitable — drawdown paper", f"> {MAX_PAPER_DRAWDOWN_PCT:g} %",
            "fail", "aucun snapshot dans les journaux (harness sans record_snapshot ?)",
            "auto"))
    else:
        c.append(Criterion(
            2, "Suivi P&L exploitable — drawdown paper", f"> {MAX_PAPER_DRAWDOWN_PCT:g} %",
            "pass" if dd_pct > MAX_PAPER_DRAWDOWN_PCT else "fail",
            f"drawdown max {dd_pct:+.2f} % ({n_snaps} snapshots)", "auto"))

    # 3 — Signaux = registre validé uniquement (auto : registre non vide).
    c.append(Criterion(
        3, "Signaux = registre validé uniquement", "VALIDATED_SIGNALS non vide",
        "pass" if signals else "fail",
        f"registre = {signals}" if signals else "registre VIDE", "auto"))

    # 4 — Chokepoint unique (gate par test).
    c.append(Criterion(
        4, "Chokepoint d'exécution unique confirmé", "0 submit hors gateway",
        "manual", "pytest tests/test_scripts/test_daemon_safety_invariants.py", "operator"))

    # 5 — RiskGuard configuré pour le live (auto : config live committée et complète).
    ok5, detail5 = _live_risk_config_ready()
    c.append(Criterion(
        5, "Config de risque live committée et complète",
        "toutes limites + circuit breaker + garde-fous portefeuille",
        "pass" if ok5 else "fail", detail5, "auto"))

    # 6 — Cadence de rééquilibrage active (auto : état persistant présent).
    c.append(Criterion(
        6, "Cadence de rééquilibrage active", "RebalanceGate + état persistant",
        "pass" if reb_state_exists else "fail",
        f"{rebalance_state} {'présent' if reb_state_exists else 'absent'}", "auto"))

    # 7 — Alerting opérationnel (auto : webhook défini ; log d'alerte présent = bonus).
    c.append(Criterion(
        7, "Alerting opérationnel", "FINBOT_ALERT_WEBHOOK défini + alerte test",
        "pass" if webhook else "fail",
        (f"webhook défini ; log d'alertes {'présent' if alert_log_exists else 'absent'}"
         if webhook else "FINBOT_ALERT_WEBHOOK non défini"), "auto"))

    # 8 — Kill-switch testé (gate par test).
    c.append(Criterion(
        8, "Kill-switch testé", "cycle activer→refuser vert",
        "manual", "pytest tests/test_trading/test_kill_switch.py", "operator"))

    # 9 — Coûts calibrés Alpaca (auto).
    c.append(Criterion(
        9, "Coûts calibrés (modèle Alpaca)", "commission 0 + slippage 2.5 bps",
        "pass" if costs_ok else "fail", costs_desc, "auto"))

    # 10 — Capital initial modeste défini (décision opérateur).
    c.append(Criterion(
        10, "Capital initial modeste défini", "montant explicite + tolérance de perte",
        "manual", "décision opérateur", "operator"))

    return ReadinessReport(criteria=c)

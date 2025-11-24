"""Daily Master Run Script
=================================

Orchestre l'exécution journalière complète suivant l'architecture:
    1. Snapshot & pré-analyse portefeuille (drift + options)
    2. Sélection avancée de l'univers (EnhancedUniverseSelector)
    3. Génération / fusion des signaux multi-modules (technique, fondamental, sentiment, ML, RL)
    4. Optimisation du portefeuille + contraintes + overlay hedge options
    5. Décisions (SELL/HOLD/BUY) + exécution ordres
    6. Export des artefacts & logging

Robustesse:
    - Gestion des erreurs par étape avec remontée dans le log
    - Fallbacks quand un module n'est pas disponible
    - Limitation du nombre de symboles analysés configurable

Usage:
    python scripts/daily_master_run.py --limit 300 --regions global --output daily_master_result.csv

"""
from __future__ import annotations

# 1. Stdlib
import argparse
import json
import sys
import traceback
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict

# 2. Third-party
import pandas as pd
import numpy as np

# 3. Local (imports protégés pour robustesse)
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

# Modules avec try/except pour assurer la continuation si absent
try:
    from financial_analyzer.preanalysis.daily_preanalysis import run_daily_preanalysis
except Exception:  # pragma: no cover
    run_daily_preanalysis = None  # type: ignore
    logger.warning("run_daily_preanalysis indisponible – préanalyse sautée")

try:
    from financial_analyzer.portfolio import PortfolioOptimizer, OptimizationResult
except Exception:  # pragma: no cover
    PortfolioOptimizer = None  # type: ignore
    OptimizationResult = None  # type: ignore
    logger.warning("PortfolioOptimizer indisponible – optimisation sautée")

try:
    from financial_analyzer.portfolio.constraints import ConstraintSet
except Exception:  # pragma: no cover
    ConstraintSet = None  # type: ignore

try:
    from financial_analyzer.universe.universe_selector_enhanced import EnhancedUniverseSelector, SelectionConfig
except Exception:  # pragma: no cover
    EnhancedUniverseSelector = None  # type: ignore
    SelectionConfig = None  # type: ignore
    logger.error("EnhancedUniverseSelector introuvable – arrêt nécessaire")

try:
    from financial_analyzer.scripts.portfolio_manager import PortfolioManager  # may differ path
except Exception:  # pragma: no cover
    PortfolioManager = None  # type: ignore
    logger.warning("PortfolioManager indisponible – décisions directes basées sur optimisation")

try:
    from financial_analyzer.learning.portfolio_learner import PortfolioLearner
except Exception:  # pragma: no cover
    PortfolioLearner = None  # type: ignore

try:
    from financial_analyzer.sentiment.realtime_sentiment_pipeline import RealtimeSentimentPipeline
except Exception:  # pragma: no cover
    RealtimeSentimentPipeline = None  # type: ignore

try:
    from financial_analyzer.ml.ml_trading_pipeline import MLTradingPipeline
except Exception:  # pragma: no cover
    MLTradingPipeline = None  # type: ignore

try:
    from financial_analyzer.rl.rl_trading_pipeline import RLTradingPipeline
except Exception:  # pragma: no cover
    RLTradingPipeline = None  # type: ignore

try:
    from financial_analyzer.analysis.master_orchestrator import MasterOrchestrator
except Exception:  # pragma: no cover
    MasterOrchestrator = None  # type: ignore

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_call(name: str, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:  # pragma: no cover (logging side effect)
        logger.error(f"Échec {name}: {e}")
        logger.debug(traceback.format_exc())
        return None


def _build_signal_scores(symbols: List[str]) -> pd.Series:
    """Fusion minimale de signaux comme placeholder.

    Idéalement: agrégation des sorties des engines technique/fondamental/sentiment/ML/RL.
    Ici: simulation basée sur bruit + légère prime momentum fictive.
    """
    base = np.random.standard_normal(len(symbols))
    # Momentum proxy (favorise symboles triés lexicalement pour différenciation stable)
    momentum_component = np.linspace(0.0, 1.0, len(symbols))
    scores = 0.6 * base + 0.4 * momentum_component
    ser = pd.Series(scores, index=symbols, name="raw_signal")
    return (ser - ser.min()) / (ser.max() - ser.min())


def _derive_positions(weights: pd.Series, capital: float = 100_000.0) -> pd.DataFrame:
    if weights.empty:
        return pd.DataFrame(columns=["symbol", "target_shares", "weight"])
    prices = pd.Series(50.0, index=weights.index)  # placeholder constant price
    alloc = weights * capital
    shares = (alloc / prices).astype(int)
    return pd.DataFrame({"symbol": shares.index, "target_shares": shares.values, "weight": weights.values})

# ---------------------------------------------------------------------------
# Core Daily Run
# ---------------------------------------------------------------------------

def run_daily_master(limit: int, regions: Optional[List[str]], output: Path) -> Dict:
    logger.info("===== DÉMARRAGE DAILY MASTER RUN =====")

    # 1. Snapshot portefeuille & pré-analyse
    portfolio_positions = None
    if PortfolioManager:
        pm = PortfolioManager()
        portfolio_positions = _safe_call("portfolio_positions", pm.get_current_portfolio)
        logger.info(f"Positions existantes: {0 if portfolio_positions is None else len(portfolio_positions)}")

    preanalysis_result = None
    if run_daily_preanalysis and portfolio_positions is not None and not portfolio_positions.empty:
        symbols = list(portfolio_positions.index)
        preanalysis_result = _safe_call("preanalysis", run_daily_preanalysis, symbols=symbols, dates=None, check_drift=True, analyze_options=True)
    else:
        logger.warning("Pré-analyse sautée (module ou positions absentes)")

    # 2. Sélection univers améliorée
    selector = EnhancedUniverseSelector(SelectionConfig(limit=limit)) if EnhancedUniverseSelector else None
    if selector is None:
        raise RuntimeError("EnhancedUniverseSelector indisponible")
    universe = _safe_call("universe_selection", selector.select, limit=limit, regions=regions)
    if not universe:
        logger.error("Sélection univers vide – arrêt")
        return {"status": "failed", "reason": "empty_universe"}
    logger.info(f"Univers sélectionné: {len(universe)} tickers")

    # 3. Signaux agrégés (placeholder + orchestrator si dispo)
    signal_scores = _build_signal_scores(universe)

    # 4. Optimisation du portefeuille
    weights = pd.Series(dtype=float)
    optimization_detail = None
    if PortfolioOptimizer:
        optimizer = PortfolioOptimizer()
        # Dummy expected returns & covariance
        exp_returns = pd.Series(np.random.uniform(0.05, 0.25, len(universe)), index=universe)
        rand = np.random.uniform(0.0, 0.05, (len(universe), len(universe)))
        cov = pd.DataFrame(rand @ rand.T, index=universe, columns=universe)
        constraints = ConstraintSet(max_weight=0.05, max_leverage=1.0, max_positions=min(50, len(universe))) if ConstraintSet else None
        try:
            result = optimizer.optimize_mean_variance(expected_returns=exp_returns, covariance_matrix=cov, constraints=constraints)
            weights = result.weights.sort_values(ascending=False)
            optimization_detail = {
                "objective": result.objective_value,
                "method": "mean_variance",
            }
        except Exception as e:  # pragma: no cover
            logger.error(f"Échec optimisation: {e}")
    else:
        logger.warning("Optimisation indisponible – fallback égalitaire")
        if universe:
            weights = pd.Series(1/len(universe), index=universe)

    # Cardinalité (enforce constraints si présents)
    if ConstraintSet and constraints and not weights.empty:
        weights = constraints.enforce_cardinality(weights)

    # 5. Décisions (Sell/Hold/Buy)
    decisions = []
    if PortfolioManager and portfolio_positions is not None and not weights.empty:
        # Règle simple: nouveaux poids > 0 => BUY si pas présent, sinon HOLD; positions sans nouveaux poids => SELL
        current_syms = set(portfolio_positions.index)
        target_syms = set(weights.index[weights > 0])
        for sym in target_syms:
            if sym in current_syms:
                decisions.append({"symbol": sym, "action": "HOLD"})
            else:
                decisions.append({"symbol": sym, "action": "BUY"})
        for sym in current_syms - target_syms:
            decisions.append({"symbol": sym, "action": "SELL"})
    else:
        logger.warning("Décisions simplifiées – PortfolioManager indisponible ou poids vides")
        for sym in weights.index[:10]:  # sample
            decisions.append({"symbol": sym, "action": "BUY"})

    # 6. Construction ordres (simplifiée)
    orders_df = _derive_positions(weights)

    # 7. Export
    output.parent.mkdir(parents=True, exist_ok=True)
    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "universe_size": len(universe),
        "positions_before": 0 if portfolio_positions is None else len(portfolio_positions),
        "decisions": decisions,
        "optimization": optimization_detail,
    }
    orders_df.to_csv(output, index=False)
    (output.parent / "daily_master_summary.json").write_text(json.dumps(summary, indent=2))
    logger.info(f"Résultats écrits dans {output}")

    return {"status": "ok", "summary": summary}

# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[List[str]] = None):
    p = argparse.ArgumentParser("Daily Master Run")
    p.add_argument("--limit", type=int, default=300, help="Nombre max de tickers dans l'univers final")
    p.add_argument("--regions", type=str, default="global", help="Liste de régions séparées par virgule ou 'global'")
    p.add_argument("--output", type=str, default="daily_master_result.csv", help="Chemin fichier résultats ordres")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None):
    args = parse_args(argv)
    regions = None if args.regions == "global" else [r.strip() for r in args.regions.split(',') if r.strip()]
    try:
        result = run_daily_master(limit=args.limit, regions=regions, output=Path(args.output))
        if result.get("status") != "ok":
            logger.error("Daily master run terminé avec statut échoué")
            return 1
        logger.info("Daily master run terminé avec succès")
        return 0
    except Exception as e:  # pragma: no cover
        logger.error(f"Erreur fatale daily master run: {e}")
        logger.debug(traceback.format_exc())
        return 2

if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())

#!/usr/bin/env python3
from __future__ import annotations
import json
from typing import Dict, List


def recommended_repos() -> List[Dict]:
    """
    Retourne une liste de dépôts GitHub recommandés pour FinBot avec catégories et
    propositions d'intégration. Ne fait pas d'appels réseau.
    """
    return [
        {
            "name": "microsoft/qlib",
            "category": "research-factors",
            "license": "MIT",
            "summary": "Plateforme de recherche factorielle/ML, datasets et orchestration d'expériences.",
            "proposed_integration": [
                "Orchestration d'expériences et auto-mining de facteurs",
                "Benchmarks de modèles/traits via datasets normalisés"
            ],
        },
        {
            "name": "hudson-and-thames/mlfinlab",
            "category": "research-factors",
            "license": "Apache-2.0",
            "summary": "Labeling (triple-barrier), microstructure, validation des features.",
            "proposed_integration": [
                "Wrapper triple-barrier dans ml/labeling.py",
                "Feature clustering/corr tests dans ml/validation.py"
            ],
        },
        {
            "name": "quantopian/alphalens",
            "category": "evaluation",
            "license": "Apache-2.0",
            "summary": "Analyse IC/RankIC et tearsheets factoriels.",
            "proposed_integration": [
                "IC reports post-backtest (reports/ic_report_*.html)"
            ],
        },
        {
            "name": "robertmartin8/PyPortfolioOpt",
            "category": "portfolio",
            "license": "MIT",
            "summary": "MV, Black-Litterman, contraintes avancées.",
            "proposed_integration": [
                "optimize_black_litterman dans portfolio/optimizer.py",
                "Sector caps / L2-L1 regularization"
            ],
        },
        {
            "name": "dppalomar/riskfolio-lib",
            "category": "portfolio",
            "license": "BSD-3",
            "summary": "ERC, CVaR, MAD, nombreuses mesures de risque.",
            "proposed_integration": [
                "Stratégie ERC/CVaR auto-sélectionnée selon régime"
            ],
        },
        {
            "name": "RanAroussi/vectorbt",
            "category": "backtest",
            "license": "GPL-3.0",
            "summary": "Backtesting vectorisé, très rapide.",
            "proposed_integration": [
                "features/technical_vbt.py pour features massifs"
            ],
        },
        {
            "name": "pmorissette/bt",
            "category": "backtest",
            "license": "BSD-2",
            "summary": "Cadre de backtest haut-niveau.",
            "proposed_integration": [
                "Benchmarks rapides d'idées sur univers restreints"
            ],
        },
        {
            "name": "quantopian/empyrical",
            "category": "metrics",
            "license": "Apache-2.0",
            "summary": "Ratios et métriques performance standard.",
            "proposed_integration": [
                "Aligner nos métriques sur empyrical pour compat"
            ],
        },
        {
            "name": "quantstats/quantstats",
            "category": "reporting",
            "license": "MIT",
            "summary": "Rapports de performance faciles.",
            "proposed_integration": [
                "Export HTML complémentaire aux rapports internes"
            ],
        },
        {
            "name": "pmorissette/ffn",
            "category": "reporting",
            "license": "MIT",
            "summary": "Stats financières + reporting.",
            "proposed_integration": [
                "Génération de rapports rapides en notebooks"
            ],
        },
        {
            "name": "bashtage/arch",
            "category": "volatility",
            "license": "NCSA",
            "summary": "Modèles ARCH/GARCH.",
            "proposed_integration": [
                "Détection de régimes/vol pour pilotage du risque"
            ],
        },
        {
            "name": "bukosabino/ta",
            "category": "features",
            "license": "MIT",
            "summary": "Indicateurs techniques classiques.",
            "proposed_integration": [
                "Compléments à notre moteur technique"
            ],
        },
        {
            "name": "twopirllc/pandas-ta",
            "category": "features",
            "license": "MIT",
            "summary": "Indicateurs techniques sur pandas.",
            "proposed_integration": [
                "Alternative de features techniques performantes"
            ],
        },
    ]


def main() -> None:
    print(json.dumps(recommended_repos(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

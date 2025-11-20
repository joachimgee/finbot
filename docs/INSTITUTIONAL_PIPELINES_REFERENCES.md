# Références GitHub – Pipelines Institutionnels & Outils

Objectif: lister des dépôts publics de qualité couvrant facteurs, portefeuille, backtest, risque, et proposer leur utilité pour FinBot.

## Recherche/Facteurs
- microsoft/qlib: Plateforme de recherche factorielle/ML, gestion datasets, orchestration d’expériences. Utilité: inspiration pour ordonnancement d’expériences et auto-mining de facteurs.
- hudson-and-thames/mlfinlab: Labeling (triple-barrier), microstructure, feature importance, tests de corrélation. Utilité: pipeline labeling robuste + validation feature set.
- quantopian/alphalens: Analyse factorielles IC/RankIC, tearsheets. Utilité: rapports IC standardisés post-backtest.

## Portefeuille/Risque
- robertmartin8/PyPortfolioOpt: MV, Black-Litterman, contraintes diversifiées. Utilité: scénarios Black-Litterman, caps secteur, régularisation L2/L1.
- dppalomar/riskfolio-lib: ERC, CVaR, MAD, mesures de risque avancées. Utilité: profils de risque (ERC/CVaR) alternatifs selon régimes.
- quantopian/empyrical: Ratios de performance standard. Utilité: alignement des métriques.

## Backtesting/Exécution
- pmorissette/bt: Cadre haut-niveau, flexible. Utilité: benchmarking rapide.
- RanAroussi/vectorbt: Backtest vectorisé massif. Utilité: génération accélérée de features/benchmarks.
- mhallsmoore/qstrader: Architecture d’exécution plus institutionnelle. Utilité: inspiration exécution/portefeuille.
- backtrader/backtrader: Backtesting populaire, grande communauté. Utilité: comparaison API stratégique.

## ML/NLP & Stats
- FinRL/FinRL: DRL pour trading; pipelines et exemples. Utilité: pistes futures RL.
- huggingface/transformers: LMs (FinBERT). Utilité: sentiment/NER, déjà employé.
- pmorissette/ffn, quantstats/quantstats: Reporting performance, stats financières. Utilité: rapports rapides.
- bashtage/arch: Modèles ARCH/GARCH. Utilité: modélisation vol/régimes.
- bukosabino/ta, bukosabino/pandas-ta: Indicateurs techniques. Utilité: complément rapide à notre moteur technique.

## Qualité & Licences (résumé)
- qlib (MIT), mlfinlab (Apache-2.0), PyPortfolioOpt (MIT), riskfolio-lib (BSD-3), vectorbt (GPLv3), bt (BSD-2), backtrader (GPLv3), empyrical/pyfolio (Apache-2.0).
- Intégration directe OK pour licences permissives (MIT/BSD/Apache). Pour GPL, privilégier inspiration/out-of-process.

---
Dernière mise à jour: 2025-11-18

# Repos & Forks Utiles – Intégrations FinBot

Objectif: pointer les dépôts clés et proposer des points d’intégration concrets.

## Facteurs & Recherche Quant
- `hudson-and-thames/mlfinlab` (facteurs microstructure, sampling, labeling)
  - Intégration: pipeline de labeling (triple-barrier), tests d’importance, feature clustering.
- `microsoft/qlib` (plateforme data + auto factor/mining)
  - Intégration: source de features alternatifs + ordonnancement d’expériences.
- `quantopian/alphalens` (analyse factorielles IC/tearsheets)
  - Intégration: module d’analyse IC post-run (déjà couvert en partie).

## Portfolio & Risque
- `robertmartin8/PyPortfolioOpt` (MV, Black-Litterman, L2/L1)
  - Intégration: déjà présent via wrapper – étendre scénarios BL / sector caps.
- `dppalomar/riskfolio-lib` (ERC, CVaR, MAD, RM optimizers)
  - Intégration: ajouter sélecteur d’optimiseur par profil de risque.
- `quantopian/pyfolio` (tearsheets performance – legacy)
  - Intégration: exporter métriques vers un rapport HTML optionnel.

## Backtesting & Execution
- `pmorissette/bt` (framework de backtest haut-niveau)
  - Intégration: benchmarks rapides sur univers restreints.
- `RanAroussi/vectorbt` (vectorisé, rapide)
  - Intégration: fast prototyping pour signaux techniques massifs.
- `mhallsmoore/qstrader` (backtester institutionnel open-source)
  - Intégration: comparer pipeline exécution/portfolio.

## Mesures & Utilitaires
- `quantopian/empyrical` (ratios & risques standards)
  - Intégration: aligner les mesures avec standards empyrical pour compatibilité écosystème.

## Sentiment & NLP
- `huggingface/transformers` (FinBERT, Finance-specific LMs)
  - Intégration: déjà présent – définir jeux de prompts/finetune heads de classification.

## Roadmap d’Intégration
- Étape 1: brancher Alphalens-like IC reports (post-run) + options Riskfolio (ERC/CVaR)
- Étape 2: ajouter triple-barrier labeling (mlfinlab) dans MLPredictor + feature importance robuste
- Étape 3: scenarios Black-Litterman (PyPortfolioOpt) + sector/group constraints unifiés
- Étape 4: module ‘fast-tech’ via vectorbt pour backfills de features techniques à grande échelle


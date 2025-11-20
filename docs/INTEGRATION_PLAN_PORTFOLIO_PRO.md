# Plan d’Intégration – Pipeline Professionnel

Ce plan décrit comment intégrer les références externes dans l’architecture FinBot pour une parité "pro".

## Cibles & Modules
- `features/` (techniques, fondamentaux, alpha): ajouter labeling (mlfinlab), neutralisation/normalisation stricte.
- `ml/` (prédiction): intégrer triple-barrier, features importance/stability, ensembling calibré.
- `backtest/` (runner): hooks d’évaluation IC/RankIC, turnover, coûts de transaction.
- `portfolio/` (optimisation): profils MV/BL/RC/CVaR avec contraintes unifiées (secteurs, groupes, bounds, turnover).
- `risk/` (mesures/guardrails): budget de vol, VaR/CVaR, stress-tests scénarisés, HHI/concentration.
- `trading/` (exécution): VWAP/TWAP placeholders, contrôle ordres via RiskGuard.

## Intégrations Concrètes
- Alphalens-like IC:
  - Point d’entrée: `BacktestRunner` post-simulation → exporter signaux/rendements croisés → calculs IC (rank/pearson), t-stat, decay.
  - Sortie: `reports/ic_report_*.html` + JSON.
- mlfinlab (labeling/validation):
  - `ml/labeling.py`: wrapper triple-barrier; `ml/validation.py`: feature clustering/corr tests.
  - Consommé par `MLPredictor` et `FeatureEngineer`.
- PyPortfolioOpt (Black-Litterman):
  - `portfolio/optimizer.py`: méthode `optimize_black_litterman(views, confidences, caps)`.
  - `constraints.py`: caps sectoriels/groupes, turnover bound.
- Riskfolio-Lib (ERC/CVaR):
  - Stratégie alternative auto-sélectionnée selon régime (vol/trend) détecté dans `risk/regime.py`.
- vectorbt (accélération features):
  - `features/technical_vbt.py`: génération massive de features techniques pour univers large (optionnel).

## Orchestration & Validation
- Walk-forward strict: `backtest/walk_forward.py` avec splits OOS, re-fit par fenêtre.
- IC-decay: λ configurable (0.94–0.98) et poids de facteurs dynamiques.
- Benchmarks: scripts `scripts/run_ic_report.py`, `scripts/run_bl_scenarios.py`.

## Sécurité & Licences
- MIT/BSD/Apache: intégration directe.
- GPL (vectorbt/backtrader): modules optionnels, isolation si distribution fermée.

---
Dernière mise à jour: 2025-11-18

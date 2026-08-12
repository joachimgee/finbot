# FinBot — Audit d'améliorabilité du système

*Revue transversale du dépôt (≈ 53 k LOC src / 36 k LOC tests) croisée avec la
littérature et les systèmes comparables (LEAN/QuantConnect, Qlib, Zipline/Alphalens).
Objectif : distinguer **robustesse/sûreté/maintenabilité** (améliorable ici) de
**l'edge de performance** (plafonné par la donnée — cf. `IMPROVEMENT_RESEARCH.md`).*

## 1. Ce qui est déjà solide (à préserver)

- **Chemin live propre et sûr** : daemon → `LiveTradingPipeline` → signaux validés
  (`SignalFusionEngine`) → Black-Litterman → cap de concentration → `RiskGuard` →
  `OrderGateway` (chokepoint unique : mode-gate paper/live, idempotence, audit,
  journal).
- **Discipline de validation** : portail double critère (IC t > 2 ET Sharpe net > 0)
  + Deflated Sharpe Ratio — plus rigoureux que la majorité des dépôts open-source.
- **Briques « live » souvent absentes ailleurs** : réconciliation broker↔journal
  (`trading/reconciliation.py`), coûts calibrés réels (Alpaca), fondamentaux &
  univers **point-in-time**, kill-switch + runbook + alerting fail-safe, shrinkage
  Ledoit-Wolf dans le chemin Riskfolio (`live_trading_pipeline.py`).

## 2. Améliorable — fort levier, le code existe déjà (non câblé)

| # | Amélioration | État actuel | Effort |
|---|---|---|---|
| 1 | **PBO / CSCV dans le portail** | `backtest/validation/combinatorial_cv.py` existe mais n'est pas relié au gate ; le DSR est là, pas la *Probability of Backtest Overfitting* | faible |
| 2 | **RiskGuard enrichi** | Live = position / concentration / drawdown / leverage. `risk/` (VaR, stress-test, risk-budgeting, corrélation) est **orphelin** du pré-trade | moyen |
| 3 | **Objectif portefeuille *cost-aware*** | Contrainte de turnover présente (`portfolio/constraints.py`) mais l'optimisation ne **pénalise pas** les coûts dans l'objectif | moyen |
| 4 | **Combiner *risk-weighting*** | `strategy/ensemble_allocator.py` prêt mais jamais exercé (1 seul signal validé) — prêt le jour où un 2ᵉ signal passe | faible |

## 3. Dette structurelle (fragmentation)

- **Répertoires en double** : `strategy/` + `strategies/` ; `features/` +
  `ml_features/` + `ml_features_advanced/` ; `analysis/` + `analytics/`.
  (Même schéma que la fusion `portfolio_optimization` → `portfolio` déjà réalisée.)
- **≈ 11 000 LOC de recherche orpheline** : `ml/` (6.4 k), `rl/` (2.8 k),
  `deep_learning/`, `derivatives/` — importés par 1-3 modules chacun, **hors du
  chemin qui trade**. Décision à prendre : quarantaine dans un namespace `research/`
  clairement étiqueté, ou câblage honnête via le portail. Aujourd'hui : poids mort
  ambigu (~66 marqueurs TODO/FIXME/stub au total).

## 4. Ce que la littérature / d'autres systèmes ont et qui manque

- **LEAN (QuantConnect)** — séparation nette **Alpha → PortfolioConstruction →
  Risk → Execution** en modules enfichables. Le `LiveTradingPipeline` mélange ces
  quatre étapes ; les séparer les rendrait testables/remplaçables indépendamment.
  *Amélioration architecturale la plus rentable.*
- **Qlib (Microsoft)** — *rolling retraining* / re-validation glissante automatique
  des alphas. FinBot valide une fois ; pas de re-validation périodique du registre
  (un signal peut se dégrader silencieusement).
- **Alphalens (Quantopian)** — *tearsheets* standard : décroissance d'IC, quantile
  returns, turnover. FinBot a les briques (`evaluate_signal`) sans le rapport type.
- **Exécution** — aucun algorithme (market/limit seulement). Implementation
  shortfall / TWAP / participation-rate (Almgren-Chriss). *Faible priorité à petite
  taille*, à traiter avant de scaler.
- **Détection de régime** — filtre trend/risk-off présent ; la littérature va plus
  loin (HMM, ruptures de régime). Optionnel.

## 5. Hiérarchie recommandée

1. **PBO / CSCV dans le portail** (#1) — durcit encore la validation, code présent,
   effort faible. ✅ **Fait** : `probability_of_backtest_overfitting` (CSCV) câblé
   comme 4e critère optionnel (`pbo_max=0.5`). Résultat réel sur le sweep :
   **PBO = 0.09** (sélection robuste) — complète le DSR (0.13). Détail dans
   `IMPROVEMENT_RESEARCH.md`.
2. **RiskGuard enrichi** (#2) — vraie sûreté *live* (limites corrélation/secteur +
   VaR), modules déjà écrits.
3. **Consolidation structurelle** (§3) — fusion des doublons + quarantaine du layer
   recherche. Faible risque, gros gain de lisibilité.
4. **Objectif cost-aware** (#3) — améliore directement le Sharpe *net*.
5. **Séparation type LEAN** (§4) — le plus structurant, plus d'effort.

## 6. Rappel honnête sur le plafond

Ces points améliorent **robustesse, sûreté et maintenabilité**, pas l'**edge**.
La performance reste plafonnée par la **donnée** (univers profond sans biais de
survie) — établi empiriquement sur 4 familles de signaux dans
`IMPROVEMENT_RESEARCH.md`. Ne pas confondre les deux axes.

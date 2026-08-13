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
| 2 | **RiskGuard enrichi** ✅ **Fait** | Ajout d'un contrôle **pré-trade portefeuille** corrélation-aware (`validate_portfolio`) : vol ex-ante `√(wᵀΣw)`, VaR 95 % 1 j, nombre effectif de paris — limites *opt-in*, câblées dans le pipeline (abstention si dépassement). Voir §7. | ~~moyen~~ |
| 3 | **Objectif portefeuille *cost-aware*** ✅ **Fait** | Bande de non-transaction (`backtest/cost_aware.py`), câblée en option dans `evaluate_signal` et `LiveTradingPipeline.no_trade_band`. Résultat réel : Sharpe net +0.73→+0.95, maxDD −21%→−17%, turnover −98%. Voir §8. | ~~moyen~~ |
| 4 | **Combiner *risk-weighting*** | `strategy/ensemble_allocator.py` prêt mais jamais exercé (1 seul signal validé) — prêt le jour où un 2ᵉ signal passe | faible |

## 3. Dette structurelle (fragmentation) — ✅ frontière verrouillée

### Fait : quarantaine de la couche recherche par **frontière imposée** (pas un déplacement)

Déplacer physiquement ~11 k LOC (`ml/`, `rl/`, `deep_learning/`, `derivatives/`)
casserait des dizaines d'imports de tests (7-8 tests par répertoire) pour un gain
cosmétique — mauvais rapport risque/récompense. On a fait mieux et plus sûr :

1. **Suppression du couplage recherche→live réellement mort.** Le
   `SignalFusionEngine` gardait trois méthodes `_init_lstm_predictor` /
   `_init_ml_factor_engine` / `_init_rl_pipeline` **jamais appelées** (zombies de
   la purge P0) qui importaient `deep_learning`/`ml`/`rl` dans le chemin live pour
   rien ; idem deux imports gardés (`LSTMPredictor`, `MLPredictor`) inutilisés dans
   `live_trading_pipeline`. Supprimés. Les sources correspondantes **s'abstiennent**
   déjà via `_get_*_signal → _abstain` (registre `ABSTAINING_SOURCES` conservé).
2. **Frontière verrouillée par un test** : `tests/test_architecture/test_layering.py`
   vérifie qu'**aucun** fichier du cœur de décision (`trading/`, les deux modules
   `integration/` du live, le portail + éval `backtest/`, `portfolio/`) n'importe
   `ml`/`rl`/`deep_learning`/`derivatives`. Empêche toute ré-introduction silencieuse.

Résultat : la couche recherche est *de facto* en quarantaine (aucun lien vers le
live), sans le risque d'un déménagement massif. Elle reste utilisable en R&D et
re-branchable **via le portail** le jour où un modèle est réellement entraîné/validé.

### Carte des couches (référence)

| Couche | Répertoires | Rôle |
|---|---|---|
| **Live (décision)** | `trading/`, `integration/signal_fusion_engine`+`signal_portfolio_bridge`, `backtest/`(gate, éval, facteurs, vol, robustness, coûts), `portfolio/`, `data/` | ce qui trade |
| **Recherche (quarantaine)** | `ml/`, `rl/`, `deep_learning/`, `derivatives/` | R&D, hors live, re-branchable via le portail |
| **Analytics / reporting** | `analytics/`, `reports/`, `analysis/` | post-hoc, non décisionnel |

### Reste (déféré, faible priorité) : fusion des répertoires en double

`strategy/`+`strategies/`, `features/`+`ml_features/`+`ml_features_advanced/`,
`analysis/`+`analytics/`. Fusion physique **déférée** : chacun est couplé à
plusieurs suites de tests → churn élevé pour un gain purement cosmétique. À traiter
répertoire par répertoire, avec mise à jour des imports et suite verte, quand le
besoin de lisibilité le justifie (même méthode que la fusion
`portfolio_optimization`→`portfolio` déjà faite). ~66 marqueurs TODO/FIXME/stub au
total restent à éponger au fil de l'eau.

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
3. **Consolidation structurelle** (§3) — ✅ **Fait** : couche recherche mise en
   quarantaine par *frontière imposée* (test de layering) + suppression du couplage
   recherche→live mort. Fusion des répertoires doublons déférée (churn/cosmétique).
4. **Objectif cost-aware** (#4) — ✅ **Fait** : bande de non-transaction (§8),
   Sharpe net +0.73→+0.95 sur momentum réel. Câblée opt-in dans le pipeline.
5. **Séparation type LEAN** — le plus structurant, plus d'effort. *Reste à faire.*

## 7. Détail #2 — contrôle de risque pré-trade au niveau portefeuille

`RiskGuard.validate_order` reste **par ordre** (taille, concentration *par nom*,
leverage, drawdown, daily-loss). Nouveau : `RiskGuard.validate_portfolio(weights,
close)` juge le **book cible entier**, ce qu'un cap *par nom* ne peut pas voir —
p.ex. 5 noms à 15 % chacun mais tous très corrélés = un seul gros pari.

- **Vol ex-ante** `√(wᵀΣw)` annualisée (`max_portfolio_vol`) — corrélation-aware
  par construction (réutilise `backtest.vol_management.ex_ante_vol`, source unique).
- **VaR 95 % 1 jour** paramétrique = 1.645·vol_jour (`max_var_95`).
- **Nombre effectif de paris** `1/Σwᵢ²` (`min_effective_bets`).

Chaque limite est **opt-in** (`None` → inactive : le comportement historique est
inchangé). Données insuffisantes → **abstention** (pas de faux rejet). Câblé dans
`LiveTradingPipeline.run` entre l'allocation et la génération d'ordres : un book
qui dépasse une limite fait **s'abstenir** tout le rééquilibrage (log + statut
`skipped/portfolio_risk_limit`), sans crasher le daemon. À activer via les
paramètres du `RiskGuard` quand on passe en live (cf. runbook).

## 8. Détail #4 — rééquilibrage cost-aware (bande de non-transaction)

Sous **coûts proportionnels**, la politique optimale est une **bande de
non-transaction** (Constantinides 1986 ; Davis-Norman 1990 ; Gârleanu-Pedersen
2013) : ne trader une ligne que si son poids bouge de plus que la bande.
`backtest/cost_aware.py::apply_no_trade_band` (pur, testé), branché en option dans
`evaluate_signal(no_trade_band=…)` et `LiveTradingPipeline(no_trade_band=…)`
(défaut 0 → comportement inchangé, fail-safe).

**Résultat réel** (`run_cost_aware_band_alpaca.py`, momentum_12_1 à **poids
continus**, reb quotidien, coûts Alpaca calibrés) :

| bande | turnover | Sharpe brut | Sharpe net | maxDD |
|---|---|---|---|---|
| 0.000 | 0.057 | +0.75 | +0.73 | −21.1 % |
| 0.020 | 0.006 | +0.83 | +0.83 | −20.4 % |
| 0.050 | 0.001 | +0.95 | **+0.95** | **−17.3 %** |

**Caveat honnête** : le gain n'est **pas** que des coûts. Le *Sharpe brut* monte
aussi (+0.75→+0.95) → la bande **ralentit** le signal (on tient les gagnants plus
longtemps), ce qui aide *parce que le momentum est lent* — même raison que reb=10 >
reb=1. Une bande large est donc une **généralisation continue** de la cadence de
rééquilibrage déjà en place, pas seulement une économie de coûts. Sur un book
**quantile équipondéré** (poids discrets 0/±step) la bande est ~sans effet : elle
vise les **poids continus** (chemin BL du pipeline live), d'où le test sur poids
continus.

## 6. Rappel honnête sur le plafond

Ces points améliorent **robustesse, sûreté et maintenabilité**, pas l'**edge**.
La performance reste plafonnée par la **donnée** (univers profond sans biais de
survie) — établi empiriquement sur 4 familles de signaux dans
`IMPROVEMENT_RESEARCH.md`. Ne pas confondre les deux axes.

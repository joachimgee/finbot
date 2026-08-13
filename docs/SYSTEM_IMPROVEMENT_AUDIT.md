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
- **Alphalens (Quantopian)** — *tearsheets* standard. ✅ **Fait** :
  `backtest/tearsheet.py` compose les métriques déjà codées mais **non branchées**
  (Sortino, Calmar, max drawdown de `metrics.py`) avec le PSR (`robustness.py`) en
  un tearsheet à partir d'un `SignalEvalResult`. Corrige au passage un bug d'unité
  (`max_dd_pct` est une fraction, pas un %). Ex. réel `momentum_12_1` : Sharpe
  net +0.76, **Sortino +0.92**, **Calmar +0.64**, **maxDD −13.9 %**, PSR 0.88
  (`run_tearsheet_alpaca.py`).
- **Exécution** — ✅ **Fait (planification)** : `trading/execution_algos.py`
  (TWAP, VWAP, POV, Almgren-Chriss + modèle de coût d'impact) et
  `framework.ScheduledExecution` (découpe en tranches à clés idempotentes uniques,
  via le gateway audité). Démo : 1-shot 125 k$ d'impact → TWAP 12,5 k$ (×10). §12.
  *Réserve honnête* : l'**étalement temps-réel** intraday exige un driver dédié
  (hors périmètre) ; le bénéfice ne se matérialise qu'à grande taille. À petite
  taille sur large-caps liquides, non prioritaire.
- **Détection de régime** — ✅ **Fait** : HMM gaussien 2 états (`backtest/regime.py`,
  numpy pur, `hmmlearn` absent) avec **filtre avant causal** (pas de Viterbi lissé →
  no look-ahead), ré-estimé en fenêtre glissante ; exposition = 1 − (1−rof)·P(état
  turbulent). Résultat réel (momentum_12_1) : drawdown −14.6 % → **−12.2 %** (rof=0.3,
  −16 %), Sharpe net +0.56 → +0.49 (coût de dé-risque habituel). **Bat le filtre
  MA200** (qui n'a quasi rien déclenché sur 2023-26, marché haussier). Overlay
  causal enfichable comme risk-off *data-driven* alternatif. Détail : §11.

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
5. **Séparation type LEAN** — ✅ **Fait** : quatre étages enfichables
   (Alpha→Construction→Risk→Execution) via `trading/framework.py`, injectables dans
   `LiveTradingPipeline`, défauts = logique existante (comportement inchangé). §9.

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

## 9. Détail #5 — séparation en couches enfichables (façon LEAN)

`trading/framework.py` définit quatre **Protocols** (contrats) et leurs
implémentations par défaut :

    Alpha  ─►  PortfolioConstruction  ─►  Risk  ─►  Execution
   data→signaux   signaux→poids cibles    veto/ajuste   poids→ordres soumis

| étage | contrat | défaut (délègue à) |
|---|---|---|
| `AlphaModel` | `generate(data) → signaux` | `_generate_signals` (signaux validés + abstention) |
| `PortfolioConstructionModel` | `construct(signaux, data) → poids` | `_construct_weights` (BL + cap + vol + bande) |
| `RiskModel` | `evaluate(poids, data) → (ok, poids)` | `_portfolio_risk_ok` (pré-trade corrélation-aware) |
| `ExecutionModel` | `execute(poids, data, dry_run) → résultats` | ordres → chokepoint audité |

Refactor **strangler** : `LiveTradingPipeline` compose désormais ces quatre étages
(`self.alpha/construction/risk_model/execution`), injectables au constructeur. Les
défauts reproduisent exactement l'ancien comportement (322 tests trading verts,
inchangés). Injecter un modèle custom remplace **un seul** étage sans toucher aux
autres — prouvé par test (alpha/construction/risk/execution custom). Bénéfice :
chaque couche est testable et remplaçable isolément (p.ex. brancher un exécuteur
TWAP, ou un autre modèle d'alpha) sans risque pour le reste du chemin.

*Le chokepoint d'ordres unique (mode-gate + RiskGuard + idempotence + audit +
journal) reste en aval de l'ExecutionModel : la sûreté n'est pas court-circuitable
par un exécuteur custom.*

## 10. Idées tirées des docs déconnectés (`docs/AUDITS/AUDIT_FORKS`)

Ces audits documentent 8 repos externes (backtesting.py, Riskfolio-Lib,
PyPortfolioOpt, ML4T, FinanceToolkit…). Deux idées concrètes en ont été tirées et
**testées via le portail** (discipline inchangée) :

**A. Momentum résiduel PCA** (`PORTFOLIO_PRO_RESEARCH` « décorrélation PCA/ICA »).
`backtest/residual_momentum.pca_residual_momentum_score` : retire les k premières
composantes principales (marché + secteur/style implicites, sans labels), momentum
sur le résidu. **Résout la décorrélation** que le résiduel mono-facteur ratait :
corr au momentum brut +0.87 → **+0.17** (k=5), Sharpe net **+0.81** (≈ brut). Non
inscrit (IC t=1.65 < 2, plafonné par la breadth sur 80 noms), mais **meilleur
candidat breadth de la session**. Détail dans `IMPROVEMENT_RESEARCH.md`.

**B. HRP en construction** (`AUDIT_RISKFOLIO_LIB`, López de Prado).
`portfolio/hrp.hrp_weights` (implémentation directe scipy, sans inversion de
matrice → robuste au bruit de covariance) + `framework.HRPConstruction` (le
momentum *sélectionne*, HRP *dimensionne*), enfichable via la couche #5. Résultat
réel (sizing du book momentum top-20 %, reb=10) :

| sizing | Sharpe net | turnover | maxDD |
|---|---|---|---|
| équipondéré (EW) | **+1.40** | 0.040 | −23.5 % |
| inverse-variance | +1.22 | 0.050 | −20.8 % |
| **HRP** | +1.29 | 0.060 | **−19.4 %** |

**Lecture honnête** : HRP livre sa promesse *là où la théorie l'attend* — le
**drawdown le plus bas** (−17 % vs EW) — mais **pas** le meilleur Sharpe : sur ~80
large-caps homogènes, l'edge du momentum est dans la **sélection**, pas la
pondération, et HRP échange du rendement contre moins de risque. Ce n'est pas un
free lunch mais un arbitrage risque/rendement. HRP reste **enfichable en option**
pour une config *risk-averse* ; son vrai gain apparaîtrait sur un univers plus large
et hétérogène (clusters de corrélation distincts) — encore le thème « données ».

## 11. Détail — détection de régime HMM

`backtest/regime.py` : HMM gaussien à 2 états sur le rendement marché équipondéré,
estimé par **Baum-Welch (EM) en numpy pur** (aucune dépendance ; `hmmlearn` absent).
États typiques : *calme* (faible vol) / *turbulent* (forte vol), identifiés par la
variance. **Anti-look-ahead strict** : on n'utilise pas `predict` (Viterbi lissé,
qui voit le futur) mais le **filtre avant** — `P(état_t | rendements ≤ t)` — et le
modèle est gelé sur une fenêtre d'apprentissage *passée*, ré-estimé périodiquement.
`regime_risk_series` renvoie une exposition ∈ [rof, 1] causale.

| variante (momentum_12_1) | Sharpe net | max drawdown | expo. moy. |
|---|---|---|---|
| brut (non géré) | +0.56 | −14.6 % | 1.00 |
| **régime-HMM rof=0.3** | +0.49 | **−12.2 %** | 0.86 |
| régime-HMM rof=0.5 | +0.51 | −12.9 % | 0.90 |
| réf. filtre tendance MA200 | +0.49 | −14.6 % | 0.98 |

**Lecture honnête** : le régime-HMM livre un vrai **−16 % de drawdown** et **bat le
filtre MA200** (qui n'a quasi rien déclenché — marché haussier 2023-26), au prix d'un
léger Sharpe (arbitrage de dé-risque classique, comme le vol-target et HRP). Ce n'est
pas un gain de rendement mais un **outil de risque data-driven** supérieur au filtre
naïf. Enfichable comme risk-off alternatif pour une config prudente (tests : 6, dont
recouvrement des régimes et **causalité vérifiée**).

## 12. Détail — algorithmes d'exécution

`trading/execution_algos.py` : logique de **planification pure** (quantités enfants
entières, somme préservée), testée :

| algo | principe |
|---|---|
| `twap_schedule` | tranches égales dans le temps (baseline) |
| `vwap_schedule` | tranches ∝ profil de volume (suivre le marché) |
| `pov_schedule` | *participation of volume* : enfant = min(reste, part·volume) |
| `almgren_chriss_schedule` | trajectoire optimale impact↔risque (urgence κ) |
| `expected_impact_cost` | coût d'impact (modèle AC) pour comparer les plannings |

Démo (`run_execution_algos_demo.py`, ordre 50 k / ADV 1 M) — coût d'impact
temporaire : **1-shot 125 k$ → TWAP 12,5 k$ (×10)** ; Almgren-Chriss urgent (κ élevé)
= front-loaded = moins de risque de timing, plus d'impact. `ScheduledExecution`
(couche #5) découpe chaque ordre et soumet les tranches — **clé idempotente unique
par tranche** (sinon deux tranches de même quantité seraient dédupliquées par le
gateway ; un passthrough `idempotency_key` a été ajouté au chemin d'exécution).

**Réserve honnête** : le daemon n'est pas un moteur temps-réel — les tranches
partent en séquence, sans espacement intraday. Le *plumbing* (découpe + idempotence
+ chokepoint audité) est prêt ; l'espacement réel (et donc le vrai gain d'impact)
demande un **driver d'exécution temps-réel**, à ajouter le jour où le notional le
justifie. Le chokepoint audité (mode-gate + RiskGuard + journal) reste en aval :
chaque tranche est risk-checkée.

## 6. Rappel honnête sur le plafond

Ces points améliorent **robustesse, sûreté et maintenabilité**, pas l'**edge**.
La performance reste plafonnée par la **donnée** (univers profond sans biais de
survie) — établi empiriquement sur 4 familles de signaux dans
`IMPROVEMENT_RESEARCH.md`. Ne pas confondre les deux axes.

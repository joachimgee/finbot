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

## 13. Multi-stratégie en paper trading (forward-test)

Le book combiné (momentum + PCA-résiduel + paires, risk-weighted) est **déployable
en paper** via la couche enfichable #5 : `trading/multi_strategy_book.combined_book`
produit les poids cibles **long/short** du jour ; `framework.MultiStrategyConstruction`
les branche dans le `LiveTradingPipeline` ; `run_multi_strategy_paper.py` exécute
contre le compte **paper** Alpaca (double-verrou : jamais live sans jeton).

Exécution réelle (paper) : book **market-neutral** (31 positions, brut=1.00,
net=+0.00, 16 longs / 15 shorts) soumis via l'**OrderGateway audité** (mode-gate +
RiskGuard + journal). Réconciliation honnête : ordres **soumis mais non remplis**
(hors séance → en file pour la prochaine ouverture) — l'audit détecte correctement
l'écart soumis≠rempli, ce qui est le comportement attendu.

⚠️ **Discipline** : PCA-résiduel & paires ne sont **pas validés** (seul momentum
l'est) → **paper uniquement**, forward-test pour accumuler un track record avant
toute décision. Le passage live resterait interdit par le double-verrou.

## 6. Rappel honnête sur le plafond

Ces points améliorent **robustesse, sûreté et maintenabilité**, pas l'**edge**.
La performance reste plafonnée par la **donnée** (univers profond sans biais de
survie) — établi empiriquement sur 4 familles de signaux dans
`IMPROVEMENT_RESEARCH.md`. Ne pas confondre les deux axes.

---

## 14. Revue d'état 2026-08-19 — « reste-t-il quelque chose à faire ? »

Audit contradictoire du système tel qu'il tourne, croisé avec
[NautilusTrader](https://nautilustrader.io/) (parité backtest/live, réconciliation,
persistance d'état, risque pré-trade) et [QuantConnect/LEAN](https://www.quantconnect.com/)
(chaîne recherche → backtest → paper → live). Chiffres mesurés, pas estimés :
**203 modules src / 56 436 LOC / 2 404 tests**.

### 14.1 🔴 Défaut corrigé — la réconciliation ne pouvait JAMAIS passer

`reconcile_orders` compare le journal du run aux ordres du broker, et signale comme
« inattendu chez le broker » (= ordre ayant contourné le chokepoint audité) tout ordre
broker absent du journal. Or le runner passait `get_orders(status="all", limit=400)` :
les **400 derniers ordres du COMPTE**, stratégies précédentes comprises.

Mesuré sur le compte réel, en rejouant le seul run qui avait produit un rapport :

| | appariés | manquants | **inattendus** | verdict |
|---|---|---|---|---|
| avant (sans bornage) | 56 | 0 | **88** | 🚨 ÉCART |
| après (borné au run) | 56 | 0 | **0** | ✅ OK |

Les 88 « anomalies » étaient des ordres ORCL/ABT du book momentum et de la liquidation.
Conséquence : le **critère #1 du runbook (20 runs consécutifs sans écart) était
structurellement inatteignable** — et une alarme qui ne peut jamais s'éteindre n'est
plus une alarme, elle éduque à l'ignorer.

Correctif : `reconcile_orders(..., since=run_start)` ignore les ordres antérieurs au
début du run. **Le bornage ne relâche rien du côté qui compte** : un ordre journalisé
introuvable chez le broker reste détecté quel que soit `since`, et tout ordre postérieur
au début du run absent du journal reste un drapeau rouge (5 tests de régression).

### 14.2 ⚠️ Défauts identifiés, NON corrigés (décision à prendre)

| # | Constat | Gravité | Pourquoi c'est laissé ouvert |
|---|---|---|---|
| A | ~~Le critère #1 n'avance que les jours de rééquilibrage (~1,7 an)~~ → **CORRIGÉ le 2026-08-20**, cf. §16. | ~~haute~~ | Réconciliation de **positions** les jours de book tenu + le rapport regarde enfin le bon book. 1,7 an → ~4 semaines. |
| B | ~~La formule d'Amihud est écrite 5 fois~~ → **CORRIGÉ le 2026-08-19**, cf. §15. | ~~haute~~ | Définition unique dans `backtest/illiquidity.py`, consommée par le live, le moniteur et les 5 scripts. Parité vérifiée sur données + garde-fou anti-duplication. |
| C | **Aucun contrôle de « shortable / easy-to-borrow » dans le chemin d'ordre.** | **basse** | Vérifié sur le book réel : **28/28 des shorts sont `shortable` ET `easy_to_borrow`**. Structurel, pas chanceux : on shorte par construction les titres *les plus liquides*. Reste un contrôle pré-trade standard ailleurs, à ajouter par hygiène. |
| D | **Aucun plafond de participation / ADV à l'ordre.** La capacité (~19 M$) a été mesurée en backtest, rien ne l'applique en live. | basse | À 97 k$ d'equity sur des titres à 31 M$/jour de volume médian, la participation est de l'ordre de **0,003 %** — immatériel. Devient réel si le capital change d'ordre de grandeur. |
| E | **`execution_algos` (Almgren-Chriss/TWAP) et `SlicedExecution` existent mais ne sont pas câblés** : les ordres partent au marché. | basse | Même raison que D : sans contrainte de capacité, découper n'apporte rien. À câbler le jour où le capital le justifie. |

### 14.3 Comparaison honnête aux systèmes de référence

| capacité | FinBot | NautilusTrader / LEAN |
|---|---|---|
| Portail de validation statistique (IC t, Sharpe net, **DSR, PBO**, purged CV) | ✅ **plus strict** que les deux | ⚪ absent (ce sont des moteurs, pas des juges) |
| Réconciliation journal ↔ broker | ✅ (bornée depuis ce jour) | ✅ |
| Chokepoint d'exécution unique + double-verrou paper/live | ✅ | ✅ |
| Kill-switch + halte gradée sans liquidation auto | ✅ (fondée Kaminski & Lo 2014) | ⚪ variable |
| Audit quotidien du book + moniteur de décroissance du signal | ✅ | ⚪ à écrire soi-même |
| Fondamentaux et univers **point-in-time** | ✅ | ⚪ dépend du fournisseur |
| **Parité backtest/live (un seul chemin de code)** | ❌ **écart n°1** | ✅ argument central |
| Persistance d'état / redémarrage | ⚠️ contourné (garde de cadence via l'historique broker, sessions éphémères) | ✅ (Redis) |
| Contrôles pré-trade (notionnel, borrow, rate-limit, marge) | ⚠️ partiels (RiskGuard : concentration, levier, drawdown ; pas de borrow) | ✅ complets |
| Modèle de fill / latence / carnet | ❌ coûts en bps constants | ✅ configurable |

**Lecture.** Le système est **en avance** sur la partie que la plupart des dépôts
bâclent — la discipline de preuve — et **en retard** sur la partie que les moteurs
industriels traitent par construction — l'unicité du chemin de code. Ce n'est pas un
hasard : ce dépôt a été construit comme un laboratoire de validation, pas comme un
moteur d'exécution.

### 14.4 Ce qui reste vraiment à faire, par ordre

1. **(B) Définition unique du signal**, partagée backtest ↔ live. Cause racine
   démontrée de deux bugs en une journée. Le seul chantier de conception restant.
2. **(A) Décider** de la sémantique de « run propre » pour le critère #1, sinon le
   passage au live est bloqué ~1,7 an par construction.
3. **Le forward-test Amihud doit tourner.** C'est la seule chose qui puisse trancher
   la question du biais de survie, et aucun refactor ne la remplacera. Rien à coder :
   il faut du **temps calendaire**.
4. (C) puis (E)/(D) — hygiène, à faire quand le capital le justifie.

**Non, le système n'est pas « fini » — mais ce qui manque n'est plus de la recherche.**
Les quatre bloquants du rapport de live-readiness sont : #1 réconciliation (voir A),
#3 **registre vide** (aucun signal validé — c'est l'état honnête), #6 état de cadence,
#7 webhook d'alerte. Aucun ne se résout par un modèle de plus.


---

## 15. Correctif B — définition unique du signal, partagée backtest ↔ live

Le point (B) du §14 était l'écart n°1 face aux moteurs industriels, et la **cause
racine démontrée** des deux bugs du 18-08 (bande de non-transaction gelante, horizon
d'IC du moniteur). Aucun des deux n'était une erreur de formule : les deux étaient des
erreurs de **duplication** — deux endroits censés dire la même chose, et rien pour
l'imposer.

### Ce qui a été fait

`backtest/illiquidity.py` devient la **définition canonique** et unique :

* `amihud_illiquidity(close, volume, window)` — la formule ;
* `prepare_panels(close, volume, min_history_frac)` — le prétraitement (c'était aussi
  une divergence : les scripts filtraient sur l'historique, le chemin live non) ;
* `amihud_weights(row, quantile, min_names)` — la construction du book, avec abstention
  sous `min_names` ;
* `AmihudSpec` (frozen) — les **paramètres validés** : `window=60`, `quantile=0.2`,
  `rebalance_every=21`, `cost_bps=60`, `min_names=20`, `no_trade_band=0.0`. Le chemin
  live ne redéfinit plus ses défauts, il **lit** la spécification.

Consommateurs branchés : `trading/framework.py` (`AmihudConstruction`),
`monitor_amihud_decay.py`, `run_smallcap_illiquidity.py`,
`run_amihud_module_transfer.py`, `run_amihud_window_gate.py`,
`run_microstructure_validation_alpaca.py`.

### La sixième copie

Le grep manuel en avait trouvé cinq. Le **test anti-duplication** en a trouvé une
**sixième** — `run_microstructure_validation_alpaca.py` — et elle utilisait déjà une
échelle `×1e6` là où les autres utilisaient `×1e9`. Neutre sur les rangs, donc sans
conséquence numérique, mais c'était **la dérive en train de commencer**. C'est
exactement l'argument pour lequel ce test existe : la vigilance humaine avait déjà
laissé passer 1 copie sur 6.

### Vérification — un refactor ne doit RIEN changer

| contrôle | avant | après |
|---|---|---|
| `run_amihud_window_gate.py` (5 fenêtres, PBO, DSR) | 5/5, PBO 43.7 %, IC t +4.43/+4.34/+4.36/+4.44/+4.54 | **identique au bit près** |
| `run_amihud_module_transfer.py` (16 configs) | réf. +2.13, PBO 61.5 %, DSR 0.999 | **identique** |
| **book live** (mêmes données, ancien vs nouveau chemin) | 50 lignes | **50 lignes, mêmes symboles, écart de poids max 0.00e+00** |
| moniteur Amihud | HEALTHY | HEALTHY |
| suites de tests | vertes | **815 passés** + 15 nouveaux |

### Ce qui garantit que ça tient

Deux tests, et c'est la distinction qui compte :

1. **Parité sur données** (`test_live_and_backtest_produce_the_same_book`, plus une
   variante sur panel dégradé — trous, titres lacunaires, volumes nuls). Vérifier
   « les deux chemins appellent la même fonction » ne suffit pas : une refactorisation
   peut défaire ça sans bruit. On vérifie qu'ils **produisent le même book**.
2. **Garde anti-duplication** (`test_no_duplicate_amihud_formula_in_the_repo`) : la
   signature `|r| / $volume` ne doit apparaître que dans le module canonique. Sans lui,
   le prochain script de recherche la recopiera — c'est ainsi qu'on est arrivé à six.

**Limite assumée** : ce chantier unifie *le signal d'Amihud*, pas *l'ensemble du
moteur*. La parité complète à la NautilusTrader (même horloge, même modèle
d'événements, même simulateur de fill en backtest et en live) reste hors de portée de
ce dépôt, et n'est pas nécessaire pour un book rééquilibré à 21 jours. Ce qui est
désormais garanti, c'est que **le book qui trade est celui qui a été validé**.


---

## 16. Correctif A — le critère #1 peut enfin avancer (1,7 an → ~4 semaines)

Le §14.1 avait corrigé la réconciliation d'**ordres** (bornage au run). Restait le
point (A) : ce contrôle ne s'exécute que les **jours de rééquilibrage**, soit 1 séance
sur 21. À 20 runs propres exigés, le critère demandait ~1,7 an. Ce n'est pas une porte
d'accès, c'est un mur.

### La question de conception, et pourquoi elle n'était pas triviale

Corriger, c'était **redéfinir ce qu'est un « run propre »** pour un garde-fou de
sûreté. La contrainte dure : `logs/` n'est pas versionné, donc les journaux **ne
survivent pas aux sessions éphémères**. La seule source de vérité durable est le
**broker** — même raison qui avait fait passer la garde de cadence sur l'historique
d'ordres. Le contrôle des jours tenus doit donc se reconstruire depuis `get_orders`.

### Ce qui a été mesuré avant de coder

Reconstruction des positions en sommant les ordres remplis, comparée aux positions
réelles du compte :

| | résultat |
|---|---|
| positions détenues appariées (sens **et** quantité) | **56/56 exactes** |
| détenues sans explication | **0** |
| attendues non détenues | 22 — **tous** des large-caps de l'ancien book momentum liquidé |

Les 22 sont un pur artefact de **troncature** : `get_orders` ne renvoie qu'une fenêtre,
et un titre dont les achats sont hors fenêtre mais les ventes dedans apparaît
« attendu short, non détenu » sans qu'il se soit rien passé. Une clôture normale, elle,
ne fait aucun bruit (le net tombe à zéro, le symbole disparaît de l'attendu).

### L'asymétrie assumée

Les deux directions n'ont pas la même valeur de preuve, donc elles ne pèsent pas pareil :

* **détenu sans explication → ÉCHEC.** Une ligne que l'historique ne justifie pas
  signifie qu'un ordre a contourné le chokepoint, ou qu'une opération sur titre a créé
  une position. Robuste : mesuré 0/56.
* **écart de quantité ou de sens → ÉCHEC.** Robuste : mesuré 56/56 exactes.
* **attendu non détenu → INFORMATIF.** En faire un échec reproduirait exactement le
  défaut corrigé au §14.1 : une alarme perpétuellement rouge, donc ignorée.

Le contrôle **peut échouer** — c'est ce que vérifient d'abord ses tests (position
étrangère, écart de quantité, inversion de sens), avant de vérifier qu'il reste vert
sur un book sain.

### Un troisième défaut trouvé en vérifiant

Le contrôle écrivait bien son rapport, et le critère restait à `streak=0`. Cause : les
motifs par défaut du rapport de readiness nommaient `multistrat_paper_*` **en dur** et
ne voyaient donc pas `amihud_paper_*`. **Le rapport mesurait la préparation au live de
stratégies éteintes en ignorant la seule en forward-test.** Un garde-fou qui regarde
ailleurs ne garde rien.

Motif générique `logs/*_paper_*.jsonl`, qui s'auto-entretient, plus un test qui vérifie
que les motifs couvrent les noms de journaux réellement produits.

### Résultat

| | avant | après |
|---|---|---|
| journaux vus par le rapport | 6 | **24** |
| critère #1 | `streak=0` | **`streak=1`**, +1 par séance |
| délai pour 20 runs propres | ~1,7 an | **~4 semaines** |

Le critère reste **bloquant** aujourd'hui, et c'est normal : il doit accumuler ses
20 séances. Ce qui a changé, c'est qu'il le **peut**.

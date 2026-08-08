# FinBot — Évaluation du système & feuille de route

> Document vivant. Établi à partir d'une lecture réelle du code (≈ 50 200 LOC src,
> 33 914 LOC tests, 180 fichiers src, 33 modules). Objet : connaître honnêtement
> l'état du système, mesurer l'écart au but, et lister — avec checklists — ce qu'il
> faut **corriger / construire / élaguer** pour l'atteindre.
>
> Convention : `[ ]` à faire · `[~]` partiel · `[x]` fait. Aucune complaisance —
> le code « mauvais » est nommé.

---

## 0. Le but du système

**Ce que dit le README** : « application d'analyse financière (sentiment + ML +
optimisation de portefeuille) pour générer des recommandations d'actions ». C'est
un but *large et marketing*.

**Ce que le système essaie réellement d'être** (déduit du code et de la
trajectoire) : un **système de trading automatisé quotidien** sur actions US,
exécuté via Alpaca (paper → live), qui sélectionne un univers, calcule des
signaux multi-sources, construit un portefeuille et **soumet des ordres réels**.

> ⚠️ **À confirmer avec le porteur du projet** : le but est-il (A) un vrai système
> de trading qui engage de l'argent, ou (B) un outil d'analyse/reco sans exécution ?
> Toute la trajectoire récente pointe vers (A) ; cette feuille de route suppose (A),
> « sûreté et correction d'abord ». Si (B), l'axe exécution/sûreté se réduit.

**Critère de réussite proposé** (mesurable) : sur données réelles, out-of-sample,
net de coûts, une stratégie dont l'edge est **statistiquement significatif** (IC
t > 2) **et** économiquement positif (Sharpe net > 0), exécutée par un chemin
**unique, audité, sûr**, observable et reproductible.

---

## 1. Carte de la réalité (vivant vs mort)

Le système est **massivement sur-construit et accrété** (nommage « Phase 5.x /
Phase F », rapports « delivery/integration » multiples). Sur ≈ 50 k LOC, seule une
minorité est réellement câblée au chemin de décision.

### 1.1 Le vrai chemin de production (ce que le daemon exécute)

`scripts/professional_analysis_daemon.py` est le point d'entrée planifié. Flux réel :

1. **Univers** — `universe/universe_selector_enhanced` (FinanceDatabase).
2. **Pré-analyse** — `preanalysis/daily_preanalysis` + `learning/portfolio_learner`
   (drift, décisions SELL/HOLD/BUY_MORE sur positions courantes).
3. **Signaux** — `integration/signal_fusion_engine` (**SignalFusionEngine**) +
   `compute_professional_score` (de `scripts/professional_analysis.py`) →
   `composite_score` / `confidence` par symbole.
4. **Orchestrateur** — `analysis/master_orchestrator` en **dry-run uniquement**
   (analyse/reporting ; son exécution réelle est neutralisée, cf. §2).
5. **Exécution (étape 10)** — sizing adaptatif → `trading/order_gateway`
   (**OrderGateway** : mode-gate + RiskGuard + idempotence + audit) → Alpaca ;
   puis **réconciliation** + **journal** + **manifeste**.

### 1.2 Ce qui est RÉEL et de bonne qualité

- [x] **Chemin d'exécution durci** (`trading/`) : `safety` (fail-safe paper/live),
  `order_gateway` (chokepoint unique), `risk_guard` (limites + circuit breaker),
  `account_monitor`, `journal`, `reconciliation`, `run_manifest`. Testé, câblé au
  daemon. **C'est le socle sain.**
- [x] **Infra de validation** (`backtest/signal_evaluation`, `factor_combiner`,
  `classic_factors`) : IC/Sharpe net walk-forward OOS, coûts inclus. Réel, testé.
- [x] **Facteurs price-based validés OOS** (8 facteurs) — voir §3. `momentum_12_1`
  significatif et net-positif sur données réelles Alpaca.
- [x] **Sentiment** (`sentiment/`) : FinBERT réel (ProsusAI/finbert) sur news scrapées.
- [x] **Données prix** (`data/`) : `pit_loader` (Alpaca ajusté, fail-safe),
  `alpaca_history`. Réel.
- [~] **`compute_professional_score`** : combinaison IC-weighted de catégories de
  facteurs — **réel** (pas un stub), mais dépend de systèmes de facteurs redondants.

### 1.3 Ce qui est MORT, STUB, ou ORPHELIN (le poids inutile)

Modules importés par **0** autre fichier src (orphelins complets) :
`ml_features` (les « 114 facteurs ML »), `async_pipeline`, `database`.

Modules **vides** (0 LOC réelle) : `api/`, `dashboard/`, `recommendations/`,
`backtesting/`.

Sous-systèmes **non câblés au chemin de décision réel** (orphelins ou quasi) :

- [ ] **`rl/`** (2 831 LOC, 27 fichiers) — RL pour trading, **aucun modèle entraîné**,
  non câblé. Cathédrale.
- [ ] **`deep_learning/`** (961 LOC) — LSTM/GRU/Transformer, **TensorFlow absent**,
  aucun poids chargé. Stub.
- [ ] **`ml/`** (6 394 LOC, « 100+ alpha factors ») — importé par 2 fichiers ; large
  chevauchement avec `ml_features`, `ml_features_advanced`, `features`,
  `backtest/classic_factors`. **5 systèmes de features/facteurs concurrents.**
- [ ] **`derivatives/`** (1 454 LOC) — options ; importé par 1 fichier.
- [ ] **`risk/`** (2 777 LOC) — mesure de risque/stress, distinct de
  `trading/risk_guard` (le seul réellement appliqué). Importé par 3.

Signaux stub **dans le chemin réel** (grave) :

- [ ] **`SignalFusionEngine`** pondère ≈ **50 % sur des sources stub** :
  `ml_lstm` (0.20, proxy momentum déguisé), `ml_factor` (0.10, constante ~0.5),
  `rl` (≈ 0.20, constante ~0.5). Seuls `technical` (0.20) et `sentiment` (0.15)
  sont potentiellement réels. **Le daemon trade en partie sur du bruit constant.**

### 1.4 Redondances structurelles

- [ ] `portfolio/` **vs** `portfolio_optimization/` (optimisation en double).
- [ ] `strategy/` **vs** `strategies/` (fusion de signaux en double).
- [ ] `backtest/` **vs** `backtesting/` (ce dernier vide).
- [ ] `ml/` **vs** `ml_features/` **vs** `ml_features_advanced/` **vs** `features/`
  (features/facteurs en quadruple).
- [ ] ≈ 5 scripts « daily » historiques (2 déjà dépréciés ; le daemon est le canonique).
- [ ] 40+ fichiers `docs/`, dont de nombreux « delivery/integration reports »
  aspirationnels à réconcilier avec la réalité.

---

## 2. L'écart au but — constats critiques

1. **Deux chemins de trading parallèles, et les corrections ont visé le mauvais.**
   - Le **daemon** (production) trade via `SignalFusionEngine` + `professional_score`.
   - Le **`LiveTradingPipeline`** (que les corrections récentes de *signaux* ont
     visé : abstention des stubs, Black-Litterman, momentum 12-1 validé) est
     **orphelin de la prod** — instancié seulement par l'orchestrateur (mort) et 2
     scripts de test. **Ses améliorations de signaux n'atteignent pas le daemon.**
   - En revanche, le **durcissement d'exécution** (chokepoint/journal/réconciliation)
     **est** bien câblé au daemon. Donc : *exécution sûre ✓, signaux du daemon encore
     stub-lourds ✗*.

2. **Le chemin de décision du daemon repose en partie sur des constantes.**
   `SignalFusionEngine` injecte ml_factor/rl ≈ 0.5 constants + ml_lstm proxy : la
   moitié du poids de fusion n'a aucune valeur prédictive. C'est la **même classe de
   bug** que celle corrigée dans le pipeline — mais sur le chemin réellement exécuté.

3. **L'orchestrateur est neutralisé mais toujours appelé (en dry-run).** Son chemin
   d'exécution a été délibérément désactivé (données synthétiques + méthodes
   d'optimiseur cassées). Il ne trade pas, mais consomme du temps et entretient la
   confusion des « deux systèmes ».

4. **Données fondamentales absentes / biais de survie.** L'univers = membres
   *actuels* de FinanceDatabase (biais de survie) ; pas de fondamentaux point-in-time
   → tout facteur value/quality est aujourd'hui infaisable honnêtement.

5. **Poids mort massif.** ≈ 30–35 k LOC (rl, deep_learning, la majeure partie de ml,
   ml_features*, derivatives, modules vides) ne servent pas la décision, mais
   augmentent la surface de bug, le temps de test et la charge cognitive.

6. **Coûts non calibrés.** Le modèle de coûts (commission/slippage bps) est un outil ;
   ses valeurs réelles pour Alpaca ne sont pas calibrées.

---

## 3. Ce qui a été validé sur données réelles (acquis)

Validation OOS Alpaca (walk-forward, coûts inclus) :

- **Univers large-caps liquides (~80)** : seuls `momentum_12_1` (t≈3.2) et
  `momentum_6_1` (t≈2.1) sont significatifs ; `momentum_12_1` net-positif.
- **Univers large (516 titres réels)** : **7/8 facteurs significatifs** (|t| 3.8→7.8)
  — reversal/lottery/low-vol/52w s'expriment hors mega-caps — **mais** la plupart ne
  sont **pas** profitables nets de coûts en rebalancement quotidien.
- **⚠️ Anomalie** : le combinateur affiche un IC négatif (t≈−1.96) *et* un Sharpe net
  positif (+0.43) sur l'univers large — incohérent, **à investiguer avant confiance**.

Conclusion : `momentum_12_1` est l'edge robuste et *tradeable* aujourd'hui ; les
autres facteurs sont réels mais exigent une **calibration de la période de
rebalancement** (levier turnover/coûts) pour devenir rentables.

---

## 4. Feuille de route (par priorité, avec checklists)

> Principe directeur inchangé : **correction & sûreté d'abord**, réparer en place,
> rien ne trade sur un stub, rien ne touche à l'argent sans validation OOS nette.

### P0 — Réconcilier les deux chemins & purger le stub du chemin RÉEL *(bloquant)*

Le trou n°1 : le daemon trade via un fusion engine stub-lourd, pendant que les
bonnes corrections vivent sur un pipeline orphelin.

- [ ] **Décider du chemin canonique unique** : soit (a) faire du `LiveTradingPipeline`
  (déjà corrigé, testé) le moteur de décision du daemon, soit (b) porter les
  corrections dans `SignalFusionEngine` + step-10. Recommandé : **(a)** — un seul
  moteur signaux→allocation→ordres, déjà durci.
- [ ] **Quarantaine des sources stub du `SignalFusionEngine`** (si (b) retenu) :
  `ml_lstm`/`ml_factor`/`rl` s'abstiennent (poids 0 + log) au lieu d'injecter des
  constantes ; renormaliser sur les sources réelles.
- [ ] **Supprimer le double moteur** : un seul chemin signaux→ordres exécuté par le
  daemon ; l'autre est retiré du chemin d'import de prod (ou supprimé).
- [ ] **Tests bout-en-bout du daemon** (broker mocké) : le signal réel n'est jamais
  une constante ; chaque ordre passe par `OrderGateway`.

### P1 — Rendre l'edge tradeable & fiabiliser la décision

- [ ] **Câbler `momentum_12_1` validé comme source du chemin canonique** (fait dans
  le pipeline ; à propager au chemin réellement exécuté selon la décision P0).
- [ ] **Sweep de période de rebalancement** (`rebalance_every` = 5/10/21) sur les 7
  facteurs significatifs → retenir la config *tradeable* (Sharpe net > 0). Documenter.
- [ ] **Investiguer l'anomalie du combinateur** (IC négatif / Sharpe net positif) :
  bug de construction du portefeuille combiné ? surapprentissage ? sign-flip ?
  Ne pas déployer le combinateur avant résolution.
- [ ] **Portail de validation** : *aucun* facteur/source n'entre dans la décision
  réelle sans IC t > 2 **et** Sharpe net > 0 OOS. En faire une règle vérifiée.
- [ ] **Calibrer le modèle de coûts** aux frais/slippage réels d'Alpaca.

### P2 — Intégrité des données *(débloque value/quality)*

- [ ] **Univers point-in-time** (anti biais de survie) : membres *historiques*, pas
  courants ; inclure les delistings.
- [ ] **Fondamentaux point-in-time** (fournisseur as-of : Polygon/FMP/…), même
  contrat fail-safe que `pit_loader` (pas de source réelle → abstention/erreur).
- [ ] Une fois les fondamentaux réels : **facteurs value/quality** validés OOS, puis
  intégrés au mérite.

### P3 — Élaguer la cathédrale *(réduire la surface de bug)*

Prudemment, sans casser le chemin canonique. Chaque suppression = tests verts.

- [ ] **Supprimer les modules vides** : `api/`, `dashboard/`, `recommendations/`,
  `backtesting/` (ou les implémenter au mérite).
- [ ] **Supprimer/geler les orphelins purs** : `async_pipeline/`, `database/`,
  `ml_features/` (0 import) — après confirmation qu'aucun plan ne les réactive.
- [ ] **Fusionner les redondances** : `portfolio` + `portfolio_optimization` ;
  `strategy` + `strategies` ; retirer `backtest`/`backtesting` doublon.
- [ ] **Unifier les systèmes de features** : un seul moteur de facteurs
  (`backtest/classic_factors` validé + le nécessaire de `features`/`ml`), retirer
  les 3 autres ou les marquer expérimentaux hors chemin de prod.
- [ ] **RL / deep_learning** : les sortir du chemin de prod et les marquer
  *recherche expérimentale* explicitement (ou supprimer). Ne rejoignent la décision
  que via le portail de validation, jamais par défaut.
- [ ] **Neutraliser/retirer l'orchestrateur** de la boucle du daemon si le chemin
  canonique le remplace (aujourd'hui appelé en dry-run pour du reporting seulement).

### P4 — Ops & confiance avant argent réel

- [x] **Journal d'exécution + réconciliation + manifeste** (fait).
- [ ] **Suivi P&L** exploitable (paper puis live) à partir du journal + snapshots.
- [ ] **Alerting** sur échec de run / circuit breaker / écart de réconciliation
  (au-delà du log ERROR actuel : notification réelle).
- [ ] **Runbook paper→live** : critères chiffrés de passage, procédure kill-switch
  testée, checklist d'activation `FINBOT_ENABLE_LIVE_TRADING`.

### P5 — Hygiène documentaire

- [ ] **Réconcilier `docs/`** : archiver/supprimer les « delivery/integration
  reports » aspirationnels ; garder une architecture et un README qui décrivent le
  système **réel** (le chemin canonique), pas l'intention.
- [ ] Faire de ce document la **source de vérité** de l'état et du plan.

---

## 5. Prochaine action recommandée

**P0 en premier** : trancher le chemin canonique unique (recommandé : promouvoir le
`LiveTradingPipeline` déjà durci comme moteur de décision du daemon) et **purger le
stub du chemin réellement exécuté**. C'est le point où « le système trade sur du
bruit » se referme — tout le reste (facteurs, données, élagage) vient après.

---

### Informations à obtenir (questions ouvertes)

- [ ] Confirmer le but : trading réel (A) vs analyse/reco (B).
- [ ] Fournisseur de fondamentaux point-in-time souhaité (budget/API) ?
- [ ] Intention réelle sur `rl/` et `deep_learning/` : recherche à conserver, ou à
  supprimer ?
- [ ] Capital cible et tolérance au risque (dimensionne RiskGuard et le passage live).

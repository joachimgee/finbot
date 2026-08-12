# FinBot — Pistes d'amélioration (recherche externe → code réel)

> Recherche sur des systèmes/repos reconnus et la littérature performante, mappée
> sur l'**état réel** de FinBot (cf. [`CANONICAL_ARCHITECTURE.md`](CANONICAL_ARCHITECTURE.md)) :
> **un seul** signal validé (`momentum_12_1`, cross-sectionnel, reb=10, Sharpe net
> +0.76), portail `IC t>2 ET Sharpe net>0` en walk-forward, univers ~12-80
> large-caps, allocation Black-Litterman + cap de concentration. Priorisé par
> **impact × faisabilité**.

---

## Tier 1 — Améliorer le SEUL edge prouvé (impact immédiat, faible risque)

### 1.1 Momentum piloté par la volatilité (*risk-managed momentum*)
**Constat externe.** Barroso & Santa-Clara (2015, *Momentum has its Moments*) :
le risque du momentum est prévisible par sa **propre variance réalisée** ; scaler
la position par l'inverse de la vol réalisée (cible ~12 % annualisée) **élimine
quasiment les krachs de momentum et fait passer le Sharpe de 0.53 à 0.97** (≈ ×2).
Même principe chez Moskowitz-Ooi-Pedersen (*Time Series Momentum*) et AQR (scaler à
vol constante 10 %).

**Chez FinBot.** Le momentum 12-1 est utilisé **brut** (`tanh(mom*3)`), sans
gestion de vol, dans `live_trading_pipeline._generate_signals`. Le drawdown paper
n'est pas maîtrisé.

**Action concrète.** Multiplier le poids/score du signal momentum par
`vol_cible / vol_réalisée_récente` (vol EWMA 3-6 mois), plafonné. À faire côté
allocation (`compute_target_weights`) ou signal. **Re-valider par le portail** —
attendu : Sharpe net ↑ et drawdown ↓. *Le plus haut ratio valeur/effort du lot.*

### 1.2 Ciblage de volatilité au niveau du portefeuille + overlay risk-off
**Externe.** AQR (*Trends Everywhere*, *Macro Momentum*) : scaler l'exposition
totale à une vol cible ; les stratégies trend réduisent l'exposition en régime
adverse. Overlay classique : réduire l'exposition quand l'indice est sous sa
moyenne 200 j.

**Chez FinBot.** Exposition ≈ pleinement investie (somme des poids ≈ 1), pas de
régulation de vol ni de filtre de régime.

**Action.** Un `TargetVolSizer` : échelle l'exposition brute pour viser ~10 % de
vol ex-ante ; un filtre de tendance marché (SPY vs 200 j) réduit l'exposition en
risk-off. Câbler dans l'allocation, avant l'`OrderGateway`.

---

## Tier 2 — Augmenter la *breadth* (loi fondamentale de la gestion active)

**Externe.** Grinold-Kahn : **IR ≈ IC × √Breadth**. Un IR élevé exige soit un IC
plus fort, soit **plus de paris indépendants** (nombre de titres × nombre de
signaux décorrélés). Attention : accroître la breadth peut baisser l'IC (bruit) —
c'est un compromis.

**Chez FinBot (le vrai plafond).** **1** signal lent sur ~12-80 large-caps →
breadth faible → IR structurellement plafonné. Cela **explique honnêtement**
pourquoi value/quality et sentiment n'ont pas passé le portail : ce ne sont pas
juste de « mauvais facteurs », c'est aussi que l'espace de paris est étroit.

**Actions.**
- **Ajouter des signaux *indépendants* validés** (chacun via le portail) :
  *time-series momentum* (ensemble 1/3/12 mois, vol-scalé — cf. 1.1),
  *momentum résiduel/idiosyncratique* (Blitz : plus robuste que le momentum brut),
  *reversal court terme* proprement construit. Chaque signal qui passe le portail
  est combiné par **risk-weighting** (pas le combinateur ridge, écarté — cf.
  anomalie P1).
- **Élargir l'univers** (mid/small-caps) : plus de titres = plus de breadth *et*
  plus de dispersion (là où value a un edge). **Bloqué** par les prix des delistés
  (biais de survie 36.8 % mesuré) → nécessite un dataset sans biais (Sharadar/CRSP).

### ✅ Fait (Tier 2) — time-series momentum testé, et REJETÉ honnêtement

Implémenté `backtest/timeseries_momentum.py` (`tsmom_ensemble_score` : ensemble
1/3/12 mois des rendements propres, **vol-normalisé** — un t-stat de tendance
comparable entre actifs, sans look-ahead) et passé par EXACTEMENT le portail
(`run_tsmom_validation_alpaca.py`, mêmes coûts Alpaca, reb=10, 5 fenêtres OOS,
+ DSR avec 33 essais comptés).

**Verdict réel** (753 j × 80 large-caps, 2023-08→2026-07) :

| critère | valeur | seuil | passe ? |
|---|---|---|---|
| IC t-stat | **+1.01** | > 2 | ❌ |
| Sharpe net | +0.27 | > 0 | ✅ |
| DSR (33 essais) | **0.03** | ≥ 0.95 | ❌ |
| corrélation OOS vs `momentum_12_1` | **+0.72** | (breadth) | ❌ peu indépendant |

**Non inscrit.** Sur cet univers de large-caps liquides, le TSMOM vol-normalisé
se comporte comme un cousin **bruité et fortement corrélé** (ρ=+0.72) du momentum
cross-section : il n'apporte quasi aucune *breadth* et son IC n'est pas
significatif. C'est le résultat attendu de la loi de Grinold-Kahn : sur ~80 titres
très corrélés, l'espace de paris indépendants est étroit. La vraie breadth exige
d'**élargir l'univers** (bloqué par le biais de survie, cf. ci-dessus) ou des
signaux d'une *autre* famille (fondamentaux PIT, résiduel idiosyncratique) — pas
une n-ième variante de trend. Le module reste comme **infrastructure testée**,
prêt à être re-testé sur un univers large sans biais de survie ; il n'entre pas
dans la décision tant qu'il n'a pas franchi le portail.

### ✅ Fait (Tier 2 bis) — test de breadth empirique : le nombre de titres ≠ breadth

On a *testé l'hypothèse breadth elle-même* : univers étendu de 80 à **475 titres
liquides** (top dollar-volume, fonds exclus, via `data/alpaca_universe_liquid.py`
+ `run_breadth_test_alpaca.py`), puis re-passage du **même portail**.

| grandeur | 80 titres | 475 titres | attendu si breadth×5.9 |
|---|---|---|---|
| momentum_12_1 IC t-stat | +2.56 | **+2.70** | ~×2.4 → ≈ +6 |
| momentum_12_1 Sharpe net | +0.76 | +0.81 | ↑ franc |
| momentum_12_1 DSR | 0.13 | **0.06** | ↑ |
| TSMOM↔momentum corrélation | +0.72 | +0.74 | ↓ (plus indépendant) |
| autres facteurs passant le portail | 0 | **0** | quelques-uns |

**Résultat net : multiplier les titres par ~6 n'a *pas* relevé l'edge.** Le t-stat
de l'IC est passé de 2.56 à 2.70 — au lieu du ×√6 (≈ +6) qu'impliquerait une vraie
breadth ×6. La leçon, centrale : **le nombre de titres n'est pas le nombre de paris
*indépendants***. 475 large/mid-caps partagent d'énormes expositions communes
(marché, secteurs) → la breadth *effective* n'augmente presque pas, la corrélation
TSMOM reste ~0.74, et aucun autre facteur n'émerge. Le levier n'est donc **pas de
compter plus de tickers** mais la **décorrélation** :

1. une *autre famille* de signaux vraiment orthogonale (fondamentaux PIT, résiduel
   idiosyncratique à la Blitz — retirer β marché/secteur *avant* de trier) ;
2. un univers plus **profond et dispersé** (small-caps), là où les paris sont moins
   redondants — mais cela **exige** un dataset sans biais de survie (Sharadar/CRSP),
   toujours le vrai blocage. ⚠️ Le test ci-dessus est lui-même survivor-biased
   (Alpaca = titres encore cotés) : il mesure l'effet breadth, pas un rendement
   absolu.

Autrement dit, la recherche confirme la théorie (Grinold-Kahn) *et* montre
empiriquement que l'implémenter demande de la **décorrélation**, pas du volume de
tickers. C'est la direction du travail suivant (momentum résiduel).

### ✅ Fait (Tier 2 ter) — momentum résiduel testé, REJETÉ, et la vraie conclusion

Implémenté `backtest/residual_momentum.py` (Blitz-Huij-Martens : β marché glissant
retiré, momentum sur le résidu idiosyncratique, standardisé — sans look-ahead) et
passé au portail sur l'univers large (475 titres).

| grandeur | résiduel | classique (référence) |
|---|---|---|
| IC t-stat | **+2.00** (≤ 2, échec strict) | +2.70 |
| Sharpe net | +0.47 | +0.81 |
| DSR | **0.05** | 0.14 |
| corrélation OOS ↔ classique | **+0.85** | — |

**Non inscrit** — et le résultat est *contre-intuitif et instructif* : le momentum
résiduel est **+0.85 corrélé** au momentum classique, soit *plus* que le TSMOM brut
(+0.74). Retirer le seul β **marché** ne décorrèle pas deux signaux qui trient tous
deux sur la tendance *idiosyncratique* : sur des large-caps, l'edge du momentum est
déjà largement idiosyncratique, et une orthogonalisation mono-facteur laisse les
communalités secteur/style. Le vrai momentum résiduel de Blitz retire un modèle
**multi-facteurs** (marché + taille + value) estimé sur **36 mois** — hors de portée
avec 3 ans d'historique Alpaca.

**Conclusion honnête (3 tentatives convergentes).** TSMOM, élargissement d'univers,
momentum résiduel : *aucun* signal prix ne décorrèle du seul edge ni ne survit au
DSR sur cet échantillon. Le plafond n'est **pas** l'ingéniosité du signal — c'est
la **donnée** : (1) biais de survie (36.8 % mesuré), (2) univers large-cap trop
corrélé (breadth effective faible), (3) **3 ans** d'historique (trop court pour un
modèle multi-facteurs *et* pour un DSR crédible). Continuer à tester des variantes
de signal sur *le même* échantillon **aggrave** le problème de tests multiples
(N ↑ → barre DSR ↑) : ce serait de l'overfitting déguisé, contraire à la discipline
du portail. **Le déblocage passe par de meilleures données** (dataset profond sans
biais de survie type Sharadar/CRSP, +10 ans, small-caps), pas par une n-ième
variante. Les trois modules restent comme **infrastructure testée**, prêts à être
re-passés au portail dès qu'un tel dataset est disponible.

### ✅ Fait (Tier 2 quater) — sentiment FinBERT (vraie famille décorrélée), REJETÉ mais prometteur

Le test de sentiment initial (IC t = −0.93) notait le champ `insight` **brut** de
Polygon (±1/0). On a refait le test **proprement** : **112 082 articles réels**
(titre+description, 80 large-caps, 2023-08→2026-07) notés par **FinBERT**
(ProsusAI/finbert) → panel point-in-time (fenêtre 7 j) → même portail.
(`data/polygon_news_sentiment.py` + `scripts/run_finbert_sentiment_alpaca.py`.)

| grandeur | valeur | lecture |
|---|---|---|
| couverture panel non-NaN | 87 % | données denses (vs sentiment natif clairsemé) |
| IC t-stat | **−0.69** | ≈ 0 : aucun edge cross-section |
| Sharpe net | +0.17 | quasi nul |
| PSR (P[Sharpe>0]) | 0.61 | faible |
| **corrélation OOS ↔ momentum** | **+0.24** | ✅ **vraiment décorrélé** (vs +0.72/+0.85 des variantes prix) |

**Non inscrit** — mais le résultat est *le plus encourageant des candidats breadth*.
La corrélation **+0.24** confirme que le sentiment est une **famille réellement
décorrélée** (là où TSMOM/résiduel restaient collés au momentum). Le problème n'est
donc pas la famille mais la **construction** : le *niveau* moyen de sentiment sur 7 j
n'a pas d'edge (il est vraisemblablement **déjà price-in**). La théorie (et la
littérature event-study) dit que ce qui bouge les prix, c'est l'**innovation** de
sentiment (surprise = niveau − moyenne glissante), pas le niveau ; et l'horizon
compte (l'impact news décroît en quelques jours, parfois avec **reversal**). C'est
**une** alternative motivée *ex-ante* (pas du p-hacking) — à tester une fois, en la
comptant honnêtement dans le DSR, avant toute inscription. Le module FinBERT +
fetch d'articles (avec retries/checkpoint) reste comme **infrastructure testée**.

**Suivi (1 test, comme promis) — surprise de sentiment, aussi REJETÉ.** On a testé
l'innovation `surprise = niveau(3j) − norme(30j)`, reb=3 (`--signal surprise`) :

| grandeur | niveau (7j) | **surprise (3j/30j)** |
|---|---|---|
| IC t-stat | −0.69 | **−0.60** (≈ 0) |
| Sharpe net | +0.17 | **−1.30** (turnover 0.55 → mangé par les coûts) |
| PSR | 0.61 | 0.02 |
| corrélation ↔ momentum | +0.24 | +0.07 |

Ni le niveau ni l'innovation n'ont d'edge cross-section : sur ces 80 large-caps, à
horizon jour/semaine et sur 3 ans, **il n'y a pas de relation sentiment→rendement
exploitable**. La famille est bien décorrélée (breadth potentielle réelle) mais le
signal n'existe pas *ici*. Raisons honnêtes probables : (1) les large-caps sont les
titres les plus **efficients et saturés de news** — l'edge sentiment vit plutôt sur
des small-caps sous-couvertes ; (2) 3 ans d'échantillon ; (3) le sentiment EOD rate
le drift **intraday**. **On s'arrête** : sweeper d'autres fenêtres/horizons serait
du multiple-testing. Conclusion inchangée et désormais *robuste sur 4 familles*
(TSMOM, univers large, résiduel, sentiment) : **le levier restant est la donnée**
(univers profond sans biais de survie, idéalement small-caps — là où sentiment *et*
value ont de la place), pas une variante de plus sur ce même échantillon.

---

## Tier 3 — Durcir le portail contre le sur-apprentissage (multiple testing)

**Externe.** Bailey & López de Prado : le **Deflated Sharpe Ratio (DSR)** corrige
le Sharpe pour (a) le **biais de sélection sous tests multiples** et (b) la
non-normalité ; la **Probability of Backtest Overfitting (PBO)** quantifie le
risque de sur-ajustement ; la **Purged/Combinatorial Purged Cross-Validation
(CPCV)** supprime la fuite d'information aux frontières de folds et donne une
*distribution* de Sharpe OOS.

**Chez FinBot.** Le portail utilise `IC t > 2` (or j'ai déjà noté que le t-stat de
l'IC est **gonflé en cross-section large** — un IC nul sort « significatif ») +
walk-forward simple (5 fenêtres). Pas de correction de tests multiples, pas de
purge/embargo.

**Actions** (implémenter les formules *directement* — `mlfinlab` est désormais
payant/fermé) :
- **DSR dans le portail** : ajouter le Sharpe *déflaté* (fonction du nombre d'essais
  et de la non-normalité) comme critère, à côté de l'IC t et du Sharpe net.
- **Purged K-fold + embargo** dans `walk_forward_evaluate` : purger les
  observations chevauchant la fenêtre de test, embargo après. Donne une PBO.
- **Compter les essais** : le sweep teste N configs (facteurs × rebalance) ; le
  DSR doit connaître N pour déflater correctement.

*Impact : moins de faux positifs — mais probablement moins de « survivants » encore.
C'est le prix de l'honnêteté statistique.*

### ✅ Fait (Tier 3) — et un résultat inconfortable, rapporté honnêtement

Implémenté dans `backtest/robustness.py` (formules directes, sans dépendance
payante) : `probabilistic_sharpe_ratio`, `expected_max_sharpe`,
`deflated_sharpe_ratio`, `purged_kfold_indices` (purge + embargo). Le portail
(`validation_gate.decide`) accepte un **3e critère DSR optionnel** (`dsr_min=0.95`),
*actif seulement si on lui fournit `n_trials`* — il ne peut que resserrer, jamais
relâcher le double critère historique.

**Verdict réel sur le seul edge validé** (`run_deflated_sharpe_alpaca.py`,
32 essais = 8 facteurs × 4 cadences, 626 obs OOS) :

| grandeur | valeur |
|---|---|
| Sharpe/période observé (momentum_12_1 @ reb=10) | +0.048 (annualisé **+0.76**) |
| repère dégonflé E[max Sharpe \| H0] sur 32 essais | +0.093 (annualisé **+1.47**) |
| **Deflated Sharpe Ratio** | **0.13** (❌ < 0.95) |

Autrement dit : sur *ce seul échantillon* et vu le nombre d'essais du sweep, le
Sharpe de momentum est **en dessous** de ce qu'on attendrait du meilleur de 32
tirages de pur bruit. **On garde quand même momentum au registre**, mais en le
disant : momentum est un facteur à **fort prior** (littérature de plusieurs
décennies, multi-marchés/multi-périodes) — pas une trouvaille par data-mining sur
*ce* backtest. Le DSR suppose N essais a priori équiprobables et *sur-pénalise* un
signal théoriquement fondé. La crédibilité tient au prior + IC/Sharpe OOS, pas à ce
seul run. C'est précisément pourquoi le DSR reste **optionnel** dans le portail :
un futur signal *sans* prior fort, lui, devra le franchir. La mise en garde est
inscrite noir sur blanc dans l'`evidence` de `VALIDATED_SIGNALS["momentum_12_1"]`.

---

## Tier 4 — Maturité plateforme (inspiration Qlib / QuantConnect-LEAN)

- **Couche de données PIT formalisée** (Qlib : *DataHandler*/loaders point-in-time,
  modules faiblement couplés). FinBot a déjà des loaders PIT (prix/fondamentaux/
  univers/sentiment) ; les unifier derrière une interface commune type Qlib
  faciliterait l'ajout de signaux.
- **Meta-labeling** (López de Prado) au lieu du combinateur ridge (échoué) : un
  modèle *secondaire* décide **la taille/le filtrage** des paris du signal primaire
  (momentum), pas la direction. Plus discipliné, moins sujet aux artefacts de queue.
- **Model zoo léger** (Qlib) : si un jour on entraîne (GBDT sur features validées),
  garder l'entraînement **hors** chemin de décision tant qu'il n'a pas passé le
  portail — jamais par défaut.
- **Exécution** (LEAN) : ordres limit / TWAP vs market. *Faible priorité* au niveau
  de capital et de liquidité actuels (large-caps) — le slippage mesuré est ~2.5 bps.

---

## Ce que la recherche confirme sur l'approche déjà tenue

- **Coûts nets et walk-forward OOS** comme filtre : aligné avec la pratique.
- **Abstention plutôt que constantes**, **portail avant décision** : va dans le
  sens de la lutte anti-overfitting (DSR/PBO) — il faut juste la *renforcer* (Tier 3).
- **Un seul edge prouvé assumé** : cohérent avec la loi fondamentale — mieux vaut
  1 vrai signal bien géré (Tier 1) que 100 facteurs non validés.

---

## Ordre recommandé

1. **1.1 Momentum vol-scalé** (re-validé) — meilleur ratio impact/effort, agit sur
   le seul edge prouvé.
2. **1.2 Ciblage de vol + risk-off** — maîtrise du drawdown avant tout live.
3. **Tier 3 (DSR + purged CV)** — durcir le portail *avant* d'ajouter des signaux,
   pour ne pas empiler des faux positifs.
4. **Tier 2 (signaux indépendants + univers)** — la vraie montée en IR, une fois le
   portail durci ; l'univers élargi dépend d'un dataset sans biais de survie.

## Sources

- Barroso & Santa-Clara, *Momentum has its Moments* (2015).
- Moskowitz, Ooi & Pedersen, *Time Series Momentum* ; AQR, *Trends Everywhere* / *Macro Momentum*.
- Grinold & Kahn, *Active Portfolio Management* (loi fondamentale, IR = IC·√Breadth).
- Bailey & López de Prado, *The Deflated Sharpe Ratio* ; *The Probability of Backtest Overfitting* ; *Advances in Financial ML* (purged/combinatorial CV, meta-labeling).
- Microsoft **Qlib** (github.com/microsoft/qlib) — couche PIT, model zoo, modules découplés.

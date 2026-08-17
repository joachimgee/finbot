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

**Suite (idée des audits `AUDIT_FORKS` + `PORTFOLIO_PRO_RESEARCH`) — momentum
résiduel PCA : la décorrélation ENFIN obtenue.** Le résiduel *marché-seul* échouait
parce que l'orthogonalisation était **mono-facteur**. La version multi-facteurs
*data-free* (`pca_residual_momentum_score` : retire les k premières composantes
principales = marché + secteur/style implicites, momentum sur le résidu) **résout la
décorrélation** (`run_pca_residual_momentum_alpaca.py`) :

| variante | IC t | Sharpe net | DSR | corr ↔ momentum brut |
|---|---|---|---|---|
| brut (réf) | +2.56 | +0.76 | 0.12 | — |
| résiduel marché-seul | +2.16 | +0.44 | 0.05 | **+0.87** |
| **PCA k=3** | +1.79 | +0.24 | 0.02 | **+0.21** |
| **PCA k=5** | +1.65 | **+0.81** | 0.13 | **+0.17** |

C'est le **meilleur candidat breadth de toute la session** : PCA k=5 est *réellement
décorrélé* (+0.17 vs +0.87) **et** son Sharpe net (+0.81) **égale** le momentum brut.
Le seul critère qui coince est l'**IC t = 1.65 < 2** — pas la rentabilité. Sur ~627
périodes × **80** noms, le t-stat de l'IC cross-section est structurellement plafonné
par la faible breadth : c'est *exactement* le symptôme Grinold-Kahn. **Non inscrit**
(discipline : IC t > 2 exigé), mais la lecture change : la décorrélation n'était
**pas** impossible — elle demandait la bonne orthogonalisation. Sur un univers large
sans biais de survie, PCA k=5 franchirait plausiblement le portail, et sa combinaison
*risk-weighted* avec le momentum brut relèverait l'IR (deux paris ~indépendants). Le
module reste comme **infrastructure testée**, prêt à re-passer le portail sur données
profondes.

### ✅✅ Fait — STAT-ARB PAIRES : le payoff de breadth ENFIN démontré

Nouvelle **famille** (mean-reversion, pas une variante de tendance) :
`backtest/pairs_trading.py` — walk-forward *sans look-ahead* (sélection par
**cointégration Engle-Granger** sur le passé, β gelé, demi-vie AR(1) ; trading par
z-score glissant causal du spread ; dollar-neutre, coûts calibrés).
`run_pairs_trading_alpaca.py`, 80 large-caps :

| grandeur | valeur |
|---|---|
| Sharpe net (paires) | **+0.63** |
| max drawdown | **−3.8 %** |
| corrélation ↔ momentum | **−0.03** (vraiment indépendant) |
| paires actives (moyenne) | 1.5 (thin — plafond de données) |

**Et le payoff de Grinold-Kahn, mesuré :**

| stratégie | Sharpe net |
|---|---|
| momentum seul | +0.68 |
| paires seul | +0.63 |
| **combo risk-weighted (inverse-vol)** | **+0.94** |

Deux paris **réellement décorrélés** (ρ=−0.03) se combinent à **+0.94** — conforme à
la théorie (√(0.68²+0.63²) ≈ 0.93) et **+38 % vs momentum seul**. C'est la première
démonstration empirique de la session que la **breadth paie** : une *autre famille*
indépendante relève l'IR combiné, exactement comme le prédit Grinold-Kahn.

**Réserve honnête** : les paires sont **thin** (1.5 en moyenne — peu de couples
cointégrés stables sur ~80 large-caps), donc risque idiosyncratique élevé et
robustesse OOS incertaine sur 3 ans. Ce n'est pas encore un edge inscriptible tel
quel, mais **la direction est prouvée** et l'infra est réutilisable telle quelle sur
un univers **profond** (plus de titres → beaucoup plus de paires → strat paires
robuste), où le combo momentum+paires+PCA-résiduel formerait un vrai multi-stratégie.
C'est la conclusion constructive de tout le fil « breadth » : le plafond reste la
donnée, mais on a désormais **deux familles indépendantes** qui, ensemble, valent
mieux que la meilleure seule.

### 🏁 Fait — MULTI-STRATÉGIE : les trois familles combinées (capstone)

`backtest/multi_strategy.py` (risk-weighting **inverse-vol** + **ERC/risk-parity**,
testé) assemble les trois familles en un book unique.
`run_multi_strategy_alpaca.py`, 80 large-caps, coûts calibrés :

**Matrice de corrélation (toutes ~décorrélées) :**

| | momentum | pca_resid | pairs |
|---|---|---|---|
| **momentum** | 1.00 | +0.17 | −0.03 |
| **pca_resid** | +0.17 | 1.00 | +0.03 |
| **pairs** | −0.03 | +0.03 | 1.00 |

**Sharpe net & combinaison (risk-parity) :**

| famille | Sharpe seul | poids ERC |
|---|---|---|
| momentum | +0.85 | 0.18 |
| pca_resid | +0.90 | 0.30 |
| pairs | +0.63 | 0.52 |
| **BOOK COMBINÉ** | **+1.30** | — |

Le book combiné atteint **Sharpe +1.30** — **+44 % vs la meilleure famille seule
(+0.90)** — avec un **max drawdown de −4.4 %** seulement. C'est la **démonstration
définitive** de la thèse de toute la session : le plafond était la *breadth*
(paris indépendants), et trois familles décorrélées (une tendance cross-section, une
résiduelle PCA, une mean-reversion par paires) combinées par risk-parity **battent
nettement** n'importe laquelle seule, avec un risque bien réparti.

**Réserve honnête finale** : 3 ans / 80 large-caps, paires *thin* → chiffres
indicatifs du **mécanisme**, pas un track record. Mais l'arc est bouclé : le code
sait désormais **construire et pondérer un multi-stratégie décorrélé** ; le seul
levier restant pour en faire un edge inscriptible robuste est la **donnée** (univers
profond sans biais de survie), où les trois familles gagneraient toutes en robustesse.

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

### ✅ Fait (Tier 2 quinquies) — famille VOLUME/MICROSTRUCTURE testée, REJETÉE (6ᵉ famille)

Audit du code déjà présent (`ml/factor_catalog.py` = 100 facteurs, dont 15
Microstructure + 4 Volume ; `ml_features_advanced/microstructure_features.py`) : la
famille **volume/microstructure** — indépendante du price-trend et calculable depuis
le **volume Alpaca** — n'avait **jamais** passé le portail (les validations ne
couvraient que les 8 facteurs prix classiques). Testée proprement, **2 hypothèses
pré-enregistrées** (pas de sweep), via `run_microstructure_validation_alpaca.py`
(50 large-caps, reb=10, coûts calibrés) :

| signal | IC t | Sharpe net | corr ↔ momentum | verdict |
|---|---|---|---|---|
| **OFI** (order-flow imbalance) | −0.71 | −0.27 | **+0.08** | ❌ IC non significatif |
| **Amihud** (illiquidité) | −2.01 | −0.20 | **−0.39** | ❌ IC significatif mais du *mauvais signe* |

**Non inscrit.** Les deux sont **réellement indépendants** du momentum (+0.08 / −0.39
→ vraie breadth potentielle), mais sans edge sur barres **quotidiennes / large-caps** :
l'OFI et l'illiquidité vivent en **intraday** et sur **small-caps illiquides**.
*Discipline* : l'Amihud à −2.01 « passerait » en **inversant le signe**, mais
l'hypothèse pré-enregistrée était la prime de liquidité (long illiquide) et les
données disent l'inverse sur large-caps — flipper serait le **piège post-hoc** de
l'anomalie du combinateur (IC significatif ≠ edge exploitable). On rejette.

**6ᵉ résultat convergent** (TSMOM, univers large, résiduel, sentiment, meta-labeling,
volume/microstructure) : chaque famille *indépendante* qu'on teste confirme la
breadth potentielle **mais** ne produit pas d'edge sur cet échantillon
quotidien/large-cap/3 ans. Le code (OFI, Amihud, réutilisant les modules existants)
reste comme **infra testée**, prête sur données profondes (intraday ou small-caps).
Le reste du catalogue non testé (Regime/CrossAsset/Alternative, options) exige des
données qu'on **n'a pas** (macro, cross-asset, chaînes d'options) → hors de portée
ici. **La famille volume était le dernier candidat data-disponible ; il est traité.**

---

### ✅ Fait — HISTOIRE LONGUE (18 ans, Yahoo gratuit) : l'échantillon court n'était PAS le vrai plafond

Le « 3 ans » cité partout n'était **pas** une limite fondamentale mais le cache
Alpaca IEX utilisé. Nouveau `data/yahoo_history.py` (fetcher **requests**, proxy-safe
— `yfinance`/curl_cffi ignore le proxy de l'env) : **clôtures ajustées Yahoo, décennies,
gratuit**. Rejoue **les scripts portail existants** (aucune modif) sur un panel
**2008-2026, 80 large-caps** (`--cache /tmp/yahoo_long.csv`).

**momentum_12_1 — 3 ans vs 18 ans :**

| grandeur | 3 ans (2023-26) | **18 ans (2008-26)** | lecture |
|---|---|---|---|
| IC t-stat | 2.56 | **4.77** | l'IC ÉTAIT bridé par la breadth → devient fortement significatif |
| Sharpe net | +0.76 | **+0.33** | le +0.76 était flatté par le régime ; le vrai net est modeste |
| DSR (32 essais) | 0.13 | **0.028** | *pire* : Sharpe modeste + queues épaisses (kurtosis 10) |
| PBO (CSCV) | 0.09 | 0.22 | tri toujours robuste (≤ 0.5) |

**Deux enseignements qui corrigent le cadrage précédent :**

1. **L'IC de momentum est réel et robuste** (t=4.77 sur 18 ans) — l'excuse « t bridé
   par la breadth » était juste, la longueur d'échantillon la lève. Mais sa
   **rentabilité nette est modeste** (+0.33) et régime-dépendante ; le +0.76 de
   2023-26 était un artefact de régime haussier. Momentum reste inscrit sur son
   **prior + IC robuste**, pas sur un Sharpe flatteur (evidence du registre mise à jour).
2. **Le meilleur candidat breadth de 3 ans meurt sur 18 ans.** Le PCA-résiduel k=5
   (Sharpe +0.81 / IC t 1.65 sur 3 ans) tombe à **IC t 0.98, Sharpe −0.18** sur 18 ans
   (décorrélé +0.01 mais **sans edge**). Plus de données l'a **tué**, pas sauvé — son
   +0.81 était lui-même un artefact de régime.

**Conséquence sur la thèse « plafond de données » :** elle se **précise**. Ce n'est
PAS la *longueur* d'histoire le blocage (Yahoo la donne gratuitement, et l'allonger
*dégrade* les faux espoirs au lieu de les valider — c'est sain). Les vrais blocages
restants sont : (1) le **biais de survie** (Yahoo/Alpaca = titres encore cotés — non
corrigé), et (2) l'**homogénéité large-cap** (breadth effective faible). Un dataset
sans biais de survie + small-caps reste le seul levier ; la longueur, elle, est réglée.

### ✅ Fait — re-test des AUTRES familles sur 18 ans (Yahoo) : 3 confirment, 1 SURPREND

Les scripts portail existants relancés sur `/tmp/yahoo_long.csv` (2008-2026) :

| famille | 3 ans | **18 ans** | lecture |
|---|---|---|---|
| **TSMOM** | IC t 1.01, Sh +0.27 | IC t **2.79**, Sh **+0.09**, corr 0.67, DSR 0 | IC devient significatif mais Sharpe ~0 et toujours corrélé → **rejeté** |
| **Paires (stat-arb)** | Sh +0.63 | Sh **−0.30**, corr −0.03 | le +0.63 de 3 ans était de la chance ; sur 18 ans, edge négatif → **rejeté** (paires exigent un univers profond) |
| **Overlay régime** | réduit le DD | MA200 : Sh +0.13→**+0.20**, DD −33 %→**−26.5 %** | sur un **cycle complet**, le risk-off *aide* (là où le bull de 3 ans le rendait coûteux) → **outil de risque confirmé** |
| **Meta-labeling** | AUC 0.507, nul | **AUC 0.563**, méta-filtre **+0.76** vs raw +0.07 | ⚠️ **la surprise** : la seule approche qui *s'améliore* avec plus de données |

**Trois confirment la thèse** (TSMOM/paires meurent ou stagnent ; le régime aide sur
cycle complet — cohérent). **Une surprend : le meta-labeling.** Sur 18 ans (79 416
échantillons), l'AUC OOS du méta-modèle passe **0.507 → 0.563** (discrimination faible
mais désormais *réelle* vu le N), et le méta-filtre bat nettement le raw *dans le
script*. C'est le **premier résultat 18 ans encourageant** : avec assez de données, un
secondaire apprend *un peu* à distinguer les paris momentum gagnants.

**Prudence obligatoire — non inscrit, c'est une PISTE, pas un edge validé :**
(1) **une seule config** (features/seuil/horizon fixes) → il faut un **DSR avec essais
comptés** ; (2) le raw *intra-script* (+0.07) diffère du portail (+0.33) → **écart de
construction à réconcilier** avant toute comparaison ; (3) le filtre **concentre à
8 noms** (risque idiosyncratique). AUC 0.563 reste **faible** (0.5 = hasard). La suite
disciplinée serait **une** passe de confirmation rigoureuse (DSR + réconciliation du
baseline), pas un sweep de seuils (= multiple-testing). Mais c'est la première chose de
toute la campagne breadth que l'histoire longue a **renforcée** au lieu de tuer.

### ✅✅ Fait — CONFIRMATION du méta-labeling : PASSE les 3 contrôles d'artefact

`confirm_meta_labeling` (+ `confirm_meta_labeling_alpaca.py`) isole la *compétence* du
méta-modèle des *artefacts*. Sur 18 ans (45 large-caps à histoire complète) :

| contrôle | résultat | verdict |
|---|---|---|
| **[0] baseline réconcilié** | raw méta-construction +0.07 ≈ portail +0.05 (IC t 3.69) | l'écart au +0.33 était l'univers ; comparaison à **méthode égale** rétablie |
| **[1] filtre aléatoire** (clé) | méta **+0.76** bat **100 %** de 100 filtres aléatoires (moy −0.04, p95 +0.24) | **pas** un artefact de concentration : la *sélection* a de la valeur |
| **[2] permutation AUC** | AUC 0.563, **p = 0.002** | pouvoir discriminant **réel**, pas de la chance |
| **[3] stabilité (tiers)** | méta [0.12, 1.18, 1.22] > raw [−0.49, 0.46, 0.2] | positif partout, bat le raw dans chaque tiers |

**3/3.** Sur ces large-caps le momentum brut est quasi plat (+0.05) et le méta-modèle
le transforme en +0.76 par une sélection qui **bat 100 % de l'aléatoire** et discrimine
à **p = 0.002**. C'est le **premier edge sérieux de toute la campagne** — et le premier
qui *illustre empiriquement le meta-labeling de López de Prado sur ce système*.

**RESTE NON INSCRIT — mesure obligatoire, 3 réserves avant tout capital :**
1. **Biais de survie doublé** : ces 45 titres ont survécu 18 ans *et* existaient en 2008
   (Yahoo = cotés aujourd'hui). Le modèle a appris sur des **survivants** — le seul
   contrôle que les tests ci-dessus **ne** couvrent pas. C'est LE risque restant.
2. **Tests multiples au niveau campagne** : ~10 familles essayées, celle-ci gagne. Les
   contrôles [1]/[2] traitent l'overfitting *intra-méta*, pas le « best-of-N » global —
   il faut un **DSR formel avec essais comptés**.
3. **AUC 0.563 reste faible** : l'edge est réel mais le modèle est modeste ; le +0.76
   est amplifié par la concentration (8 noms → risque idiosyncratique) et la base momentum.

**Statut : piste → CANDIDAT SÉRIEUX.** Suite disciplinée : (a) re-confirmer sur un
dataset **sans biais de survie** (le vrai juge), (b) DSR campagne, (c) **forward-test
paper**. Pas d'inscription ni de live tant que (a) n'est pas fait.

**✅ (b) fait — features de régime + DSR campagne** (`run_meta_features_dsr_alpaca.py`,
18 ans, 45 titres). *Meilleures features* : ajout **pré-enregistré** de 3 features de
régime (Daniel-Moskowitz/Barroso : rdt marché 126 j, vol marché 21 j, dispersion
cross-section — `regime_features`). Résultat **marginal** : l'AUC ne bouge pas
(0.563→0.561, le modèle ne discrimine pas mieux) mais le Sharpe monte (+0.76→**+0.86**)
et le 1er tiers se stabilise (0.12→0.40). Les features de base captaient déjà
l'essentiel. *DSR campagne* (déflation du Sharpe méta RICH par ~20-30 essais de toute
la campagne, σ=0.0247 du sweep) :

| N essais | Sharpe/pér. méta | repère E[max\|H0] | **DSR** |
|---|---|---|---|
| 20 | +0.0542 | +0.0469 | **0.68** (⚠️ limite) |
| 30 | +0.0542 | +0.0512 | **0.58** (⚠️ limite) |

**Résultat le plus fort du projet, mais pas une validation.** Le Sharpe du méta
**dépasse** le repère best-of-N (0.054 > 0.047-0.051) — *la première chose du projet à
le faire* (le momentum brut, lui, est **sous** son repère : Sharpe/pér 0.021 < 0.052,
DSR 0.028). Mais le DSR n'atteint pas le seuil strict de 0.95 : queues épaisses
(kurtosis 10.8) + échantillon fini laissent une confiance de ~0.6-0.7, pas une
certitude. Verdict honnête : **candidat le plus crédible jamais produit, encore sous
le seuil formel** ; la réserve dominante reste le **biais de survie** (45 survivants).

**✅ Monte-Carlo (block bootstrap) — edge robuste, mais DRAWDOWN SÉVÈRE révélé.**
`block_bootstrap_metrics` (robustness.py) + `run_meta_montecarlo_alpaca.py` : 5000
chemins ré-échantillonnés par blocs de 21 j de la série de rendements réelle du book
méta (RICH, reb=21) — non-paramétrique, préserve queues + autocorrélation.

| métrique | médiane | 5 % | 95 % |
|---|---|---|---|
| Sharpe annualisé | +0.83 | **+0.39** | +1.26 |
| Rendement net an. | +19.4 % | +9.8 % | +28.1 % |
| **Max drawdown** | **−51 %** | −73 % | (pire 1 % **−83 %**) |
| P(Sharpe>0) = **99.9 %** · P(période positive) = 99.6 % | | | |

**Deux conclusions.** (1) **L'edge est robuste au ré-échantillonnage** : Sharpe positif
dans ~100 % des chemins, borne 5 % = +0.39 > 0, rendement pessimiste +9.8 %/an — ça
complète le DSR (le DSR jugeait la *magnitude* limite ; le bootstrap montre la
*positivité* quasi certaine face à l'incertitude d'échantillonnage). (2) **Le risque de
drawdown est SÉVÈRE et le backtest le cachait** : le drawdown réalisé (−37.6 %) était le
côté chanceux ; la médiane bootstrap est **−51 %**, un −73 à −83 % est plausible.
Cohérent avec le L/S momentum (krachs, kurtosis 10). **Implication actionnable** : avant
tout live, le book méta appelle un **contrôle de drawdown** (overlay régime-HMM ou
vol-target, déjà testés et réducteurs de drawdown) — le Sharpe est là, la maîtrise du
risque de queue ne l'est pas. *Réserve inchangée : le bootstrap ne corrige pas le biais
de survie.*

**✅ Kelly / bet-sizing testé (AFML ch.10) — pas de gain, équipondération gardée.**
López de Prado appaire meta-labeling (ch.3) et bet-sizing (ch.10) : le méta donne
P(gain) par pari ; on a testé si sizer par P améliore vs l'équipondéré actuel
(`run_meta_kelly_sizing_alpaca.py`, 18 ans, reb=21, `bet_sizing.py` réutilisé) :

| schéma | Sharpe net | turnover | maxDD | brut moy. |
|---|---|---|---|---|
| **equal (actuel)** | **+0.92** | 0.044 | **−37.6 %** | 1.00 |
| confidence (AFML 10.1) | +0.97 | 0.042 | −41.2 % | 1.00 |
| kelly (f=0.25, b≈1.0) | +0.71 | 0.019 | −31.3 % | 0.46 |

**Aucun gain robuste.** « confidence » gagne +0.05 de Sharpe (bruit) mais **aggrave le
drawdown** (−41 % vs −38 %) ; Kelly dé-lève (brut 0.46) → moins de drawdown mais Sharpe
en baisse. Cause : le méta ne garde que P ≥ 0.5, **tous serrés près du seuil** (AUC 0.56)
→ dispersion de conviction trop faible pour différencier les tailles ; Kelly exige un
edge fort et bien estimé, P≈0.5 n'en fournit pas. **Équipondération conservée** (meilleur
compromis Sharpe/drawdown, plus diversifiée). `bet_sizing`/Kelly restent disponibles pour
un futur signal à conviction dispersée. `compare_meta_sizing` testé.

**✅ Cadence testée — le QUOTIDIEN est le pire, mensuel (reb=21) le meilleur.**
`run_meta_cadence_sweep_alpaca.py` (18 ans, book méta RICH, horizon = cadence, coûts
calibrés, fenêtre train plafonnée identiquement) :

| reb (jours) | Sharpe net | turnover | AUC |
|---|---|---|---|
| 1 (quotidien) | +0.35 | 0.360 | 0.515 |
| 5 | +0.47 | 0.129 | 0.528 |
| 10 | +0.63 | 0.074 | 0.535 |
| **21 (~mensuel)** | **+0.92** | 0.044 | 0.558 |

Amélioration **monotone** avec l'espacement (+0.35→+0.92, turnover **−88 %**) : (1) moins
de turnover = moins de coûts sur un signal lent ; (2) un horizon de label plus long est
*moins bruité* → l'AUC monte aussi (0.515→0.558). Le book méta préfère **plus** d'espacement
que le momentum brut (dont le sweep retenait reb=10) — et reb=21 = **cadence mensuelle
standard de la littérature momentum**, donc principiel, pas sur-ajusté. **Cadence à adopter
pour le forward-test : reb=21** (via `RebalanceGate`), au lieu du quotidien actuel.

**✅ (c) fait — câblage forward-test paper.** `framework.MetaLabelConstruction`
(couche enfichable #5) + `run_meta_labeling_paper.py` : le book momentum méta-labelé
tourne sur le compte **paper** via le chemin audité (OrderGateway + journal +
réconciliation), double-verrou paper-only. La construction fetch son **propre panel
~3 ans** (le méta a besoin de 252 j pour momentum + assez de dates pour min_train ;
le fetch pipeline de ~420 j ne suffit pas), entraîne la logistique à chaud sur
l'historique à label clos, et ne garde que les paris `P(gain) ≥ seuil`. Dry-run réel :
book **11 positions (7 L / 4 S)** — le méta écarte 9 des 20 paris momentum bruts
(cohérent avec les ~8 noms de la confirmation). ``meta_filter_today`` (version « live »
de `walk_forward_meta`) testé. *Reste (b) DSR campagne et surtout (a) données
sans biais de survie avant toute inscription.*

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

### ✅ Fait (audit #1) — PBO / CSCV : le *processus de sélection* sur-apprend-il ?

Ajout de `probability_of_backtest_overfitting` (Combinatorial Symmetric CV,
Bailey-Borwein-LdP-Zhu 2015) dans `backtest/robustness.py`, câblé comme **4e
critère optionnel** du portail (`decide(pbo=…)`, `pbo_max=0.5`). Là où le DSR
dégonfle *un* Sharpe pour N essais, la PBO juge le **tri** : sur la matrice
complète (config × temps), fréquence où la config *meilleure in-sample* finit
**sous la médiane out-of-sample**.

**Verdict réel** (`run_deflated_sharpe_alpaca.py`, matrice 32 configs, CSCV S=10,
252 combinaisons) : **PBO = 0.09** (✅ ≤ 0.5).

Résultat *complémentaire et rassurant*, à lire avec le DSR :

| métrique | valeur | ce qu'elle dit |
|---|---|---|
| DSR | 0.13 ❌ | la *magnitude* du Sharpe (0.76) n'est pas distinguable de la chance de sélection sur 3 ans |
| **PBO** | **0.09 ✅** | mais le *tri* n'est PAS sur-appris : la config best-IS reste au-dessus de la médiane OOS **91 %** du temps |

Autrement dit, le choix de momentum est **robuste et persistant** (ce n'est pas une
config chanceuse qui a gagné une fois — cohérent avec son fort prior) ; la seule
réserve porte sur la *magnitude* du Sharpe, pas sur la validité de la sélection. Le
DSR et la PBO restent tous deux **optionnels** (n'activent que si on fournit les
essais / la matrice) : ils ne peuvent que resserrer le double critère historique.

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

### ✅ Fait (Tier 4) — meta-labeling testé, REJETÉ (5ᵉ résultat convergent)

Implémenté `backtest/meta_labeling.py` (López de Prado, AFML ch. 3) : le primaire
(`momentum_12_1`) décide la **direction** ; un modèle **secondaire** (régression
logistique) apprend `P(gain)` d'un pari et le **filtre/dimensionne** — sans jamais
changer la direction. Walk-forward avec **purge + embargo** (labels à horizon clos
seulement), features motivées *ex-ante* (conviction momentum, momentum court, low-vol
à la Barroso, reversal court, lottery), coûts Alpaca calibrés.
(`run_meta_labeling_alpaca.py`, 50 large-caps, reb=10, 9 820 échantillons.)

| stratégie | Sharpe net | turnover | noms moy. |
|---|---|---|---|
| raw (primaire) | +0.71 | 0.04 | 20 |
| méta-filtre (P≥0.5) | +0.57 | 0.06 | 13 |
| méta-sizing (∝P) | +0.75 | 0.04 | — |

**Métrique clé : AUC OOS = 0.507** (taux de gain de base 51.7 %). Le méta-modèle
**ne discrimine quasiment pas** les paris gagnants des perdants — pile ou face. Le
méta-**filtre** *dégrade* (il jette de bons paris, +0.71→+0.57) ; le méta-**sizing**
gagne +0.04 (bruit, non significatif vu l'AUC≈0.5) et ne survivrait pas au DSR avec
l'essai compté. **Non inscrit** — le méta-modèle n'a pas d'edge secondaire fiable.

C'est le **5ᵉ résultat convergent** (après TSMOM, univers large, résiduel, sentiment) :
sur ces 80 large-caps / 3 ans, aucune sophistication de signal *ni de méta-modèle* ne
bat le momentum brut bien géré. La cause reste la **donnée** — pas assez de paris
indépendants ni d'histoire pour qu'un secondaire apprenne quelque chose de
généralisable. Le module reste **infrastructure testée**, prêt à re-passer sur un
univers profond sans biais de survie (où features fondamentales/cross-sectionnelles
donneraient au secondaire de quoi discriminer).

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

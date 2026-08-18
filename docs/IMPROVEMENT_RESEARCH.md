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

**✅ Triple-barrier labeling (AFML ch.3) testé — ≈ équivalent au label horizon ici.**
Le méta a une AUC de ~0.59 (labels bruités). López de Prado propose le **triple-barrier**
(1ère barrière touchée : profit-take/stop-loss ∝ vol du titre, ou temps). Implémenté
(`build_meta_samples(label_method='triple_barrier')`) et comparé au label horizon par les
mêmes contrôles (`run_meta_triple_barrier_alpaca.py`, 18 ans, reb=21) :

| labeling | AUC | méta Sharpe |
|---|---|---|
| horizon | 0.586 | +0.82 |
| triple-barrier (pt=sl=1) | 0.588 (**+0.002**) | +0.90 (+0.09) |

**AUC inchangée** → le triple-barrier ne rend pas le modèle plus discriminant ; le +0.09
de Sharpe est dans le bruit et, sans gain d'AUC, n'est pas une vraie compétence. Raison :
sur 21 j en large-caps **sans exits intra-holding**, « 1ère barrière vol-scalée » et « signe
du rendement à 21 j » sont quasi équivalents — le triple-barrier paie surtout avec des
**sorties réelles sur barrières** (intraday), hors périmètre (le book tient jusqu'au rééq.).
**Label horizon conservé** (book inchangé) ; le code triple-barrier reste dispo pour un
futur moteur d'exits réels. C'est la dernière idée AFML des docs de recherche — testée.

**✅ Contrôle de drawdown branché — vol-target (Barroso) divise le drawdown par ~2.**
Suite au Monte-Carlo, test des overlays de dé-risque *déjà présents* sur la série méta
(RICH, reb=21), drawdown re-mesuré par bootstrap (`run_meta_drawdown_control_alpaca.py`) :

| variante | Sharpe | DD médian | DD pire 1 % | levier moy. |
|---|---|---|---|---|
| raw | +0.82 | −51 % | −83 % | 1.00 |
| **vol-target 10 % cap1** | **+0.84** | **−24 %** | **−47 %** | 0.47 |
| vol-target 10 % cap2 (lève) | +0.85 | −24 % | −47 % | 0.47 |
| régime-HMM | +0.94 | −33 % | −61 % | 0.73 |

**Le vol-target (Barroso-Santa-Clara) est le meilleur contrôle de drawdown** : il **divise
le drawdown par ~2** (médiane −51 %→−24 %, pire −83 %→−47 %) **en préservant le Sharpe**
(+0.82→+0.84) — le résultat classique « la vol prédit les krachs de momentum ». Le
régime-HMM donne le meilleur *Sharpe* (+0.94) mais réduit moins le drawdown. cap1≈cap2
(le book veut surtout dé-risquer, rarement lever) → on retient **cap1 (jamais de levier)**.
**Branché** : `MetaLabelConstruction` applique l'overlay de vol du pipeline
(`_apply_vol_overlay`, ex-ante) quand `target_vol` est défini ; `run_meta_labeling_paper.py`
le met à **10 %** par défaut. Dry-run réel : book à **brut 0.38** (dé-risqué en régime
volatil). Le forward-test paper mesure désormais la version *risk-managed*.

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

### ✅ Fait — UNIVERS LARGE (1895 small/mid-caps) + long-only : l'angle mort levé

Déclencheur : l'ancien FinBot a fait ~+80 % (déc. 2025) sur un panier **small/micro-cap
long-only** (payoffs asymétriques, quelques 5×). Tous nos tests étaient sur ~50-80
large-caps **en L/S market-neutral** — un double angle mort (univers ET forme de
stratégie). Testé (`run_broad_universe_momentum.py`, 1895 titres Alpaca, 2023-2026, reb=21) :

| univers | IC t | **Sh net L/S** | **Sh net long-only** |
|---|---|---|---|
| large-cap ~50 (réf) | +2.56 | +0.76 | — |
| tout (1895) | +2.97 | **−0.28** | **+1.18** |
| T1 grand/liquide | +2.92 | +0.52 | +1.32 |
| T3 petit (small-cap) | +2.46 | **−0.70** | +1.03 |
| **benchmark « acheter TOUT équipondéré »** | — | — | **+1.43** |

**Deux enseignements décisifs.** (1) En **L/S** (qui isole l'alpha), le momentum small-cap
**perd** (−0.70) : le côté **short** en small-cap = squeezes, coûts d'emprunt, les −99 %
qui rebondissent. (2) En **long-only** (l'approche de l'ancien système), le Sharpe est beau
(+1.18) **mais le benchmark equipondéré sans aucun signal fait MIEUX (+1.43)** → c'est du
**BETA** (univers +29 %/an en 2023-26), **pas de l'alpha**. Le momentum ne bat même pas
« acheter tout ».

### ⚠️ CORRECTION (18 ans) — la conclusion « c'est du beta » était un ARTEFACT DE 3 ANS

Le tableau ci-dessus portait sur 2023-2026 (un bull). Rejoué sur **2008-2026** (Yahoo,
1458 titres survivants, GFC + 2020 + 2022 inclus) — `--source yahoo --start 2008-01-01` :

| | 3 ans (2023-26) | **18 ans (2008-26)** |
|---|---|---|
| momentum long-only (tout) | +1.18 | **+1.10** |
| momentum long-only (small-cap T3) | +1.03 | **+1.14** |
| **benchmark équipondéré (aucun signal)** | **+1.43** (battait tout) | **+0.92** (**battu**) |
| IC t (small-cap) | +2.46 | **+4.77** |
| momentum **L/S** small-cap | −0.70 | −0.39 (toujours négatif) |

**Sur un échantillon multi-cycles, le momentum small-cap long-only BAT le beta de son
univers** (+1.10/+1.14 vs +0.92) et son **IC devient très significatif (t=4.77 vs 2.56 en
large-cap)** — conforme à **Hong-Lim-Stein (2000)** : momentum plus fort là où l'info
diffuse lentement. La conclusion « pur beta » venait de la fenêtre courte (même erreur que
pour le momentum large-cap, où 3 ans donnaient +0.76 flatté). **Deux leçons convergentes :
une fenêtre de 3 ans ment.**

**Ce qui tient donc :** (1) la **famille** visée par l'ancien système (small-cap momentum)
est la bonne ; (2) la **forme long-only** est la bonne — le côté short reste toxique en
small-cap (L/S −0.39 : squeezes, coûts d'emprunt) ; (3) **réserve majeure inchangée** :
1458 survivants de 18 ans (Shumway 1997) — le benchmark subit le même biais, donc l'**écart**
momentum-vs-benchmark est plus fiable que les niveaux, mais le momentum small-cap
surpondère les titres qui montent et les faillites (−100 %) sont absentes → l'alpha réel
est **plus faible que +0.20**, d'un montant indéterminable sans base sans-biais ; (4) coûts
small-cap sous-estimés (2,5 bps vs spreads réels de 1-10 %).

**Le ~80 % de l'ancien système = beta d'un régime small-cap haussier × survivorship, pas
un edge répétable.**

### 🚩 (a) PORTAIL COMPLET — le small-cap momentum long-only ÉCHOUE (et ma « correction » était fausse)

`run_smallcap_momentum_gate.py` (18 ans, tercile small-cap, reb=21). **Erreur de benchmark
détectée** : ma « correction » comparait le book **small-cap** (+1.14) au benchmark
équipondéré de l'**univers ENTIER** (+0.92) — apples-to-oranges. Le bon benchmark est
l'équipondéré **du même univers small-cap**, qui vaut **+1.09**.

| critère | valeur | seuil | verdict |
|---|---|---|---|
| IC t-stat | **+4.77** | > 2 | ✅ |
| Sharpe net long-only | +1.14 | > 0 | ✅ *(trivial : contient le beta)* |
| **Sharpe EXCÉDENTAIRE** (book − benchmark **même** univers) | **+0.12 (t=0.52)** | — | ❌ **non significatif** |
| rendement excédentaire annualisé | +4.21 % | — | — |
| **DSR sur l'excès** (32 essais) | **0.053** | ≥ 0.95 | ❌ |
| PBO (CSCV, 32 configs) | 0.000 | ≤ 0.5 | ✅ |

**Verdict : NE PASSE PAS.** Le momentum small-cap long-only **ne bat pas de façon
démontrable le simple fait d'acheter le même univers small-cap équipondéré** (excès
t=0.52, DSR 0.05). Son IC est réel (t=4.77 — le signal *classe* bien les titres) mais
l'**alpha net du beta de son univers n'est pas distinguable du bruit**.

**Trois enseignements méthodologiques :** (1) pour un long-only, « Sharpe > 0 » est un
critère vide — seul l'**excès sur le benchmark du même univers** mesure l'alpha ; (2)
**le choix du benchmark peut fabriquer un faux alpha** (mon erreur : le tercile small-cap
a un beta plus élevé que l'univers entier) ; (3) un **IC significatif n'implique pas un
alpha exploitable** — même leçon que l'anomalie du combinateur.

### 🚩 (c) COÛTS RÉELS — le point mort est à 76 bps, dans la plage small-cap

`run_smallcap_cost_reality.py`. *La mesure de spreads live a échoué* (marché fermé → le
feed IEX renvoie des cotations périmées : 888 bps sur des titres **liquides**, absurde ;
le script détecte et refuse de conclure dessus). Le résultat **robuste** ne dépend que du
turnover et de l'excédent mesurés en (a) :

* turnover annualisé du book = **5.54 × le capital** ;
* excédent brut = **+4.21 %/an** ;
* → **POINT MORT = 75.9 bps** de coût aller simple.

| coût aller simple | coût annuel | excédent net | profil |
|---|---|---|---|
| 2.5 bps | 0.14 % | +4.07 % | large-cap (calibré repo) |
| 25 bps | 1.39 % | +2.82 % | small-cap liquide |
| 50 bps | 2.77 % | +1.44 % | small-cap |
| **75.9 bps** | 4.21 % | **0.00 %** | **point mort** |
| 100 bps | 5.54 % | −1.33 % | small-cap peu liquide |
| 200 bps | 11.09 % | −6.88 % | micro-cap / penny |

Les small-caps ont typiquement **50-300 bps** d'écart effectif (Lesmond-Schill-Zhou 2004)
→ l'excédent est **mangé ou proche de zéro** dans la plage réaliste, et **franchement
négatif** en micro-cap/penny — exactement le segment de l'ancien book. **Et il n'était
déjà pas significatif avant coûts** (t=0.52, DSR 0.05) : les frictions ne font qu'enfoncer
un edge non prouvé.

**Conclusion (a)+(c) :** le small-cap momentum long-only **ne constitue pas un edge
exploitable** — pas d'alpha démontrable sur son propre univers, et le peu d'excédent brut
qu'il affiche ne survit pas aux frictions réelles de ce segment. La famille visée par
l'ancien système était la bonne *intuition* (Hong-Lim-Stein), mais son rendement observé
reste **beta × régime × survivorship**, non un edge répétable. Cohérent avec la littérature : Hou-Xue-Zhang (2020, les anomalies ne
répliquent pas hors micro-caps sur-pondérés) ; Shumway (1997, delisting bias — les radiées
à zéro sont invisibles dans un compte, gonflant l'affichage) ; Lesmond-Schill-Zhou (2004,
momentum small-cap mangé par les coûts) ; Bali-Cakici-Whitelaw (2011, les titres loterie
sous-performent en moyenne — on voit les gagnants). ⚠️ Tout ci-dessus est **encore
survivor-biased à la hausse** (Alpaca = cotés). L'edge *répétable* reste le momentum **L/S
large-cap modeste** ; le reste est beta + convexité + survivorship — un choix d'**appétit
au risque** (rendement/drawdown élevés, régime-dépendant), pas un edge validé.

### 🚩 ÉTUDE SYSTÉMATIQUE FACTEURS × TAILLE (8 facteurs × 3 terciles, 18 ans, coûts par segment)

Trou comblé : les tests small-cap précédents ne portaient que sur **un** facteur (momentum).
`run_size_factor_study.py` teste **les 8 facteurs classiques × 3 terciles de taille** sur
18 ans, avec deux corrections méthodologiques : **coûts différenciés par segment**
(grand 5 / moyen 25 / petit 60 bps aller simple) et **alpha excédentaire** en long-only
(book − équipondéré du *même* tercile).

Benchmarks équipondérés : T1 grand **+0.90**, T2 moyen **+0.84**, T3 petit **+0.93** —
acheter n'importe quel segment équipondéré donnait déjà un excellent Sharpe.

**Meilleurs alphas excédentaires par segment (aucun significatif) :**

| tercile | meilleur facteur | IC t | excès Sharpe | excès t | excès an. |
|---|---|---|---|---|---|
| T1 grand | reversal_21 | +1.06 | +0.10 | +0.43 | +3.6 % |
| T2 moyen | reversal_5 | +1.93 | +0.17 | **+0.75** | **+12.6 %** |
| T3 petit | momentum_12_1 | +1.98 | +0.03 | +0.11 | +0.9 % |

**AUCUN facteur ne passe** (aucun `|IC t| > 2` **et** `excès t > 2`) dans **aucun**
segment après coûts réalistes. Trois observations :

1. **Le short est ruineux en small-cap** : tous les Sharpe L/S y sont négatifs
   (−0.42 à −1.68) — squeezes + coûts d'emprunt, cohérent avec (a).
2. **Reversal court terme en mid-cap** est le « moins mort » (+12.6 %/an) mais avec
   **t = 0.75** : rendement élevé, volatilité énorme, non significatif. C'est le seul
   candidat que la littérature (Jegadeesh 1990/Lehmann 1990, reversal plus fort en
   illiquide) rendrait plausible — mais les données ne le confirment pas.
3. **IC significatif ≠ book profitable** : `max_lottery` a IC t = +2.70 en small-cap mais
   un excès de **−0.37** — relation **non monotone** (même artefact de queue que
   l'anomalie du combinateur, cf. P1). Confirme aussi Bali-Cakici-Whitelaw (2011) :
   acheter les titres « loterie » sous-performe.

**Conclusion :** l'hypothèse « l'edge est ailleurs, en small/mid-cap » est **testée et
non confirmée** pour l'ensemble des facteurs *prix*. Le beta du segment (≈ +0.9 de Sharpe)
domine tout ce que les facteurs prix peuvent ajouter, dans les trois tailles.

**Reste honnêtement non testé (limite de données, pas de conclusion possible) :** les
facteurs **fondamentaux** (value/quality — Piotroski F-score conçu *pour* les small
values) et l'**illiquidité d'Amihud** sur small-caps — ils exigent des fondamentaux PIT
et des volumes sur 1458 titres × 18 ans, hors de portée des sources actuelles (quota
Polygon 5 req/min ; panel Yahoo close-only).

### ✅ VALUE / QUALITY sur SMALL-CAPS (fondamentaux PIT réels) — REJETÉS

Les facteurs value/quality n'avaient été testés que sur **50 large-caps**. Or Fama-French
(value plus fort en small) et surtout **Piotroski (2000)** — dont le F-score a été conçu
*pour* les small value stocks — les y attendent. Re-testés sur **123 small-caps** avec
**fondamentaux point-in-time réels** (Polygon, ``filing_date``, `allow_synthetic_fallback=
False` → aucune donnée synthétique), coûts 60 bps, 2016-2026
(`run_smallcap_value_quality.py`) :

| facteur | couverture | IC t | L/S Sharpe | LO excès Sh | excès t |
|---|---|---|---|---|---|
| earnings_yield (E/P) | 61 % | +0.30 | −0.65 | −0.12 | −0.37 |
| book_to_price (B/P) | 65 % | +0.37 | +0.19 | −0.03 | −0.10 |
| roe | 63 % | +0.19 | −0.93 | −0.25 | −0.76 |
| gross_profitability (GP/A) | 46 % | +0.34 | +0.13 | +0.05 | +0.14 |

**Aucun signal, même pas au niveau de l'IC** (t entre 0.19 et 0.37 — nul). Le résultat
large-cap se reproduit en small-cap : la value/quality n'a pas d'edge exploitable ici.
*Réserves : sous-échantillon de 123 titres (quota Polygon 5 req/min), couverture
fondamentale partielle (46-65 %), univers survivant.*

### ⭐ ILLIQUIDITÉ D'AMIHUD EN SMALL-CAP — le meilleur candidat de toute la campagne

Correction d'un **contresens** : Amihud (2002) avait été testé sur **50 large-caps** et
rejeté — or la prime d'illiquidité est *par construction* un phénomène **small-cap**.
Re-testé au bon endroit (`run_smallcap_illiquidity.py`, 484 small-caps, **vrais volumes**
Alpaca 2020-2026, 3 hypothèses **pré-enregistrées**, coûts 60 bps) :

| facteur | IC t | **L/S Sharpe net** | LO excès Sh | excès t |
|---|---|---|---|---|
| **amihud (illiquidité)** | **+2.29** | **+1.55** | +0.74 | +1.77 |
| turnover_low (négligé) | +2.23 | +1.47 | +0.62 | +1.50 |
| volume_shock (attention) | +0.56 | −1.91 | −0.53 | −1.26 |

**Examen approfondi du candidat Amihud (L/S market-neutral — son Sharpe *est* l'alpha) :**

| test | résultat |
|---|---|
| Sharpe net total | **+1.55** (t = **+3.72**) |
| Sous-périodes (COVID / bear 2022 / 2024-26) | **+1.58 / +1.95 / +1.83** — stable partout |
| Rendement net an. / max drawdown | **+29.4 %** / **−7.4 %** |
| Sensibilité coûts (25→300 bps) | +1.62 / +1.55 / +1.47 / +1.27 / **+1.07 à 300 bps** |
| DSR | **0.995** (N=3) · 0.708 (N=11) · 0.233 (N=32) |

C'est le **premier signal de toute la campagne** à combiner : IC significatif, Sharpe L/S
net élevé, **stabilité sur trois régimes distincts**, drawdown faible, et **robustesse
extrême aux coûts** (survit à 300 bps). Structure favorable à l'implémentation : on
**shorte les plus liquides** (borrow facile) et on **achète les plus illiquides** (côté
achat seulement).

**⚠️ RÉSERVE FATALE — le biais de survie est MAXIMALEMENT concentré sur ce facteur.**
Acheter les titres **les plus illiquides** revient à acheter exactement ceux qui ont le
plus de probabilité d'être **radiés** — et les radiés sont **absents** du panel (Alpaca =
cotés aujourd'hui). Pour tout autre facteur ce biais gonfle modérément ; ici il frappe
**directement le côté long**. Ajoutons : fenêtre de **6 ans seulement** (profondeur IEX)
démarrant au creux COVID, et DSR qui échoue si l'on compte les ~32 essais de la campagne.

**Statut : CANDIDAT SÉRIEUX, non inscrit.** La seule validation qui compte pour ce facteur
précis est un panel **incluant les radiés** (Sharadar/CRSP). Sans lui, impossible de
distinguer une vraie prime d'illiquidité d'un artefact de survivants. *Note théorique :
la prime d'illiquidité est une compensation POUR le coût de transaction — sa robustesse
apparente aux coûts (+1.07 à 300 bps) est cohérente avec la théorie, mais mérite la même
prudence.*

#### ⭐⭐ Extension 18 ANS (volumes consolidés) — le seul signal à passer le portail complet

Le test ci-dessus était limité à 6 ans (profondeur du feed Alpaca). Extension du fetcher
Yahoo aux **volumes** (`fetch_daily_ohlcv_yahoo`) → **486 small-caps × 18 ans (2008-2026)** :

| grandeur | valeur |
|---|---|
| **Sharpe L/S net** (60 bps) | **+2.16** (t = **+9.24**) |
| Rendement net / max drawdown | +13.8 %/an / **−5.7 %** |
| **DSR** | **1.000** — à N=3, N=11 **et N=32** |
| Sensibilité coûts (25→300 bps) | +2.26 / +2.16 / +2.05 / +1.75 / **+1.46** |

**Positif dans les SIX régimes** — y compris la crise de 2008 :

| régime | Sharpe | t | rdt an |
|---|---|---|---|
| 2008-2009 (crise) | +2.22 | +2.94 | +21.1 % |
| 2010-2014 (reprise) | +0.75 | +1.67 | +3.6 % |
| 2015-2019 (bull calme) | +1.52 | +3.39 | +7.8 % |
| 2020-2021 (COVID) | +2.48 | +3.51 | +19.3 % |
| 2022-2023 (bear/taux) | +2.72 | +3.83 | +15.0 % |
| 2024-2026 | +4.61 | +7.39 | +35.0 % |

**Capacité et implémentabilité — vérifiées :** la jambe « illiquide » a un $volume médian
de **31 M$/jour** (ce ne sont PAS des penny stocks, mais les titres *relativement* moins
liquides d'un univers déjà filtré) → capacité ≈ **19 M$** à 1 % de participation. Le
signal **survit aux planchers de liquidité** : +2.16 (aucun) → +1.75 (>1 M$/j) → **+1.14
(>10 M$/j)**, décroissance monotone conforme à une vraie prime d'illiquidité.

**🔧 Défaut d'implémentation critique corrigé.** Le feed **Alpaca IEX ne rapporte que le
volume de la bourse IEX** — mesuré à **~4 % du consolidé** (ratios 20-73× sur AMC, ALGT,
ACIW…). Un Amihud calculé dessus est un proxy dégradé : **+1.55 (IEX) vs +3.48 (consolidé)
sur la même période**. *Cela réfute au passage mon hypothèse initiale* (« l'écart 6 ans vs
18 ans = signature du biais de survie ») : les deux panels contenaient les **mêmes titres**
à 2 près — l'écart venait de la **source des volumes**, pas de la survie.
`AmihudConstruction` récupère donc les volumes **consolidés (Yahoo)** pour la décision.

**Statut : premier signal à franchir le portail complet** (IC t > 2, Sharpe net > 0,
**DSR ≥ 0.95 même à 32 essais**), stable sur 6 régimes, robuste aux coûts et à la
liquidité. **Reste NON INSCRIT** tant que le **biais de survie** n'est pas levé — il
demeure non mesuré (l'univers reste celui des titres cotés aujourd'hui) et frappe
précisément la jambe longue. → **forward-test paper**, qui en est par construction exempt.

### 🔴 TRANSFERT DES MODULES momentum → Amihud : un **bug de production** trouvé

Huit modules avaient été construits pendant la campagne momentum (`vol_management`,
`regime`, `cost_aware`, `meta_labeling`, `multi_strategy`, `robustness`, `tearsheet`,
`execution_algos`). Inventaire : **aucun n'était branché sur le book Amihud** — sauf un,
la **bande de non-transaction à 0.02**, héritée par copie du book méta-momentum et
**jamais testée pour Amihud**. (`run_amihud_module_transfer.py`, 453 small-caps × 18 ans.)

| module | meilleure config | Sharpe | vs référence | verdict |
|---|---|---|---|---|
| — | **band = 0 (référence)** | **+2.13** | — | — |
| `cost_aware` | band = 0.02 **← ce qui tournait en live** | **+0.27** | **−1.87** | 🔴 **BUG** |
| `cost_aware` | band = 10 % de \|w\| (0.0009) | +2.14 | +0.00 | neutre → non retenu |
| `vol_management` | vol-target 15 % | +2.15 | +0.02 | neutre (rdt +25 %, DD −9.4 %) |
| `vol_management` | filtre tendance 200 j | +2.17 | +0.04 | neutre |
| `regime` | HMM risk-off (×0.5) | +2.11 | −0.02 | neutre |
| — | stop-loss 5 % / 10 % / 15 % | +2.08…+2.13 | ≤ 0 | ✅ conforme Kaminski-Lo |

**Le bug, et sa mécanique exacte.** La bande est un seuil en poids **absolu** : elle n'a
de sens que rapportée à la taille d'une ligne. Le book méta-momentum tenait ~10 lignes à
\|w\| ≈ 0.10 → 0.02 = 20 % d'une position, un vrai filtre anti-churn. Le book Amihud tient
**68 lignes à \|w\| ≈ 0.0148**, dont le mouvement maximal mesuré est **\|Δw\| = 0.0263** et
le p99 **0.0185** : une bande de 0.02 **gèle 100 % des mouvements**. Mesuré sur l'univers
exact du runner live (188 titres) : turnover 0.155 → **0.009**, Sharpe **+1.69 → +0.55**.
Le book aurait cessé de se rééquilibrer **définitivement**, sans qu'aucune erreur ne
remonte — la panne silencieuse la plus dangereuse qui soit.

Le book n'a pas encore été touché (`apply_no_trade_band` est un no-op à la mise en place,
`prev = None`) : le gel aurait frappé au **prochain rééquilibrage**. Deux correctifs :

1. `run_amihud_paper.py` : `--no-trade-band` **par défaut 0.0**. Correctement dimensionnée
   (≤ 25 % de \|w\|) la bande ne rapporte rien ici (+2.14 vs +2.13, turnover inchangé) —
   on ne paie pas la complexité d'un paramètre sans gain.
2. `live_trading_pipeline._apply_no_trade_band` : **garde d'échelle** — si
   `band ≥ poids médian d'une ligne`, la bande est neutralisée et journalisée en `error`.
   Le paramètre ne peut plus geler un book en silence, quel que soit le book.
   (Tests de régression : `test_no_trade_band_larger_than_position_is_neutralised`.)

**PBO = 61.5 %** sur les 16 configurations ci-dessus. C'est la bonne lecture du tableau :
*choisir* le meilleur overlay serait du sur-apprentissage 6 fois sur 10. Les overlays ne
sont pas « légèrement positifs », ils sont **indiscernables du bruit** → **book nu**,
aucun overlay inscrit. Le vol-target 15 % est le seul à mériter d'être reconsidéré un jour
(même Sharpe, rendement quasi doublé) — mais au prix d'un levier moyen de 1.93×, hors du
mandat de risque actuel.

### 🔧 SENSIBILITÉ DE LA FENÊTRE au portail — et un **bug de mesure du portail lui-même**

La fenêtre de 60 j d'Amihud n'avait jamais été justifiée : elle a été posée, pas choisie.
Testée par le **portail** (pas par un sweep) sur 5 fenêtres **pré-enregistrées** — 21, 42,
60, 90, 126 j — avec les essais comptés cumulativement (**N = 36** : les 32 de la campagne
+ 4 nouvelles fenêtres) et la **PBO** du choix de fenêtre. Critère de succès **déclaré
avant** le test : le résultat souhaitable n'est pas « 60 j gagne » mais que **toutes** les
fenêtres passent — un signal qui ne survit qu'à un réglage est un artefact de réglage.

**Premier passage : 0/5 fenêtres, IC t négatif partout** (−1.22 à −0.66), y compris celle
en production. Plutôt que d'accepter le verdict, diagnostic de l'écart avec le +2.29 de la
campagne. La cause n'était pas dans le signal :

| horizon de mesure de l'IC | IC moyen | t |
|---|---|---|
| 1 jour (ce que mesurait le portail) | −0.0028 | **−1.74** |
| 1 jour, aux dates de rééquilibrage | −0.0032 | −0.43 |
| **21 jours (l'horizon de détention réel)** | **+0.0335** | **+4.37** |

**Le portail mesurait une décision que la stratégie ne prend pas.** `evaluate_signal`
acceptait `rebalance_every=N` — le book tient donc ses poids N périodes — mais calculait
l'IC contre le rendement à **une** période. Incohérence par construction, pour *tout*
signal. Économiquement, c'est aussi le bon sens : une prime d'illiquidité est une
compensation lente, elle ne prédit pas le lendemain.

Vérification que le Sharpe n'était pas, lui, fabriqué par une queue épaisse (le piège que
le double critère est censé attraper) : médiane quotidienne **+3.74 bps** vs moyenne
+5.33 bps, **54.5 %** de jours positifs, et Sharpe **+1.64 en retirant le top 1 %** des
jours. L'edge est large, pas concentré sur quelques dates.

**Correctif** (`signal_evaluation.evaluate_signal`) : l'IC est mesuré à l'horizon de
détention (`ic_horizon`, défaut = `rebalance_every`) et **échantillonné sans
recouvrement** — une observation tous les h pas, pour ne pas gonfler le t-stat avec des
fenêtres qui partagent leurs rendements. `rebalance_every=1` → comportement historique
inchangé. 5 tests de régression.

**Second passage — 5/5 fenêtres passent** (IC t > 2, Sharpe net > 0, DSR ≥ 0.95 à N=36,
PBO ≤ 0.50) :

| fenêtre | IC t | Sharpe net | DSR | verdict |
|---|---|---|---|---|
| 21 j | +4.43 | +2.19 | 1.000 | ✅ |
| 42 j | +4.34 | +2.26 | 1.000 | ✅ |
| **60 j ← production** | **+4.36** | **+2.26** | **1.000** | ✅ |
| 90 j | +4.44 | +2.26 | 1.000 | ✅ |
| 126 j | +4.54 | +2.30 | 1.000 | ✅ |

**PBO du choix de fenêtre = 43.7 %** — sous le seuil, mais assez haut pour interdire de
« passer à la meilleure » : basculer sur 126 j pour +0.04 de Sharpe serait exactement le
sur-apprentissage que la PBO mesure. **La production reste à 60 j.**

**⚠️ Nuance essentielle : ce ne sont pas 5 confirmations indépendantes.** Corrélation de
rang entre panels : **0.965 à 0.996** ; recouvrement de la jambe longue entre 21 j et
126 j : **75 %**. L'illiquidité est une **caractéristique quasi permanente** d'un titre,
pas un état rapide — la moyenner sur 1 mois ou 6 mois classe presque à l'identique. Le
bon énoncé est donc : *la fenêtre n'est pas un levier*, pas *l'edge a été confirmé cinq
fois*. C'est rassurant (aucun risque de réglage) sans rien ajouter à la preuve.

### 🔻 Effet collatéral du correctif : **momentum_12_1 ne franchit plus le portail**

Le correctif d'horizon tranche **dans les deux sens** — c'est ce qui atteste qu'il mesure
quelque chose de réel plutôt que d'avoir été taillé pour sauver Amihud. Sur les 486
large-caps × 18 ans, reb=10, walk-forward 5 fenêtres :

| horizon de mesure | IC moyen | IC t | Sharpe net | portail |
|---|---|---|---|---|
| 1 j (avant) | +0.0170 | **+4.85** | +0.27 | ✅ |
| **10 j (après)** | **+0.0193** | **+1.83** | +0.27 | ❌ |

L'IC moyen **monte** ; c'est son *t* qui s'effondre, parce que le comptage passe de ~3 900
observations à ~390 — le nombre de **paris réellement indépendants**. Le +4.85 était
gonflé par des fenêtres chevauchantes. La qualité de tri de momentum n'est pas contestée ;
sa **significativité** ne l'est plus sur cet échantillon.

**Décision prise : momentum_12_1 est DÉCLASSÉ.** La suite de tests portait déjà
l'invariant qui tranche — *toute entrée du registre doit réellement passer le portail* —
et le registre est la source de vérité de ce qui a le droit de trader : il ne peut pas
contenir un signal que le portail rejette. L'entrée est déplacée vers un registre
`DECLASSED_SIGNALS` qui **conserve toute la preuve** (décision auditable et réversible),
et dont aucune entrée n'a le droit de décider (`require_validated` la refuse comme un
inconnu).

**`VALIDATED_SIGNALS` est donc VIDE — et c'est l'état honnête du système.** Un registre
vide est aussi l'état le plus **sûr** : `is_validated` renvoie faux pour tout, donc aucun
signal ne décide. Conséquences vérifiées, toutes conformes :

| consommateur | comportement avec registre vide |
|---|---|
| `live_trading_pipeline` (daemon) | abandonne sa composante momentum et **s'abstient** — mécanisme déjà prévu |
| `readiness` critère #3 | **échec** : « registre VIDE » → système **non prêt pour le live** |
| `RebalanceGate` | repli sur cadence 1 — sans effet réel : sans signal validé, il n'y a rien à rééquilibrer |
| `signal_monitor` | garde la base de comparaison via `DECLASSED_SIGNALS` (surveiller la dérive reste utile) |
| **book paper Amihud** | **inchangé** — il n'a jamais dépendu du registre (délibérément non inscrit) |

Le rapport de live-readiness dit désormais la vérité : **aucun signal n'est autorisé à
passer en live**. Le seul candidat (Amihud) attend son forward-test.

**Le moniteur Amihud portait le même bug** — il recopiait la boucle du book au lieu
d'appeler `evaluate_signal`, et calculait donc son IC contre le rendement du lendemain.
Sur sa propre fenêtre récente : **t = +0.62 à 1 j contre t = +3.91 à 21 j**. Comme l'IC à
1 j est *négatif* sur 18 ans (t = −1.74), le critère d'alarme « IC < 0 = edge inversé »
se serait déclenché **à tort sur un signal parfaitement sain**, à la première fenêtre un
peu longue. Le moniteur passe désormais par `evaluate_signal` (le primitif du portail —
une seule définition de la mesure, plus de dérive possible entre les deux) et ses bases
sont recalculées par ce même chemin : `BASELINE_SHARPE` 2.16 → **2.12**, `BASELINE_IC_T`
2.29 → **4.37** (horizon 21 j). État actuel : **HEALTHY**, Sharpe récent +4.53, IC(h=21j)
+0.1755 (t = +3.91) contre une base de +4.37. Le moniteur momentum, lui, appelait déjà
`evaluate_signal` et a hérité du correctif sans modification ; il tire correctement sa
base de `DECLASSED_SIGNALS` (IC t = +1.83).

### ✅ Robustesse microstructure (Asparouhova-Bessembinder-Kalcheva) — l'edge SURVIT

La critique la plus sérieuse contre un résultat d'illiquidité : le **bruit de
microstructure** (bid-ask bounce) biaise à la hausse les portefeuilles **équipondérés**
de titres illiquides — exactement notre jambe longue (ABK, *JFE* 2010 ; *JF* 2013). Leur
correction : pondérer les rendements par `(1 + r_{t−1})`. Testé, plus un saut d'un jour
(`t+2`) qui casse le bounce par construction :

| variante | Sharpe |
|---|---|
| référence (équipondérée, t+1) | **+2.16** |
| saut d'un jour (t+2) | +2.18 |
| **correction ABK (return-weighted)** | **+2.14** |
| ABK + t+2 | +2.15 |
| pondérée par le $volume | +0.83 |

L'edge **survit à toutes les corrections de microstructure** (−0.02 au pire). La chute à
+0.83 en pondération $volume est attendue et cohérente : pondérer par le volume, c'est
sous-pondérer les illiquides — donc désactiver le signal lui-même, pas le corriger.

### ❌ Combinaison multi-facteurs sur Amihud — DÉGRADE (et pourquoi c'était prévisible)

Grinold-Kahn (IR ≈ IC·√Breadth) suppose des composantes à IR **toutes positives**. En
small-cap, les autres facteurs sont **négatifs** : momentum −0.69, reversal −0.44,
low_vol −1.63. Combiner Amihud avec eux fait passer le book de **+2.16 à +0.79**.
Amihud + momentum seul : +1.28. Corrélations : amihud/momentum −0.26, amihud/reversal
−0.02, amihud/low_vol −0.44. **Conclusion : ne pas combiner.** Ajouter un facteur à IR
négatif ne diversifie pas, il dilue.

### 📚 Littérature — la critique la plus sérieuse : *the vanishing illiquidity premium*

Recherche académique ciblée sur ce qui **contredit** notre résultat, pas sur ce qui le
conforte :

- **Amihud (2002)** et la littérature d'origine documentent un alpha 4-facteurs de
  **0.43 %/mois (t = 2.83)** pour l'illiquidité — cohérent avec nos ordres de grandeur.
- **Mais** : *The Vanishing Illiquidity Premium* (Alpha Architect / IBKR Quant, d'après
  Ben-Rephael, Kadan & Wohl) montre que la prime a **fortement décliné, voire disparu**
  dans les marchés développés depuis les années 2000 — la cause étant précisément ce qui
  rend notre stratégie exécutable : **resserrement des spreads, effondrement des
  commissions, décimalisation**. Ce qui subsiste se concentre sur les **microcaps**.
- **Lu & Marisetty (2014)**, *Why is the Amihud measure priced?* : ce que la mesure
  capture n'est pas seulement l'illiquidité mais aussi un **effet de compensation du
  risque de prix** — l'interprétation économique n'est pas univoque.
- **Amihud (2019, *Critical Finance Review*)** réaffirme le pricing de l'illiquidité, y
  compris hors États-Unis — le débat n'est **pas tranché**.

**Ce que cela impose intellectuellement.** Notre backtest 18 ans (2008-2026) dit +2.16
sur *toute* la période, y compris la seconde moitié où la littérature dit la prime
éteinte. Deux lectures, et je ne peux pas trancher entre elles depuis le backtest :
(a) notre construction en **quantiles cross-sectionnels** capture un différentiel
*relatif* d'illiquidité, qui survit même quand le niveau absolu de la prime s'effondre ;
(b) c'est le **biais de survie** qui maintient le chiffre (l'univers est celui des titres
cotés *aujourd'hui*, et la jambe longue illiquide est exactement là où les disparitions
frappent). Ces deux explications produisent le même backtest. **Seul le forward-test
paper les sépare** — ce qui renforce, plutôt qu'il n'affaiblit, la décision de ne pas
inscrire le signal avant d'avoir du hors-échantillon réel. Le moniteur
`monitor_amihud_decay.py` est calibré exactement pour ça : il alarme sur le **signe**
(Sharpe < 0, IC < 0), pas sur l'écart de magnitude à la base 18 ans.

### 🔍 Systèmes comparables (GitHub) — ce qui existe, et ce qu'on n'y trouve pas

- **[SystemicRisk](https://github.com/TommasoBelluzzo/SystemicRisk)** — implémentation de
  référence de l'ILLIQ d'Amihud parmi une batterie d'indicateurs de risque systémique.
  Confirme notre formule ; usage **descriptif**, pas de book long/short.
- **[Stock_master](https://github.com/Brent-Morrison/Stock_master)** — pipeline de données
  calculant les mesures d'Amihud à **1 mois et 3 mois** en parallèle. Notre fenêtre de
  60 j se situe entre les deux ; suggère qu'un test de sensibilité de fenêtre serait
  banal et attendu (non fait — et à ne faire que via le portail, essais comptés).
- **[paperswithbacktest — Amihud Illiquidity Ratio](https://paperswithbacktest.com/course/amihud-illiquidity-ratio)**
  — matériel pédagogique sur le ratio comme signal de trading.
- **Microsoft Qlib**, **QuantConnect-LEAN** — architecture (couches enfichables, PIT),
  déjà source d'inspiration du `framework.py` local.

**Constat honnête de cette revue** : on trouve en abondance le *calcul* de la mesure
d'Amihud, et très peu de **books long/short d'illiquidité validés hors échantillon avec
coûts réels**. C'est cohérent avec la littérature ci-dessus (une prime réputée éteinte
n'attire pas les implémentations publiques) et cela veut dire qu'il n'existe **pas de
référence externe** contre laquelle recouper notre +2.16. Aucun repo trouvé ne traite le
biais de survie sur ce facteur.

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

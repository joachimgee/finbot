"""Robustesse statistique (Tier 3) — anti-surapprentissage / tests multiples.

Un Sharpe OOS positif ne suffit pas : quand on *essaie* beaucoup de
configurations (facteurs, cadences de rééquilibrage, univers…), la meilleure
paraît bonne par pure chance. Bailey & López de Prado (2014) fournissent deux
correctifs, implémentés ici sans dépendance payante :

* **Probabilistic Sharpe Ratio (PSR)** — probabilité que le vrai Sharpe dépasse
  un repère, en tenant compte de la longueur d'échantillon *et* de la
  non-normalité (asymétrie, kurtosis) des rendements.
* **Deflated Sharpe Ratio (DSR)** — le PSR dont le repère est le Sharpe *attendu
  du maximum* sur ``N`` essais indépendants. Il « dégonfle » le Sharpe observé du
  biais de sélection : avec beaucoup d'essais, il faut un Sharpe bien plus élevé
  pour être crédible.

* **Purged & embargoed K-fold** (López de Prado, *Advances in Financial ML*,
  ch. 7) — découpage temporel qui **purge** les observations d'entraînement dont
  la fenêtre d'étiquette chevauche le test, et pose un **embargo** juste après le
  bloc test. Évite la fuite d'information quand les étiquettes se recouvrent
  (horizon de détention > 1 période).

Responsabilité unique : métriques/dispositifs de robustesse purs. Aucune décision
de trading ici ; le portail (``validation_gate``) les consomme.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from scipy.stats import norm

__all__ = [
    "deflated_sharpe_ratio",
    "expected_max_sharpe",
    "probabilistic_sharpe_ratio",
    "probability_of_backtest_overfitting",
    "purged_kfold_indices",
    "sharpe_per_period",
]

_EULER = 0.5772156649015329  # constante d'Euler-Mascheroni (γ)


def sharpe_per_period(returns: pd.Series) -> float:
    """Sharpe **par période** (non annualisé) : moyenne / écart-type.

    Les formules PSR/DSR raisonnent en Sharpe par observation ; annualiser
    fausserait la variance de l'estimateur. Renvoie 0.0 si dégénéré.
    """
    r = pd.Series(returns).dropna().astype(float)
    sd = r.std(ddof=1)
    if len(r) < 2 or sd == 0:
        return 0.0
    return float(r.mean() / sd)


def probabilistic_sharpe_ratio(
    returns: pd.Series, sr_benchmark: float = 0.0,
) -> float:
    """PSR : P(Sharpe vrai > ``sr_benchmark``), corrigé de skew/kurtosis et de T.

    ``sr_benchmark`` est un Sharpe **par période** (mêmes unités que
    :func:`sharpe_per_period`). Renvoie une probabilité dans ``[0, 1]`` ; 0.0 si
    l'échantillon est trop court pour estimer la variance de l'estimateur.

    PSR = Φ( (SR − SR₀)·√(T−1) / √(1 − γ₃·SR + ((γ₄−1)/4)·SR²) ),
    avec γ₃ l'asymétrie et γ₄ la kurtosis *non* excédentaire (normale = 3).
    """
    r = pd.Series(returns).dropna().astype(float)
    t = len(r)
    if t < 3:
        return 0.0
    sr = sharpe_per_period(r)
    skew = float(r.skew())
    kurt = float(r.kurt()) + 3.0  # pandas rend l'excès -> repasser en non-excès
    denom = 1.0 - skew * sr + ((kurt - 1.0) / 4.0) * sr * sr
    if denom <= 0 or math.isnan(denom):
        return 0.0
    z = (sr - sr_benchmark) * math.sqrt(t - 1) / math.sqrt(denom)
    return float(norm.cdf(z))


def expected_max_sharpe(n_trials: int, sr_std: float) -> float:
    """Sharpe **attendu du maximum** sur ``n_trials`` essais indépendants (par période).

    E[max SR] ≈ σ_SR·[ (1−γ)·Φ⁻¹(1 − 1/N) + γ·Φ⁻¹(1 − 1/(N·e)) ]  (Bailey-LdP).

    ``sr_std`` est l'écart-type des Sharpes (par période) *à travers les essais*
    — la dispersion réellement observée sur les configurations testées. Avec un
    seul essai, le repère est 0 (pas de biais de sélection).
    """
    if n_trials <= 1 or sr_std <= 0:
        return 0.0
    n = float(n_trials)
    q1 = norm.ppf(1.0 - 1.0 / n)
    q2 = norm.ppf(1.0 - 1.0 / (n * math.e))
    return float(sr_std * ((1.0 - _EULER) * q1 + _EULER * q2))


def deflated_sharpe_ratio(
    returns: pd.Series, n_trials: int, sr_std: float,
) -> tuple[float, dict[str, float]]:
    """DSR : PSR dont le repère est le Sharpe attendu du max sur ``n_trials``.

    Args:
        returns: rendements **nets par période** de la meilleure configuration.
        n_trials: nombre de configurations essayées (facteurs × cadences × …).
        sr_std: écart-type des Sharpes par période à travers ces essais.

    Returns:
        ``(dsr, diag)`` — ``dsr`` ∈ [0,1] est P(vrai Sharpe > E[max sous H0]).
        ``diag`` expose SR observé, repère dégonflé, skew, kurtosis, T.
    """
    r = pd.Series(returns).dropna().astype(float)
    sr0 = expected_max_sharpe(n_trials, sr_std)
    dsr = probabilistic_sharpe_ratio(r, sr_benchmark=sr0)
    diag = {
        "sr_per_period": sharpe_per_period(r),
        "sr_benchmark": sr0,
        "skew": float(r.skew()) if len(r) >= 3 else float("nan"),
        "kurtosis": (float(r.kurt()) + 3.0) if len(r) >= 4 else float("nan"),
        "n_obs": float(len(r)),
        "n_trials": float(n_trials),
    }
    return dsr, diag


def purged_kfold_indices(
    n_obs: int, n_splits: int = 5, *, embargo: int = 0, purge: int = 1,
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Indices K-fold **purgés + embargo** pour séries temporelles à étiquettes recouvrantes.

    Variante *index-only* et à **purge bilatérale**, taillée pour le portail de
    signaux cross-section. Elle complète la classe
    :class:`financial_analyzer.backtest.validation.purged_cv.PurgedKFold` (voie ML,
    orientée modèle/timestamps) dont la méthode ``'simple'`` ne purge *que* le côté
    postérieur (test + embargo) : ici on purge **des deux côtés**, car le score en
    t prédit un rendement t→t+h et l'entraînement *juste avant* le test fuit tout
    autant que celui juste après.

    Chaque *test* est un bloc temporel contigu. L'*entraînement* exclut :

    * une bande de ``purge`` observations de part et d'autre du bloc test (dont
      l'étiquette chevauche la fenêtre test),
    * ``embargo`` observations supplémentaires *juste après* le bloc test.

    Args:
        n_obs: nombre d'observations (dates) ordonnées dans le temps.
        n_splits: nombre de plis.
        embargo: taille de l'embargo (en observations) après chaque test.
        purge: nombre d'observations purgées de chaque côté (≈ horizon d'étiquette).

    Returns:
        Liste de ``(train_idx, test_idx)`` (tableaux d'entiers positionnels).
    """
    if n_splits < 2:
        raise ValueError("n_splits doit être ≥ 2")
    if n_obs < n_splits:
        raise ValueError(f"n_obs ({n_obs}) < n_splits ({n_splits})")
    all_idx = np.arange(n_obs)
    bounds = np.linspace(0, n_obs, n_splits + 1).astype(int)
    folds: list[tuple[np.ndarray, np.ndarray]] = []
    for k in range(n_splits):
        t0, t1 = bounds[k], bounds[k + 1]  # bloc test [t0, t1)
        test_idx = all_idx[t0:t1]
        lo = max(0, t0 - purge)
        hi = min(n_obs, t1 + purge + embargo)
        mask = np.ones(n_obs, dtype=bool)
        mask[lo:hi] = False  # purge des deux côtés + embargo après
        train_idx = all_idx[mask]
        folds.append((train_idx, test_idx))
    return folds


def probability_of_backtest_overfitting(
    perf: pd.DataFrame, n_splits: int = 10,
) -> tuple[float, dict[str, float]]:
    """PBO par CSCV (Combinatorial Symmetric Cross-Validation, Bailey-LdP 2015).

    Répond à : « en choisissant *la meilleure* configuration in-sample, quelle est
    la probabilité qu'elle soit sous la médiane out-of-sample ? » (= le tri a
    sur-appris). Complète le DSR : le DSR dégonfle *un* Sharpe pour N essais ; la PBO
    juge le **processus de sélection** sur la matrice de performance complète.

    Algorithme : on partitionne le temps en ``n_splits`` blocs (pair) ; pour chaque
    combinaison de la moitié des blocs (train) vs l'autre moitié (test), on prend la
    config au meilleur Sharpe *in-sample* et on mesure son **rang** *out-of-sample*.
    ``PBO = P(logit(rang relatif) < 0)`` = fréquence où le meilleur IS finit sous la
    médiane OOS.

    Args:
        perf: matrice ``(temps × configurations)`` de rendements par période — une
            colonne par configuration essayée (facteur × cadence, etc.).
        n_splits: nombre de blocs temporels S (rendu pair ; C(S, S/2) combinaisons).

    Returns:
        ``(pbo, diag)`` — ``pbo`` ∈ [0,1] (plus bas = sélection plus robuste) ;
        ``diag`` expose #configs, #combinaisons, logit médian.
    """
    from itertools import combinations

    m = perf.dropna(how="any")
    t, n = m.shape
    if n < 2:
        raise ValueError("PBO exige ≥ 2 configurations (colonnes).")
    if n_splits % 2:
        n_splits += 1
    if t < n_splits:
        raise ValueError(f"Historique ({t}) < n_splits ({n_splits}).")
    vals = m.to_numpy()
    bounds = np.linspace(0, t, n_splits + 1).astype(int)
    blocks = [np.arange(bounds[i], bounds[i + 1]) for i in range(n_splits)]
    full = set(range(n_splits))

    def _sharpe_cols(idx: np.ndarray) -> np.ndarray:
        sub = vals[idx]
        mu = sub.mean(axis=0)
        sd = sub.std(axis=0, ddof=1)
        return np.where(sd > 0, mu / sd, -np.inf)

    logits: list[float] = []
    for train in combinations(range(n_splits), n_splits // 2):
        tr = np.concatenate([blocks[i] for i in train])
        te = np.concatenate([blocks[i] for i in sorted(full - set(train))])
        r_is = _sharpe_cols(tr)
        r_oos = _sharpe_cols(te)
        best = int(np.argmax(r_is))
        # Rang OOS de la config best (1 = pire, n = meilleur).
        order = np.argsort(r_oos, kind="stable")
        rank = np.empty(n, dtype=float)
        rank[order] = np.arange(1, n + 1)
        omega = rank[best] / (n + 1)  # rang relatif ∈ (0,1)
        omega = min(max(omega, 1e-6), 1 - 1e-6)
        logits.append(float(np.log(omega / (1.0 - omega))))
    arr = np.array(logits)
    pbo = float((arr < 0).mean())
    return pbo, {
        "n_configs": float(n),
        "n_combinations": float(len(arr)),
        "median_logit": float(np.median(arr)),
    }

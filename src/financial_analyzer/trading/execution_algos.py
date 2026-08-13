"""Algorithmes d'exécution — planification d'ordres enfants (TWAP/VWAP/POV/AC).

Un gros ordre exécuté d'un coup paie un **impact de marché** (∝ taille/ADV). Le
découper en ordres enfants étalés réduit l'impact — au prix d'un **risque de
timing** (le prix bouge pendant qu'on trade). C'est l'arbitrage d'Almgren-Chriss
(2000). Ce module fournit la **logique de planification pure** (quantités enfants),
testable et indépendante de tout moteur temps-réel :

* :func:`twap_schedule` — tranches égales dans le temps (baseline).
* :func:`vwap_schedule` — tranches ∝ profil de volume (suivre le marché).
* :func:`pov_schedule` — *participation of volume* : enfant = min(reste, part·volume).
* :func:`almgren_chriss_schedule` — trajectoire optimale impact vs risque (urgence κ).
* :func:`expected_impact_cost` — coût d'impact d'un planning (modèle AC) pour évaluer.

⚠️ L'étalement *réel* dans le temps exige un driver d'exécution temps-réel (hors de
ce module) ; ici on calcule **quoi** envoyer et **quand** (par intervalle), pas le
sommeil entre envois. Quantités entières, somme = quantité parente (préservée).
"""
from __future__ import annotations

import numpy as np

__all__ = [
    "almgren_chriss_schedule",
    "expected_impact_cost",
    "pov_schedule",
    "twap_schedule",
    "vwap_schedule",
]


def _round_preserve_sum(weights: np.ndarray, total: int) -> list[int]:
    """Répartit ``total`` (entier) selon ``weights`` (≥0) en entiers de somme exacte
    (méthode du plus grand reste)."""
    w = np.asarray(weights, float)
    w = np.clip(w, 0.0, None)
    s = w.sum()
    if s <= 0 or total <= 0:
        return [0] * len(w)
    raw = w / s * total
    floor = np.floor(raw).astype(int)
    rem = total - int(floor.sum())
    # Distribuer les unités restantes aux plus grands restes fractionnaires.
    order = np.argsort(-(raw - floor))
    for i in range(rem):
        floor[order[i % len(order)]] += 1
    return floor.tolist()


def twap_schedule(total_qty: int, n_slices: int) -> list[int]:
    """TWAP : ``n_slices`` tranches ~égales (somme = ``total_qty``)."""
    if n_slices < 1:
        raise ValueError("n_slices doit être ≥ 1")
    return _round_preserve_sum(np.ones(n_slices), int(total_qty))


def vwap_schedule(total_qty: int, volume_profile) -> list[int]:
    """VWAP : tranches ∝ ``volume_profile`` (une valeur par intervalle)."""
    prof = np.asarray(volume_profile, float)
    if prof.size == 0:
        raise ValueError("volume_profile ne peut pas être vide")
    return _round_preserve_sum(prof, int(total_qty))


def pov_schedule(
    total_qty: int, interval_volumes, participation: float,
) -> list[int]:
    """POV : par intervalle, enfant = ``min(reste, participation × volume)``.

    S'arrête quand tout est placé ; le reste éventuel (volume insuffisant) est
    ajouté au dernier intervalle disponible. ``participation`` ∈ (0, 1].
    """
    if not 0.0 < participation <= 1.0:
        raise ValueError("participation doit être dans (0, 1]")
    vols = np.asarray(interval_volumes, float)
    remaining = int(total_qty)
    out: list[int] = []
    for v in vols:
        take = min(remaining, int(np.floor(max(v, 0.0) * participation)))
        out.append(take)
        remaining -= take
    if remaining > 0 and out:  # reste non plaçable -> dernier intervalle
        out[-1] += remaining
    return out


def almgren_chriss_schedule(
    total_qty: int, n_slices: int, kappa: float = 0.0,
) -> list[int]:
    """Trajectoire d'Almgren-Chriss (impact vs risque), urgence ``kappa`` ≥ 0.

    ``kappa → 0`` ⇒ TWAP (trajectoire linéaire, patient). ``kappa`` élevé ⇒
    **front-loaded** (on trade vite pour réduire le risque de timing, au prix de
    plus d'impact). Trades enfants = décroissance des positions restantes
    ``xⱼ = Q·sinh(κ(T−tⱼ))/sinh(κT)``.
    """
    if n_slices < 1:
        raise ValueError("n_slices doit être ≥ 1")
    if kappa < 0:
        raise ValueError("kappa doit être ≥ 0")
    if kappa == 0:
        return twap_schedule(total_qty, n_slices)
    t = np.arange(n_slices + 1)
    x = np.sinh(kappa * (n_slices - t)) / np.sinh(kappa * n_slices)  # positions restantes
    trades = x[:-1] - x[1:]  # part de chaque intervalle (somme = 1)
    return _round_preserve_sum(trades, int(total_qty))


def expected_impact_cost(
    schedule, adv: float, price: float,
    eta: float = 0.1, sigma: float = 0.02, tau: float = 1.0, risk_aversion: float = 0.0,
) -> float:
    """Coût espéré (impact temporaire + terme de risque) d'un planning — modèle AC.

    Impact temporaire par intervalle : ``η · (nⱼ/(ADV·τ)) · nⱼ · price`` (impact ∝
    taux de participation). Terme de risque : ``½·risk_aversion·σ²·Σ xⱼ²`` (variance
    du prix sur les positions résiduelles). Sert à *comparer* des plannings ; unités
    monétaires cohérentes, pas une prédiction exacte.
    """
    n = np.asarray(schedule, float)
    if n.sum() <= 0 or adv <= 0:
        return 0.0
    rate = n / (adv * max(tau, 1e-9))
    impact = float((eta * rate * n * price).sum())
    remaining = n[::-1].cumsum()[::-1]  # positions restantes avant chaque tranche
    timing_risk = 0.5 * risk_aversion * (sigma ** 2) * float((remaining ** 2).sum())
    return impact + timing_risk

"""Définition **canonique** du signal d'illiquidité d'Amihud — une seule, partagée.

Ce module existe pour une raison précise, et c'est une leçon payée deux fois.

La formule d'Amihud était écrite **cinq fois** dans le dépôt : une dans le chemin live
(``trading/framework.py``) et quatre dans les scripts de recherche. Les copies
concordaient — jusqu'à ce qu'elles cessent de concorder ailleurs :

* une **bande de non-transaction** calibrée sur un book concentré (~10 lignes, |w| ≈ 0.10)
  a été recopiée sur le book Amihud (~68 lignes, |w| ≈ 0.015) : 100 % des mouvements gelés,
  Sharpe 18 ans +1.69 → +0.55 ;
* le **moniteur** recopiait la boucle du book et mesurait son IC contre le rendement du
  lendemain alors que le book détient 21 jours : l'alarme « edge inversé » se serait
  déclenchée sur un signal parfaitement sain.

Aucun des deux n'était une erreur de formule. Les deux étaient des erreurs de
**duplication** : deux endroits censés dire la même chose, et rien pour l'imposer.
C'est exactement ce que les moteurs industriels (NautilusTrader, LEAN) traitent par
construction — *le même chemin de code tourne en backtest et en live*.

Règle de ce module : **le backtest, le moniteur et le book live appellent tous les
fonctions ci-dessous.** Aucun ne recalcule l'illiquidité par lui-même. Une
divergence de définition devient alors impossible, pas seulement improbable — et un
test de parité (``test_amihud_parity.py``) vérifie que les deux chemins produisent le
**même book** à partir des mêmes données.

Référence : Amihud (2002), *Illiquidity and stock returns: cross-section and
time-series effects*, Journal of Financial Markets.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

__all__ = [
    "AMIHUD_SCALE",
    "AmihudSpec",
    "amihud_illiquidity",
    "amihud_weights",
    "prepare_panels",
]

#: Facteur d'échelle appliqué à la mesure brute, pour lisibilité seulement.
#: **Neutre sur le signal** : multiplier par une constante positive ne change aucun
#: rang cross-sectionnel, donc aucun poids. Fixé ici pour que backtest et live
#: affichent les mêmes ordres de grandeur dans les journaux.
AMIHUD_SCALE = 1e9


@dataclass(frozen=True)
class AmihudSpec:
    """Paramètres du book d'illiquidité — **source unique**, backtest et live.

    Chaque valeur est celle qui a été validée, pas une valeur par défaut de confort :

    * ``window`` — 60 j. Passée au portail sur 5 fenêtres pré-enregistrées
      (21/42/60/90/126) : les 5 passent, la corrélation de rang entre panels est de
      0.965 à 0.996. La fenêtre n'est pas un levier ; on garde celle qui tourne.
    * ``quantile`` — 20 % de chaque côté (long les plus illiquides, short les plus
      liquides).
    * ``rebalance_every`` — 21 j ouvrés, cadence testée (plateau de Sharpe).
    * ``cost_bps`` — 60 bps, coûts small-cap retenus pour toute la campagne.
    * ``min_names`` — en deçà, le tri cross-sectionnel n'a pas de sens : on s'abstient.
    * ``min_history_frac`` — fraction d'historique exigée pour retenir un titre.

    ``no_trade_band`` vaut **0** délibérément : la bande est un seuil en poids absolu,
    elle n'a de sens que rapportée à la taille d'une ligne, et sur ce book (|w| ≈ 0.015)
    toute valeur usuelle le gèlerait. Correctement dimensionnée elle n'apporte rien
    (+2.14 vs +2.13). Cf. ``scripts/run_amihud_module_transfer.py``.
    """

    window: int = 60
    quantile: float = 0.2
    rebalance_every: int = 21
    cost_bps: float = 60.0
    min_names: int = 20
    min_history_frac: float = 0.6
    no_trade_band: float = 0.0


#: Spécification en vigueur (celle du book paper en cours).
DEFAULT_SPEC = AmihudSpec()


def prepare_panels(
    close: pd.DataFrame,
    volume: pd.DataFrame,
    *,
    min_history_frac: float = DEFAULT_SPEC.min_history_frac,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Aligne et nettoie les panels (close, volume) — **prétraitement canonique**.

    Étapes, dans cet ordre : report des derniers cours connus (``ffill``), abandon des
    titres dont l'historique est trop lacunaire, abandon des dates entièrement vides,
    puis réalignement du volume sur le close retenu.

    Ce prétraitement faisait aussi partie des divergences : les scripts filtraient sur
    ``min_history_frac`` et le chemin live ne filtrait pas du tout.

    Args:
        close: panel de clôtures (dates × tickers).
        volume: panel de volumes, mêmes axes.
        min_history_frac: fraction minimale de dates non manquantes pour garder un titre.

    Returns:
        ``(close, volume)`` nettoyés et alignés. Panels vides en entrée → panels vides
        en sortie (aucune exception : une préparation de données ne casse pas un run).
    """
    if close is None or close.empty:
        return pd.DataFrame(), pd.DataFrame()
    c = close.sort_index().ffill()
    if min_history_frac > 0:
        c = c.dropna(axis=1, thresh=int(min_history_frac * len(c)))
    c = c.dropna(how="all")
    if c.empty:
        return pd.DataFrame(), pd.DataFrame()
    v = (volume if volume is not None else pd.DataFrame()).reindex(
        columns=c.columns, index=c.index
    )
    return c, v


def amihud_illiquidity(
    close: pd.DataFrame,
    volume: pd.DataFrame,
    window: int = DEFAULT_SPEC.window,
) -> pd.DataFrame:
    """Mesure d'illiquidité d'Amihud (2002) — **la** définition du dépôt.

    ``ILLIQ[t] = moyenne sur `window` jours de |r| / (close × volume)``, mise à
    l'échelle par :data:`AMIHUD_SCALE`. Une valeur **haute** = titre **illiquide**
    (le prix bouge beaucoup par dollar échangé) → jambe **longue** du book.

    Le volume doit être **consolidé** : le feed Alpaca IEX ne rapporte que le volume
    de la bourse IEX (~4 % du consolidé, ratios mesurés 20-73×) et dégrade la mesure
    (+1.55 contre +3.48 sur la même période). Les appelants récupèrent donc les volumes
    Yahoo ; cette fonction ne fait que le calcul et fait confiance à son entrée.

    Args:
        close: panel de clôtures (dates × tickers), déjà passé par :func:`prepare_panels`.
        volume: panel de volumes, mêmes axes.
        window: fenêtre de moyennage, en jours.

    Returns:
        Panel (dates × tickers) d'illiquidité. Les dates avant la fin du warm-up et les
        titres à volume nul valent ``NaN`` — jamais 0, qui serait un rang fabriqué.
    """
    if close is None or close.empty or volume is None or volume.empty:
        return pd.DataFrame()
    rets = close.pct_change()
    dollar_volume = (close * volume).replace(0, np.nan)
    return (rets.abs() / dollar_volume).rolling(int(window)).mean() * AMIHUD_SCALE


def amihud_weights(
    scores_row: pd.Series,
    quantile: float = DEFAULT_SPEC.quantile,
    *,
    min_names: int = DEFAULT_SPEC.min_names,
) -> pd.Series:
    """Convertit une ligne d'illiquidité en book long/short dollar-neutre.

    Long le quantile le plus **illiquide**, short le plus **liquide**, équipondéré de
    chaque côté et normalisé à ``somme des |poids| = 1``.

    Args:
        scores_row: illiquidité d'une date (index = tickers).
        quantile: fraction retenue de chaque côté.
        min_names: en deçà, on renvoie un book **vide** — s'abstenir plutôt que trier
            un échantillon trop petit pour que le tri veuille dire quelque chose.

    Returns:
        Series de poids alignée sur ``scores_row`` (0 hors des quantiles retenus) ;
        Series vide si l'abstention s'applique.
    """
    from financial_analyzer.backtest.signal_evaluation import cross_sectional_weights

    row = scores_row.dropna() if scores_row is not None else pd.Series(dtype=float)
    if len(row) < min_names:
        return pd.Series(dtype=float)
    return cross_sectional_weights(row, quantile=quantile, long_short=True)

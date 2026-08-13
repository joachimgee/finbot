"""Rééquilibrage *cost-aware* — bande de non-transaction (Tier / audit #4).

Sous **coûts de transaction proportionnels**, la politique optimale n'est *pas* de
viser exactement le portefeuille cible à chaque date : c'est de ne trader que
lorsque l'écart au cible dépasse un seuil — une **bande de non-transaction**
(Constantinides 1986 ; Davis & Norman 1990 ; Gârleanu & Pedersen 2013, « trade
partially towards the aim »). En deçà de la bande, on *tient* les poids : on paie
moins de turnover, au prix d'un léger décalage au signal. Pour un signal lent
(momentum), l'arbitrage est favorable → **Sharpe net** plus élevé.

Ce module fournit la primitive pure (sans état) ; l'évaluateur (`evaluate_signal`)
et le pipeline live la branchent en option (bande = 0 → comportement inchangé).
"""
from __future__ import annotations

import pandas as pd

__all__ = ["apply_no_trade_band"]


def apply_no_trade_band(
    target: pd.Series, prev: pd.Series | None, band: float,
) -> pd.Series:
    """Applique une **bande de non-transaction** au poids cible.

    Pour chaque actif : si ``|target − prev| < band`` on **garde** ``prev`` (pas de
    trade) ; sinon on va au ``target``. Réduit le turnover (donc les coûts) sans
    dériver du cible au-delà de la bande.

    Args:
        target: poids cibles (Series, index = univers).
        prev: poids détenus avant rééquilibrage (``None`` = mise en place initiale
            → aucun poids à tenir, on renvoie ``target`` tel quel).
        band: largeur de la bande (en poids absolu, p.ex. 0.02 = 2 %). ≤ 0 → no-op.

    Returns:
        Series de poids ajustés (même index que ``target``).
    """
    if band <= 0 or prev is None:
        return target
    idx = target.index.union(prev.index)
    t = target.reindex(idx).fillna(0.0)
    p = prev.reindex(idx).fillna(0.0)
    # Tenir prev là où le mouvement est sous la bande ; sinon aller au cible.
    adjusted = t.where((t - p).abs() >= band, p)
    return adjusted.reindex(target.index).fillna(0.0)

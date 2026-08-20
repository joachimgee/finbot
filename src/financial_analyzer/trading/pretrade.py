"""Contrôles **pré-trade** de négociabilité : emprunt (C) et participation (D).

Le ``RiskGuard`` couvre le risque de *portefeuille* — concentration, levier, drawdown,
circuit breaker. Il ne dit rien de la **faisabilité d'un ordre donné sur un titre donné** :

* un short n'est possible que si le titre est **shortable** et **empruntable** ;
* un ordre n'est absorbable que s'il reste petit devant le **volume quotidien** du titre.

Ces deux contrôles sont standard dans les moteurs d'exécution (NautilusTrader les range
sous *pre-trade risk checks*) et absents ici jusqu'à présent. Ils se branchent sur
l'``OrderGateway`` — le chokepoint unique — donc **tout** chemin d'ordre en hérite, sans
qu'aucun appelant ait à y penser.

Trois issues possibles, et la nuance compte :

* ``allow`` — rien à signaler ;
* ``resize`` — l'ordre dépasse la limite de participation mais une **fraction** passe :
  on réduit plutôt que de renoncer (le book se complètera au rééquilibrage suivant) ;
* ``reject`` — infaisable (short non empruntable, ou titre non négociable).

**Mesure avant conception.** Sur le book Amihud réel (equity ~99 k$, titres à 31 M$/jour
de volume médian), la participation d'un ordre est de l'ordre de **0,003 %** — quatre
ordres de grandeur sous toute limite raisonnable. Et **28/28** des shorts détenus sont
`shortable` **et** `easy_to_borrow`, ce qui n'est pas de la chance : ce book shorte par
construction les titres *les plus liquides*. Ces contrôles ne mordent donc pas
aujourd'hui — ils sont là pour le jour où le capital change d'ordre de grandeur, et pour
que ce jour-là le système refuse au lieu de subir.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Literal, Optional

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

__all__ = ["PretradeDecision", "PretradePolicy", "check_tradability"]

Action = Literal["allow", "resize", "reject"]


@dataclass(frozen=True)
class PretradeDecision:
    """Issue d'un contrôle pré-trade."""

    action: Action
    qty: float
    reason: str = ""

    @property
    def allowed(self) -> bool:
        return self.action != "reject"

    def summary(self) -> str:
        if self.action == "allow":
            return "ok"
        return f"{self.action}: {self.reason}"


@dataclass
class PretradePolicy:
    """Politique de négociabilité appliquée à chaque ordre par le gateway.

    Args:
        max_participation: fraction maximale du volume quotidien moyen qu'un ordre
            peut représenter. 0.01 = 1 %, valeur d'usage courant pour rester sous le
            seuil d'impact significatif. ``None`` désactive le contrôle.
        require_easy_to_borrow: exiger ``easy_to_borrow`` pour vendre à découvert, et
            pas seulement ``shortable``. Un titre `shortable` mais *hard-to-borrow* peut
            être emprunté à un coût élevé et **rappelé** — pour un book tenu 21 jours,
            l'exiger est la position prudente.
        adv_provider: ``symbole -> volume quotidien moyen en dollars``, ou ``None`` si
            inconnu. Fourni par l'appelant, qui a déjà les panels de prix/volume.
        asset_provider: ``symbole -> métadonnées`` (``shortable``, ``easy_to_borrow``,
            ``tradable``), typiquement ``AlpacaAdapter.get_asset``.
        allow_on_unknown: comportement quand l'information manque. ``True`` (défaut) =
            laisser passer en journalisant.

            *Fail-open assumé* : une requête de métadonnée qui échoue ne doit pas geler
            un book entier — le broker refusera lui-même un short impossible, et ce
            refus est journalisé comme un rejet d'ordre, donc visible. L'inverse
            (fail-closed) transformerait une panne d'API en arrêt de la stratégie.
    """

    max_participation: Optional[float] = 0.01
    require_easy_to_borrow: bool = True
    adv_provider: Optional[Callable[[str], Optional[float]]] = None
    asset_provider: Optional[Callable[[str], Optional[dict]]] = None
    allow_on_unknown: bool = True
    _asset_cache: dict = field(default_factory=dict, repr=False)

    def asset(self, symbol: str) -> Optional[dict]:
        """Métadonnées du titre, mises en cache (un appel réseau par symbole et par run)."""
        if symbol in self._asset_cache:
            return self._asset_cache[symbol]
        info = None
        if self.asset_provider is not None:
            try:
                info = self.asset_provider(symbol)
            except Exception as e:  # noqa: BLE001 - une info manquante n'est pas fatale
                logger.warning("Métadonnées indisponibles pour %s (%s).", symbol, e)
                info = None
        self._asset_cache[symbol] = info
        return info

    def check(self, symbol: str, qty: float, side: str,
              price: float | None = None) -> PretradeDecision:
        """Applique la politique à un ordre. Voir :func:`check_tradability`."""
        return check_tradability(symbol, qty, side, price, policy=self)


def check_tradability(
    symbol: str,
    qty: float,
    side: str,
    price: float | None = None,
    *,
    policy: PretradePolicy | None = None,
    opening_short: bool | None = None,
) -> PretradeDecision:
    """Décide si un ordre est négociable, et à quelle taille.

    Args:
        symbol: symbole.
        qty: quantité demandée (positive).
        side: ``'buy'`` ou ``'sell'``.
        price: prix attendu, nécessaire pour convertir la quantité en dollars et la
            comparer au volume quotidien. Absent → le contrôle de participation est
            sauté (on ne fabrique pas un notionnel).
        policy: politique appliquée. ``None`` → tout est autorisé (comportement
            historique inchangé).
        opening_short: ``True`` si cette vente **ouvre ou creuse** un short. ``None``
            (défaut) = inconnu → on traite toute vente comme potentiellement short,
            ce qui est le côté prudent.

    Returns:
        :class:`PretradeDecision`.
    """
    if policy is None:
        return PretradeDecision("allow", qty)
    qty = float(qty)
    if qty <= 0:
        return PretradeDecision("allow", qty)

    # --- (C) Emprunt : une vente à découvert exige un titre shortable ET empruntable.
    is_short = side.lower() == "sell" and (opening_short is not False)
    info = policy.asset(symbol) if (is_short or policy.asset_provider) else None
    if info is None and not policy.allow_on_unknown and is_short:
        return PretradeDecision("reject", 0.0, f"{symbol}: négociabilité inconnue")
    if info is not None:
        if not info.get("tradable", True):
            return PretradeDecision("reject", 0.0, f"{symbol} non négociable chez le broker")
        if is_short:
            if not info.get("shortable", False):
                return PretradeDecision("reject", 0.0, f"{symbol} non shortable")
            if policy.require_easy_to_borrow and not info.get("easy_to_borrow", False):
                return PretradeDecision(
                    "reject", 0.0,
                    f"{symbol} difficile à emprunter (rappel possible sur un book tenu 21 j)")

    # --- (D) Participation : l'ordre doit rester petit devant le volume du titre.
    if policy.max_participation is None or price is None or policy.adv_provider is None:
        return PretradeDecision("allow", qty)
    try:
        adv = policy.adv_provider(symbol)
    except Exception as e:  # noqa: BLE001
        logger.warning("Volume moyen indisponible pour %s (%s).", symbol, e)
        adv = None
    if not adv or adv <= 0:
        return PretradeDecision("allow", qty)

    notional = qty * float(price)
    cap_notional = float(adv) * float(policy.max_participation)
    if notional <= cap_notional:
        return PretradeDecision("allow", qty)

    capped = cap_notional / float(price)
    # Sous une action entière, il n'y a rien à réduire : l'ordre est refusé plutôt que
    # tronqué à zéro (un ordre de quantité nulle serait un faux « exécuté »).
    if capped < 1.0:
        return PretradeDecision(
            "reject", 0.0,
            f"{symbol}: {notional:,.0f} $ dépasse {policy.max_participation:.1%} "
            f"du volume quotidien ({adv:,.0f} $) et ne peut être réduit à ≥ 1 action")
    return PretradeDecision(
        "resize", float(int(capped)),
        f"{symbol}: réduit de {qty:.0f} à {int(capped)} actions "
        f"({policy.max_participation:.1%} du volume quotidien {adv:,.0f} $)")

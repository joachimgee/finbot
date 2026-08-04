"""Politique de sûreté du mode de trading (garde-fou P0).

Sur Alpaca, « paper » vs « live » est déterminé par la **base URL**
(``paper-api.alpaca.markets`` vs ``api.alpaca.markets``), pas par une simple
chaîne ``mode``. Un système qui passe le mode d'un côté et l'URL de l'autre peut
diverger — et trader en réel par accident. Ce module centralise la décision et
la rend *fail-safe* : le live n'est possible que s'il est explicitement, sans
ambiguïté, activé via l'environnement.

Responsabilité unique : décider du mode effectif et de l'URL correspondante.
L'adaptateur broker reste un pur mécanisme ; cette politique est appliquée aux
frontières (factory ``from_env``, chokepoint d'exécution).
"""

from __future__ import annotations

import os
from enum import Enum

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)

__all__ = [
    "LIVE_BASE_URL",
    "LIVE_CONFIRM_TOKEN",
    "LIVE_ENABLE_ENV",
    "PAPER_BASE_URL",
    "TradingMode",
    "assert_live_allowed",
    "base_url_for_mode",
    "live_trading_enabled",
    "resolve_trading_mode",
]

PAPER_BASE_URL = "https://paper-api.alpaca.markets"
LIVE_BASE_URL = "https://api.alpaca.markets"

#: Variable d'environnement qui déverrouille le live. Doit valoir *exactement*
#: le jeton de confirmation ci-dessous — toute autre valeur (absente, vide,
#: "true", faute de frappe) laisse le système en paper.
LIVE_ENABLE_ENV = "FINBOT_ENABLE_LIVE_TRADING"
LIVE_CONFIRM_TOKEN = "I_UNDERSTAND_LIVE_TRADING_RISKS"


class TradingMode(str, Enum):
    """Mode de trading. Hérite de ``str`` pour rester compatible avec le code
    existant qui compare à ``'paper'`` / ``'live'``."""

    PAPER = "paper"
    LIVE = "live"

    @classmethod
    def coerce(cls, value: str | TradingMode) -> TradingMode:
        """Convertit une valeur en TradingMode (insensible à la casse)."""
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).strip().lower())
        except ValueError as exc:  # pragma: no cover - garde-fou
            raise ValueError(
                f"Mode de trading invalide: {value!r} (attendu 'paper' ou 'live')"
            ) from exc


class LiveTradingNotEnabledError(PermissionError):
    """Levée quand du live est tenté sans activation explicite."""


def live_trading_enabled() -> bool:
    """True uniquement si le live est explicitement activé.

    Fail-safe : n'accepte que la valeur exacte du jeton de confirmation. Absente,
    vide, ``"true"``, ``"1"`` ou une faute de frappe → False.
    """
    return os.environ.get(LIVE_ENABLE_ENV, "").strip() == LIVE_CONFIRM_TOKEN


def resolve_trading_mode(requested: str | TradingMode) -> TradingMode:
    """Retourne le mode effectif, en dégradant le live vers paper si non activé.

    Une demande de PAPER passe toujours. Une demande de LIVE n'est honorée que si
    :func:`live_trading_enabled` est vrai ; sinon elle est rétrogradée en PAPER
    avec un avertissement bruyant.
    """
    mode = TradingMode.coerce(requested)
    if mode is TradingMode.LIVE and not live_trading_enabled():
        logger.warning(
            "LIVE trading demandé mais non activé — rétrogradation en PAPER. "
            "Pour activer le live, définir %s=%s.",
            LIVE_ENABLE_ENV,
            LIVE_CONFIRM_TOKEN,
        )
        return TradingMode.PAPER
    return mode


def base_url_for_mode(mode: str | TradingMode) -> str:
    """URL de base Alpaca déterministe à partir du mode.

    C'est *ici* que paper vs live est tranché — jamais par une variable
    d'environnement isolée qui pourrait diverger du mode.
    """
    return LIVE_BASE_URL if TradingMode.coerce(mode) is TradingMode.LIVE else PAPER_BASE_URL


def assert_live_allowed(mode: str | TradingMode) -> None:
    """Lève :class:`LiveTradingNotEnabledError` si du live est tenté sans activation.

    À appeler au dernier moment avant toute action live irréversible (connexion
    d'un broker live, soumission d'un ordre live).
    """
    if TradingMode.coerce(mode) is TradingMode.LIVE and not live_trading_enabled():
        raise LiveTradingNotEnabledError(
            "Trading live non activé : action live refusée. "
            f"Définir {LIVE_ENABLE_ENV}={LIVE_CONFIRM_TOKEN} pour l'autoriser."
        )

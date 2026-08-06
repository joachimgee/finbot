"""Point de soumission d'ordres unique et audité (garde-fou P0).

Avant ce module, la séquence « valider le risque puis soumettre au broker » était
dupliquée à deux endroits (``LiveTradingPipeline._execute_orders_with_risk_checks``
et ``MasterOrchestrator``). Deux copies = deux occasions d'oublier un contrôle.

``OrderGateway`` est le **chokepoint** : tout ordre réel passe par lui, dans un
ordre fixe et audité — garde de mode, contrôle de risque, idempotence, journal —
avant d'atteindre le broker. Il ne réécrit rien : il *compose* le ``RiskGuard`` et
le ``BrokerAdapter`` existants (injection de dépendance) et applique la politique
de sûreté de :mod:`financial_analyzer.trading.safety`.

Responsabilité unique : router un ordre validé vers le broker, une seule fois.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from financial_analyzer.trading.broker_adapter import BrokerAdapter
from financial_analyzer.trading.risk_guard import RiskGuard
from financial_analyzer.trading.safety import assert_live_allowed
from financial_analyzer.utils.helpers import get_logger

if TYPE_CHECKING:
    from financial_analyzer.trading.journal import TradingJournal

logger = get_logger(__name__)

__all__ = ["OrderGateway"]


class OrderGateway:
    """Unique porte de sortie des ordres vers le broker.

    Chaque ``submit`` applique, dans l'ordre :

    1. **Garde de mode** — refuse le live non explicitement activé
       (:func:`~financial_analyzer.trading.safety.assert_live_allowed`).
    2. **Idempotence** — un même ``idempotency_key`` n'est soumis qu'une fois par
       session ; une seconde tentative est ignorée et loggée (protège des doubles
       soumissions accidentelles au sein d'un run).
    3. **Contrôle de risque** — délègue au ``RiskGuard`` injecté (limites dures +
       circuit breaker). Les exceptions du RiskGuard remontent au caller.
    4. **Audit** — journalise l'intention puis le résultat.
    5. **Soumission** — appelle ``broker.submit_order`` (sauf en ``dry_run``).

    Le gateway *ne rattrape pas* les exceptions de validation : il les laisse
    remonter pour que l'appelant décide (abandonner sur circuit breaker, ignorer
    l'ordre sur dépassement de limite, etc.).
    """

    def __init__(
        self,
        broker: BrokerAdapter,
        risk_guard: RiskGuard,
        journal: TradingJournal | None = None,
    ) -> None:
        """
        Args:
            broker: Adaptateur broker connecté (mécanisme de soumission).
            risk_guard: Garde de risque partagé (limites + circuit breaker).
            journal: journal d'exécution optionnel ; si fourni, chaque issue
                (soumission, dry-run, dédup, rejet) y est persistée. La
                journalisation ne peut jamais interrompre le trading.
        """
        self.broker = broker
        self.risk_guard = risk_guard
        self.journal = journal
        # Clés d'idempotence déjà soumises pendant cette session -> résultat broker.
        self._submitted: dict[str, dict[str, Any]] = {}

    def _record(self, **fields: Any) -> None:
        """Persiste un événement d'ordre si un journal est branché (best-effort)."""
        if self.journal is None:
            return
        try:
            self.journal.record_order(mode=getattr(self.broker, "mode", "paper"), **fields)
        except Exception as je:  # noqa: BLE001 - journaling must never break trading
            logger.warning("Journalisation d'ordre échouée: %s", je)

    def submit(
        self,
        symbol: str,
        qty: int,
        side: str,
        price: float | None = None,
        order_type: str = "market",
        idempotency_key: str | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """Soumet un ordre à travers le chokepoint.

        Args:
            symbol: Symbole (ex. ``'AAPL'``).
            qty: Quantité (entier positif).
            side: ``'buy'`` ou ``'sell'``.
            price: Prix attendu, pour le calcul de taille du RiskGuard.
            order_type: ``'market'`` ou ``'limit'``.
            idempotency_key: Clé de déduplication intra-session. Si absente, une
                clé est dérivée de ``(symbol, side, qty, order_type)``.
            dry_run: Si vrai, tout est appliqué (garde, risque, audit) **sauf** la
                soumission réelle — utile pour valider sans engager d'argent.

        Returns:
            Le dict de résultat du broker en cas de soumission ; en ``dry_run`` un
            dict ``{'status': 'dry_run', ...}`` ; sur rejet idempotent, le résultat
            précédemment mémorisé.

        Raises:
            LiveTradingNotEnabledError: Live tenté sans activation.
            CircuitBreakerTriggered / RiskLimitExceeded / InvalidOrderError:
                Propagées telles quelles depuis le RiskGuard.
        """
        key = idempotency_key or f"{symbol}:{side}:{qty}:{order_type}"

        # 1-3. Garde de mode, idempotence et contrôle de risque. Toute issue de
        # rejet est journalisée avant de remonter au caller.
        try:
            # 1. Garde de mode : dernier verrou avant une action potentiellement live.
            assert_live_allowed(getattr(self.broker, "mode", "paper"))

            # 2. Idempotence : ne pas resoumettre une clé déjà passée cette session.
            if key in self._submitted:
                logger.warning(
                    "Ordre idempotent déjà soumis cette session (clé=%s) — ignoré.", key
                )
                self._record(
                    symbol=symbol, side=side, qty=qty, order_type=order_type,
                    status="duplicate_skipped", price=price, dry_run=dry_run,
                )
                return self._submitted[key]

            # 3. Contrôle de risque (les exceptions remontent volontairement).
            self.risk_guard.validate_order(symbol=symbol, qty=qty, side=side, price=price)
        except Exception as e:
            self._record(
                symbol=symbol, side=side, qty=qty, order_type=order_type,
                status="rejected", price=price, reason=str(e), dry_run=dry_run,
            )
            raise

        # 4. Audit de l'intention.
        logger.info(
            "ORDER intent: %s %s %s @ %s (type=%s, mode=%s, dry_run=%s)",
            side,
            qty,
            symbol,
            f"{price:.2f}" if price is not None else "mkt",
            order_type,
            getattr(self.broker, "mode", "paper"),
            dry_run,
        )

        # 5. Soumission (ou simulation en dry_run).
        if dry_run:
            result: dict[str, Any] = {
                "status": "dry_run",
                "symbol": symbol,
                "qty": qty,
                "side": side,
                "order_type": order_type,
            }
            logger.info("ORDER dry_run: non soumis au broker (%s %s %s).", side, qty, symbol)
            self._record(
                symbol=symbol, side=side, qty=qty, order_type=order_type,
                status="dry_run", price=price, dry_run=True,
            )
            return result

        result = self.broker.submit_order(
            symbol=symbol,
            qty=qty,
            side=side,
            order_type=order_type,
        )
        self._submitted[key] = result
        _is_dict = isinstance(result, dict)
        logger.info(
            "ORDER submitted: %s %s %s (order_id=%s)",
            side,
            qty,
            symbol,
            result.get("order_id", "N/A") if _is_dict else "N/A",
        )
        self._record(
            symbol=symbol, side=side, qty=qty, order_type=order_type,
            status=str(result.get("status", "submitted")) if _is_dict else "submitted",
            order_id=result.get("order_id") if _is_dict else None,
            filled_qty=result.get("filled_qty") if _is_dict else None,
            price=price,
        )
        return result

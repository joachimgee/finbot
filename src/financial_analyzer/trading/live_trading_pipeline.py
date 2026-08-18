"""
Live Trading Pipeline - Execute trading strategy in real-time.

Features:
- Schedule execution (market open, daily, weekly, monthly)
- Data fetching (prices, fundamentals, news, sentiment)
- Signal generation (ML models, technical indicators, sentiment)
- Portfolio optimization (Riskfolio-Lib, PyPortfolioOpt)
- Order generation from target weights
- Risk validation (RiskGuard with circuit breakers)
- Order execution (via BrokerAdapter)
- Performance tracking (AccountMonitor)
- Logging & metrics (Prometheus compatible)

Integrates:
- Phase 6.1: BrokerAdapter (Alpaca, IB)
- Phase 6.2: AccountMonitor, RiskGuard
- Phase 5: ML models, portfolio optimization, backtesting

Architecture:
    LiveTradingPipeline
         ├─ BrokerAdapter (fetch data, submit orders)
         ├─ AccountMonitor (track portfolio state)
         ├─ RiskGuard (validate orders)
         └─ SignalGenerator (ML models, indicators)
"""

from __future__ import annotations
from typing import TYPE_CHECKING, Dict, List, Optional, Literal, Callable, Tuple
from datetime import datetime, time as dt_time, timedelta
from dataclasses import dataclass
import pandas as pd
import numpy as np
import logging
from collections import defaultdict
import time

logger = logging.getLogger(__name__)

from .broker_adapter import BrokerAdapter
from .account_monitor import AccountMonitor
from .framework import (
    PipelineAlpha,
    PipelineConstruction,
    PipelineExecution,
    PipelineRisk,
)
from .risk_guard import RiskGuard, CircuitBreakerTriggered, RiskLimitExceeded
from .order_gateway import OrderGateway

if TYPE_CHECKING:
    from .journal import TradingJournal

try:
    from financial_analyzer.portfolio.pyportfolioopt_optimizer import PyPortfolioOptOptimizer
except Exception:
    PyPortfolioOptOptimizer = None

try:
    from financial_analyzer.portfolio.riskfolio_optimizer import RiskfolioOptimizer
except Exception:
    RiskfolioOptimizer = None

try:
    from financial_analyzer.data.market_data import MarketDataFetcher
except Exception:
    MarketDataFetcher = None

try:
    from financial_analyzer.features.technical import TechnicalFeatureEngine
except Exception:
    TechnicalFeatureEngine = None

try:
    from financial_analyzer.sentiment.finbert_engine import FinBERTEngine
except Exception:
    FinBERTEngine = None

try:
    from financial_analyzer.data.news_scraper import FinancialNewsScraper
except Exception:
    FinancialNewsScraper = None

# NB : les imports gardés de LSTMPredictor (deep_learning) et MLPredictor
# (analysis.ml_predictor) ont été retirés — non utilisés dans le chemin de
# décision (les sources ML/LSTM s'abstiennent, cf. _generate_signals). Le pipeline
# ne dépend donc plus de la couche recherche. Boundary verrouillé par
# tests/test_architecture/test_layering.py.

# Portail de validation (P1) : source de vérité des signaux autorisés à décider.
# Import gardé pour éviter tout couplage dur si le module bouge.
try:
    from financial_analyzer.backtest.validation_gate import VALIDATED_SIGNALS, is_validated
except Exception:  # pragma: no cover - dégradation gracieuse
    VALIDATED_SIGNALS = {}

    def is_validated(_name: str) -> bool:
        return False


def _cap_and_renormalize(
    weights: Dict[str, float], cap: float, max_iter: int = 100
) -> Dict[str, float]:
    """Plafonne chaque poids à ``cap`` et redistribue l'excédent aux non-plafonnés.

    Itère car redistribuer peut à son tour pousser d'autres poids au-dessus du cap.
    Si ``cap * n < 1`` (trop peu de noms pour tout investir sous le cap), tous les
    poids finissent au cap et la somme reste < 1 (le reste demeure en cash) — c'est
    le comportement correct : on ne viole jamais la limite de concentration.

    Args:
        weights: poids positifs (somme ≈ 1) issus de l'optimiseur.
        cap: poids maximal par position (ex. 0.25 = 25 %).
    """
    w = {k: float(v) for k, v in weights.items() if v > 0}
    if not w:
        return {}
    for _ in range(max_iter):
        over = {k: v for k, v in w.items() if v > cap + 1e-12}
        if not over:
            break
        excess = sum(v - cap for v in over.values())
        for k in over:
            w[k] = cap
        under = {k: v for k, v in w.items() if v < cap - 1e-12}
        under_sum = sum(under.values())
        if under_sum <= 0:
            break  # tout est au cap : impossible d'investir davantage sans violer
        for k in under:
            w[k] += excess * (w[k] / under_sum)
    return w


@dataclass
class TradingSchedule:
    """
    Trading schedule configuration.
    
    Attributes:
        execution_time: Time to execute (HH:MM format, ET timezone)
        frequency: Execution frequency ('daily', 'weekly', 'monthly')
        day_of_week: Day of week (0=Monday, 4=Friday) for weekly
        day_of_month: Day of month (1-31) for monthly
        enabled: Schedule enabled
    
    Example:
        >>> # Execute daily at 9:35 AM ET
        >>> schedule = TradingSchedule(
        ...     execution_time="09:35",
        ...     frequency='daily',
        ...     enabled=True
        ... )
        >>> 
        >>> # Execute weekly on Mondays at 10:00 AM
        >>> schedule = TradingSchedule(
        ...     execution_time="10:00",
        ...     frequency='weekly',
        ...     day_of_week=0
        ... )
    """
    execution_time: str = "09:35"  # 5 min after market open
    frequency: Literal['daily', 'weekly', 'monthly'] = 'daily'
    day_of_week: int = 0  # Monday for weekly
    day_of_month: int = 1  # 1st for monthly
    enabled: bool = True
    
    def should_execute_today(self, now: datetime) -> bool:
        """
        Check if should execute today.
        
        Args:
            now: Current datetime
        
        Returns:
            True if should execute today based on frequency
        
        Example:
            >>> schedule = TradingSchedule(frequency='weekly', day_of_week=0)
            >>> now = datetime(2025, 11, 10)  # Monday
            >>> schedule.should_execute_today(now)
            True
        """
        if not self.enabled:
            return False
        
        if self.frequency == 'daily':
            return True
        elif self.frequency == 'weekly':
            return now.weekday() == self.day_of_week
        elif self.frequency == 'monthly':
            return now.day == self.day_of_month
        
        return False
    
    def get_execution_time(self) -> dt_time:
        """
        Get execution time as time object.
        
        Returns:
            time object for execution time
        
        Example:
            >>> schedule = TradingSchedule(execution_time="09:35")
            >>> t = schedule.get_execution_time()
            >>> print(t)  # 09:35:00
        """
        hour, minute = map(int, self.execution_time.split(':'))
        return dt_time(hour=hour, minute=minute)


class LiveTradingPipeline:
    """
    Live trading pipeline for executing strategies in real-time.
    
    Integrates signal generation, portfolio optimization, risk management,
    and order execution into a single automated pipeline.
    
    Attributes:
        broker: BrokerAdapter instance for market data and order execution
        tickers: List of ticker symbols to trade
        strategy: Strategy name being used
        monitor: AccountMonitor for portfolio tracking
        risk_guard: RiskGuard for pre-trade validation
        schedule: TradingSchedule for automated execution
        is_running: Whether pipeline is currently running
        last_execution: Timestamp of last execution
        execution_history: List of execution results
    
    Example:
        >>> from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
        >>> 
        >>> # Setup
        >>> adapter = AlpacaAdapter(api_key='...', api_secret='...', paper=True)
        >>> 
        >>> # Initialize pipeline
        >>> pipeline = LiveTradingPipeline(
        ...     broker_adapter=adapter,
        ...     tickers=['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA'],
        ...     initial_capital=100000.0,
        ...     strategy='factor_ensemble'
        ... )
        >>> 
        >>> # Run (manual)
        >>> result = pipeline.run(force=True)
        >>> print(f"Status: {result['status']}")
        >>> print(f"Orders executed: {result['orders_executed']}")
    """
    
    def __init__(
        self,
        broker_adapter: BrokerAdapter,
        tickers: List[str],
        initial_capital: float = 100000.0,
        strategy: str = 'factor_ensemble',
        risk_config: Optional[Dict] = None,
        schedule_config: Optional[TradingSchedule] = None,
        enable_logging: bool = True,
        account_monitor: Optional[AccountMonitor] = None,
        risk_guard: Optional[RiskGuard] = None,
        journal: Optional[TradingJournal] = None,
        target_vol: Optional[float] = None,
        vol_lookback: int = 126,
        max_exposure: float = 1.0,
        risk_off_ma: int = 200,
        risk_off_factor: float = 0.5,
        no_trade_band: float = 0.0,
        alpha: Optional[object] = None,
        construction: Optional[object] = None,
        risk_model: Optional[object] = None,
        execution: Optional[object] = None,
    ) -> None:
        """
        Initialize live trading pipeline.

        Args:
            broker_adapter: Connected BrokerAdapter instance
            tickers: List of ticker symbols to trade
            initial_capital: Initial capital for tracking
            strategy: Strategy name ('factor_ensemble', 'sentiment_momentum', 'ml_fusion')
            risk_config: Risk limits config (default: conservative)
            schedule_config: Execution schedule config
            enable_logging: Enable detailed logging
            account_monitor: Moniteur de compte pré-construit à réutiliser (DI).
                Si None, un ``AccountMonitor`` est créé. Permet à un orchestrateur
                (ex. le daemon) de partager un moniteur déjà mis à jour.
            risk_guard: ``RiskGuard`` pré-construit à réutiliser (DI). Si None, un
                garde conservateur est créé depuis ``risk_config``. Partager le
                garde garantit des limites cohérentes sur tout le book.
            journal: journal d'exécution optionnel (``TradingJournal``) branché sur
                le chokepoint : chaque ordre routé par le gateway y est audité.
                Préserve la piste d'audit quand le daemon délègue l'allocation.

        Raises:
            ValueError: If broker_adapter not connected or tickers empty

        Example:
            >>> adapter = AlpacaAdapter(api_key='...', api_secret='...', paper=True)
            >>> pipeline = LiveTradingPipeline(
            ...     broker_adapter=adapter,
            ...     tickers=['AAPL', 'MSFT'],
            ...     initial_capital=50000.0
            ... )
        """
        if not broker_adapter.connected:
            raise ValueError("BrokerAdapter must be connected. Call connect() first.")

        if not tickers:
            raise ValueError("Tickers list cannot be empty")

        self.broker = broker_adapter
        self.tickers = tickers
        self.strategy = strategy

        # AccountMonitor : injecté (partagé) ou construit par défaut.
        self.monitor = account_monitor or AccountMonitor(
            broker_adapter=broker_adapter,
            initial_capital=initial_capital,
            track_history=True
        )

        # RiskGuard : injecté (partagé) ou construit depuis la config conservatrice.
        if risk_guard is not None:
            self.risk_guard = risk_guard
        else:
            risk_config = risk_config or self._default_risk_config()
            self.risk_guard = RiskGuard(
                account_monitor=self.monitor,
                **risk_config
            )

        # Single audited execution chokepoint (mode-gate + risk + idempotence +
        # audit). Le journal partagé, s'il est fourni, persiste chaque ordre.
        self.order_gateway = OrderGateway(self.broker, self.risk_guard, journal=journal)

        # Overlay de gestion de volatilité (Tier 1.2), opt-in. Si target_vol est
        # défini, l'exposition est scalée = min(max_exposure, target_vol/vol_ex_ante)
        # × filtre de tendance (risk-off). max_exposure=1.0 (défaut) => l'overlay ne
        # peut que RÉDUIRE l'exposition (de-risk), jamais lever — sûreté d'abord.
        self.target_vol = target_vol
        self.vol_lookback = vol_lookback
        self.max_exposure = max_exposure
        self.no_trade_band = no_trade_band
        self.risk_off_ma = risk_off_ma
        self.risk_off_factor = risk_off_factor

        # Couches enfichables (audit #5, façon LEAN) : Alpha → Construction → Risk
        # → Execution. Par défaut, des adaptateurs qui délèguent à la logique déjà
        # validée ci-dessous (comportement inchangé) ; injecter un modèle custom
        # remplace *un seul* étage sans toucher aux autres.
        self.alpha = alpha or PipelineAlpha(self)
        self.construction = construction or PipelineConstruction(self)
        self.risk_model = risk_model or PipelineRisk(self)
        self.execution = execution or PipelineExecution(self)

        # Schedule
        self.schedule = schedule_config or TradingSchedule()
        
        # State
        self.is_running = False
        self.last_execution: Optional[datetime] = None
        self.execution_history: List[Dict] = []
        
        # Logging
        self.enable_logging = enable_logging
        
        logger.info(
            f"LiveTradingPipeline initialized: "
            f"tickers={len(tickers)}, strategy={strategy}, "
            f"mode={broker_adapter.mode if hasattr(broker_adapter, 'mode') else 'unknown'}"
        )
    
    @staticmethod
    def _default_risk_config() -> Dict:
        """
        Get default risk configuration (conservative).
        
        Returns:
            Dict with conservative risk limits
        
        Example:
            >>> config = LiveTradingPipeline._default_risk_config()
            >>> print(config['max_position_pct'])
            0.25
        """
        return {
            'max_position_size': 50000.0,
            'max_position_pct': 0.25,
            'max_total_positions': 20,
            'max_drawdown': -0.15,
            'max_daily_loss': 5000.0,
            'max_leverage': 2.0,
            'enable_circuit_breaker': True
        }
    
    def run(self, force: bool = False, dry_run: bool = False) -> Dict:
        """
        Execute trading pipeline (single run).

        Args:
            force: Force execution even if schedule/market says no.
            dry_run: If True, run the FULL chain (data -> signals -> allocation ->
                orders -> gateway) but the gateway applies everything (mode-gate,
                risk, audit) EXCEPT the real broker submission. Use it to validate
                the whole path end-to-end without placing orders.

        Steps:
        1. Check if market is open
        2. Check schedule (unless force=True)
        3. Update account monitor
        4. Fetch latest data
        5. Generate signals
        6. Optimize portfolio (target weights)
        7. Generate orders
        8. Validate orders (risk checks)
        9. Execute orders
        10. Update monitor
        11. Log results
        
        Args:
            force: Force execution even if schedule says no
        
        Returns:
            Dict with execution results:
            - status: 'success', 'skipped', 'failed'
            - reason: Reason if skipped/failed
            - orders_generated: Number of orders generated
            - orders_executed: Number of orders executed
            - orders_rejected: Number of orders rejected (risk)
            - portfolio_value: Current portfolio value
            - daily_pnl: Daily P&L
            - execution_time: Execution timestamp
        
        Example:
            >>> pipeline = LiveTradingPipeline(broker, ['AAPL', 'MSFT'])
            >>> result = pipeline.run(force=True)
            >>> if result['status'] == 'success':
            ...     print(f"Executed {result['orders_executed']} orders")
        """
        now = datetime.now()
        
        try:
            # 1. Check market open (unless forced)
            if not force and not self.broker.is_market_open():
                logger.warning("Market is closed")
                return self._result('skipped', 'market_closed')
            
            # 2. Check schedule
            if not force and not self.schedule.should_execute_today(now):
                logger.info(f"Not scheduled for today ({self.schedule.frequency})")
                return self._result('skipped', 'not_scheduled')
            
            # 3. Update monitor
            logger.info("Updating account monitor...")
            self.monitor.update()
            
            # Log current state
            logger.info(
                f"Portfolio: ${self.monitor.portfolio_value:.2f}, "
                f"Daily P&L: ${self.monitor.daily_pnl:+.2f}, "
                f"Positions: {len(self.monitor.positions)}"
            )
            
            # 4-6. Data -> signaux (validés, avec abstention) -> allocation
            # Black-Litterman. Cœur signal→allocation exposé publiquement via
            # compute_target_weights (réutilisé par le daemon comme moteur d'alloc).
            logger.info(f"Fetching data for {len(self.tickers)} tickers...")
            target_weights, data = self.compute_target_weights()

            # 6b. Étage RISK (pré-trade portefeuille, corrélation-aware). Un book
            #     trop risqué -> on s'ABSTIENT de tout le rééquilibrage (pas de
            #     crash du daemon) : la sûreté prime sur le fait de trader.
            risk_ok, target_weights = self.risk_model.evaluate(target_weights, data)
            if target_weights and not risk_ok:
                return self._result(
                    status='skipped', reason='portfolio_risk_limit',
                    orders_generated=0, orders_executed=0, orders_rejected=0,
                )

            # 7-8. Étage EXECUTION : poids cibles -> ordres -> chokepoint audité.
            #      (dry_run applique tout sauf la soumission réelle au broker.)
            logger.info("Executing target weights...")
            execution_results = self.execution.execute(
                target_weights, data, dry_run=dry_run
            )

            # 9. Update monitor after execution
            self.monitor.update()

            # 10. Log results
            executed = sum(1 for r in execution_results if r['status'] == 'executed')
            rejected = sum(1 for r in execution_results if r['status'] == 'rejected')
            result = self._result(
                status='success',
                orders_generated=len(execution_results),
                orders_executed=executed,
                orders_rejected=rejected,
                execution_results=execution_results
            )
            
            # Save to history
            self.last_execution = now
            self.execution_history.append(result)
            
            logger.info(
                f"Execution complete: "
                f"{result['orders_executed']}/{result['orders_generated']} executed, "
                f"{result['orders_rejected']} rejected"
            )
            
            return result
        
        except CircuitBreakerTriggered as e:
            logger.critical(f"Circuit breaker triggered: {e}")
            return self._result('failed', f'circuit_breaker: {e}')
        
        except Exception as e:
            logger.error(f"Execution failed: {e}", exc_info=True)
            return self._result('failed', str(e))
    
    def compute_target_weights(
        self,
        data: Optional[Dict] = None,
    ) -> Tuple[Dict[str, float], Dict]:
        """Cœur signal→allocation, sans exécution : poids cibles Black-Litterman.

        C'est l'API publique qui fait de ce pipeline un **moteur d'allocation**
        réutilisable : un orchestrateur (le daemon) peut obtenir des poids pilotés
        par les signaux *validés* (momentum 12-1, abstention des sources stub) et
        inclinés par Black-Litterman, sans passer par la génération/soumission
        d'ordres du pipeline. ``run()`` s'appuie sur la même méthode, garantissant
        que le chemin exécuté et le chemin délégué partagent exactement la même
        logique de décision.

        Args:
            data: Données de marché déjà récupérées (format de ``_fetch_data``).
                Si None, les données sont récupérées pour ``self.tickers``.

        Returns:
            ``(target_weights, data)`` — un dict {symbole: poids ∈ [0,1], somme≈1}
            sur les seuls signaux positifs (long-only), et les données utilisées
            (pour un éventuel calcul d'ordres en aval). ``target_weights`` est vide
            si aucun signal positif n'émerge (abstention → pas de position).
        """
        if data is None:
            data = self._fetch_data()
        # Étages enfichables : Alpha (data→signaux) puis Construction
        # (signaux→poids). Les défauts délèguent à la logique validée ci-dessous.
        signals = self.alpha.generate(data)
        target_weights = self.construction.construct(signals, data)
        return target_weights, data

    def _construct_weights(self, signals: Dict[str, float], data: Dict) -> Dict[str, float]:
        """Construction de portefeuille par défaut : BL puis finalisation.

        (Corps historique de ``compute_target_weights``, extrait pour l'étage
        Construction enfichable — comportement identique.)
        """
        target_weights = self._optimize_portfolio(signals, data)
        return self._finalize_weights(target_weights, data)

    def _finalize_weights(self, target_weights: Dict[str, float], data: Dict) -> Dict[str, float]:
        """Finalisation commune à toute construction : cap → overlay vol → bande.

        Partagée par la construction par défaut (BL) et les constructions
        alternatives (p.ex. HRP) pour garantir les mêmes garde-fous en aval.
        """
        # Plafonner chaque poids au cap de concentration du RiskGuard et
        # redistribuer l'excédent : sinon la position la plus convaincue dépasse la
        # limite et se fait REJETER à l'exécution (on perd le meilleur signal). Le
        # plafonnement en amont respecte la limite tout en déployant le capital.
        cap = getattr(self.risk_guard, "max_position_pct", None)
        if isinstance(cap, (int, float)) and 0.0 < cap < 1.0 and target_weights:
            target_weights = _cap_and_renormalize(target_weights, float(cap))
        # Overlay de vol (opt-in) : scale l'exposition globale vers target_vol et
        # applique le filtre risk-off. Réduit l'exposition (laisse du cash) sans
        # jamais toucher aux poids relatifs. Aucune donnée exploitable -> pas de scale.
        if self.target_vol and target_weights:
            target_weights = self._apply_vol_overlay(target_weights, data)
        # Rééquilibrage cost-aware (opt-in) : bande de non-transaction vs les poids
        # détenus. Ne bouge une ligne que si son poids change de plus que la bande —
        # évite de churner le book pour des micro-variations de signal (coûts).
        if self.no_trade_band > 0 and target_weights:
            target_weights = self._apply_no_trade_band(target_weights)
        return target_weights

    def _apply_no_trade_band(self, weights: Dict[str, float]) -> Dict[str, float]:
        """Applique la bande de non-transaction aux poids cibles vs les poids détenus.

        Poids détenus = valeur de marché des positions / valeur du portefeuille
        (via le moniteur). Fail-safe : toute erreur -> poids inchangés.

        **Garde d'échelle** : la bande est un seuil en poids *absolu*, elle n'a donc de
        sens que rapportée à la taille typique d'une ligne. Une bande supérieure au poids
        médian d'une position **gèle le book** : plus aucun mouvement ne franchit le
        seuil, le portefeuille cesse de se rééquilibrer sans qu'aucune erreur ne remonte.
        C'est exactement ce qui s'est produit en transposant à Amihud (~68 lignes,
        |w| ≈ 0.015) une bande de 0.02 calibrée sur un book concentré (~10 lignes,
        |w| ≈ 0.10) : 100 % des mouvements gelés, Sharpe 18 ans +1.69 → +0.55. La garde
        neutralise la bande dans ce cas et le signale au niveau ``error``.
        """
        try:
            import pandas as pd

            from financial_analyzer.backtest.cost_aware import apply_no_trade_band

            pv = float(getattr(self.monitor, "portfolio_value", 0.0) or 0.0)
            positions = getattr(self.monitor, "positions", None) or []
            if pv <= 0 or not positions:
                return weights  # pas de book détenu -> mise en place, rien à tenir
            nz = [abs(w) for w in weights.values() if abs(w) > 1e-9]
            if nz:
                median_w = float(pd.Series(nz).median())
                if self.no_trade_band >= median_w:
                    logger.error(
                        "Bande de non-transaction (%.4f) ≥ poids médian d'une ligne "
                        "(%.4f) : elle gèlerait le book (%d lignes). Bande ignorée — "
                        "recalibrer par rapport à la taille des positions.",
                        self.no_trade_band, median_w, len(nz),
                    )
                    return weights
            current = {}
            for p in positions:
                sym = p.get("symbol") if isinstance(p, dict) else None
                mv = float(p.get("market_value", 0.0)) if isinstance(p, dict) else 0.0
                if sym:
                    current[sym] = mv / pv
            idx = sorted(set(weights) | set(current))
            tgt = pd.Series({s: weights.get(s, 0.0) for s in idx})
            prev = pd.Series({s: current.get(s, 0.0) for s in idx})
            banded = apply_no_trade_band(tgt, prev, self.no_trade_band)
            return {s: float(w) for s, w in banded.items() if abs(w) > 1e-9}
        except Exception as e:  # noqa: BLE001 - le cost-aware ne doit jamais casser la décision
            logger.warning("Bande de non-transaction indisponible (%s) — poids inchangés.", e)
            return weights

    def _apply_vol_overlay(self, weights: Dict[str, float], data: Dict) -> Dict[str, float]:
        """Scale l'exposition du book selon le ciblage de vol + filtre de tendance."""
        try:
            from financial_analyzer.backtest.vol_management import exposure_scalar

            prices = data.get("prices", {}) or {}
            frames = {s: df["close"] for s, df in prices.items()
                      if s in weights and df is not None and not df.empty and "close" in df}
            if not frames:
                return weights
            close = pd.DataFrame(frames).dropna(how="all")
            exposure, diag = exposure_scalar(
                weights, close, target_vol=self.target_vol, lookback=self.vol_lookback,
                max_exposure=self.max_exposure, ma_window=self.risk_off_ma,
                risk_off_factor=self.risk_off_factor,
            )
            logger.info(
                "Vol overlay: exposition=%.2f (vol ex-ante=%s, vol_scalar=%.2f, trend=%.2f)",
                exposure,
                f"{diag['ex_ante_vol']:.1%}" if diag["ex_ante_vol"] else "n/a",
                diag["vol_scalar"], diag["trend_scalar"],
            )
            return {s: w * exposure for s, w in weights.items()}
        except Exception as e:  # noqa: BLE001 - l'overlay ne doit jamais casser la décision
            logger.warning("Vol overlay indisponible (%s) — exposition inchangée.", e)
            return weights

    def _portfolio_risk_ok(self, weights: Dict[str, float], data: Dict) -> bool:
        """Contrôle pré-trade portefeuille (corrélation-aware) via le RiskGuard.

        Renvoie ``True`` si le book cible passe (ou si le guard n'a pas de limite
        portefeuille configurée / n'expose pas ``validate_portfolio``). ``False`` si
        une limite est franchie -> le daemon s'abstient de rééquilibrer.
        """
        validate = getattr(self.risk_guard, "validate_portfolio", None)
        if not callable(validate):
            return True
        try:
            prices = (data or {}).get("prices", {}) or {}
            frames = {s: df["close"] for s, df in prices.items()
                      if s in weights and df is not None and not df.empty and "close" in df}
            close = pd.DataFrame(frames).dropna(how="all") if frames else None
            diag = validate(weights, close)
            if isinstance(diag, dict):
                logger.info(
                    "Contrôle risque portefeuille OK (vol ex-ante=%s, VaR95 1j=%s, paris eff.=%s)",
                    f"{diag.get('ex_ante_vol'):.1%}" if diag.get("ex_ante_vol") else "n/a",
                    f"{diag.get('var_95_1d'):.2%}" if diag.get("var_95_1d") else "n/a",
                    f"{diag.get('effective_bets'):.1f}" if diag.get("effective_bets") else "n/a",
                )
            return True
        except RiskLimitExceeded as e:
            logger.critical("🚨 Book cible REFUSÉ par le contrôle de risque portefeuille : %s", e)
            return False
        except Exception as e:  # noqa: BLE001 - un check de risque ne doit jamais crasher le run
            logger.warning("Contrôle risque portefeuille indisponible (%s) — non bloquant.", e)
            return True

    def _fetch_data(self) -> Dict:
        """
        Fetch latest market data for all tickers.
        
        Returns:
            Dict with keys:
            - prices: Dict[symbol, DataFrame] - Historical prices
            - fundamentals: Dict[symbol, Dict] - Fundamental metrics
            - news: Dict[symbol, List] - Recent news (optional)
            - sentiment: Dict[symbol, float] - Sentiment scores (optional)
        
        Example:
            >>> data = pipeline._fetch_data()
            >>> print(data['prices']['AAPL'].tail())
        """
        data = {
            'prices': {},
            'fundamentals': {},
            'news': {},
            'sentiment': {}
        }
        
        # Fetch ~14 months of history: enough calendar days (~420) to leave 252
        # trading days for the validated 12-1 momentum factor, plus the shorter
        # windows (RSI/MACD, 20-day momentum) used by the other components.
        end_date = datetime.now()
        start_date = end_date - timedelta(days=420)
        
        # Prefer batched fetching when available (reduces API calls, better for 1000+ tickers)
        if hasattr(self.broker, 'get_bars_multi'):
            try:
                multi = getattr(self.broker, 'get_bars_multi')(
                    self.tickers, start_date, end_date, timeframe='1D'
                )
                if isinstance(multi, dict):
                    for ticker, df in multi.items():
                        if df is not None and not df.empty:
                            data['prices'][ticker] = df
                    logger.info(f"Fetched data (batched) for {len(data['prices'])}/{len(self.tickers)} tickers")
                else:
                    logger.warning("get_bars_multi returned non-dict; falling back to single requests")
                    raise RuntimeError("invalid_multi_return")
            except Exception as e:
                logger.warning(f"Batched fetch failed ({e}); falling back to single requests")
                # Fallback per-symbol
                for ticker in self.tickers:
                    try:
                        df = self.broker.get_bars(
                            symbol=ticker,
                            start=start_date,
                            end=end_date,
                            timeframe='1D'
                        )
                        if not df.empty:
                            data['prices'][ticker] = df
                            logger.debug(f"Fetched {len(df)} bars for {ticker}")
                        else:
                            logger.warning(f"No price data for {ticker}")
                    except Exception as ie:
                        logger.error(f"Failed to fetch data for {ticker}: {ie}")
        else:
            for ticker in self.tickers:
                try:
                    # Get historical bars
                    df = self.broker.get_bars(
                        symbol=ticker,
                        start=start_date,
                        end=end_date,
                        timeframe='1D'
                    )
                    
                    if not df.empty:
                        data['prices'][ticker] = df
                        logger.debug(f"Fetched {len(df)} bars for {ticker}")
                    else:
                        logger.warning(f"No price data for {ticker}")
                
                except Exception as e:
                    logger.error(f"Failed to fetch data for {ticker}: {e}")
        
        # Log summary
        fetched = len(data['prices'])
        logger.info(f"Fetched data for {fetched}/{len(self.tickers)} tickers")
        
        # Fetch fundamentals if MarketDataFetcher available
        if MarketDataFetcher is not None:
            try:
                mdf = MarketDataFetcher(api_key=None)  # yfinance fallback
                for ticker in list(data['prices'].keys())[:10]:  # limit to avoid timeout
                    try:
                        statements = mdf.get_financial_statements(ticker)
                        data['fundamentals'][ticker] = statements
                    except Exception:
                        pass
                logger.debug(f"Fetched fundamentals for {len(data['fundamentals'])} tickers")
            except Exception as e:
                logger.debug(f"Fundamentals fetch skipped: {e}")
        
        # Fetch news if FinancialNewsScraper available
        if FinancialNewsScraper is not None:
            try:
                scraper = FinancialNewsScraper()
                for ticker in list(data['prices'].keys())[:20]:  # limit for performance
                    try:
                        news_items = scraper.get_news(ticker, limit=5)
                        if news_items:
                            data['news'][ticker] = news_items
                    except Exception:
                        pass
                logger.debug(f"Fetched news for {len(data['news'])} tickers")
            except Exception as e:
                logger.debug(f"News fetch skipped: {e}")
        
        # Sentiment analysis via FinBERT if available. A ticker gets a sentiment
        # entry ONLY when FinBERT actually scores real news for it. On any failure
        # (no analyzer, no news, empty text, exception) the key is left ABSENT so
        # the signal layer abstains, instead of being diluted by a fabricated
        # neutral 0.0 that would look like a real "neutral" view.
        if FinBERTEngine is not None and data['news']:
            try:
                analyzer = FinBERTEngine()
                for ticker, news_list in data['news'].items():
                    try:
                        texts = [item.get('title', '') + ' ' + item.get('description', '') for item in news_list[:3]]
                        texts = [t for t in texts if t.strip()]
                        if texts:
                            scores = [analyzer.analyze_text(t) for t in texts]
                            if scores:
                                data['sentiment'][ticker] = float(np.mean(scores))
                    except Exception:
                        # Abstain for this ticker (no fabricated neutral score).
                        continue
                logger.debug(f"Analyzed sentiment for {len(data['sentiment'])} tickers")
            except Exception as e:
                logger.debug(f"Sentiment analysis skipped: {e}")
        # No analyzer or no news -> data['sentiment'] stays empty and every ticker
        # abstains from the sentiment component.
        
        return data
    
    def _generate_signals(self, data: Dict) -> Dict[str, float]:
        """
        Generate trading signals for each ticker.
        
        Combines multiple signal sources:
        - Technical indicators (RSI, MACD, Bollinger, etc.)
        - ML models (LSTM predictions if available)
        - Sentiment analysis (FinBERT scores)
        - Momentum (20D fallback)
        
        Args:
            data: Market data dict from _fetch_data()
        
        Returns:
            Dict mapping symbol to signal (-1 to +1)
            +1 = strong buy, 0 = neutral, -1 = strong sell
        
        Example:
            >>> signals = pipeline._generate_signals(data)
            >>> print(signals)  # {'AAPL': 0.65, 'MSFT': -0.23, ...}
        """
        signals = {}
        
        for ticker in self.tickers:
            if ticker not in data['prices']:
                signals[ticker] = 0.0
                continue
            
            df = data['prices'][ticker]
            
            if len(df) < 20:
                signals[ticker] = 0.0
                continue
            
            # A component is only included when its source truly produced a value
            # ("maximize what works" + abstain on stubs). Each carries a base
            # weight; weights are renormalised over the AVAILABLE components, so a
            # missing or stubbed source neither dilutes the decision with a
            # fabricated 0.0 nor silently drops a real one.
            components: List[Tuple[float, float]] = []  # (signal, base_weight)

            # 1. Technical Indicators (RSI, MACD)
            if TechnicalFeatureEngine is not None:
                try:
                    engine = TechnicalFeatureEngine()
                    features = engine.generate_features(df)
                    if not features.empty and len(features) > 0:
                        tech_signal = 0.0
                        tech_fired = False
                        if 'rsi_14' in features.columns:
                            rsi = float(features['rsi_14'].iloc[-1])
                            if rsi < 30:
                                tech_signal += 0.5  # oversold
                                tech_fired = True
                            elif rsi > 70:
                                tech_signal -= 0.5  # overbought
                                tech_fired = True
                        if 'macd' in features.columns and 'macd_signal' in features.columns:
                            macd = float(features['macd'].iloc[-1])
                            macd_sig = float(features['macd_signal'].iloc[-1])
                            tech_signal += 0.3 if macd > macd_sig else -0.3
                            tech_fired = True
                        if tech_fired:
                            components.append((float(np.clip(tech_signal, -1, 1)), 0.3))
                except Exception as e:
                    logger.debug(f"Technical signal failed for {ticker}: {e}")

            # 2. ML/LSTM prediction — no trained model is loaded, so this source
            #    ABSTAINS rather than contributing a fabricated 0.0. Append a real
            #    prediction with its weight here once a model exists; until then it
            #    must not influence the decision.

            # 3. Sentiment (FinBERT) — present only when really scored upstream.
            if ticker in data.get('sentiment', {}):
                sentiment_signal = float(np.clip(data['sentiment'][ticker], -1, 1))
                components.append((sentiment_signal, 0.2))

            # 4. Momentum — UNIQUEMENT le facteur 12-1 validé OOS (rendement 12 mois
            #    hors dernier mois), et seulement s'il figure au registre du portail
            #    de validation (VALIDATED_SIGNALS) avec assez d'historique (≥252 j).
            #    L'ancien repli « momentum 20 jours » était NON validé : conformément
            #    au portail P1 (aucun signal non validé ne décide), il est retiré —
            #    un titre à historique court s'abstient simplement de cette source.
            if is_validated("momentum_12_1") and len(df) >= 252:
                try:
                    mom = df['close'].iloc[-21] / df['close'].iloc[-252] - 1  # 12-1
                    components.append((float(np.tanh(mom * 3)), 0.3))
                except Exception:
                    pass

            # Renormalised weighted combine over available components only.
            if components:
                weight_sum = sum(w for _, w in components)
                combined = (
                    sum(s * w for s, w in components) / weight_sum
                    if weight_sum > 0
                    else 0.0
                )
            else:
                # No real signal source for this ticker -> abstain (no position).
                combined = 0.0
                logger.debug(f"{ticker}: no real signal source available; abstaining")

            signals[ticker] = float(np.clip(combined, -1, 1))
        
        logger.info(
            f"Generated signals for {len(signals)} tickers "
            f"(Technical: {TechnicalFeatureEngine is not None}, "
            f"Sentiment: {FinBERTEngine is not None}, "
            f"validated signals: {sorted(VALIDATED_SIGNALS)})"
        )
        return signals
    
    def _optimize_portfolio(self, signals: Dict[str, float], data: Dict) -> Dict[str, float]:
        """
        Optimize portfolio weights based on signals.
        
        Uses PyPortfolioOpt (Max Sharpe) or Riskfolio-Lib (Mean-CVaR) if available,
        otherwise falls back to signal-proportional allocation.
        
        Args:
            signals: Trading signals for each ticker
            data: Market data
        
        Returns:
            Dict[str, float]: mapping symbol to target weight (0-1, sum=1)
        
        Example:
            >>> signals = {'AAPL': 0.8, 'MSFT': 0.6, 'GOOGL': -0.2}
            >>> weights = pipeline._optimize_portfolio(signals, data)
            >>> print(weights) # {'AAPL': 0.57, 'MSFT': 0.43}
        """
        # Filter positive signals only (long-only for now)
        positive_signals = {k: v for k, v in signals.items() if v > 0}
        
        if not positive_signals:
            logger.warning("No positive signals, no positions")
            return {}
        
        # Build prices DataFrame for optimization ('prices' peut être absent :
        # le fallback proportionnel ci-dessous prend alors le relais)
        price_frames = []
        available_prices = data.get('prices', {})
        for sym in positive_signals:
            if sym in available_prices and not available_prices[sym].empty:
                close = available_prices[sym]['close'].rename(sym)
                price_frames.append(close)
        
        if not price_frames:
            logger.warning("No price data for optimization; fallback to proportional")
            total_signal = sum(positive_signals.values())
            return {symbol: signal / total_signal for symbol, signal in positive_signals.items()}
        
        prices_df = pd.concat(price_frames, axis=1).dropna()
        if prices_df.empty or len(prices_df) < 20:
            logger.warning("Insufficient price data; fallback to proportional")
            total_signal = sum(positive_signals.values())
            return {symbol: signal / total_signal for symbol, signal in positive_signals.items()}
        
        # Primary: Black-Litterman. The signal magnitudes become expected-return
        # views blended with the market prior, so the real signals actually tilt
        # the weights. (Plain Max-Sharpe below ignores signal strength — it would
        # optimise the same regardless of how strong each signal is.)
        try:
            from financial_analyzer.portfolio.optimizer import PortfolioOptimizer

            returns_bl = prices_df.pct_change().dropna()
            if len(returns_bl) >= 20:
                max_view = 0.15  # a +1 signal -> +15% annual expected-return view
                views = {
                    sym: float(positive_signals[sym]) * max_view
                    for sym in returns_bl.columns
                    if sym in positive_signals
                }
                confidences = {
                    sym: float(min(1.0, abs(positive_signals[sym]))) for sym in views
                }
                if views:
                    optimizer = PortfolioOptimizer(returns=returns_bl)
                    bl = optimizer.optimize_black_litterman(views, confidences=confidences)
                    weights_dict = {
                        k: max(0.0, float(v)) for k, v in bl["weights"].to_dict().items()
                    }
                    total = sum(weights_dict.values())
                    if total > 0:
                        weights_dict = {k: v / total for k, v in weights_dict.items()}
                        logger.info(
                            f"Optimized with Black-Litterman ({len(views)} signal views)"
                        )
                        return weights_dict
        except Exception as e:
            logger.warning(f"Black-Litterman failed: {e}; trying PyPortfolioOpt")

        # Try PyPortfolioOpt (Max Sharpe)
        if PyPortfolioOptOptimizer is not None:
            try:
                opt = PyPortfolioOptOptimizer(prices_df)
                weights_series = opt.optimize_max_sharpe()
                weights_dict = weights_series.to_dict()
                # Normalize and clip
                total = sum(weights_dict.values())
                if total > 0:
                    weights_dict = {k: max(0, v / total) for k, v in weights_dict.items()}
                    logger.info("Optimized with PyPortfolioOpt (Max Sharpe)")
                    return weights_dict
            except Exception as e:
                logger.warning(f"PyPortfolioOpt failed: {e}; trying Riskfolio")
        
        # Fallback: Riskfolio (Mean-CVaR)
        if RiskfolioOptimizer is not None:
            try:
                returns = prices_df.pct_change().dropna()
                if len(returns) < 10:
                    raise ValueError("Not enough returns")
                opt = RiskfolioOptimizer(returns, covariance_method='ledoit_wolf')
                weights_series = opt.optimize_mean_cvar(risk_aversion=1.0, cvar_alpha=0.05)
                weights_dict = weights_series.to_dict()
                total = sum(weights_dict.values())
                if total > 0:
                    weights_dict = {k: max(0, v / total) for k, v in weights_dict.items()}
                    logger.info("Optimized with Riskfolio (Mean-CVaR)")
                    return weights_dict
            except Exception as e:
                logger.warning(f"Riskfolio failed: {e}; fallback to proportional")
        
        # Final fallback: proportional to signals
        total_signal = sum(positive_signals.values())
        target_weights = {symbol: signal / total_signal for symbol, signal in positive_signals.items()}
        logger.info("Using signal-proportional allocation (fallback)")
        return target_weights
    
    def _generate_orders(self, target_weights: Dict[str, float], data: Dict) -> List[Dict]:
        """
        Generate orders to reach target weights.
        
        Args:
            target_weights: Target weights for each ticker
            data: Market data (for current prices)
        
        Returns:
            List of order dicts:
            - symbol: Ticker symbol
            - qty: Quantity to buy/sell
            - side: 'buy' or 'sell'
            - price: Current market price
            - order_type: 'market'
        
        Example:
            >>> weights = {'AAPL': 0.6, 'MSFT': 0.4}
            >>> orders = pipeline._generate_orders(weights, data)
            >>> print(orders[0])
            {'symbol': 'AAPL', 'qty': 40, 'side': 'buy', 'price': 150.0, ...}
        """
        orders = []
        
        portfolio_value = self.monitor.portfolio_value
        current_positions = {p['symbol']: p for p in self.monitor.positions}
        
        # Target positions
        for symbol, target_weight in target_weights.items():
            target_value = portfolio_value * target_weight
            
            # Current position
            current_pos = current_positions.get(symbol)
            current_value = current_pos['market_value'] if current_pos else 0.0
            
            # Delta
            delta_value = target_value - current_value
            
            # Skip small changes (< 1% of portfolio)
            if abs(delta_value) < portfolio_value * 0.01:
                continue
            
            # Get current price
            if symbol not in data['prices'] or data['prices'][symbol].empty:
                logger.warning(f"No price data for {symbol}, skipping")
                continue
            
            price = float(data['prices'][symbol]['close'].iloc[-1])
            
            # Calculate quantity
            qty = int(abs(delta_value) / price)
            
            if qty == 0:
                continue
            
            side = 'buy' if delta_value > 0 else 'sell'
            
            orders.append({
                'symbol': symbol,
                'qty': qty,
                'side': side,
                'price': price,
                'order_type': 'market'
            })
        
        # Close positions not in target weights
        for symbol, pos in current_positions.items():
            if symbol not in target_weights and pos['qty'] > 0:
                price = pos['current_price']
                
                orders.append({
                    'symbol': symbol,
                    'qty': pos['qty'],
                    'side': 'sell',
                    'price': price,
                    'order_type': 'market'
                })
        
        return orders
    
    def _execute_orders_with_risk_checks(self, orders: List[Dict], dry_run: bool = False) -> List[Dict]:
        """
        Execute orders with risk validation.

        Args:
            orders: List of order dicts
            dry_run: If True, the gateway applies mode-gate + risk + audit but does
                NOT submit to the broker (returns a 'dry_run' result).

        Returns:
            List of execution results:
            - status: 'executed', 'rejected', 'failed'
            - order: Original order
            - result: Broker result (if executed)
            - reason: Rejection/failure reason

        Example:
            >>> orders = [{'symbol': 'AAPL', 'qty': 10, 'side': 'buy', 'price': 150.0}]
            >>> results = pipeline._execute_orders_with_risk_checks(orders)
            >>> print(results[0]['status'])  # 'executed' or 'rejected'
        """
        results = []

        for order in orders:
            try:
                # Single audited chokepoint: mode-gate + risk check + idempotence
                # + audit, then broker submission (skipped when dry_run).
                broker_result = self.order_gateway.submit(
                    symbol=order['symbol'],
                    qty=order['qty'],
                    side=order['side'],
                    price=order['price'],
                    order_type=order.get('order_type', 'market'),
                    dry_run=dry_run,
                    # Clé d'idempotence explicite si fournie (ordres enfants d'un
                    # algo d'exécution : évite la collision de deux tranches de même
                    # quantité, que la clé dérivée (symbol,side,qty,type) dédupliquerait).
                    idempotency_key=order.get('idempotency_key'),
                )

                # Classify by the broker's actual order status rather than
                # assuming a submitted order was executed: an order can be
                # rejected/canceled by the broker without raising, and market
                # orders can fill partially. True position state is reconciled by
                # monitor.update() after this loop; here we report faithfully.
                broker_status = (
                    str(broker_result.get('status', '')).lower()
                    if isinstance(broker_result, dict)
                    else ''
                )
                if broker_status in ('rejected', 'canceled', 'cancelled', 'expired', 'suspended'):
                    results.append({
                        'status': 'rejected',
                        'order': order,
                        'result': broker_result,
                        'reason': f'broker_status={broker_status}',
                    })
                    logger.warning(
                        f"Order rejected by broker: {order['side']} {order['qty']} "
                        f"{order['symbol']} (status={broker_status})"
                    )
                    continue

                filled_qty = (
                    broker_result.get('filled_qty')
                    if isinstance(broker_result, dict)
                    else None
                )
                results.append({
                    'status': 'executed',
                    'order': order,
                    'result': broker_result,
                    'filled_qty': filled_qty,
                })

                logger.info(
                    f"Order executed: {order['side']} {order['qty']} {order['symbol']} "
                    f"@ ${order['price']:.2f} (order_id={broker_result.get('order_id', 'N/A')}, "
                    f"status={broker_status or 'n/a'}, filled_qty={filled_qty})"
                )

            except Exception as e:
                results.append({
                    'status': 'rejected',
                    'order': order,
                    'reason': str(e)
                })
                
                logger.warning(f"Order rejected: {order} - {e}")
        
        return results
    
    def _result(self, status: str, reason: str = '', **kwargs) -> Dict:
        """
        Build result dict.
        
        Args:
            status: Result status ('success', 'skipped', 'failed')
            reason: Reason for skipped/failed
            **kwargs: Additional key-value pairs to include
        
        Returns:
            Dict with execution result details
        """
        result = {
            'status': status,
            'reason': reason,
            'timestamp': datetime.now(),
            'portfolio_value': self.monitor.portfolio_value,
            'daily_pnl': self.monitor.daily_pnl,
            'num_positions': len(self.monitor.positions),
            'circuit_breaker_active': self.risk_guard.circuit_breaker_active
        }
        result.update(kwargs)
        return result
    
    def get_status(self) -> Dict:
        """
        Get current pipeline status.
        
        Returns:
            Dict with pipeline status, schedule, portfolio, and risk summary
        
        Example:
            >>> status = pipeline.get_status()
            >>> print(f"Last execution: {status['last_execution']}")
            >>> print(f"Portfolio value: ${status['portfolio']['portfolio_value']:.2f}")
            >>> print(f"Circuit breaker: {status['circuit_breaker_active']}")
        """
        return {
            'is_running': self.is_running,
            'last_execution': self.last_execution,
            'num_executions': len(self.execution_history),
            'schedule': {
                'enabled': self.schedule.enabled,
                'frequency': self.schedule.frequency,
                'execution_time': self.schedule.execution_time
            },
            'portfolio': self.monitor.get_summary(),
            'risk': self.risk_guard.get_risk_summary(),
            'circuit_breaker_active': self.risk_guard.circuit_breaker_active
        }
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        mode = self.broker.mode if hasattr(self.broker, 'mode') else 'unknown'
        return (
            f"LiveTradingPipeline("
            f"tickers={len(self.tickers)}, "
            f"strategy='{self.strategy}', "
            f"mode='{mode}')"
        )


# ==================== TESTING HELPERS ====================

def create_demo_pipeline(mode: str = 'paper') -> LiveTradingPipeline:
    """
    Create demo pipeline for testing.
    
    Args:
        mode: 'paper' or 'live'
    
    Returns:
        LiveTradingPipeline instance
        Note: Broker may not be connected if credentials invalid (demo mode)
    
    Raises:
        ValueError: If invalid mode
    
    Example:
        >>> pipeline = create_demo_pipeline(mode='paper')
        >>> # Broker auto-connects if ALPACA_API_KEY env var set
        >>> if pipeline.broker.connected:
        ...     result = pipeline.run(force=True)
        >>> else:
        ...     print("Broker not connected (demo mode - provide credentials)")
    
    Notes:
        - If ALPACA_API_KEY and ALPACA_SECRET_KEY are set, broker connects automatically
        - If not set, creates unconnected adapter (demo mode)
        - Always use paper=True for testing, never live mode
    """
    from .alpaca_adapter import AlpacaAdapter
    import os
    
    api_key = os.environ.get('APCA_API_KEY_ID') or os.environ.get('ALPACA_API_KEY', 'DEMO_KEY')
    secret_key = os.environ.get('APCA_API_SECRET_KEY') or os.environ.get('ALPACA_API_SECRET') or os.environ.get('ALPACA_SECRET_KEY', 'DEMO_SECRET')

    adapter = AlpacaAdapter(api_key=api_key, secret_key=secret_key, mode=('paper' if mode == 'paper' else 'live'))
    
    # Try to connect if real credentials, otherwise enable demo-connected mode
    if api_key != 'DEMO_KEY':
        try:
            logger.info("Attempting to connect to broker...")
            adapter.connect()
        except Exception as e:
            logger.warning(f"Could not connect broker: {e}")
    else:
        # Demo mode: mark as connected to allow pipeline construction in tests
        try:
            adapter.connected = True
            logger.info("Demo mode: broker marked as connected (no real API calls).")
        except Exception:
            pass
    
    pipeline = LiveTradingPipeline(
        broker_adapter=adapter,
        tickers=['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA'],
        initial_capital=100000.0,
        strategy='factor_ensemble'
    )
    
    return pipeline

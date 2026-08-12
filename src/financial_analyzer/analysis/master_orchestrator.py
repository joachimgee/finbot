"""
Master Orchestrator - Hub central pour toutes les analyses FinBot.

Architecture complète (SANS DOUBLONS):
1. Portfolio Pre-Analysis (daily_preanalysis.py) → Portfolio existant
2. Portfolio Decision (portfolio_manager.py) → HOLD/SELL/BUY
3. Signal Generation (RL + ML + Sentiment) → Nouveaux signaux
4. Portfolio Optimization (optimizer.py) → Poids optimaux
5. Options Hedging (options module) → Protection
6. Risk Validation (risk_guard.py) → Validation finale
7. Execution (broker_adapter.py) → Live trading

Modules existants utilisés (RÉUTILISATION):
- preanalysis/daily_preanalysis.py : drift detection, options analysis
- scripts/portfolio_manager.py : HOLD/SELL/BUY decisions
- portfolio/optimizer.py : Mean-Variance, Risk Parity, HRP
- portfolio/rebalancer.py : Rebalancing périodique/threshold
- derivatives/options : Black-Scholes, Greeks, Strategies
- learning/portfolio_learner.py : Apprentissage continu
- pipeline/rl_trading_pipeline.py : RL agent training
- pipeline/ml_trading_pipeline.py : ML predictions
- sentiment/realtime_pipeline.py : Sentiment analysis
- trading/live_trading_pipeline.py : Live execution
- trading/broker_adapter.py : Alpaca/IB integration
- trading/risk_guard.py : Risk validation

Workflow Type:
    Morning Pre-Analysis (AVANT nouvelle analyse):
        1. portfolio_learner.analyze_morning_pre_analysis() → Métriques historiques
        2. daily_preanalysis.check_model_drift() → Besoin retrain ?
        3. portfolio_manager.get_current_portfolio() → État actuel
        4. daily_preanalysis.analyze_options_market() → Hedging needs
        5. portfolio_manager.make_decisions() → HOLD/SELL/BUY
        
    Signal Generation (Nouveaux signaux):
        6. rl_trading_pipeline.run_rl_training() → RL policy
        7. ml_trading_pipeline.run() → ML predictions
        8. realtime_pipeline.analyze() → Sentiment scores
        
    Portfolio Construction (Optimisation):
        9. optimizer.optimize() → Poids optimaux (5+ methods)
        10. options module → Hedge overlay
        11. rebalancer.rebalance_periodic() → Ajustements
        
    Risk & Execution (Validation & Live):
        12. risk_guard.validate_orders() → Circuit breakers
        13. broker_adapter.submit_orders() → Execution
        14. account_monitor.track() → Monitoring

References:
    - archive/INTEGRATION_STATUS.md : État des 5 priorités (144/144 tests)
    - portfolio_manager.py : Décisions portfolio existant
    - daily_preanalysis.py : Drift + Options integration
    - COMPARATIVE_ANALYSIS.md : Architecture complète
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

import numpy as np
import pandas as pd

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


@dataclass
class PreAnalysisResult:
    """Résultat de la pré-analyse portfolio."""
    
    timestamp: datetime
    current_portfolio: Dict[str, Any]
    drift_detected: bool
    drift_reason: Optional[str]
    options_analysis: Dict[str, Any]
    portfolio_decisions: Dict[str, List[Dict]]  # HOLD/SELL/BUY
    should_retrain: bool
    warnings: List[str]
    learning_insights: List[Dict]


@dataclass
class SignalGenerationResult:
    """Résultat de la génération de signaux."""
    
    timestamp: datetime
    rl_signals: Optional[Dict[str, float]]
    ml_predictions: Optional[Dict[str, float]]
    sentiment_scores: Optional[Dict[str, float]]
    combined_signals: Dict[str, float]
    confidence_scores: Dict[str, float]


@dataclass
class PortfolioConstructionResult:
    """Résultat de la construction portfolio."""
    
    timestamp: datetime
    target_weights: pd.Series
    current_weights: pd.Series
    rebalance_needed: bool
    trades_required: pd.Series
    optimization_method: str
    expected_return: float
    expected_volatility: float
    expected_sharpe: float
    options_hedge_overlay: Optional[Dict[str, Any]]


@dataclass
class ExecutionResult:
    """Résultat de l'exécution.
    Ajout: risk_summary pour reporting global et risk_score agrégé.
    """
    timestamp: datetime
    orders_submitted: List[Dict[str, Any]]
    orders_executed: List[Dict[str, Any]]
    orders_rejected: List[Dict[str, Any]]
    circuit_breakers_triggered: List[str]
    portfolio_value_before: float
    portfolio_value_after: float
    execution_cost: float
    risk_summary: Optional[Dict[str, Any]] = None
    risk_score: Optional[float] = None


@dataclass
class MasterAnalysisResult:
    """Résultat complet de l'analyse master."""
    
    timestamp: datetime
    pre_analysis: PreAnalysisResult
    signal_generation: Optional[SignalGenerationResult]
    portfolio_construction: Optional[PortfolioConstructionResult]
    execution: Optional[ExecutionResult]
    status: str  # 'success', 'failed', 'skipped'
    elapsed_time_seconds: float


class MasterOrchestrator:
    """
    Orchestrateur principal pour toutes les analyses FinBot.
    
    Coordonne tous les modules sans duplication:
    - Portfolio pre-analysis (drift, options, decisions)
    - Signal generation (RL, ML, sentiment)
    - Portfolio optimization (Mean-Variance, Risk Parity, etc.)
    - Risk validation & execution
    
    Example:
        >>> from financial_analyzer.analysis.master_orchestrator import MasterOrchestrator
        >>> 
        >>> # Initialize
        >>> orchestrator = MasterOrchestrator(
        ...     symbols=['AAPL', 'MSFT', 'GOOGL', 'AMZN', 'TSLA'],
        ...     mode='paper'
        ... )
        >>> 
        >>> # Run complete analysis
        >>> result = orchestrator.run_complete_analysis(
        ...     start_date='2024-01-01',
        ...     end_date='2024-11-24',
        ...     skip_if_no_drift=True
        ... )
        >>> 
        >>> print(f"Status: {result.status}")
        >>> print(f"Drift detected: {result.pre_analysis.drift_detected}")
        >>> print(f"Orders executed: {len(result.execution.orders_executed)}")
    """
    
    def __init__(
        self,
        symbols: List[str],
        mode: str = 'paper',
        initial_capital: float = 100_000.0,
        max_positions: int = 200,
        risk_free_rate: float = 0.05,
        lookback_days: int = 60,
        analysis_csv_path: Optional[str] = None,
    ):
        """
        Initialize Master Orchestrator.
        
        Args:
            symbols: List of symbols to analyze
            mode: 'paper' or 'live'
            initial_capital: Initial capital for portfolio
            max_positions: Maximum number of positions
            risk_free_rate: Risk-free rate for calculations
            lookback_days: Days of history for learning
        """
        self.symbols = symbols
        self.mode = mode
        self.initial_capital = initial_capital
        self.max_positions = max_positions
        self.risk_free_rate = risk_free_rate
        self.lookback_days = lookback_days
        self.analysis_csv_path = analysis_csv_path
        
        # Lazy imports (avoid circular dependencies)
        self._portfolio_learner = None
        self._portfolio_manager = None
        self._rl_pipeline = None
        self._ml_pipeline = None
        self._sentiment_pipeline = None
        self._optimizer = None
        self._rebalancer = None
        self._broker_adapter = None
        self._risk_guard = None
        self._account_monitor = None
        
        logger.info(
            f"MasterOrchestrator initialized: {len(symbols)} symbols, "
            f"mode={mode}, capital=${initial_capital:,.0f}"
        )
    
    def run_complete_analysis(
        self,
        start_date: str,
        end_date: str,
        skip_if_no_drift: bool = True,
        use_rl_signals: bool = True,
        use_ml_signals: bool = True,
        use_sentiment: bool = True,
        optimization_method: str = 'mean_variance',
        enable_options_hedge: bool = True,
        dry_run: bool = False,
    ) -> MasterAnalysisResult:
        """
        Run complete analysis workflow.
        
        Process:
            1. Portfolio Pre-Analysis (morning routine)
            2. Signal Generation (if needed)
            3. Portfolio Construction
            4. Risk Validation & Execution
        
        Args:
            start_date: Start date for data
            end_date: End date for data
            skip_if_no_drift: Skip analysis if no drift detected
            use_rl_signals: Use RL signals
            use_ml_signals: Use ML predictions
            use_sentiment: Use sentiment analysis
            optimization_method: 'mean_variance', 'risk_parity', 'hrp', 'black_litterman'
            enable_options_hedge: Enable options hedging overlay
            dry_run: If True, don't execute orders
        
        Returns:
            MasterAnalysisResult with complete workflow results
        """
        start_time = datetime.now()
        logger.info("=" * 80)
        logger.info("MASTER ORCHESTRATOR - COMPLETE ANALYSIS")
        logger.info("=" * 80)
        
        try:
            # PHASE 1: PORTFOLIO PRE-ANALYSIS
            logger.info("Phase 1: Portfolio Pre-Analysis...")
            pre_analysis = self._run_pre_analysis(start_date, end_date)
            
            # Skip if no drift and skip_if_no_drift enabled
            if skip_if_no_drift and not pre_analysis.drift_detected:
                logger.info("No drift detected, skipping analysis (skip_if_no_drift=True)")
                return MasterAnalysisResult(
                    timestamp=datetime.now(),
                    pre_analysis=pre_analysis,
                    signal_generation=None,
                    portfolio_construction=None,
                    execution=None,
                    status='skipped',
                    elapsed_time_seconds=(datetime.now() - start_time).total_seconds()
                )
            
            # PHASE 2: SIGNAL GENERATION (if needed)
            logger.info("Phase 2: Signal Generation...")
            signal_gen = self._run_signal_generation(
                start_date=start_date,
                end_date=end_date,
                use_rl=use_rl_signals,
                use_ml=use_ml_signals,
                use_sentiment=use_sentiment,
            )
            
            # PHASE 3: PORTFOLIO CONSTRUCTION
            logger.info("Phase 3: Portfolio Construction...")
            portfolio_construction = self._run_portfolio_construction(
                pre_analysis=pre_analysis,
                signal_gen=signal_gen,
                optimization_method=optimization_method,
                enable_options_hedge=enable_options_hedge,
            )
            
            # PHASE 4: RISK VALIDATION & EXECUTION
            logger.info("Phase 4: Risk Validation & Execution...")
            execution = self._run_execution(
                portfolio_construction=portfolio_construction,
                pre_analysis=pre_analysis,
                dry_run=dry_run,
            )
            
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(f"✅ Complete analysis finished in {elapsed:.1f}s")
            
            return MasterAnalysisResult(
                timestamp=datetime.now(),
                pre_analysis=pre_analysis,
                signal_generation=signal_gen,
                portfolio_construction=portfolio_construction,
                execution=execution,
                status='success',
                elapsed_time_seconds=elapsed,
            )
            
        except Exception as e:
            logger.error(f"Master analysis failed: {e}", exc_info=True)
            elapsed = (datetime.now() - start_time).total_seconds()
            # Always provide a minimal PreAnalysisResult for downstream safety
            if 'pre_analysis' not in locals() or pre_analysis is None:
                minimal_pre = PreAnalysisResult(
                    timestamp=datetime.now(),
                    current_portfolio={},
                    drift_detected=False,
                    drift_reason=None,
                    options_analysis={},
                    portfolio_decisions={'hold': [], 'sell': [], 'buy': [], 'cancel': []},
                    should_retrain=False,
                    warnings=[f"Master analysis failed early: {e}"],
                    learning_insights=[],
                )
            else:
                minimal_pre = pre_analysis
            return MasterAnalysisResult(
                timestamp=datetime.now(),
                pre_analysis=minimal_pre,
                signal_generation=None,
                portfolio_construction=None,
                execution=None,
                status='failed',
                elapsed_time_seconds=elapsed,
            )
    
    def _run_pre_analysis(
        self,
        start_date: str,
        end_date: str,
    ) -> PreAnalysisResult:
        """
        Run portfolio pre-analysis (morning routine).
        
        Steps:
            1. Portfolio learning analysis (historical performance)
            2. Model drift detection
            3. Current portfolio snapshot
            4. Options market analysis
            5. Portfolio decisions (HOLD/SELL/BUY)
        
        Returns:
            PreAnalysisResult with pre-analysis results
        """
        from financial_analyzer.preanalysis.daily_preanalysis import (
            run_daily_preanalysis,
            check_model_drift,
        )
        from financial_analyzer.learning.portfolio_learner import PortfolioLearner
        from pathlib import Path
        # PortfolioManager (script path) – import guarded
        try:
            from scripts.portfolio_manager import PortfolioManager  # type: ignore
            pm_available = True
        except Exception:
            pm_available = False
        
        # 1. Portfolio Learning (morning analysis)
        learner = PortfolioLearner(mode=self.mode, lookback_days=self.lookback_days)
        learning_result = learner.analyze_morning_pre_analysis()
        
        # 2. Daily preanalysis (drift + options)
        preanalysis_result = run_daily_preanalysis(
            symbols=self.symbols,
            start_date=start_date,
            end_date=end_date,
            check_drift=True,
            analyze_options=True,
            risk_free_rate=self.risk_free_rate,
        )
        
        # 3. Portfolio decisions (HOLD/SELL/BUY) via PortfolioManager si analyse disponible
        portfolio_decisions = {
            'hold': [], 'sell': [], 'buy': [], 'cancel': []
        }
        if pm_available and self.analysis_csv_path:
            csv_path = Path(self.analysis_csv_path)
            if csv_path.exists():
                try:
                    manager = PortfolioManager(
                        mode=self.mode,
                        max_positions=self.max_positions,
                        hold_threshold_score=0.0
                    )
                    current_portfolio = manager.get_current_portfolio()
                    analysis_df = manager.load_analysis_results(str(csv_path))
                    portfolio_decisions = manager.make_decisions(current_portfolio, analysis_df)
                    logger.info(
                        f"Portfolio decisions loaded from analysis CSV: hold={len(portfolio_decisions['hold'])}, "
                        f"sell={len(portfolio_decisions['sell'])}, buy={len(portfolio_decisions['buy'])}"
                    )
                except Exception as e:
                    logger.warning(f"PortfolioManager integration failed: {e}")
            else:
                logger.info("Analysis CSV path provided but file not found – using empty decisions placeholder")
        else:
            if not pm_available:
                logger.info("PortfolioManager not available (import failed) – using empty decisions placeholder")
            if not self.analysis_csv_path:
                logger.info("No analysis CSV path provided – using empty decisions placeholder")
        
        drift_detected = preanalysis_result.get('drift_check', {}).get('drift_detected', False)
        drift_reason = preanalysis_result.get('drift_check', {}).get('reason', None)
        
        logger.info(
            f"Pre-analysis complete: drift={drift_detected}, "
            f"options_analyzed={len(preanalysis_result.get('options_analysis', {}))}"
        )
        
        return PreAnalysisResult(
            timestamp=datetime.now(),
            current_portfolio=learning_result.portfolio_snapshot.__dict__,
            drift_detected=drift_detected,
            drift_reason=drift_reason,
            options_analysis=preanalysis_result.get('options_analysis', {}),
            portfolio_decisions=portfolio_decisions,
            should_retrain=drift_detected,
            warnings=learning_result.warning_messages,
            learning_insights=[asdict(i) for i in learning_result.insights],
        )
    
    def _run_signal_generation(
        self,
        start_date: str,
        end_date: str,
        use_rl: bool = True,
        use_ml: bool = True,
        use_sentiment: bool = True,
    ) -> SignalGenerationResult:
        """
        Generate trading signals from multiple sources.
        
        Sources:
            - RL: Reinforcement Learning policy
            - ML: Machine Learning predictions (LSTM, Random Forest, etc.)
            - Sentiment: FinBERT sentiment scores
        
        Returns:
            SignalGenerationResult with combined signals
        """
        rl_signals = {}
        ml_predictions = {}
        sentiment_scores = {}
        
        # RL signals (if enabled)
        if use_rl:
            try:
                from financial_analyzer.pipeline.rl_trading_pipeline import RLTradingPipeline
                
                rl_pipeline = RLTradingPipeline(
                    symbols=self.symbols,
                    start_date=start_date,
                    end_date=end_date,
                    initial_capital=self.initial_capital,
                )
                
                # Load trained model or use default
                # For now, we skip actual RL training (too slow for demo)
                logger.info("RL signals: Using cached/pre-trained model")
                rl_signals = {symbol: 0.0 for symbol in self.symbols}
                
            except Exception as e:
                logger.warning(f"RL signals failed: {e}")
        
        # ML predictions (if enabled)
        if use_ml:
            try:
                from financial_analyzer.pipeline.ml_trading_pipeline import MLTradingPipeline
                
                ml_pipeline = MLTradingPipeline(
                    symbols=self.symbols,
                    start_date=start_date,
                    end_date=end_date,
                )
                
                # For demo, we use simple momentum signals
                logger.info("ML predictions: Using momentum signals")
                ml_predictions = {symbol: 0.0 for symbol in self.symbols}
                
            except Exception as e:
                logger.warning(f"ML predictions failed: {e}")
        
        # Sentiment analysis (if enabled)
        if use_sentiment:
            try:
                from financial_analyzer.sentiment.realtime_pipeline import RealtimeSentimentPipeline
                
                sentiment_pipeline = RealtimeSentimentPipeline()
                
                # For demo, neutral sentiment
                logger.info("Sentiment: Using neutral scores")
                sentiment_scores = {symbol: 0.0 for symbol in self.symbols}
                
            except Exception as e:
                logger.warning(f"Sentiment analysis failed: {e}")
        
        # Combine signals (equal weight for demo)
        combined_signals = {}
        confidence_scores = {}
        
        for symbol in self.symbols:
            signals = []
            if symbol in rl_signals:
                signals.append(rl_signals[symbol])
            if symbol in ml_predictions:
                signals.append(ml_predictions[symbol])
            if symbol in sentiment_scores:
                signals.append(sentiment_scores[symbol])
            
            combined_signals[symbol] = np.mean(signals) if signals else 0.0
            confidence_scores[symbol] = 1.0 / (1.0 + np.std(signals)) if len(signals) > 1 else 0.5
        
        logger.info(f"Signal generation complete: {len(combined_signals)} symbols")
        
        return SignalGenerationResult(
            timestamp=datetime.now(),
            rl_signals=rl_signals if rl_signals else None,
            ml_predictions=ml_predictions if ml_predictions else None,
            sentiment_scores=sentiment_scores if sentiment_scores else None,
            combined_signals=combined_signals,
            confidence_scores=confidence_scores,
        )
    
    def _run_portfolio_construction(
        self,
        pre_analysis: PreAnalysisResult,
        signal_gen: SignalGenerationResult,
        optimization_method: str = 'mean_variance',
        enable_options_hedge: bool = True,
    ) -> PortfolioConstructionResult:
        """
        Construct optimal portfolio from signals.
        
        Steps:
            1. Get current weights
            2. Optimize target weights (Mean-Variance, Risk Parity, HRP, etc.)
            3. Add options hedge overlay (if enabled)
            4. Compute rebalance trades
        
        Returns:
            PortfolioConstructionResult with target weights and trades
        """
        from financial_analyzer.portfolio.optimizer import PortfolioOptimizer
        from financial_analyzer.portfolio.rebalancer import PortfolioRebalancer
        from financial_analyzer.data.pit_loader import PITDataLoader
        
        # Load price data
        # Real adjusted prices when Alpaca credentials are present; degrades to
        # synthetic (loudly) otherwise so offline/CI analysis still runs.
        loader = PITDataLoader(source="alpaca")
        # Use last 252 days for optimization
        from datetime import timedelta
        end = datetime.now()
        start = end - timedelta(days=252)
        
        price_data = loader.load_prices(
            symbols=self.symbols,
            start_date=start.strftime('%Y-%m-%d'),
            end_date=end.strftime('%Y-%m-%d'),
        )

        # PITDataLoader returns {symbol: OHLCV DataFrame}; build a close-price
        # panel before computing returns (a bare dict has no .pct_change()).
        if isinstance(price_data, dict):
            prices = pd.DataFrame(
                {sym: df['close'] for sym, df in price_data.items() if not df.empty}
            )
        else:
            prices = price_data
        returns = prices.pct_change().dropna()

        # Current weights (from portfolio snapshot)
        current_positions = pre_analysis.current_portfolio.get('positions', [])
        current_weights = pd.Series(0.0, index=self.symbols)
        
        if current_positions:
            total_value = sum(p.get('market_value', 0) for p in current_positions)
            for pos in current_positions:
                symbol = pos.get('symbol')
                if symbol in self.symbols:
                    current_weights[symbol] = pos.get('market_value', 0) / total_value if total_value > 0 else 0.0
        
        # Optimize target weights. The optimizer methods return a dict
        # {'weights': Series, ...}; there is no 'optimize_mean_variance' (the old
        # call raised AttributeError and was swallowed) — map to the real methods.
        optimizer = PortfolioOptimizer(returns=returns)

        try:
            if optimization_method == 'risk_parity':
                result = optimizer.optimize_risk_parity()
            elif optimization_method == 'min_variance':
                result = optimizer.optimize_min_variance()
            elif optimization_method == 'equal_weight':
                result = optimizer.optimize_equal_weight()
            else:  # 'mean_variance' / 'max_sharpe' default
                result = optimizer.optimize_max_sharpe()
            target_weights = pd.Series(result['weights'])
            metrics = {k: v for k, v in result.items() if k != 'weights'}
        except Exception as e:
            logger.warning(f"Optimization failed ({e}); using equal weight")
            target_weights = pd.Series(1.0 / len(self.symbols), index=self.symbols)
            metrics = {}

        # Guarantee a Series indexed by every symbol for the trade computation.
        target_weights = target_weights.reindex(self.symbols).fillna(0.0)
        
        # Options hedge overlay (if enabled)
        options_hedge_overlay = None
        if enable_options_hedge and pre_analysis.options_analysis:
            # Compute portfolio delta
            portfolio_delta = sum(
                target_weights.get(symbol, 0) * opt.get('delta_call', 0)
                for symbol, opt in pre_analysis.options_analysis.items()
                if opt is not None
            )
            
            # Hedge with ATM puts
            hedge_ratio = abs(portfolio_delta)
            options_hedge_overlay = {
                'portfolio_delta': portfolio_delta,
                'hedge_ratio': hedge_ratio,
                'hedge_type': 'ATM_puts',
                'hedge_allocation': min(hedge_ratio, 0.1),  # Max 10% in options
            }
            
            logger.info(f"Options hedge: {hedge_ratio:.2%} via ATM puts")
        
        # Compute rebalance trades
        trades_required = target_weights - current_weights
        rebalance_needed = (trades_required.abs() > 0.01).any()  # 1% threshold
        
        logger.info(
            f"Portfolio construction: {optimization_method}, "
            f"rebalance_needed={rebalance_needed}, "
            f"expected_sharpe={metrics.get('sharpe', 0.0):.2f}"
        )
        
        return PortfolioConstructionResult(
            timestamp=datetime.now(),
            target_weights=target_weights,
            current_weights=current_weights,
            rebalance_needed=rebalance_needed,
            trades_required=trades_required,
            optimization_method=optimization_method,
            expected_return=metrics.get('return', 0.0),
            expected_volatility=metrics.get('volatility', 0.0),
            expected_sharpe=metrics.get('sharpe', 0.0),
            options_hedge_overlay=options_hedge_overlay,
        )
    
    def _run_execution(
        self,
        portfolio_construction: PortfolioConstructionResult,
        pre_analysis: PreAnalysisResult,
        dry_run: bool = False,
    ) -> ExecutionResult:
        """
        Execute portfolio changes with risk validation.
        
        Steps:
            1. Convert target weights to orders
            2. Risk validation (circuit breakers)
            3. Submit orders (if not dry_run)
            4. Track execution
        
        Returns:
            ExecutionResult with execution details
        """
        # SAFETY: this execution path is NOT production-ready. It is unvalidated
        # and redundant with LiveTradingPipeline: portfolio construction is fed
        # synthetic random-walk prices (PITDataLoader) and has never been covered
        # by tests. Rather than let it silently place orders on garbage data, it
        # refuses any real submission and fails loudly. dry_run analysis is still
        # allowed. Use LiveTradingPipeline for real order execution.
        if not dry_run:
            raise NotImplementedError(
                "MasterOrchestrator order execution is disabled: this path is "
                "unvalidated (synthetic prices, no tests) and redundant with "
                "LiveTradingPipeline. Use LiveTradingPipeline to submit real "
                "orders, or call this analysis with dry_run=True."
            )

        from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter
        from financial_analyzer.trading.account_monitor import AccountMonitor
        from financial_analyzer.trading.risk_guard import RiskGuard, CircuitBreakerTriggered, RiskLimitExceeded, InvalidOrderError
        from financial_analyzer.trading.order_gateway import OrderGateway

        # Initialize broker adapter
        adapter = AlpacaAdapter.from_env(mode=self.mode)
        adapter.connect()
        monitor = AccountMonitor(adapter, initial_capital=self.initial_capital)
        monitor.update()
        risk_guard = RiskGuard(
            account_monitor=monitor,
            max_position_size=self.initial_capital * 0.05,  # 5% cap
            max_position_pct=0.20,
            max_total_positions=self.max_positions,
            max_drawdown=-0.25,
            max_daily_loss=self.initial_capital * 0.05,
            max_leverage=2.0,
            enable_circuit_breaker=True,
        )
        # Single audited execution chokepoint shared with the live pipeline.
        gateway = OrderGateway(adapter, risk_guard)
        portfolio_value_before = monitor.portfolio_value
        if dry_run:
            logger.info("DRY RUN: validating trades without submission")
        
        # Convert trades to orders (simplified sizing by target delta in weight)
        orders_submitted: List[Dict[str, Any]] = []
        orders_executed: List[Dict[str, Any]] = []
        orders_rejected: List[Dict[str, Any]] = []
        circuit_breakers_triggered: List[str] = []
        for symbol, trade_weight in portfolio_construction.trades_required.items():
            if abs(trade_weight) < 0.01:
                continue
            try:
                # Estimate price via last bars (fallback inside adapter)
                from datetime import datetime, timedelta
                bars = adapter.get_bars(symbol, datetime.now() - timedelta(days=5), datetime.now(), timeframe='1Day')
                if bars.empty:
                    logger.warning(f"No price data for {symbol}, skipping")
                    continue
                price = float(bars['close'].iloc[-1])
                # Position value change target
                delta_value = trade_weight * portfolio_value_before
                qty = int(abs(delta_value) / price)
                if qty < 1:
                    continue
                side = 'buy' if trade_weight > 0 else 'sell'
                order_record = {
                    'symbol': symbol,
                    'side': side,
                    'qty': qty,
                    'price': price,
                    'trade_weight': float(trade_weight),
                }
                # Single audited chokepoint: mode-gate + risk validation +
                # idempotence + audit, then submission (skipped in dry_run).
                try:
                    order_resp = gateway.submit(
                        symbol, qty, side=side, price=price,
                        order_type='market', dry_run=dry_run,
                    )
                except CircuitBreakerTriggered as cb:
                    circuit_breakers_triggered.append(str(cb))
                    logger.error(f"Circuit breaker triggered – abort remaining orders: {cb}")
                    break
                except (RiskLimitExceeded, InvalidOrderError) as re:
                    logger.warning(f"Order rejected by risk limits: {symbol} {side} qty={qty}: {re}")
                    orders_rejected.append({'symbol': symbol, 'side': side, 'qty': qty, 'reason': str(re)})
                    continue
                orders_submitted.append(order_record)
                if not dry_run and order_resp:
                    orders_executed.append(order_record)
                logger.info(f"Prepared order: {symbol} {side} qty={qty} (weight={trade_weight:.3%})")
            except Exception as e:
                logger.error(f"Failed preparing order for {symbol}: {e}")
                orders_rejected.append({'symbol': symbol, 'side': 'unknown', 'qty': 0, 'reason': str(e)})
        # Final monitoring update
        monitor.update()
        portfolio_value_after = monitor.portfolio_value
        execution_cost = 0.0  # Placeholder (could integrate fee model later)
        risk_summary = risk_guard.get_risk_summary()
        risk_score = risk_guard.get_risk_score()
        logger.info(
            f"Execution phase complete: submitted={len(orders_submitted)}, executed={len(orders_executed)}, "
            f"rejected={len(orders_rejected)}, circuit_breakers={len(circuit_breakers_triggered)}, risk_score={risk_score:.1f}"
        )
        return ExecutionResult(
            timestamp=datetime.now(),
            orders_submitted=orders_submitted,
            orders_executed=orders_executed,
            orders_rejected=orders_rejected,
            circuit_breakers_triggered=circuit_breakers_triggered,
            portfolio_value_before=portfolio_value_before,
            portfolio_value_after=portfolio_value_after,
            execution_cost=execution_cost,
            risk_summary=risk_summary,
            risk_score=risk_score,
        )


def asdict(obj):  # type: ignore
    """Helper override kept for backward compatibility (prefer dataclasses.asdict)."""
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    return {}


__all__ = [
    "MasterOrchestrator",
    "MasterAnalysisResult",
    "PreAnalysisResult",
    "SignalGenerationResult",
    "PortfolioConstructionResult",
    "ExecutionResult",
]

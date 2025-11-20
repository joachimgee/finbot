"""
Backtesting wrapper autour de backtesting.py.

Ce module fournit une interface simplifiée pour backtester des stratégies
avec les features générées par FeaturePipeline.

Author: FinBot Team
Date: 2025-11-06
Version: 2.0.0
"""

from typing import Any, Dict, Optional, Type, Union

import numpy as np
import pandas as pd
from backtesting import Backtest, Strategy

from financial_analyzer.utils.helpers import get_logger
from financial_analyzer.backtest.ic_reporting import (
    compute_cross_sectional_ic,
    ic_summary,
    compute_ic_decay,
    generate_ic_report_html,
)

logger = get_logger(__name__)


class CustomStrategy(Strategy):
    """
    Classe de base pour stratégies custom avec accès complet aux features.
    
    Hérite de backtesting.Strategy et expose toutes les colonnes features
    via self.data. Subclasses doivent implémenter init() et next().
    
    Attributes:
        data: DataFrame features accessible via self.data.ColumnName.
    
    Example:
        >>> class MyStrategy(CustomStrategy):
        ...     def init(self):
        ...         self.sma = self.I(lambda x: x, self.data.SMA_20)
        ...     
        ...     def next(self):
        ...         if self.data.Close[-1] > self.sma[-1]:
        ...             if not self.position:
        ...                 self.buy()
        ...         else:
        ...             if self.position:
        ...                 self.position.close()
    """
    
    def init(self):
        """
        Initialisation de la stratégie (appelée une fois au début).
        
        Override dans subclass pour définir indicateurs/signaux.
        """
        pass
    
    def next(self):
        """
        Logique de trading (appelée à chaque barre/timestamp).
        
        Override dans subclass pour implémenter règles buy/sell.
        """
        pass


class BacktestRunner:
    """
    Wrapper autour de backtesting.Backtest pour intégration avec FeaturePipeline.
    
    Simplifie le backtesting de stratégies avec features ML-ready. Gère
    automatiquement la commission et la conversion DataFrame → OHLCV.
    Remarque: le slippage global n'est pas supporté directement par
    backtesting.py; implémentez le slippage dans votre stratégie si
    nécessaire (voir la section Note plus bas).
    
    Attributes:
    features (pd.DataFrame): DataFrame features (OHLCV + tech + fund).
    strategy (Type[CustomStrategy]): Classe stratégie à backtester.
    target_col (str): Colonne prix principal (default 'Close').
    cash (float): Capital initial en USD.
    commission (float): Taux commission par trade (0.002 = 0.2%).
    backtest (Backtest): Instance backtesting.Backtest (créée après init).
    
    Example:
        >>> from financial_analyzer.features import FeaturePipeline
        >>> pipeline = FeaturePipeline(ohlcv_df)
        >>> features = pipeline.add_technical_features().get_features()
        >>> 
        >>> class SimpleStrategy(CustomStrategy):
        ...     def init(self):
        ...         self.rsi = self.data.RSI_14
        ...     def next(self):
        ...         if self.rsi[-1] < 30 and not self.position:
        ...             self.buy()
        ...         elif self.rsi[-1] > 70 and self.position:
        ...             self.position.close()
        >>> 
        >>> runner = BacktestRunner(features, SimpleStrategy, cash=100_000)
        >>> result = runner.run()
        >>> print(result['Return [%]'])
    """
    
    def __init__(
        self,
        features: pd.DataFrame,
        strategy: Type[CustomStrategy],
        target_col: str = 'Close',
        cash: float = 100_000,
        commission: float = 0.002,
        **kwargs
    ):
        """
        Initialise le BacktestRunner.
        
        Args:
            features: DataFrame features (doit contenir OHLCV minimum).
            strategy: Classe héritant de CustomStrategy.
            target_col: Colonne prix principal (default 'Close').
            cash: Capital initial USD (default 100,000).
            commission: Taux commission par trade (default 0.002 = 0.2%).
            **kwargs: Arguments additionnels pour backtesting.Backtest.
        
            Note:
            backtesting.py ne supporte pas slippage global dans Backtest().
            Pour implémenter slippage, gérez-le dans votre strategy via
            self.buy(limit=price*(1+X)) ou self.sell(limit=price*(1-X)),
            ou ajustez la logique d'ordre dans la stratégie.
        
        Raises:
            ValueError: Si features n'est pas DataFrame ou colonnes OHLCV manquantes.
            TypeError: Si strategy n'est pas subclass de CustomStrategy.
        
            Example:
            >>> runner = BacktestRunner(
            ...     features_df,
            ...     MyStrategy,
            ...     cash=50_000,
            ...     commission=0.001,
            ... )
        """
        # Validation inputs
        self._validate_inputs(features, strategy, target_col)
        
        self.features = features.copy()
        self.strategy = strategy
        self.target_col = target_col
        self.cash = cash
        self.commission = commission
        self.kwargs = kwargs
        
        # Préparer données OHLCV pour backtesting.py
        self.ohlcv_data = self._prepare_ohlcv_data()
        
        # Créer instance Backtest
        # Default: finalize trades to ensure closed trades counted in stats
        backtest_kwargs = dict(self.kwargs) if isinstance(self.kwargs, dict) else {}
        if 'finalize_trades' not in backtest_kwargs:
            backtest_kwargs['finalize_trades'] = True

        self.backtest = Backtest(
            self.ohlcv_data,
            self.strategy,
            cash=self.cash,
            commission=self.commission,
            **backtest_kwargs
        )
        
        logger.info(
            f"BacktestRunner initialisé: strategy={strategy.__name__}, "
            f"cash=${cash:,.0f}, commission={commission:.4f}"
        )
    
    def _validate_inputs(
        self,
        features: pd.DataFrame,
        strategy: Type[CustomStrategy],
        target_col: str
    ) -> None:
        """
        Valide les inputs du constructor.
        
        Args:
            features: DataFrame à valider.
            strategy: Classe stratégie à valider.
            target_col: Colonne target à valider.
        
        Raises:
            ValueError: Si validation échoue.
            TypeError: Si types incorrects.
        """
        # Valider features DataFrame
        if not isinstance(features, pd.DataFrame):
            raise TypeError(f"features doit être DataFrame, reçu {type(features)}")
        
        if features.empty:
            raise ValueError("features DataFrame ne peut pas être vide")
        
        if not isinstance(features.index, pd.DatetimeIndex):
            raise ValueError("features index doit être DatetimeIndex")
        
        # Valider colonnes OHLCV requises
        required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        missing_cols = [col for col in required_cols if col not in features.columns]
        if missing_cols:
            raise ValueError(f"Colonnes OHLCV manquantes: {missing_cols}")
        
        # Valider target_col existe
        if target_col not in features.columns:
            raise ValueError(f"target_col '{target_col}' absent de features")
        
        # Valider strategy est subclass de CustomStrategy
        if not isinstance(strategy, type) or not issubclass(strategy, Strategy):
            raise TypeError(
                f"strategy doit être subclass de Strategy, reçu {type(strategy)}"
            )
        
        logger.debug("Validation inputs réussie")
    
    def _prepare_ohlcv_data(self) -> pd.DataFrame:
        """
        Prépare DataFrame OHLCV pour backtesting.Backtest.
        
        backtesting.py requiert DataFrame avec colonnes exactes:
        Open, High, Low, Close, Volume (capitalized).
        
        Inclut aussi toutes les autres colonnes features pour accessibilité
        dans la stratégie via self.data.FeatureName.
        
        Returns:
            DataFrame avec OHLCV + features additionnelles.
        """
        # Copier features complet
        ohlcv = self.features.copy()
        
        # Assurer colonnes OHLCV en float
        ohlcv_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
        for col in ohlcv_cols:
            ohlcv[col] = ohlcv[col].astype(float)
        
        # Valider absence NaN dans OHLCV (backtesting.py échoue sinon)
        if ohlcv[ohlcv_cols].isna().any().any():
            logger.warning(
                "NaN détectés dans colonnes OHLCV. Utiliser FeaturePipeline.handle_missing_values() "
                "avant backtesting."
            )
            # Forward fill puis drop NaN restants
            ohlcv = ohlcv.ffill().dropna(subset=ohlcv_cols)
            logger.info(f"NaN traités: {len(ohlcv)} lignes restantes après nettoyage")
        
        # Assurer index trié (requis par backtesting.py)
        if not ohlcv.index.is_monotonic_increasing:
            ohlcv = ohlcv.sort_index()
            logger.debug("Index trié (monotonic increasing)")
        
        return ohlcv
    
    def run(self, return_plot: bool = False, **kwargs) -> Union[pd.Series, Dict[str, Any]]:
        """
        Lance le backtest et retourne les résultats.
        
        Args:
            return_plot: Si True, retourne aussi plot Bokeh (default False).
            **kwargs: Arguments additionnels pour backtest.run().
        
        Returns:
            Si return_plot=False: pd.Series avec métriques performance.
            Si return_plot=True: Dict avec {'stats': pd.Series, 'plot': Bokeh figure}.
        
        Raises:
            RuntimeError: Si backtest échoue.
        
        Example:
            >>> result = runner.run()
            >>> print(f"Return: {result['Return [%]']:.2f}%")
            >>> print(f"Sharpe: {result['Sharpe Ratio']:.2f}")
            >>> 
            >>> # Avec plot
            >>> result = runner.run(return_plot=True)
            >>> result['plot'].show()
        """
        logger.info(f"Lancement backtest avec {self.strategy.__name__}...")
        
        try:
            # Run backtest
            stats = self.backtest.run(**kwargs)
            
            # Log résultats clés
            self._log_results(stats)
            
            # Retourner résultats
            if return_plot:
                plot = self.backtest.plot()
                return {
                    'stats': stats,
                    'plot': plot
                }
            else:
                return stats
                
        except Exception as e:
            logger.error(f"Backtest échoué: {e}", exc_info=True)
            raise RuntimeError(f"Backtest échoué: {e}") from e
    
    def _log_results(self, stats: pd.Series) -> None:
        """
        Log résultats clés du backtest.
        
        Args:
            stats: Série de métriques performance.
        """
        logger.info("=" * 60)
        logger.info("RÉSULTATS BACKTEST")
        logger.info("=" * 60)
        
        # Métriques clés
        key_metrics = [
            'Return [%]',
            'Sharpe Ratio',
            'Max. Drawdown [%]',
            'Win Rate [%]',
            '# Trades',
            'Avg. Trade [%]',
        ]
        
        for metric in key_metrics:
            if metric in stats.index:
                value = stats[metric]
                logger.info(f"{metric:.<30} {value:.2f}")
        
        logger.info("=" * 60)
    
    def optimize(
        self,
        constraint: Optional[callable] = None,
        maximize: str = 'Return [%]',
        method: str = 'grid',
        max_tries: Optional[int] = None,
        random_state: Optional[int] = None,
        return_heatmap: bool = False,
        **params
    ) -> Union[pd.Series, Dict[str, Any]]:
        """
        Optimise les paramètres de la stratégie.
        
        Args:
            constraint: Fonction constraint(param_dict) → bool.
            maximize: Métrique à maximiser (default 'Return [%]').
            method: Méthode optimisation ('grid', 'skopt').
            max_tries: Nombre max tentatives (grid search).
            random_state: Seed random (reproductibilité).
            return_heatmap: Si True, retourne aussi heatmap.
            **params: Paramètres à optimiser (ranges).
        
        Returns:
            Si return_heatmap=False: pd.Series avec meilleurs params.
            Si return_heatmap=True: Dict avec {'stats': pd.Series, 'heatmap': ...}.
        
        Example:
            >>> result = runner.optimize(
            ...     rsi_period=range(10, 30, 2),
            ...     rsi_lower=range(20, 40, 5),
            ...     rsi_upper=range(60, 80, 5),
            ...     maximize='Sharpe Ratio'
            ... )
            >>> print(result)
        """
        logger.info(f"Optimisation stratégie avec méthode '{method}'...")
        
        try:
            stats = self.backtest.optimize(
                constraint=constraint,
                maximize=maximize,
                method=method,
                max_tries=max_tries,
                random_state=random_state,
                return_heatmap=return_heatmap,
                **params
            )
            
            # Log meilleurs paramètres
            if isinstance(stats, dict) and 'stats' in stats:
                best_stats = stats['stats']
            else:
                best_stats = stats
            
            logger.info("=" * 60)
            logger.info("MEILLEURS PARAMÈTRES TROUVÉS")
            logger.info("=" * 60)
            
            # Afficher paramètres optimisés
            for param_name in params.keys():
                if hasattr(best_stats, '_strategy'):
                    param_value = getattr(best_stats._strategy, param_name, 'N/A')
                    logger.info(f"{param_name:.<30} {param_value}")
            
            logger.info("=" * 60)
            logger.info(f"{maximize:.<30} {best_stats[maximize]:.2f}")
            logger.info("=" * 60)
            
            return stats
            
        except Exception as e:
            logger.error(f"Optimisation échouée: {e}", exc_info=True)
            raise RuntimeError(f"Optimisation échouée: {e}") from e
    
    def get_trades(self) -> pd.DataFrame:
        """
        Retourne DataFrame des trades exécutés (après run()).
        
        Returns:
            DataFrame avec colonnes: EntryTime, ExitTime, EntryPrice,
            ExitPrice, PnL, PnLPct, Size, Duration, etc.
        
        Raises:
            RuntimeError: Si run() n'a pas encore été appelé.
        
        Example:
            >>> result = runner.run()
            >>> trades = runner.get_trades()
            >>> print(trades[['EntryTime', 'ExitTime', 'PnL']].head())
        """
        if not hasattr(self.backtest, '_results') or self.backtest._results is None:
            raise RuntimeError(
                "Aucun résultat disponible. Appeler run() d'abord."
            )
        
        trades_df = self.backtest._results['_trades']
        logger.info(f"Récupération {len(trades_df)} trades")
        
        return trades_df
    
    def get_equity_curve(self) -> pd.Series:
        """
        Retourne courbe equity (capital au cours du temps).
        
        Returns:
            Series avec index DatetimeIndex et valeurs equity USD.
        
        Raises:
            RuntimeError: Si run() n'a pas encore été appelé.
        
        Example:
            >>> result = runner.run()
            >>> equity = runner.get_equity_curve()
            >>> equity.plot(title='Equity Curve')
        """
        if not hasattr(self.backtest, '_results') or self.backtest._results is None:
            raise RuntimeError(
                "Aucun résultat disponible. Appeler run() d'abord."
            )
        
        equity = self.backtest._results['_equity_curve']['Equity']
        logger.info(f"Récupération equity curve: {len(equity)} points")
        
        return equity
    
    def get_stats_dict(self) -> Dict[str, Any]:
        """
        Retourne stats backtest en dictionnaire (après run()).
        
        Convertit pd.Series en dict pour serialization facile (JSON, etc.).
        
        Returns:
            Dict avec métriques performance.
        
        Example:
            >>> result = runner.run()
            >>> stats = runner.get_stats_dict()
            >>> import json
            >>> print(json.dumps(stats, indent=2))
        """
        if not hasattr(self.backtest, '_results') or self.backtest._results is None:
            raise RuntimeError(
                "Aucun résultat disponible. Appeler run() d'abord."
            )
        
        stats_series = self.backtest._results
        
        # Convertir Series → Dict (skip objets non-serializable)
        stats_dict = {}
        for key, value in stats_series.items():
            if key.startswith('_'):
                continue  # Skip internal attributes
            
            # Convertir types pandas → types Python
            if isinstance(value, (np.integer, np.floating)):
                stats_dict[key] = float(value)
            elif isinstance(value, (pd.Timestamp, pd.DatetimeIndex)):
                stats_dict[key] = str(value)
            elif isinstance(value, (int, float, str, bool, type(None))):
                stats_dict[key] = value
            else:
                stats_dict[key] = str(value)  # Fallback
        
        logger.debug(f"Stats convertis en dict: {len(stats_dict)} clés")
        
        return stats_dict

    # ---------------- IC Reporting Convenience ----------------
    def generate_ic_report(
        self,
        factor_scores: pd.DataFrame,
        forward_returns: pd.DataFrame,
        max_horizon: int = 5,
        out_html_path: Optional[str] = None,
        method: str = "spearman",
    ) -> Dict[str, Any]:
        """
        Génère un rapport IC (cross-section par date) et un tableau IC(h) d'horizon.

        Args:
            factor_scores: DataFrame (dates x actifs) des scores factorielles
            forward_returns: DataFrame (dates x actifs) des rendements futurs alignés
            max_horizon: horizon max pour IC decay
            out_html_path: si fourni, écrit un mini rapport HTML
            method: 'spearman' ou 'pearson'

        Returns:
            Dict avec 'ic_series', 'summary', 'decay', 'html' (optionnel)
        """
        ic_series = compute_cross_sectional_ic(factor_scores, forward_returns, method=method)  # type: ignore[arg-type]
        summary = ic_summary(ic_series)
        decay = compute_ic_decay(factor_scores, forward_returns, max_horizon=max_horizon, method=method)  # type: ignore[arg-type]
        html = generate_ic_report_html(ic_series, decay)
        if out_html_path:
            try:
                with open(out_html_path, "w", encoding="utf-8") as f:
                    f.write(html)
            except Exception:
                pass
        return {"ic_series": ic_series, "summary": summary, "decay": decay, "html": html}

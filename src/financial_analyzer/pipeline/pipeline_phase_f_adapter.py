"""Phase F Pipeline Adapter.

Connecte les modules avancés (fractional differentiation, autocorrelation, microstructure,
feature importance) à la pipeline existante `Pipeline` sans modifier son code.

Usage:
    >>> from financial_analyzer.pipeline.pipeline_phase_f_adapter import PhaseFPipeline
    >>> p = PhaseFPipeline()
    >>> result = p.run('2025-11-19', ['AAPL','MSFT'])
    >>> list(result['steps'].keys())  # inclut 'advanced_features'

Conception:
    - Composition (évite patch massif du fichier pipeline.py existant)
    - Ajout post-run avec recalcul des features avancées sur les données OHLC brutes
    - Sécurité: chaque calcul encapsulé try/except, log + fallback

"""
from __future__ import annotations

from typing import Any, List, Dict
import pandas as pd

from financial_analyzer.pipeline.pipeline import Pipeline
from financial_analyzer.data.market_data import MarketDataFetcher
from financial_analyzer.utils.helpers import get_logger
from financial_analyzer.ml_features_advanced import (
    FractionalDifferentiator,
    AutocorrelationFeatures,
    MicrostructureFeatures,
    FeatureImportanceAnalyzer,
)
from financial_analyzer.backtest.validation import (
    WalkForwardAnalyzer,
    PurgedKFold,
    MetaLabeler,
)
from financial_analyzer.features.technical import TechnicalFeatureEngine
from sklearn.ensemble import RandomForestClassifier
import numpy as np

logger = get_logger(__name__)


class PhaseFPipeline:
    """Adaptateur ajoutant Phase F à la pipeline existante.

    Args:
        lookback_days: Fenêtre historique pour récupération OHLC
        forecast_horizon: Horizon de prédiction (passé au Pipeline interne)
        optimization_method: Méthode optimisation par défaut
    """
    def __init__(
        self,
        lookback_days: int = 120,
        forecast_horizon: int = 5,
        optimization_method: str = 'none',
    ) -> None:
        from financial_analyzer.data.universe import UniverseSelector  # lazy import
        self.universe_selector = UniverseSelector()
        self.market_data_fetcher = MarketDataFetcher()
        self.core = Pipeline(
            universe_selector=self.universe_selector,
            lookback_days=lookback_days,
            forecast_horizon=forecast_horizon,
            optimization_method=optimization_method,
        )
        self.lookback_days = lookback_days

    # ------------------------------------------------------------------
    def run(
        self, 
        run_date: str, 
        universe: List[str], 
        optimization_method: str | None = None,
        start_date: str | None = None
    ) -> Dict[str, Any]:
        """Exécute pipeline core + ajoute features Phase E & F.

        Args:
            run_date: Date fin pour récupération données
            universe: Liste tickers
            optimization_method: Méthode optimisation (optionnel)
            start_date: Date début (optionnel, override lookback_days)

        Returns:
            Dict résultats pipeline augmentés avec advanced_features (Phase F),
            walk_forward_metrics, purged_cv_metrics, meta_labeling_metrics (Phase E).
        """
        base_result = self.core.run(run_date, universe, optimization_method=optimization_method)
        raw_data = self._fetch_raw_data(universe, run_date, start_date)
        
        # Phase F: Advanced features
        advanced = self._compute_advanced_features(raw_data)
        base_result['steps']['advanced_features'] = {
            'count': len(advanced),
            'sample': next(iter(advanced.values())) if advanced else {},
        }
        base_result['steps']['advanced_features_detail'] = advanced
        
        # Phase E: Walk-forward, Purged CV, Meta-labeling
        phase_e_results = self._compute_phase_e_metrics(raw_data, universe)
        base_result['steps']['walk_forward'] = phase_e_results.get('walk_forward', {})
        base_result['steps']['purged_cv'] = phase_e_results.get('purged_cv', {})
        base_result['steps']['meta_labeling'] = phase_e_results.get('meta_labeling', {})
        
        logger.info("Phase E & F features ajoutées au résultat pipeline")
        return base_result

    # ------------------------------------------------------------------
    def _fetch_raw_data(self, universe: List[str], run_date: str, start_date: str | None = None) -> Dict[str, pd.DataFrame]:
        end_dt = pd.Timestamp(run_date)
        if start_date:
            start_dt = pd.Timestamp(start_date)
        else:
            start_dt = end_dt - pd.Timedelta(days=self.lookback_days)
        out: Dict[str, pd.DataFrame] = {}
        for t in universe:
            try:
                df = self.market_data_fetcher.get_historical_data(
                    t, start_date=start_dt.strftime('%Y-%m-%d'), end_date=end_dt.strftime('%Y-%m-%d')
                )
                out[t] = df
            except Exception as e:
                logger.error(f"Raw data fetch failed {t}: {e}")
                out[t] = pd.DataFrame()
        return out

    # ------------------------------------------------------------------
    def _compute_advanced_features(self, raw_data: Dict[str, pd.DataFrame]) -> Dict[str, Dict[str, float]]:
        fdiffer = FractionalDifferentiator()
        acf = AutocorrelationFeatures()
        micro = MicrostructureFeatures()
        results: Dict[str, Dict[str, float]] = {}
        for ticker, df in raw_data.items():
            if df.empty or 'Close' not in df.columns:
                continue
            close = df['Close']
            # Fractional diff
            try:
                if len(close) > 50:
                    frac = fdiffer.transform(close, d=0.4)
                    var_red = float(1 - (frac.var() / close.var())) if close.var() > 0 and pd.notna(frac.var()) else 0.0
                else:
                    var_red = 0.0
            except Exception:
                var_red = 0.0
            # Hurst
            try:
                hurst = float(acf.compute_hurst_exponent(close))
            except Exception:
                hurst = 0.5
            # Microstructure
            try:
                micro_df = df.copy()
                micro_df.columns = micro_df.columns.str.lower()
                spread_series = micro.compute_bid_ask_spread(micro_df, method='roll')
                spread_mean = float(spread_series.mean()) if not spread_series.empty else 0.0
                micro_df['buy_volume'] = micro_df['volume'] * (micro_df['close'] > micro_df['open']).astype(float)
                micro_df['sell_volume'] = micro_df['volume'] - micro_df['buy_volume']
                oflow_mean = float(micro.compute_order_flow_imbalance(micro_df).mean())
            except Exception:
                spread_mean = 0.0
                oflow_mean = 0.0
            # Feature importance (synthetic set)
            try:
                if len(df) > 80:
                    feats = pd.DataFrame({
                        'ret_1d': close.pct_change(),
                        'vol_5d': close.pct_change().rolling(5).std(),
                        'sma_10': close.rolling(10).mean(),
                        'sma_30': close.rolling(30).mean(),
                        'range': (df['High'] - df['Low']) if 'High' in df.columns and 'Low' in df.columns else close,
                    }).dropna()
                    target = (feats['ret_1d'] > 0).astype(int)
                    split = int(len(feats) * 0.7)
                    X_train, X_test = feats.iloc[:split], feats.iloc[split:]
                    y_train, y_test = target.iloc[:split], target.iloc[split:]
                    model = RandomForestClassifier(n_estimators=50, random_state=42, max_depth=4)
                    model.fit(X_train, y_train)
                    fia = FeatureImportanceAnalyzer(model, X_train, y_train, X_test, y_test)
                    mdi = fia.get_mdi_importance()
                    mdi_top = float(mdi.max()) if not mdi.empty else 0.0
                else:
                    mdi_top = 0.0
            except Exception:
                mdi_top = 0.0
            results[ticker] = {
                'fractional_diff_var_reduction': var_red,
                'hurst_exponent': hurst,
                'micro_liquidity_spread': spread_mean,
                'micro_order_flow_mean': oflow_mean,
                'mdi_top_feature_importance': mdi_top,
            }
        return results

    # ------------------------------------------------------------------
    # Phase E Feature Computation
    # ------------------------------------------------------------------
    def _compute_phase_e_metrics(self, raw_data: Dict[str, pd.DataFrame], universe: List[str]) -> Dict[str, Dict[str, Any]]:
        """Compute Phase E metrics: walk-forward, purged CV, meta-labeling.
        
        Returns:
            Dict with keys: walk_forward, purged_cv, meta_labeling
        """
        results: Dict[str, Dict[str, Any]] = {
            'walk_forward': {},
            'purged_cv': {},
            'meta_labeling': {},
        }
        
        # Select first ticker with sufficient data for demo
        selected_ticker = None
        selected_data = None
        for t, df in raw_data.items():
            if not df.empty and len(df) > 100 and 'Close' in df.columns:
                selected_ticker = t
                selected_data = df.copy()
                break
        
        if selected_ticker is None or selected_data is None:
            logger.warning("Pas assez de données pour Phase E metrics")
            return results
        
        # Add basic technical features
        try:
            # Add technical features (SMA, RSI, returns)
            tech = TechnicalFeatureEngine(selected_data)
            selected_data = tech.calculate_all_features()
            # Technical features already include returns - dropna to remove NaN rows
            selected_data = selected_data.dropna()
        except Exception as e:
            logger.error(f"Technical features failed: {e}")
            return results
        
        # Walk-forward analysis
        try:
            if len(selected_data) >= 120:
                wf = WalkForwardAnalyzer(
                    data=selected_data,
                    window_type='rolling',
                    train_size=60,
                    test_size=20,
                    step_size=20
                )
                
                def optimize_func(train_data):
                    return {'sma_fast': 20, 'sma_slow': 50}
                
                def backtest_func(test_data, params):
                    if 'sma_20' not in test_data.columns or 'sma_50' not in test_data.columns:
                        return {'total_return': 0.0, 'sharpe': 0.0}
                    signals = (test_data['sma_20'] > test_data['sma_50']).astype(int)
                    rets = test_data['returns'] * signals.shift(1)
                    total_ret = (1 + rets).prod() - 1
                    sharpe = rets.mean() / rets.std() * np.sqrt(252) if rets.std() > 0 else 0.0
                    return {'total_return': float(total_ret), 'sharpe': float(sharpe)}
                
                wf_results = wf.run(optimize_func, backtest_func)
                results['walk_forward'] = {
                    'ticker': selected_ticker,
                    'overfitting_ratio': float(wf_results.get('overfitting_ratio', 0.0)),
                    'in_sample_sharpe': float(wf_results.get('in_sample', {}).get('avg_return', 0.0)),
                    'out_sample_sharpe': float(wf_results.get('out_of_sample', {}).get('avg_sharpe', 0.0)),
                    'num_windows': wf_results.get('n_splits', 0),
                }
        except Exception as e:
            logger.error(f"Walk-forward failed: {e}", exc_info=True)
        
        # Purged K-Fold CV
        try:
            logger.info(f"Starting Purged CV, selected_data length: {len(selected_data)}")
            if len(selected_data) >= 100:
                X = selected_data[['sma_20', 'sma_50', 'rsi_14']].dropna()
                logger.info(f"Purged CV X shape after dropna: {X.shape}")
                if len(X) >= 50:
                    logger.info("Running PurgedKFold...")
                    cv = PurgedKFold(n_splits=5, pct_embargo=0.01)
                    splits = list(cv.split(X))
                    logger.info(f"PurgedKFold created {len(splits)} splits")
                    results['purged_cv'] = {
                        'ticker': selected_ticker,
                        'n_splits': cv.get_n_splits(),
                        'pct_embargo': float(cv.pct_embargo),
                        'data_size': len(X),
                        'avg_train_size': float(np.mean([len(train) for train, _ in splits])),
                        'avg_test_size': float(np.mean([len(test) for _, test in splits])),
                    }
        except Exception as e:
            logger.error(f"Purged CV failed: {e}", exc_info=True)
        
        # Meta-labeling
        try:
            logger.info(f"Starting Meta-labeling, selected_data length: {len(selected_data)}")
            if len(selected_data) >= 100:
                X = selected_data[['sma_20', 'sma_50', 'rsi_14']].dropna()
                logger.info(f"Meta-labeling X shape after dropna: {X.shape}")
                returns = selected_data['returns'].loc[X.index]
                signals = ((selected_data['sma_20'] > selected_data['sma_50']).astype(int) * 2 - 1).loc[X.index]
            
                if len(X) >= 80:
                    split_idx = int(len(X) * 0.7)
                    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
                    returns_train, returns_test = returns.iloc[:split_idx], returns.iloc[split_idx:]
                    signals_train, signals_test = signals.iloc[:split_idx], signals.iloc[split_idx:]
                
                    ml = MetaLabeler()
                    ml.fit(X_train, returns_train, signals_train, horizon=5)
                    metrics = ml.evaluate(X_test, returns_test, signals_test, horizon=5)
                
                    results['meta_labeling'] = {
                        'ticker': selected_ticker,
                        'accuracy': float(metrics.get('accuracy', 0.0)),
                        'precision': float(metrics.get('precision', 0.0)),
                        'recall': float(metrics.get('recall', 0.0)),
                        'f1': float(metrics.get('f1', 0.0)),
                        'train_size': len(X_train),
                        'test_size': len(X_test),
                    }
        except Exception as e:
            logger.error(f"Meta-labeling failed: {e}", exc_info=True)
        
        return results

__all__ = ["PhaseFPipeline"]

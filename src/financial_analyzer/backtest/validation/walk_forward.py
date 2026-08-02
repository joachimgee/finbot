"""
Walk-Forward Analysis Module.

Analyse walk-forward pour backtesting robuste avec :
- Rolling windows (fenêtre fixe qui avance)
- Expanding windows (fenêtre qui grandit)
- Out-of-sample testing
- Rebalancing automatique
- Drift detection

Based on : Prado, M. L. de. (2018). Advances in Financial Machine Learning.
"""

from typing import Dict, List, Optional, Tuple, Callable, Any
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import warnings

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class WalkForwardAnalyzer:
    """
    Analyseur walk-forward pour backtesting out-of-sample robuste.
    
    Le walk-forward divise les données en fenêtres train/test successives,
    optimise la stratégie sur train, et teste sur test (out-of-sample).
    
    Attributes:
        data: DataFrame avec OHLCV ou features
        window_type: 'rolling' ou 'expanding'
        train_size: Taille fenêtre train (jours ou %)
        test_size: Taille fenêtre test (jours ou %)
        step_size: Pas d'avancement (jours)
    
    Example:
        >>> analyzer = WalkForwardAnalyzer(
        ...     data=prices_df,
        ...     window_type='rolling',
        ...     train_size=252,
        ...     test_size=63,
        ...     step_size=21
        ... )
        >>> results = analyzer.run(optimize_func, backtest_func)
        >>> print(results['out_of_sample_sharpe'])
    """
    
    def __init__(
        self,
        data: pd.DataFrame,
        window_type: str = 'rolling',
        train_size: int = 252,
        test_size: int = 63,
        step_size: int = 21,
        min_train_size: Optional[int] = None
    ):
        """
        Initialise le walk-forward analyzer.
        
        Args:
            data: DataFrame avec index temporel
            window_type: 'rolling' (fixed window) ou 'expanding' (growing window)
            train_size: Taille train window (jours)
            test_size: Taille test window (jours)
            step_size: Avancement entre windows (jours)
            min_train_size: Taille min train pour expanding (si None, = train_size)
        
        Raises:
            ValueError: Si window_type invalide ou data trop petite
        """
        if window_type not in ['rolling', 'expanding']:
            raise ValueError(f"window_type must be 'rolling' or 'expanding', got {window_type}")
        
        if len(data) < train_size + test_size:
            raise ValueError(f"Data too small: {len(data)} < train({train_size}) + test({test_size})")
        
        self.data = data.copy()
        self.window_type = window_type
        self.train_size = train_size
        self.test_size = test_size
        self.step_size = step_size
        self.min_train_size = min_train_size or train_size
        
        # Générer splits
        self.splits = self._generate_splits()
        
        logger.info(f"WalkForwardAnalyzer initialized: {window_type}, {len(self.splits)} splits")
    
    def _generate_splits(self) -> List[Dict[str, Any]]:
        """
        Génère les splits train/test.
        
        Returns:
            Liste de dicts avec indices train/test
        """
        splits = []
        n = len(self.data)
        
        if self.window_type == 'rolling':
            # Rolling window : fenêtre fixe qui avance
            start_idx = 0
            
            while start_idx + self.train_size + self.test_size <= n:
                train_start = start_idx
                train_end = start_idx + self.train_size
                test_start = train_end
                test_end = test_start + self.test_size
                
                splits.append({
                    'train_start': train_start,
                    'train_end': train_end,
                    'test_start': test_start,
                    'test_end': test_end,
                    'train_dates': (self.data.index[train_start], self.data.index[train_end - 1]),
                    'test_dates': (self.data.index[test_start], self.data.index[test_end - 1])
                })
                
                start_idx += self.step_size
        
        else:  # expanding
            # Expanding window : fenêtre qui grandit
            train_start = 0
            test_start = self.min_train_size
            
            while test_start + self.test_size <= n:
                test_end = test_start + self.test_size
                
                splits.append({
                    'train_start': train_start,
                    'train_end': test_start,
                    'test_start': test_start,
                    'test_end': test_end,
                    'train_dates': (self.data.index[train_start], self.data.index[test_start - 1]),
                    'test_dates': (self.data.index[test_start], self.data.index[test_end - 1])
                })
                
                test_start += self.step_size
        
        logger.debug(f"Generated {len(splits)} walk-forward splits")
        return splits
    
    def get_split_data(self, split_idx: int) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Récupère données train/test pour un split.
        
        Args:
            split_idx: Index du split
        
        Returns:
            (train_data, test_data)
        """
        if split_idx < 0 or split_idx >= len(self.splits):
            raise ValueError(f"split_idx {split_idx} out of range [0, {len(self.splits)})")
        
        split = self.splits[split_idx]
        train_data = self.data.iloc[split['train_start']:split['train_end']].copy()
        test_data = self.data.iloc[split['test_start']:split['test_end']].copy()
        
        return train_data, test_data
    
    def run(
        self,
        optimize_func: Callable[[pd.DataFrame], Dict],
        backtest_func: Callable[[pd.DataFrame, Dict], Dict],
        reoptimize_every: int = 1,
        save_details: bool = True
    ) -> Dict:
        """
        Exécute l'analyse walk-forward complète.
        
        Args:
            optimize_func: Fonction d'optimisation (train_data) -> params
            backtest_func: Fonction de backtest (test_data, params) -> metrics
            reoptimize_every: Réoptimiser tous les N splits (1 = toujours)
            save_details: Sauvegarder détails par split
        
        Returns:
            Dict avec résultats agrégés et détails
        
        Example:
            >>> def optimize(train_data):
            ...     # Optimiser paramètres
            ...     return {'sma_fast': 20, 'sma_slow': 50}
            >>> 
            >>> def backtest(test_data, params):
            ...     # Backtester avec params
            ...     return {'sharpe': 1.5, 'total_return': 0.15}
            >>> 
            >>> results = analyzer.run(optimize, backtest)
        """
        results = {
            'n_splits': len(self.splits),
            'window_type': self.window_type,
            'splits_details': [] if save_details else None
        }
        
        # Métriques agrégées
        in_sample_returns = []
        out_sample_returns = []
        out_sample_sharpes = []
        optimized_params = []
        
        current_params = None
        
        for i, split in enumerate(self.splits):
            logger.info(f"Processing split {i+1}/{len(self.splits)}")
            
            train_data, test_data = self.get_split_data(i)
            
            # Optimiser si nécessaire
            if i % reoptimize_every == 0:
                try:
                    current_params = optimize_func(train_data)
                    optimized_params.append(current_params)
                    logger.debug(f"Split {i}: Optimized params = {current_params}")
                except Exception as e:
                    logger.error(f"Optimization failed on split {i}: {e}")
                    current_params = optimized_params[-1] if optimized_params else {}
            
            # Backtest out-of-sample
            try:
                test_results = backtest_func(test_data, current_params)
                
                out_sample_returns.append(test_results.get('total_return', 0.0))
                out_sample_sharpes.append(test_results.get('sharpe', 0.0))
                
                # Backtest in-sample (optionnel, pour comparaison)
                train_results = backtest_func(train_data, current_params)
                in_sample_returns.append(train_results.get('total_return', 0.0))
                
                if save_details:
                    results['splits_details'].append({
                        'split_idx': i,
                        'train_dates': split['train_dates'],
                        'test_dates': split['test_dates'],
                        'params': current_params,
                        'in_sample': train_results,
                        'out_sample': test_results
                    })
                
            except Exception as e:
                logger.error(f"Backtest failed on split {i}: {e}")
                continue
        
        # Agrégation finale
        results['in_sample'] = {
            'avg_return': np.mean(in_sample_returns) if in_sample_returns else 0.0,
            'total_return': np.sum(in_sample_returns) if in_sample_returns else 0.0,
            'std_return': np.std(in_sample_returns) if in_sample_returns else 0.0
        }
        
        results['out_of_sample'] = {
            'avg_return': np.mean(out_sample_returns) if out_sample_returns else 0.0,
            'total_return': np.sum(out_sample_returns) if out_sample_returns else 0.0,
            'std_return': np.std(out_sample_returns) if out_sample_returns else 0.0,
            'avg_sharpe': np.mean(out_sample_sharpes) if out_sample_sharpes else 0.0,
            'std_sharpe': np.std(out_sample_sharpes) if out_sample_sharpes else 0.0,
            'positive_periods': sum(1 for r in out_sample_returns if r > 0),
            'negative_periods': sum(1 for r in out_sample_returns if r < 0)
        }
        
        # Overfitting metric (déterioratino IS -> OOS)
        if results['in_sample']['avg_return'] > 0:
            results['overfitting_ratio'] = (
                results['out_of_sample']['avg_return'] / results['in_sample']['avg_return']
            )
        else:
            results['overfitting_ratio'] = 0.0
        
        # Stability (variance entre splits)
        results['stability'] = {
            'return_std': results['out_of_sample']['std_return'],
            'sharpe_std': results['out_of_sample']['std_sharpe'],
            'win_rate': results['out_of_sample']['positive_periods'] / len(self.splits) if self.splits else 0.0
        }
        
        logger.info(f"Walk-forward complete: OOS return = {results['out_of_sample']['avg_return']:.2%}")
        
        return results
    
    def analyze_drift(self, metric_key: str = 'sharpe') -> Dict:
        """
        Analyse la dérive temporelle de performance.
        
        Args:
            metric_key: Métrique à analyser ('sharpe', 'total_return', etc.)
        
        Returns:
            Dict avec statistiques de drift
        """
        if not hasattr(self, '_results') or self._results is None:
            raise ValueError("Run walk-forward first with save_details=True")
        
        if not self._results.get('splits_details'):
            raise ValueError("No details available, run with save_details=True")
        
        # Extraire série temporelle de la métrique
        values = []
        dates = []
        
        for detail in self._results['splits_details']:
            oos = detail['out_sample']
            if metric_key in oos:
                values.append(oos[metric_key])
                dates.append(detail['test_dates'][0])
        
        if len(values) < 3:
            logger.warning("Not enough data points for drift analysis")
            return {'error': 'Insufficient data'}
        
        # Calculer trend
        from scipy import stats as scipy_stats
        x = np.arange(len(values))
        slope, intercept, r_value, p_value, std_err = scipy_stats.linregress(x, values)
        
        drift = {
            'metric': metric_key,
            'n_periods': len(values),
            'mean': float(np.mean(values)),
            'std': float(np.std(values)),
            'trend_slope': float(slope),
            'trend_pvalue': float(p_value),
            'r_squared': float(r_value ** 2),
            'is_deteriorating': slope < 0 and p_value < 0.05,
            'values': values,
            'dates': dates
        }
        
        logger.info(f"Drift analysis: slope={slope:.4f}, p={p_value:.4f}")
        
        return drift
    
    def get_summary(self) -> pd.DataFrame:
        """
        Résumé des splits en DataFrame.
        
        Returns:
            DataFrame avec stats par split
        """
        if not hasattr(self, '_results') or not self._results or not self._results.get('splits_details'):
            # Retourner juste info sur splits
            summary_data = []
            for i, split in enumerate(self.splits):
                summary_data.append({
                    'split': i,
                    'train_start': split['train_dates'][0],
                    'train_end': split['train_dates'][1],
                    'test_start': split['test_dates'][0],
                    'test_end': split['test_dates'][1],
                    'train_size': split['train_end'] - split['train_start'],
                    'test_size': split['test_end'] - split['test_start']
                })
            return pd.DataFrame(summary_data)
        
        # Avec résultats
        summary_data = []
        for detail in self._results['splits_details']:
            summary_data.append({
                'split': detail['split_idx'],
                'test_start': detail['test_dates'][0],
                'test_end': detail['test_dates'][1],
                'in_sample_return': detail['in_sample'].get('total_return', np.nan),
                'out_sample_return': detail['out_sample'].get('total_return', np.nan),
                'out_sample_sharpe': detail['out_sample'].get('sharpe', np.nan),
                'params': str(detail['params'])
            })
        
        return pd.DataFrame(summary_data)


def walk_forward_optimize(
    data: pd.DataFrame,
    optimize_func: Callable,
    backtest_func: Callable,
    window_type: str = 'rolling',
    train_size: int = 252,
    test_size: int = 63,
    step_size: int = 21,
    **kwargs
) -> Dict:
    """
    Fonction convenience pour walk-forward optimization.
    
    Args:
        data: DataFrame avec données
        optimize_func: Fonction d'optimisation
        backtest_func: Fonction de backtest
        window_type: 'rolling' ou 'expanding'
        train_size: Taille train window
        test_size: Taille test window
        step_size: Pas d'avancement
        **kwargs: Arguments additionnels pour WalkForwardAnalyzer.run()
    
    Returns:
        Dict avec résultats walk-forward
    
    Example:
        >>> results = walk_forward_optimize(
        ...     data=prices_df,
        ...     optimize_func=my_optimizer,
        ...     backtest_func=my_backtester,
        ...     window_type='rolling'
        ... )
    """
    analyzer = WalkForwardAnalyzer(
        data=data,
        window_type=window_type,
        train_size=train_size,
        test_size=test_size,
        step_size=step_size
    )
    
    results = analyzer.run(
        optimize_func=optimize_func,
        backtest_func=backtest_func,
        **kwargs
    )
    
    # Sauvegarder résultats dans analyzer pour drift analysis
    analyzer._results = results
    
    return results

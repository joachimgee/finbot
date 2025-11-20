"""
Drawdown Analysis Module.

Analyse approfondie des drawdowns : profondeur, durée, récupération, distribution.
Complète les métriques basiques de max_drawdown présentes dans backtest/metrics.py.

Fonctionnalités :
- Conditional Drawdown at Risk (CDaR)
- Underwater periods analysis
- Recovery time statistics
- Drawdown duration distribution
- Average/Maximum drawdown
- Drawdown frequency
- Pain index
"""

from typing import Dict, List, Tuple, Optional
import numpy as np
import pandas as pd
from datetime import timedelta

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class DrawdownAnalyzer:
    """
    Analyseur de drawdowns avec métriques avancées.
    
    Attributes:
        equity_curve: Série de valeurs d'equity
        returns: Série de rendements (optionnel)
    
    Example:
        >>> analyzer = DrawdownAnalyzer(equity_curve)
        >>> cdar = analyzer.calculate_cdar(confidence=0.95)
        >>> periods = analyzer.get_underwater_periods()
        >>> stats = analyzer.get_drawdown_statistics()
    """
    
    def __init__(
        self,
        equity_curve: pd.Series,
        returns: Optional[pd.Series] = None
    ):
        """
        Initialise l'analyseur de drawdowns.
        
        Args:
            equity_curve: Série de valeurs d'equity indexée par dates
            returns: Série de rendements (calculés si non fournis)
        
        Raises:
            ValueError: Si equity_curve est vide
        """
        if equity_curve.empty:
            raise ValueError("equity_curve cannot be empty")
        
        self.equity_curve = equity_curve.copy()
        
        if returns is not None:
            self.returns = returns.copy()
        else:
            self.returns = equity_curve.pct_change().fillna(0.0)
        
        # Pre-calcul des drawdowns pour optimisation
        self._drawdowns = self._calculate_drawdowns()
        self._underwater_mask = self._drawdowns < 0
        
        logger.debug(f"DrawdownAnalyzer initialized with {len(equity_curve)} periods")
    
    def _calculate_drawdowns(self) -> pd.Series:
        """
        Calcule la série complète de drawdowns (% depuis peak).
        
        Returns:
            Series de drawdowns (valeurs négatives ou 0)
        """
        running_max = self.equity_curve.expanding().max()
        drawdowns = (self.equity_curve - running_max) / running_max
        return drawdowns
    
    def calculate_max_drawdown(self) -> Dict[str, float]:
        """
        Calcule le max drawdown avec dates et durée.
        
        Returns:
            Dict avec:
            - max_drawdown: Profondeur max (valeur positive)
            - max_drawdown_pct: En pourcentage
            - start_date: Date du peak avant DD
            - valley_date: Date du creux
            - end_date: Date de récupération (ou None si pas récupéré)
            - duration_days: Durée totale en jours
            - recovery_days: Durée récupération (ou None)
        
        Example:
            >>> max_dd = analyzer.calculate_max_drawdown()
            >>> print(f"Max DD: {max_dd['max_drawdown_pct']:.2%}")
            >>> print(f"Duration: {max_dd['duration_days']} days")
        """
        dd = self._drawdowns
        
        # Trouver le max drawdown
        max_dd_idx = dd.idxmin()
        max_dd_value = abs(dd.min())
        
        # Trouver le peak avant ce drawdown
        dd_before = dd[:max_dd_idx]
        peak_idx = dd_before[dd_before == 0].index[-1] if (dd_before == 0).any() else dd.index[0]
        
        # Trouver la récupération (si existe)
        dd_after = dd[max_dd_idx:]
        recovery_mask = dd_after == 0
        end_idx = recovery_mask[recovery_mask].index[0] if recovery_mask.any() else None
        
        # Calcul durées
        if isinstance(dd.index, pd.DatetimeIndex):
            duration_days = (max_dd_idx - peak_idx).days if hasattr(peak_idx, 'days') else len(dd[peak_idx:max_dd_idx])
            recovery_days = (end_idx - max_dd_idx).days if end_idx and hasattr(end_idx, 'days') else None
        else:
            duration_days = len(dd[peak_idx:max_dd_idx])
            recovery_days = len(dd[max_dd_idx:end_idx]) if end_idx else None
        
        result = {
            'max_drawdown': float(max_dd_value),
            'max_drawdown_pct': float(max_dd_value * 100),
            'start_date': peak_idx,
            'valley_date': max_dd_idx,
            'end_date': end_idx,
            'duration_days': int(duration_days) if duration_days else 0,
            'recovery_days': int(recovery_days) if recovery_days else None
        }
        
        logger.debug(f"Max drawdown: {result['max_drawdown_pct']:.2f}%, duration: {result['duration_days']} days")
        
        return result
    
    def calculate_cdar(
        self,
        confidence: float = 0.95
    ) -> float:
        """
        Conditional Drawdown at Risk (CDaR).
        
        CDaR est la moyenne des α% pires drawdowns.
        Mesure la sévérité moyenne des pires pertes.
        
        Formule (Chekhlov et al. 2005):
            CDaR_α = E[DD | DD > DD_α]
        
        Args:
            confidence: Niveau de confiance (0.95 = top 5% pires DD)
        
        Returns:
            CDaR (valeur positive)
        
        Example:
            >>> cdar_95 = analyzer.calculate_cdar(0.95)
            >>> print(f"Average of worst 5% DDs: {cdar_95:.2%}")
        """
        dd_abs = self._drawdowns.abs()
        
        if dd_abs.empty or dd_abs.max() == 0:
            return 0.0
        
        # Threshold pour le top (1-confidence)% pires DD
        threshold = np.percentile(dd_abs, confidence * 100)
        
        # Moyenne des DD au-delà du threshold
        worst_dds = dd_abs[dd_abs >= threshold]
        
        if worst_dds.empty:
            cdar = float(dd_abs.max())
        else:
            cdar = float(worst_dds.mean())
        
        logger.debug(f"CDaR {confidence*100:.0f}% calculated: {cdar:.6f}")
        
        return cdar
    
    def calculate_average_drawdown(self) -> float:
        """
        Average Drawdown - Moyenne de tous les drawdowns.
        
        Returns:
            Average DD (valeur positive)
        
        Example:
            >>> avg_dd = analyzer.calculate_average_drawdown()
        """
        dd_abs = self._drawdowns.abs()
        avg_dd = float(dd_abs.mean())
        
        logger.debug(f"Average drawdown: {avg_dd:.6f}")
        return avg_dd
    
    def get_underwater_periods(self) -> pd.DataFrame:
        """
        Liste toutes les périodes "underwater" (en drawdown).
        
        Returns:
            DataFrame avec colonnes:
            - start: Date début DD
            - valley: Date du creux
            - end: Date récupération (ou None)
            - depth: Profondeur max du DD (%)
            - duration: Durée totale (jours)
            - recovery: Durée récupération (jours ou None)
            - recovered: Bool (True si récupéré)
        
        Example:
            >>> periods = analyzer.get_underwater_periods()
            >>> print(f"{len(periods)} underwater periods detected")
            >>> print(periods.nlargest(5, 'depth'))  # Top 5 worst DDs
        """
        dd = self._drawdowns
        
        # Détecter les transitions underwater <-> surface
        underwater = self._underwater_mask
        transitions = underwater.astype(int).diff()
        
        # Starts = passage 0 → 1 (entrée en DD)
        starts = transitions[transitions == 1].index.tolist()
        
        # Ends = passage 1 → 0 (sortie de DD)
        ends = transitions[transitions == -1].index.tolist()
        
        # Gérer cas limites (début/fin de série)
        if underwater.iloc[0]:
            starts.insert(0, dd.index[0])
        if underwater.iloc[-1]:
            ends.append(None)
        
        # Construire DataFrame
        periods = []
        for i, start in enumerate(starts):
            end = ends[i] if i < len(ends) else None
            
            # Période DD
            if end is not None:
                dd_period = dd[start:end]
            else:
                dd_period = dd[start:]
            
            # Trouver valley (max DD)
            valley = dd_period.idxmin()
            depth = abs(dd_period.min())
            
            # Durées
            if isinstance(dd.index, pd.DatetimeIndex) and start and valley:
                duration = (valley - start).days if hasattr(start, 'days') else len(dd[start:valley])
                recovery = (end - valley).days if end and hasattr(end, 'days') else None
            else:
                duration = len(dd[start:valley]) if start and valley else 0
                recovery = len(dd[valley:end]) if end else None
            
            periods.append({
                'start': start,
                'valley': valley,
                'end': end,
                'depth': float(depth),
                'depth_pct': float(depth * 100),
                'duration': int(duration) if duration else 0,
                'recovery': int(recovery) if recovery else None,
                'recovered': end is not None
            })
        
        df = pd.DataFrame(periods)
        
        logger.info(f"Detected {len(df)} underwater periods")
        
        return df
    
    def calculate_pain_index(self) -> float:
        """
        Pain Index - Moyenne de la "douleur" ressentie (DD x durée).
        
        Mesure l'impact cumulé des drawdowns sur le temps.
        Plus élevé = plus de temps passé en drawdown profond.
        
        Formule:
            Pain Index = mean(|DD_t|) pour tous les t
        
        Returns:
            Pain Index (valeur positive)
        
        Example:
            >>> pain = analyzer.calculate_pain_index()
            >>> print(f"Pain Index: {pain:.4f}")
        """
        pain = float(self._drawdowns.abs().mean())
        
        logger.debug(f"Pain Index calculated: {pain:.6f}")
        return pain
    
    def get_recovery_statistics(self) -> Dict[str, float]:
        """
        Statistiques sur les temps de récupération.
        
        Returns:
            Dict avec:
            - avg_recovery_days: Moyenne des durées de récupération
            - max_recovery_days: Plus longue récupération
            - min_recovery_days: Plus courte récupération
            - recovery_rate: % de DDs récupérés
            - total_underwater_periods: Nombre total de périodes DD
        
        Example:
            >>> stats = analyzer.get_recovery_statistics()
            >>> print(f"Average recovery: {stats['avg_recovery_days']} days")
        """
        periods = self.get_underwater_periods()
        
        if periods.empty:
            return {
                'avg_recovery_days': 0.0,
                'max_recovery_days': 0.0,
                'min_recovery_days': 0.0,
                'recovery_rate': 1.0,
                'total_underwater_periods': 0
            }
        
        recovered = periods[periods['recovered'] == True]
        
        if recovered.empty:
            recovery_rate = 0.0
            avg_recovery = max_recovery = min_recovery = None
        else:
            recovery_rate = len(recovered) / len(periods)
            avg_recovery = float(recovered['recovery'].mean())
            max_recovery = float(recovered['recovery'].max())
            min_recovery = float(recovered['recovery'].min())
        
        stats = {
            'avg_recovery_days': avg_recovery if avg_recovery is not None else 0.0,
            'max_recovery_days': max_recovery if max_recovery is not None else 0.0,
            'min_recovery_days': min_recovery if min_recovery is not None else 0.0,
            'recovery_rate': float(recovery_rate),
            'total_underwater_periods': len(periods)
        }
        
        logger.debug(f"Recovery stats: {stats['total_underwater_periods']} periods, {stats['recovery_rate']*100:.1f}% recovered")
        
        return stats
    
    def get_drawdown_distribution(
        self,
        bins: int = 10
    ) -> pd.DataFrame:
        """
        Distribution des drawdowns par profondeur (histogramme).
        
        Args:
            bins: Nombre de bins pour l'histogramme
        
        Returns:
            DataFrame avec colonnes:
            - range: Intervalle de DD (ex: "0-5%")
            - count: Nombre de périodes dans cet intervalle
            - frequency: % du total
        
        Example:
            >>> dist = analyzer.get_drawdown_distribution(bins=5)
            >>> print(dist)
        """
        periods = self.get_underwater_periods()
        
        if periods.empty:
            return pd.DataFrame(columns=['range', 'count', 'frequency'])
        
        depths = periods['depth_pct'].values
        
        # Créer bins
        bin_edges = np.linspace(0, depths.max(), bins + 1)
        
        # Histogramme
        counts, edges = np.histogram(depths, bins=bin_edges)
        
        # Créer labels
        labels = [f"{edges[i]:.1f}-{edges[i+1]:.1f}%" for i in range(len(edges)-1)]
        
        df = pd.DataFrame({
            'range': labels,
            'count': counts,
            'frequency': counts / counts.sum() * 100
        })
        
        logger.debug(f"Drawdown distribution calculated with {bins} bins")
        
        return df
    
    def get_drawdown_statistics(self) -> Dict[str, float]:
        """
        Toutes les statistiques de drawdown en un seul appel.
        
        Returns:
            Dict avec toutes les métriques clés
        
        Example:
            >>> stats = analyzer.get_drawdown_statistics()
            >>> for key, value in stats.items():
            ...     print(f"{key}: {value}")
        """
        max_dd = self.calculate_max_drawdown()
        recovery = self.get_recovery_statistics()
        
        stats = {
            'max_drawdown': max_dd['max_drawdown'],
            'max_drawdown_pct': max_dd['max_drawdown_pct'],
            'max_drawdown_duration': max_dd['duration_days'],
            'avg_drawdown': self.calculate_average_drawdown(),
            'cdar_95': self.calculate_cdar(0.95),
            'cdar_99': self.calculate_cdar(0.99),
            'pain_index': self.calculate_pain_index(),
            'avg_recovery_days': recovery['avg_recovery_days'],
            'max_recovery_days': recovery['max_recovery_days'],
            'recovery_rate': recovery['recovery_rate'],
            'total_underwater_periods': recovery['total_underwater_periods']
        }
        
        logger.info(f"Calculated {len(stats)} drawdown statistics")
        
        return stats


def compare_drawdown_profiles(
    equity_a: pd.Series,
    equity_b: pd.Series,
    labels: tuple = ('Strategy A', 'Strategy B')
) -> pd.DataFrame:
    """
    Compare les profils de drawdown de deux stratégies.
    
    Args:
        equity_a: Equity curve stratégie A
        equity_b: Equity curve stratégie B
        labels: Noms des stratégies
    
    Returns:
        DataFrame comparatif
    
    Example:
        >>> comparison = compare_drawdown_profiles(equity1, equity2)
        >>> print(comparison)
    """
    analyzer_a = DrawdownAnalyzer(equity_a)
    analyzer_b = DrawdownAnalyzer(equity_b)
    
    stats_a = analyzer_a.get_drawdown_statistics()
    stats_b = analyzer_b.get_drawdown_statistics()
    
    df = pd.DataFrame({
        labels[0]: stats_a,
        labels[1]: stats_b
    })
    
    # Différence
    df['Difference'] = df[labels[1]] - df[labels[0]]
    
    logger.info(f"Drawdown profile comparison completed")
    
    return df

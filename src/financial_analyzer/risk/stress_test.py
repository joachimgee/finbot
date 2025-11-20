"""
Stress Testing Module.

Stress testing de portefeuilles avec scénarios historiques, Monte Carlo, 
et analyses de corrélation breakdown.

Fonctionnalités :
- Historical stress scenarios (2008, 2020, etc.)
- Monte Carlo simulation
- Correlation breakdown detection
- Extreme scenario analysis
- Value at Risk stress testing
- Tail risk scenarios
"""

from typing import Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from scipy import stats
from datetime import datetime, timedelta

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class StressTester:
    """
    Stress tester pour analyse de scénarios extrêmes.
    
    Attributes:
        returns: DataFrame de rendements (colonnes = assets)
        weights: Series de poids de portfolio (optionnel)
    
    Example:
        >>> tester = StressTester(returns_df, weights)
        >>> crisis_results = tester.apply_historical_crisis('2008_financial')
        >>> mc_results = tester.monte_carlo_stress(n_scenarios=10000)
    """
    
    # Scénarios historiques prédéfinis
    HISTORICAL_SCENARIOS = {
        '2008_financial': {
            'name': '2008 Financial Crisis',
            'start': '2008-09-15',
            'end': '2009-03-09',
            'description': 'Lehman collapse, credit crisis'
        },
        '2020_covid': {
            'name': 'COVID-19 Crash',
            'start': '2020-02-19',
            'end': '2020-03-23',
            'description': 'Pandemic market crash'
        },
        '2000_dotcom': {
            'name': 'Dot-com Bubble',
            'start': '2000-03-10',
            'end': '2002-10-09',
            'description': 'Tech bubble burst'
        },
        '1987_crash': {
            'name': 'Black Monday 1987',
            'start': '1987-10-14',
            'end': '1987-10-19',
            'description': 'Single day 22% crash'
        },
        '2011_europe': {
            'name': 'European Debt Crisis',
            'start': '2011-07-01',
            'end': '2012-06-01',
            'description': 'Sovereign debt crisis'
        }
    }
    
    def __init__(
        self,
        returns: pd.DataFrame,
        weights: Optional[pd.Series] = None
    ):
        """
        Initialise le stress tester.
        
        Args:
            returns: DataFrame de rendements (colonnes = assets, index = dates)
            weights: Poids de portfolio (si None, equal weight)
        
        Raises:
            ValueError: Si returns est vide
        """
        if returns.empty:
            raise ValueError("returns DataFrame cannot be empty")
        
        self.returns = returns.copy()
        self.assets = list(returns.columns)
        
        if weights is None:
            # Equal weight par défaut
            self.weights = pd.Series(1.0 / len(self.assets), index=self.assets)
        else:
            self.weights = weights.reindex(self.assets).fillna(0.0)
            # Normaliser
            if self.weights.sum() > 0:
                self.weights = self.weights / self.weights.sum()
        
        # Calculer returns de portfolio
        self.portfolio_returns = (self.returns * self.weights).sum(axis=1)
        
        # Statistiques de base
        self.mean_returns = self.returns.mean()
        self.cov_matrix = self.returns.cov()
        
        logger.debug(f"StressTester initialized with {len(self.assets)} assets, {len(returns)} periods")
    
    def apply_shock(
        self,
        shock_magnitude: Union[float, Dict[str, float]],
        shock_type: str = 'absolute'
    ) -> Dict[str, float]:
        """
        Applique un choc aux rendements et calcule l'impact.
        
        Args:
            shock_magnitude: Magnitude du choc (float = uniforme, Dict = par asset)
            shock_type: 'absolute' (ex: -10%) ou 'relative' (ex: -50% de la moyenne)
        
        Returns:
            Dict avec:
            - portfolio_loss: Perte totale du portfolio
            - asset_losses: Pertes par asset
            - var_95_stressed: VaR après choc
            - cvar_95_stressed: CVaR après choc
        
        Example:
            >>> # Choc uniforme -20%
            >>> result = tester.apply_shock(-0.20, 'absolute')
            >>> # Choc différencié
            >>> result = tester.apply_shock({'AAPL': -0.25, 'MSFT': -0.15})
        """
        if isinstance(shock_magnitude, (int, float)):
            # Choc uniforme
            shocks = pd.Series(shock_magnitude, index=self.assets)
        else:
            # Choc différencié
            shocks = pd.Series(shock_magnitude).reindex(self.assets).fillna(0.0)
        
        if shock_type == 'relative':
            # Choc relatif à la moyenne
            shocks = shocks * self.mean_returns
        
        # Appliquer choc
        shocked_returns = self.mean_returns + shocks
        portfolio_loss = float((shocked_returns * self.weights).sum())
        
        # Simuler returns stressés (ajouter choc à historique)
        stressed_returns = self.returns + shocks
        stressed_portfolio = (stressed_returns * self.weights).sum(axis=1)
        
        # Recalculer VaR/CVaR
        var_95 = float(np.percentile(-stressed_portfolio, 95))
        losses = -stressed_portfolio.values
        tail = losses[losses >= var_95]
        cvar_95 = float(tail.mean()) if len(tail) > 0 else var_95
        
        result = {
            'portfolio_loss': portfolio_loss,
            'asset_losses': shocked_returns.to_dict(),
            'var_95_stressed': var_95,
            'cvar_95_stressed': cvar_95,
            'worst_asset': shocked_returns.idxmin(),
            'worst_asset_loss': float(shocked_returns.min())
        }
        
        logger.info(f"Shock applied: portfolio loss {portfolio_loss:.2%}")
        
        return result
    
    def apply_historical_crisis(
        self,
        crisis_name: str,
        historical_returns: Optional[pd.DataFrame] = None
    ) -> Dict:
        """
        Applique un scénario de crise historique.
        
        Args:
            crisis_name: Nom du scénario (voir HISTORICAL_SCENARIOS)
            historical_returns: Returns historiques complets (si disponibles)
        
        Returns:
            Dict avec statistiques de la crise appliquée
        
        Example:
            >>> result = tester.apply_historical_crisis('2008_financial')
            >>> print(f"Portfolio loss: {result['total_loss']:.2%}")
        """
        if crisis_name not in self.HISTORICAL_SCENARIOS:
            logger.warning(f"Unknown crisis: {crisis_name}. Available: {list(self.HISTORICAL_SCENARIOS.keys())}")
            return {'error': f'Unknown crisis: {crisis_name}'}
        
        scenario = self.HISTORICAL_SCENARIOS[crisis_name]
        
        logger.info(f"Applying crisis scenario: {scenario['name']}")
        
        # Si returns historiques fournis, extraire période de crise
        if historical_returns is not None and isinstance(historical_returns.index, pd.DatetimeIndex):
            try:
                crisis_returns = historical_returns.loc[scenario['start']:scenario['end']]
                
                if not crisis_returns.empty:
                    # Aligner avec nos assets
                    crisis_returns = crisis_returns[self.assets]
                    
                    # Appliquer à notre portfolio
                    crisis_portfolio_returns = (crisis_returns * self.weights).sum(axis=1)
                    
                    cum = (1.0 + crisis_portfolio_returns).cumprod()
                    total_loss = float(cum.iloc[-1] - 1.0)
                    max_drawdown = float((cum / cum.cummax() - 1.0).min())
                    
                    return {
                        'scenario': scenario['name'],
                        'description': scenario['description'],
                        'start_date': scenario['start'],
                        'end_date': scenario['end'],
                        'total_loss': total_loss,
                        'max_drawdown': abs(max_drawdown),
                        'n_periods': len(crisis_returns),
                        'worst_day': float(crisis_portfolio_returns.min()),
                        'worst_day_date': crisis_portfolio_returns.idxmin()
                    }
            except Exception as e:
                logger.error(f"Error extracting crisis period: {e}")
        
        # Fallback: simuler avec paramètres typiques de la crise
        # (basé sur statistiques historiques moyennes)
        crisis_params = {
            '2008_financial': {'mean': -0.003, 'std': 0.035, 'days': 120},
            '2020_covid': {'mean': -0.008, 'std': 0.045, 'days': 23},
            '2000_dotcom': {'mean': -0.002, 'std': 0.025, 'days': 580},
            '1987_crash': {'mean': -0.050, 'std': 0.060, 'days': 3},
            '2011_europe': {'mean': -0.001, 'std': 0.020, 'days': 240}
        }
        
        params = crisis_params.get(crisis_name, {'mean': -0.005, 'std': 0.030, 'days': 60})
        
        # Simuler returns de crise (composition, évite pertes > -100%)
        simulated_returns = np.random.normal(params['mean'], params['std'], params['days'])
        cumulative = pd.Series((1.0 + simulated_returns).cumprod())
        total_loss = float(cumulative.iloc[-1] - 1.0)
        max_drawdown = float((cumulative / cumulative.cummax() - 1.0).min())
        
        return {
            'scenario': scenario['name'],
            'description': scenario['description'],
            'simulated': True,
            'total_loss': total_loss,
            'max_drawdown': abs(max_drawdown),
            'n_periods': params['days'],
            'worst_day': float(simulated_returns.min())
        }
    
    def monte_carlo_stress(
        self,
        n_scenarios: int = 10000,
        horizon_days: int = 21,
        confidence: float = 0.95,
        tail_scenarios: bool = True
    ) -> Dict:
        """
        Monte Carlo stress testing avec focus sur tail risk.
        
        Args:
            n_scenarios: Nombre de scénarios à simuler
            horizon_days: Horizon temporel (jours)
            confidence: Niveau de confiance pour VaR/CVaR
            tail_scenarios: Si True, oversample les scénarios extrêmes
        
        Returns:
            Dict avec:
            - var_95, cvar_95: Risk measures
            - worst_scenario: Pire scénario
            - best_scenario: Meilleur scénario
            - scenario_distribution: Array des résultats
            - tail_probability: Prob perte > threshold
        
        Example:
            >>> mc_results = tester.monte_carlo_stress(n_scenarios=10000)
            >>> print(f"95% VaR over 21 days: {mc_results['var_95']:.2%}")
        """
        logger.info(f"Running Monte Carlo stress test: {n_scenarios} scenarios, {horizon_days} days")
        
        # Paramètres de simulation
        mean_daily = self.portfolio_returns.mean()
        std_daily = self.portfolio_returns.std()
        
        # Distribution t-Student pour fat tails
        df_param = 5  # Degrés de liberté (plus petit = queues plus épaisses)
        
        if tail_scenarios:
            # Oversample les scénarios extrêmes (mixture distribution)
            # 80% normal, 20% extrême (2x volatilité, même moyenne)
            n_normal = int(n_scenarios * 0.8)
            n_extreme = n_scenarios - n_normal

            scenarios_normal = stats.t.rvs(df=df_param, loc=mean_daily, scale=std_daily,
                                           size=(n_normal, horizon_days))
            scenarios_extreme = stats.t.rvs(df=df_param, loc=mean_daily, scale=std_daily * 2.0,
                                            size=(n_extreme, horizon_days))

            scenarios = np.vstack([scenarios_normal, scenarios_extreme])
        else:
            # Distribution t-Student standard
            scenarios = stats.t.rvs(df=df_param, loc=mean_daily, scale=std_daily,
                                    size=(n_scenarios, horizon_days))
        
        # Calculer rendements cumulés pour chaque scénario (composition via log1p)
        cumulative_log = np.log1p(scenarios).sum(axis=1)
        cumulative_returns = np.expm1(cumulative_log)
        
        # Risk measures (sur pertes positives)
        losses = -cumulative_returns
        var_level = float(np.percentile(losses, confidence * 100))
        tail = losses[losses >= var_level]
        cvar_level = float(tail.mean()) if len(tail) > 0 else var_level
        
        # Scénarios extrêmes
        worst_idx = cumulative_returns.argmin()
        best_idx = cumulative_returns.argmax()
        
        # Tail probability (prob perte > 10%)
        tail_threshold = -0.10
        tail_prob = float((cumulative_returns < tail_threshold).sum() / n_scenarios)
        
        result = {
            'n_scenarios': n_scenarios,
            'horizon_days': horizon_days,
            'var_95': float(var_level),
            'cvar_95': float(cvar_level),
            'worst_scenario': float(cumulative_returns.min()),
            'best_scenario': float(cumulative_returns.max()),
            'mean_scenario': float(cumulative_returns.mean()),
            'std_scenario': float(cumulative_returns.std()),
            'tail_probability': tail_prob,
            'scenario_distribution': cumulative_returns
        }
        
        logger.info(f"Monte Carlo complete: VaR 95% = {var_level:.2%}, CVaR = {cvar_level:.2%}")
        
        return result
    
    def detect_correlation_breakdown(
        self,
        threshold: float = 0.50
    ) -> Dict:
        """
        Détecte les périodes de corrélation breakdown (crise).
        
        En période de crise, les corrélations tendent vers 1 (tous les assets baissent ensemble).
        Détecte ces périodes et mesure l'impact.
        
        Args:
            threshold: Seuil de corrélation moyenne (ex: 0.50)
        
        Returns:
            Dict avec:
            - breakdown_periods: Liste des périodes détectées
            - avg_correlation_normal: Corrélation moyenne en période normale
            - avg_correlation_crisis: Corrélation moyenne en crise
            - diversification_loss: Perte de bénéfice de diversification
        
        Example:
            >>> breakdown = tester.detect_correlation_breakdown()
            >>> print(f"Found {len(breakdown['breakdown_periods'])} crisis periods")
        """
        # Calcul rolling correlation moyenne
        window = 20  # 20 jours
        
        # Moyenne des corrélations par paire
        n_assets = len(self.assets)
        rolling_corr_mean = pd.Series(index=self.returns.index[window-1:], dtype=float)
        
        for i in range(window-1, len(self.returns)):
            window_returns = self.returns.iloc[i-window+1:i+1]
            corr_matrix = window_returns.corr()
            
            # Moyenne des corrélations (hors diagonale)
            mask = np.triu(np.ones_like(corr_matrix, dtype=bool), k=1)
            correlations = corr_matrix.where(mask).stack()
            rolling_corr_mean.iloc[i-window+1] = correlations.mean()
        
        # Détecter périodes au-dessus du threshold
        crisis_mask = rolling_corr_mean > threshold
        
        # Trouver périodes contiguës
        transitions = crisis_mask.astype(int).diff()
        starts = transitions[transitions == 1].index.tolist()
        ends = transitions[transitions == -1].index.tolist()
        
        # Gérer cas limites
        if crisis_mask.iloc[0]:
            starts.insert(0, rolling_corr_mean.index[0])
        if crisis_mask.iloc[-1]:
            ends.append(rolling_corr_mean.index[-1])
        
        breakdown_periods = []
        for i, start in enumerate(starts):
            end = ends[i] if i < len(ends) else rolling_corr_mean.index[-1]
            period_corr = rolling_corr_mean[start:end].mean()
            duration = len(rolling_corr_mean[start:end])
            
            breakdown_periods.append({
                'start': start,
                'end': end,
                'duration': duration,
                'avg_correlation': float(period_corr)
            })
        
        # Statistiques globales
        normal_corr = float(rolling_corr_mean[~crisis_mask].mean()) if (~crisis_mask).any() else 0.0
        crisis_corr = float(rolling_corr_mean[crisis_mask].mean()) if crisis_mask.any() else 0.0
        
        # Perte de diversification (estimation)
        # Diversification benefit = 1 - sqrt(weighted avg correlation)
        div_normal = 1 - np.sqrt(normal_corr) if normal_corr > 0 else 0.0
        div_crisis = 1 - np.sqrt(crisis_corr) if crisis_corr > 0 else 0.0
        div_loss = float(div_normal - div_crisis)
        
        result = {
            'n_breakdown_periods': len(breakdown_periods),
            'breakdown_periods': breakdown_periods,
            'avg_correlation_normal': normal_corr,
            'avg_correlation_crisis': crisis_corr,
            'diversification_loss': div_loss,
            'current_correlation': float(rolling_corr_mean.iloc[-1]) if not rolling_corr_mean.empty else 0.0
        }
        
        logger.info(f"Detected {len(breakdown_periods)} correlation breakdown periods")
        
        return result
    
    def stress_test_all(
        self,
        historical_returns: Optional[pd.DataFrame] = None
    ) -> pd.DataFrame:
        """
        Exécute tous les stress tests et compile les résultats.
        
        Args:
            historical_returns: Returns historiques pour crises (optionnel)
        
        Returns:
            DataFrame récapitulatif de tous les stress tests
        
        Example:
            >>> all_results = tester.stress_test_all()
            >>> print(all_results.sort_values('portfolio_loss'))
        """
        results = []
        
        # Chocs uniformes
        for magnitude in [-0.05, -0.10, -0.20, -0.30]:
            shock_result = self.apply_shock(magnitude, 'absolute')
            results.append({
                'scenario': f'Uniform Shock {magnitude*100:.0f}%',
                'type': 'Shock',
                'portfolio_loss': shock_result['portfolio_loss'],
                'var_95': shock_result['var_95_stressed'],
                'cvar_95': shock_result['cvar_95_stressed']
            })
        
        # Crises historiques
        for crisis_name in self.HISTORICAL_SCENARIOS.keys():
            crisis_result = self.apply_historical_crisis(crisis_name, historical_returns)
            if 'error' not in crisis_result:
                results.append({
                    'scenario': crisis_result['scenario'],
                    'type': 'Historical Crisis',
                    'portfolio_loss': crisis_result.get('total_loss', 0.0),
                    'max_drawdown': crisis_result.get('max_drawdown', 0.0),
                    'duration_days': crisis_result.get('n_periods', 0)
                })
        
        # Monte Carlo
        mc_result = self.monte_carlo_stress(n_scenarios=5000)
        results.append({
            'scenario': 'Monte Carlo Stress',
            'type': 'Monte Carlo',
            'var_95': mc_result['var_95'],
            'cvar_95': mc_result['cvar_95'],
            'worst_scenario': mc_result['worst_scenario'],
            'tail_probability': mc_result['tail_probability']
        })
        
        df = pd.DataFrame(results)
        
        logger.info(f"Completed {len(results)} stress tests")
        
        return df


def stress_test_portfolio(
    returns: pd.DataFrame,
    weights: Optional[pd.Series] = None,
    include_monte_carlo: bool = True,
    include_historical: bool = True
) -> Dict:
    """
    Fonction convenience pour stress test complet.
    
    Args:
        returns: DataFrame de rendements
        weights: Poids de portfolio
        include_monte_carlo: Inclure Monte Carlo
        include_historical: Inclure scénarios historiques
    
    Returns:
        Dict avec tous les résultats
    
    Example:
        >>> results = stress_test_portfolio(returns_df, weights)
        >>> print(results['stress_test_summary'])
    """
    tester = StressTester(returns, weights)
    
    results = {
        'stress_test_summary': tester.stress_test_all()
    }
    
    if include_monte_carlo:
        results['monte_carlo'] = tester.monte_carlo_stress(n_scenarios=10000)
    
    if include_historical:
        results['correlation_breakdown'] = tester.detect_correlation_breakdown()
    
    logger.info("Portfolio stress testing completed")
    
    return results

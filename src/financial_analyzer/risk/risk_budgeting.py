"""
Risk Budgeting and Contribution Analysis.

Décomposition du risque de portfolio en contributions par asset,
marginal risk contribution, et risk budgeting allocation.

Fonctionnalités :
- Marginal contribution au risque total
- Component risk decomposition
- Risk budgeting allocation
- Risk parity portfolio construction
- Contribution to VaR/CVaR
"""

from typing import Dict, Optional, Tuple
import numpy as np
import pandas as pd
from scipy import optimize

from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


class RiskBudgeter:
    """
    Risk budgeting et contribution analysis pour portfolios.
    
    Attributes:
        returns: DataFrame de rendements
        weights: Poids actuels du portfolio
        cov_matrix: Matrice de covariance
    
    Example:
        >>> budgeter = RiskBudgeter(returns_df, weights)
        >>> contributions = budgeter.calculate_risk_contributions()
        >>> print(contributions['marginal_contributions'])
    """
    
    def __init__(
        self,
        returns: pd.DataFrame,
        weights: Optional[pd.Series] = None
    ):
        """
        Initialise le risk budgeter.
        
        Args:
            returns: DataFrame de rendements (colonnes = assets)
            weights: Poids de portfolio (si None, equal weight)
        
        Raises:
            ValueError: Si returns est vide
        """
        if returns.empty:
            raise ValueError("returns DataFrame cannot be empty")
        
        self.returns = returns.copy()
        self.assets = list(returns.columns)
        
        if weights is None:
            self.weights = pd.Series(1.0 / len(self.assets), index=self.assets)
        else:
            self.weights = weights.reindex(self.assets).fillna(0.0)
            if self.weights.sum() > 0:
                self.weights = self.weights / self.weights.sum()
        
        # Matrice de covariance
        self.cov_matrix = self.returns.cov()
        
        # Returns de portfolio
        self.portfolio_returns = (self.returns * self.weights).sum(axis=1)
        
        logger.debug(f"RiskBudgeter initialized with {len(self.assets)} assets")
    
    def calculate_portfolio_variance(
        self,
        weights: Optional[pd.Series] = None
    ) -> float:
        """
        Calcule la variance du portfolio.
        
        Args:
            weights: Poids (si None, utilise self.weights)
        
        Returns:
            Variance du portfolio
        
        Example:
            >>> variance = budgeter.calculate_portfolio_variance()
        """
        if weights is None:
            weights = self.weights
        
        # .item() : le produit (1,1) n'est plus convertible via float() en numpy >= 2
        w = weights.values.reshape(-1, 1)
        variance = (w.T @ self.cov_matrix.values @ w).item()

        return variance
    
    def calculate_portfolio_volatility(
        self,
        weights: Optional[pd.Series] = None
    ) -> float:
        """
        Calcule la volatilité du portfolio.
        
        Args:
            weights: Poids (si None, utilise self.weights)
        
        Returns:
            Volatilité (écart-type) du portfolio
        
        Example:
            >>> vol = budgeter.calculate_portfolio_volatility()
        """
        return np.sqrt(self.calculate_portfolio_variance(weights))
    
    def calculate_marginal_risk_contribution(self) -> pd.Series:
        """
        Calcule la contribution marginale au risque pour chaque asset.
        
        MRC_i = (∂σ_p / ∂w_i) = (Cov * w)_i / σ_p
        
        Returns:
            Series des contributions marginales (unité: volatilité)
        
        Example:
            >>> mrc = budgeter.calculate_marginal_risk_contribution()
            >>> print(mrc.sort_values(ascending=False))
        """
        w = self.weights.values.reshape(-1, 1)
        portfolio_vol = self.calculate_portfolio_volatility()
        
        if portfolio_vol < 1e-10:
            # Portfolio sans risque
            return pd.Series(0.0, index=self.assets)
        
        # MRC = (Σ * w) / σ_p
        marginal = (self.cov_matrix.values @ w).flatten() / portfolio_vol
        
        return pd.Series(marginal, index=self.assets)
    
    def calculate_component_risk_contribution(self) -> pd.Series:
        """
        Calcule la contribution au risque total pour chaque asset.
        
        CRC_i = w_i * MRC_i
        
        Propriété: Σ CRC_i = σ_p (Euler decomposition)
        
        Returns:
            Series des contributions (unité: volatilité)
        
        Example:
            >>> crc = budgeter.calculate_component_risk_contribution()
            >>> print(f"Sum of contributions: {crc.sum():.4f}")
            >>> print(f"Portfolio vol: {budgeter.calculate_portfolio_volatility():.4f}")
        """
        mrc = self.calculate_marginal_risk_contribution()
        crc = self.weights * mrc
        
        return crc
    
    def calculate_percentage_risk_contribution(self) -> pd.Series:
        """
        Calcule le pourcentage de contribution au risque total.
        
        PRC_i = CRC_i / σ_p
        
        Propriété: Σ PRC_i = 1 (100%)
        
        Returns:
            Series des contributions en % (somme = 1.0)
        
        Example:
            >>> prc = budgeter.calculate_percentage_risk_contribution()
            >>> print(prc.sort_values(ascending=False))
        """
        crc = self.calculate_component_risk_contribution()
        portfolio_vol = self.calculate_portfolio_volatility()
        
        if portfolio_vol < 1e-10:
            return pd.Series(0.0, index=self.assets)
        
        prc = crc / portfolio_vol
        
        return prc
    
    def calculate_risk_contributions(self) -> Dict[str, pd.Series]:
        """
        Calcule toutes les métriques de contribution au risque.
        
        Returns:
            Dict avec:
            - marginal_contributions: MRC par asset
            - component_contributions: CRC par asset
            - percentage_contributions: PRC par asset (%)
            - portfolio_volatility: Vol totale
        
        Example:
            >>> results = budgeter.calculate_risk_contributions()
            >>> print(results['percentage_contributions'])
        """
        mrc = self.calculate_marginal_risk_contribution()
        crc = self.calculate_component_risk_contribution()
        prc = self.calculate_percentage_risk_contribution()
        vol = self.calculate_portfolio_volatility()
        
        logger.info(f"Risk contributions calculated: portfolio vol = {vol:.4f}")
        
        return {
            'marginal_contributions': mrc,
            'component_contributions': crc,
            'percentage_contributions': prc,
            'portfolio_volatility': vol
        }
    
    def optimize_risk_parity(
        self,
        target_volatility: Optional[float] = None
    ) -> Dict:
        """
        Optimise le portfolio pour atteindre risk parity.
        
        Risk parity: tous les assets contribuent également au risque total.
        PRC_i = 1/N pour tous les assets.
        
        Args:
            target_volatility: Volatilité cible (si None, pas de contrainte)
        
        Returns:
            Dict avec:
            - weights: Poids optimaux
            - contributions: Contributions finales
            - success: Succès de l'optimisation
        
        Example:
            >>> rp_result = budgeter.optimize_risk_parity()
            >>> print(rp_result['weights'])
        """
        n_assets = len(self.assets)
        target_contribution = 1.0 / n_assets
        
        def objective(w):
            """Minimise l'écart aux contributions égales."""
            weights_series = pd.Series(w, index=self.assets)
            
            # Recalculer contributions avec ces poids
            w_arr = w.reshape(-1, 1)
            portfolio_vol = np.sqrt(w_arr.T @ self.cov_matrix.values @ w_arr)[0, 0]
            
            if portfolio_vol < 1e-10:
                return 1e10  # Pénalité
            
            mrc = (self.cov_matrix.values @ w_arr).flatten() / portfolio_vol
            crc = w * mrc
            prc = crc / portfolio_vol
            
            # Erreur quadratique vs contribution égale
            error = np.sum((prc - target_contribution) ** 2)
            
            return error
        
        # Contraintes
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}  # Somme = 1
        ]
        
        if target_volatility is not None:
            def vol_constraint(w):
                w_arr = w.reshape(-1, 1)
                vol = np.sqrt(w_arr.T @ self.cov_matrix.values @ w_arr)[0, 0]
                return vol - target_volatility
            
            constraints.append({'type': 'eq', 'fun': vol_constraint})
        
        # Bounds: poids entre 0 et 1
        bounds = tuple((0.0, 1.0) for _ in range(n_assets))
        
        # Initialisation: equal weight
        w0 = np.ones(n_assets) / n_assets
        
        # Optimisation
        result = optimize.minimize(
            objective,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000}
        )
        
        if result.success:
            optimal_weights = pd.Series(result.x, index=self.assets)
            
            # Recalculer contributions finales
            self.weights = optimal_weights
            contributions = self.calculate_risk_contributions()
            
            logger.info(f"Risk parity optimization successful: error = {result.fun:.6f}")
            
            return {
                'success': True,
                'weights': optimal_weights,
                'contributions': contributions,
                'optimization_error': float(result.fun)
            }
        else:
            logger.warning(f"Risk parity optimization failed: {result.message}")
            
            return {
                'success': False,
                'message': result.message
            }
    
    def optimize_risk_budgeting(
        self,
        risk_budgets: pd.Series,
        target_volatility: Optional[float] = None
    ) -> Dict:
        """
        Optimise le portfolio selon des budgets de risque spécifiés.
        
        Risk budgeting: allouer le risque selon des proportions prédéfinies.
        Ex: 40% risque aux actions, 30% obligations, 30% alternatives.
        
        Args:
            risk_budgets: Series des budgets de risque par asset (somme = 1.0)
            target_volatility: Volatilité cible (optionnel)
        
        Returns:
            Dict avec résultats d'optimisation
        
        Example:
            >>> budgets = pd.Series({'AAPL': 0.3, 'MSFT': 0.3, 'GOOGL': 0.4})
            >>> result = budgeter.optimize_risk_budgeting(budgets)
        
        Raises:
            ValueError: Si somme des budgets != 1.0
        """
        if not np.isclose(risk_budgets.sum(), 1.0):
            raise ValueError(f"Risk budgets must sum to 1.0, got {risk_budgets.sum():.4f}")
        
        budgets = risk_budgets.reindex(self.assets).fillna(0.0)
        
        def objective(w):
            """Minimise l'écart aux budgets de risque."""
            weights_series = pd.Series(w, index=self.assets)
            
            w_arr = w.reshape(-1, 1)
            portfolio_vol = np.sqrt(w_arr.T @ self.cov_matrix.values @ w_arr)[0, 0]
            
            if portfolio_vol < 1e-10:
                return 1e10
            
            mrc = (self.cov_matrix.values @ w_arr).flatten() / portfolio_vol
            crc = w * mrc
            prc = crc / portfolio_vol
            
            error = np.sum((prc - budgets.values) ** 2)
            
            return error
        
        constraints = [
            {'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0}
        ]
        
        if target_volatility is not None:
            def vol_constraint(w):
                w_arr = w.reshape(-1, 1)
                vol = np.sqrt(w_arr.T @ self.cov_matrix.values @ w_arr)[0, 0]
                return vol - target_volatility
            
            constraints.append({'type': 'eq', 'fun': vol_constraint})
        
        bounds = tuple((0.0, 1.0) for _ in range(len(self.assets)))
        
        # Init: proportionnel aux budgets
        w0 = budgets.values / budgets.sum()
        
        result = optimize.minimize(
            objective,
            w0,
            method='SLSQP',
            bounds=bounds,
            constraints=constraints,
            options={'maxiter': 1000}
        )
        
        if result.success:
            optimal_weights = pd.Series(result.x, index=self.assets)
            
            self.weights = optimal_weights
            contributions = self.calculate_risk_contributions()
            
            logger.info(f"Risk budgeting optimization successful: error = {result.fun:.6f}")
            
            return {
                'success': True,
                'weights': optimal_weights,
                'contributions': contributions,
                'target_budgets': budgets,
                'optimization_error': float(result.fun)
            }
        else:
            logger.warning(f"Risk budgeting optimization failed: {result.message}")
            
            return {
                'success': False,
                'message': result.message
            }
    
    def calculate_var_contribution(
        self,
        confidence: float = 0.95
    ) -> pd.Series:
        """
        Calcule la contribution de chaque asset au VaR du portfolio.
        
        Utilise approche delta-normal: CVaR_i = w_i * MRC_i * z_α
        
        Args:
            confidence: Niveau de confiance (ex: 0.95)
        
        Returns:
            Series des contributions au VaR
        
        Example:
            >>> var_contrib = budgeter.calculate_var_contribution(0.95)
            >>> print(var_contrib.sort_values(ascending=False))
        """
        from scipy import stats
        
        # Z-score pour le niveau de confiance
        z_alpha = stats.norm.ppf(confidence)
        
        mrc = self.calculate_marginal_risk_contribution()
        
        # Contribution = w_i * MRC_i * z_α
        var_contrib = self.weights * mrc * z_alpha
        
        return var_contrib
    
    def analyze_diversification_benefit(self) -> Dict:
        """
        Analyse le bénéfice de diversification du portfolio.
        
        Compare risque standalone de chaque asset vs contribution au portfolio.
        
        Returns:
            Dict avec:
            - standalone_risks: Risque de chaque asset seul
            - portfolio_contributions: Contribution au risque portfolio
            - diversification_ratio: Ratio weighted standalone / portfolio risk
            - concentration_index: HHI des contributions
        
        Example:
            >>> div = budgeter.analyze_diversification_benefit()
            >>> print(f"Diversification ratio: {div['diversification_ratio']:.2f}")
        """
        # Risque standalone de chaque asset
        standalone_risks = pd.Series(
            np.sqrt(np.diag(self.cov_matrix.values)),
            index=self.assets
        )
        
        # Contributions au portfolio
        contributions = self.calculate_component_risk_contribution()
        portfolio_vol = self.calculate_portfolio_volatility()
        
        # Risque weighted standalone
        weighted_standalone = (self.weights * standalone_risks).sum()
        
        # Diversification ratio
        div_ratio = weighted_standalone / portfolio_vol if portfolio_vol > 0 else 1.0
        
        # Concentration index (HHI des contributions)
        prc = self.calculate_percentage_risk_contribution()
        hhi = (prc ** 2).sum()
        
        logger.info(f"Diversification ratio: {div_ratio:.2f}, HHI: {hhi:.4f}")
        
        return {
            'standalone_risks': standalone_risks,
            'portfolio_contributions': contributions,
            'weighted_standalone_risk': float(weighted_standalone),
            'portfolio_risk': float(portfolio_vol),
            'diversification_ratio': float(div_ratio),
            'concentration_index': float(hhi),
            'effective_n_assets': float(1.0 / hhi) if hhi > 0 else 0.0
        }


def calculate_risk_budget(
    returns: pd.DataFrame,
    weights: pd.Series,
    risk_budgets: Optional[pd.Series] = None
) -> Dict:
    """
    Fonction convenience pour risk budgeting complet.
    
    Args:
        returns: DataFrame de rendements
        weights: Poids actuels
        risk_budgets: Budgets de risque cibles (si None, analyse seulement)
    
    Returns:
        Dict avec contributions et optimisation (si budgets fournis)
    
    Example:
        >>> budgets = pd.Series({'AAPL': 0.4, 'MSFT': 0.6})
        >>> result = calculate_risk_budget(returns_df, weights, budgets)
    """
    budgeter = RiskBudgeter(returns, weights)
    
    contributions = budgeter.calculate_risk_contributions()
    diversification = budgeter.analyze_diversification_benefit()
    
    result = {
        'contributions': contributions,
        'diversification_analysis': diversification
    }
    
    if risk_budgets is not None:
        optimization = budgeter.optimize_risk_budgeting(risk_budgets)
        result['optimization'] = optimization
    
    logger.info("Risk budgeting analysis completed")
    
    return result

from __future__ import annotations

# 1. Stdlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# 2. Third-party
import numpy as np
import pandas as pd

# 3. Local
from financial_analyzer.utils.helpers import get_logger

logger = get_logger(__name__)


@dataclass
class RebalanceResult:
	weights: pd.DataFrame  # index=dates, columns=tickers
	trades: pd.DataFrame   # index=dates, columns=tickers (delta weights)


class PortfolioRebalancer:
	"""Outils de rebalancement de portefeuille.

	Hypothèses:
		- returns: DataFrame (dates x tickers) de rendements par période.
		- target_weights: Series poids cibles (somme 1).
		- Pas d'emprunt (poids somme 1). Les coûts de transaction peuvent être spécifiés.
	"""

	def __init__(self, returns: pd.DataFrame) -> None:
		if not isinstance(returns, pd.DataFrame) or returns.empty:
			raise ValueError("returns must be a non-empty DataFrame")
		self.returns = returns.sort_index()
		self.tickers: List[str] = list(self.returns.columns)

	def rebalance_periodic(
		self,
		target_weights: pd.Series,
		freq: str = 'M',
		transaction_cost: float = 0.0,
	) -> RebalanceResult:
		"""Rebalance à une fréquence calendaire.

		Args:
			target_weights: Poids cibles somme 1.
			freq: Fréquence pandas (ex: 'M' pour fin de mois).
			transaction_cost: Coût de transaction proportionnel par unité de poids transigée.

		Returns:
			RebalanceResult avec historique des poids et des trades.
		"""
		dates = self.returns.index
		target_weights = target_weights.reindex(self.tickers).fillna(0.0)
		tw = target_weights / target_weights.sum() if target_weights.sum() != 1 else target_weights
		rebal_dates = pd.date_range(start=dates.min(), end=dates.max(), freq=freq)
		rebal_dates = dates.intersection(rebal_dates)
		return _simulate_rebalancing(self.returns, tw, rebal_dates, transaction_cost)

	def rebalance_threshold(
		self,
		target_weights: pd.Series,
		threshold: float = 0.05,
		transaction_cost: float = 0.0,
	) -> RebalanceResult:
		"""Rebalance quand l'écart aux cibles dépasse un seuil.

		Args:
			target_weights: Poids cibles.
			threshold: Seuil absolu sur l'écart max |w - w*| déclenchant le rebalance.
			transaction_cost: Coûts proportionnels par unité de poids transigée.

		Returns:
			RebalanceResult avec historique des poids et trades.
		"""
		dates = self.returns.index
		target_weights = target_weights.reindex(self.tickers).fillna(0.0)
		tw = target_weights / target_weights.sum() if target_weights.sum() != 1 else target_weights

		weights = pd.DataFrame(index=dates, columns=self.tickers, dtype=float)
		trades = pd.DataFrame(0.0, index=dates, columns=self.tickers, dtype=float)
		w = tw.values.copy()
		weights.iloc[0] = w
		for t in range(1, len(dates)):
			r = self.returns.iloc[t].values
			w = _evolve_weights(w, r)
			if np.max(np.abs(w - tw.values)) > threshold:
				delta = tw.values - w
				w = tw.values.copy()
				trades.iloc[t] = delta
				if transaction_cost > 0:
					cost = transaction_cost * np.sum(np.abs(delta))
					# Adjust via cash leakage: reduce all weights proportionally
					w = w * (1 - cost)
					w = w / np.sum(w)
			weights.iloc[t] = w
		return RebalanceResult(weights=weights.ffill(), trades=trades)

	def rebalance_calendar(
		self,
		target_weights: pd.Series,
		months: Tuple[int, ...] = (3, 6, 9, 12),
		transaction_cost: float = 0.0,
	) -> RebalanceResult:
		"""Rebalance à des mois spécifiques du calendrier.

		Args:
			target_weights: Poids cibles.
			months: Mois (1-12) où rebalancer.
			transaction_cost: Coûts de transaction proportionnels.

		Returns:
			RebalanceResult avec historique des poids et trades.
		"""
		dates = self.returns.index
		cal_dates = dates[dates.month.isin(months)]
		target_weights = target_weights.reindex(self.tickers).fillna(0.0)
		tw = target_weights / target_weights.sum() if target_weights.sum() != 1 else target_weights
		return _simulate_rebalancing(self.returns, tw, cal_dates, transaction_cost)


def _simulate_rebalancing(
	returns: pd.DataFrame,
	target_weights: pd.Series,
	rebalance_dates: pd.DatetimeIndex,
	transaction_cost: float = 0.0,
) -> RebalanceResult:
	# Neutralize missing returns
	returns = returns.fillna(0.0)
	
	dates = returns.index
	tickers = list(returns.columns)
	weights = pd.DataFrame(index=dates, columns=tickers, dtype=float)
	trades = pd.DataFrame(0.0, index=dates, columns=tickers, dtype=float)

	w = target_weights.values.copy()
	weights.iloc[0] = w

	for t in range(1, len(dates)):
		r = returns.iloc[t].values
		w = _evolve_weights(w, r)
		if dates[t] in set(rebalance_dates):
			delta = target_weights.values - w
			w = target_weights.values.copy()
			trades.iloc[t] = delta
			if transaction_cost > 0:
				cost = transaction_cost * np.sum(np.abs(delta))
				w = w * (1 - cost)
				w = w / np.sum(w)
		weights.iloc[t] = w

	return RebalanceResult(weights=weights.ffill(), trades=trades)


def _evolve_weights(w: np.ndarray, r: np.ndarray) -> np.ndarray:
	# evolve via compounding then renormalize
	w = w * (1.0 + r)
	total = np.sum(w)
	if total <= 0:
		# fallback equal weight
		w = np.repeat(1.0 / len(w), len(w))
	else:
		w = w / total
	return w


# -------------------------- Module-level functions --------------------------

def rebalance_periodic(
	returns: pd.DataFrame,
	target_weights: pd.Series,
	freq: str = 'M',
	transaction_cost: float = 0.0,
) -> RebalanceResult:
	"""Wrapper module-level pour rebalancement périodique."""
	return PortfolioRebalancer(returns).rebalance_periodic(
		target_weights=target_weights, freq=freq, transaction_cost=transaction_cost
	)


def rebalance_threshold(
	returns: pd.DataFrame,
	target_weights: pd.Series,
	threshold: float = 0.05,
	transaction_cost: float = 0.0,
) -> RebalanceResult:
	"""Wrapper module-level pour rebalancement par seuil."""
	return PortfolioRebalancer(returns).rebalance_threshold(
		target_weights=target_weights, threshold=threshold, transaction_cost=transaction_cost
	)


def rebalance_calendar(
	returns: pd.DataFrame,
	target_weights: pd.Series,
	months: Tuple[int, ...] = (3, 6, 9, 12),
	transaction_cost: float = 0.0,
) -> RebalanceResult:
	"""Wrapper module-level pour rebalancement calendaire."""
	return PortfolioRebalancer(returns).rebalance_calendar(
		target_weights=target_weights, months=months, transaction_cost=transaction_cost
	)


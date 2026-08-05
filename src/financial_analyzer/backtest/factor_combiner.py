"""B — Combinateur de facteurs appris, validé out-of-sample.

Plutôt que de prédire les prix (LSTM) ou d'entraîner un agent (RL), ce module
apprend la brique ML *tractable et honnête* : comment **combiner** des sources
de signal qui ont déjà du sens (technique, fondamental, sentiment, ...) pour
maximiser le pouvoir prédictif sur le rendement forward.

Méthode : à chaque date, chaque source est standardisée en cross-section
(z-score parmi les actifs du jour) — sinon une source à grande échelle ou qui
dérive domine mécaniquement. Une régression ridge apprend les poids des sources
contre le rendement t->t+1. La validation est faite via le harness A
(`signal_evaluation`), en expanding window, sans fuite du futur.

On compare toujours le combinateur appris à deux baselines honnêtes :
l'égal-poids (moyenne des sources) et la meilleure source seule.

Exemple
-------
    >>> from financial_analyzer.backtest.factor_combiner import walk_forward_combine
    >>> out = walk_forward_combine(source_panels, returns, n_splits=5)
    >>> print(out['combined'].summary())      # combinateur appris (OOS)
    >>> print(out['equal_weight'].summary())   # baseline égal-poids (OOS)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from financial_analyzer.backtest.signal_evaluation import (
    CostModel,
    SignalEvalResult,
    cross_sectional_weights,
    evaluate_signal,
)

__all__ = [
    "FactorCombiner",
    "CostAwareCombiner",
    "walk_forward_combine",
    "walk_forward_cost_aware",
]


def _zscore_cross_section(panel: pd.DataFrame) -> pd.DataFrame:
    """Standardise chaque ligne (date) : z-score parmi les actifs du jour."""
    mean = panel.mean(axis=1)
    std = panel.std(axis=1, ddof=0).replace(0.0, np.nan)
    z = panel.sub(mean, axis=0).div(std, axis=0)
    return z.fillna(0.0)


@dataclass
class FactorCombiner:
    """Apprend des poids de sources par régression ridge cross-sectionnelle.

    method:
        'ridge'  — poids appris (défaut).
        'equal'  — égal-poids (baseline, aucun apprentissage).
    """

    method: str = "ridge"
    l2: float = 1.0
    weights_: Optional[pd.Series] = None
    sources_: Optional[List[str]] = None

    def fit(self, source_panels: Dict[str, pd.DataFrame], forward_returns: pd.DataFrame) -> "FactorCombiner":
        sources = sorted(source_panels)
        self.sources_ = sources

        if self.method == "equal":
            self.weights_ = pd.Series(1.0 / len(sources), index=sources)
            return self

        # Empile les observations (date, actif) : X = sources z-scorées, y = rdt forward
        z = {s: _zscore_cross_section(source_panels[s]) for s in sources}
        xs, ys = [], []
        common_index = forward_returns.index
        for s in sources:
            z[s] = z[s].reindex(index=common_index, columns=forward_returns.columns)
        for dt in common_index:
            y_row = forward_returns.loc[dt]
            feats = np.column_stack([z[s].loc[dt].values for s in sources])
            mask = ~np.isnan(y_row.values) & ~np.isnan(feats).any(axis=1)
            if mask.sum() == 0:
                continue
            xs.append(feats[mask])
            ys.append(y_row.values[mask])

        if not xs:
            self.weights_ = pd.Series(1.0 / len(sources), index=sources)
            return self

        X = np.vstack(xs)
        y = np.concatenate(ys)
        # Ridge closed-form : w = (X'X + l2*I)^-1 X'y  (pas d'intercept : le tri
        # cross-sectionnel est invariant par translation).
        k = X.shape[1]
        w = np.linalg.solve(X.T @ X + self.l2 * np.eye(k), X.T @ y)
        self.weights_ = pd.Series(w, index=sources)
        return self

    def predict(self, source_panels: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        if self.weights_ is None or self.sources_ is None:
            raise RuntimeError("FactorCombiner.predict appelé avant fit().")
        sources = self.sources_
        any_panel = source_panels[sources[0]]
        combined = pd.DataFrame(0.0, index=any_panel.index, columns=any_panel.columns)
        for s in sources:
            z = _zscore_cross_section(source_panels[s]).reindex(
                index=combined.index, columns=combined.columns
            ).fillna(0.0)
            combined = combined + self.weights_[s] * z
        return combined


def _slice_panels(panels: Dict[str, pd.DataFrame], idx: pd.Index) -> Dict[str, pd.DataFrame]:
    return {s: p.loc[idx] for s, p in panels.items()}


def walk_forward_combine(
    source_panels: Dict[str, pd.DataFrame],
    returns: pd.DataFrame,
    n_splits: int = 5,
    l2: float = 1.0,
    cost_model: Optional[CostModel] = None,
    quantile: float = 0.2,
    long_short: bool = True,
    periods_per_year: int = 252,
) -> Dict[str, object]:
    """Valide le combinateur appris en walk-forward, vs baselines honnêtes.

    À chaque fenêtre : fit ridge sur le passé (expanding), prédiction des scores
    combinés sur la fenêtre test, évaluation coûts inclus via le harness A. On
    calcule en parallèle, sur exactement les mêmes fenêtres OOS, l'égal-poids et
    chaque source seule — pour savoir si l'apprentissage apporte vraiment.

    Returns:
        dict: 'combined', 'equal_weight' (SignalEvalResult agrégés OOS),
        'per_source' (Dict[str, SignalEvalResult] OOS), 'avg_weights'
        (pd.Series des poids moyens appris), 'n_splits'.
    """
    cost_model = cost_model or CostModel()
    sources = sorted(source_panels)

    # Alignement temporel commun à toutes les sources + returns
    common = returns.index
    for s in sources:
        common = common.intersection(source_panels[s].index)
    common = common.sort_values()
    returns = returns.loc[common]
    source_panels = {s: source_panels[s].loc[common] for s in sources}
    fwd = returns.shift(-1)

    n = len(common)
    if n < (n_splits + 1) * 5:
        raise ValueError(f"Historique trop court ({n} dates) pour {n_splits} fenêtres.")

    fold = n // (n_splits + 1)
    combined_parts: List[pd.DataFrame] = []
    ew_parts: List[pd.DataFrame] = []
    weights_list: List[pd.Series] = []
    n_done = 0

    for i in range(1, n_splits + 1):
        tr = common[: fold * i]
        te = common[fold * i : (fold * (i + 1) if i < n_splits else n)]
        if len(te) < 5:
            continue

        combiner = FactorCombiner(method="ridge", l2=l2).fit(
            _slice_panels(source_panels, tr), fwd.loc[tr]
        )
        weights_list.append(combiner.weights_)
        combined_parts.append(combiner.predict(_slice_panels(source_panels, te)))

        ew = FactorCombiner(method="equal").fit(_slice_panels(source_panels, tr), fwd.loc[tr])
        ew_parts.append(ew.predict(_slice_panels(source_panels, te)))
        n_done += 1

    def _agg(parts: List[pd.DataFrame]) -> Optional[SignalEvalResult]:
        if not parts:
            return None
        panel = pd.concat(parts)
        return evaluate_signal(
            panel, returns.reindex(panel.index), cost_model=cost_model,
            quantile=quantile, long_short=long_short, periods_per_year=periods_per_year,
        )

    # Sources seules, sur la même union de fenêtres test
    oos_index = pd.concat(combined_parts).index if combined_parts else pd.Index([])
    per_source: Dict[str, SignalEvalResult] = {}
    for s in sources:
        per_source[s] = evaluate_signal(
            source_panels[s].reindex(oos_index), returns.reindex(oos_index),
            cost_model=cost_model, quantile=quantile, long_short=long_short,
            periods_per_year=periods_per_year,
        )

    avg_weights = pd.concat(weights_list, axis=1).mean(axis=1) if weights_list else pd.Series(dtype=float)

    return {
        "combined": _agg(combined_parts),
        "equal_weight": _agg(ew_parts),
        "per_source": per_source,
        "avg_weights": avg_weights,
        "n_splits": n_done,
    }


# ============================================================================
# B cost-aware : optimise le Sharpe NET DE COÛTS, pas l'IC
# ============================================================================
# Le combinateur ridge ci-dessus maximise l'ajustement au rendement forward
# (IC). Sur données réelles, il charge des facteurs à fort turnover (ex.
# reversal) qui ont un IC positif mais perdent de l'argent après coûts. Le
# CostAwareCombiner optimise directement le Sharpe net d'un portefeuille
# long/short — via le MÊME modèle de coûts que l'évaluation — ce qui pénalise
# de fait le turnover et écarte les facteurs qui ne « paient » pas leurs frais.


def _quantile_weight_matrix(scores: pd.DataFrame, quantile: float, long_short: bool) -> np.ndarray:
    """Matrice de poids (dates × actifs) : long top-k / short bottom-k par date.

    Version vectorisée de cross_sectional_weights sur tout le panel — même
    convention (poids ±0.5/k, somme |w|=1 ; 0 si < 5 actifs valides).
    """
    n_valid = scores.notna().sum(axis=1)
    k = (n_valid * quantile).round().clip(lower=1)
    r = scores.rank(axis=1)  # 1..n_valid, NaN reste NaN
    long_mask = r.gt(n_valid - k, axis=0).fillna(False)
    short_mask = r.le(k, axis=0).fillna(False)
    inv_k = (1.0 / k).replace([np.inf, -np.inf], 0.0)
    if long_short:
        W = long_mask.mul(0.5 * inv_k, axis=0) - short_mask.mul(0.5 * inv_k, axis=0)
    else:
        W = long_mask.mul(inv_k, axis=0)
    W = W.where((n_valid >= 5), 0.0)
    return W.values


def _net_sharpe_of_scores(
    combined: pd.DataFrame,
    returns: pd.DataFrame,
    cost_model: CostModel,
    quantile: float,
    long_short: bool,
    periods_per_year: int,
) -> float:
    """Sharpe net de coûts du portefeuille long/short issu d'un panel de scores.

    Version vectorisée (pas de calcul d'IC) pour servir de fonction-objectif.
    """
    fwd = returns.shift(-1).reindex(index=combined.index, columns=combined.columns)
    W = _quantile_weight_matrix(combined, quantile, long_short)  # (T, N)
    F = np.nan_to_num(fwd.values, nan=0.0)
    gross = np.einsum("ta,ta->t", W, F)
    turnover = np.empty(W.shape[0])
    turnover[0] = np.abs(W[0]).sum()
    turnover[1:] = np.abs(np.diff(W, axis=0)).sum(axis=1)
    net = gross - turnover * cost_model.cost_rate
    if net.size < 2:
        return 0.0
    sd = net.std(ddof=1)
    if sd == 0:
        return 0.0
    return float(net.mean() / sd * np.sqrt(periods_per_year))


@dataclass
class CostAwareCombiner:
    """Pondère les sources par leur Sharpe NET DE COÛTS standalone.

    Contrairement à FactorCombiner (ridge sur l'IC, qui charge les facteurs à
    fort turnover parce qu'ils ont un IC positif *brut*), chaque source reçoit
    un poids proportionnel à son Sharpe net de coûts sur la fenêtre
    d'entraînement, les valeurs négatives étant mises à zéro. Un facteur qui ne
    rembourse pas ses frais (piège à turnover) est donc écarté (poids 0).

    Cette heuristique est délibérément robuste : optimiser conjointement le
    Sharpe net surajuste sur petit échantillon et ne généralise pas hors
    échantillon, alors que la pondération par Sharpe net standalone est stable.
    """

    cost_model: Optional[CostModel] = None
    quantile: float = 0.2
    long_short: bool = True
    periods_per_year: int = 252
    weights_: Optional[pd.Series] = None
    sources_: Optional[List[str]] = None

    def fit(self, source_panels: Dict[str, pd.DataFrame], returns: pd.DataFrame) -> "CostAwareCombiner":
        cost = self.cost_model or CostModel()
        sources = sorted(source_panels)
        self.sources_ = sources
        idx, cols = returns.index, returns.columns
        z = {s: _zscore_cross_section(source_panels[s]).reindex(index=idx, columns=cols).fillna(0.0)
             for s in sources}

        net = {s: _net_sharpe_of_scores(z[s], returns, cost, self.quantile, self.long_short,
                                        self.periods_per_year) for s in sources}
        pos = np.array([max(0.0, net[s]) for s in sources])
        if pos.sum() > 0:
            w = pos / pos.sum()
        else:
            # aucun facteur net-positif : ne garder que le moins mauvais
            w = np.zeros(len(sources))
            w[int(np.argmax([net[s] for s in sources]))] = 1.0
        self.weights_ = pd.Series(w, index=sources)
        return self

    def predict(self, source_panels: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        if self.weights_ is None or self.sources_ is None:
            raise RuntimeError("CostAwareCombiner.predict appelé avant fit().")
        any_panel = source_panels[self.sources_[0]]
        out = None
        for s in self.sources_:
            z = _zscore_cross_section(source_panels[s]).reindex(
                index=any_panel.index, columns=any_panel.columns).fillna(0.0)
            term = self.weights_[s] * z
            out = term if out is None else out + term
        return out


def walk_forward_cost_aware(
    source_panels: Dict[str, pd.DataFrame],
    returns: pd.DataFrame,
    n_splits: int = 5,
    cost_model: Optional[CostModel] = None,
    quantile: float = 0.2,
    long_short: bool = True,
    periods_per_year: int = 252,
) -> Dict[str, object]:
    """Valide le combinateur cost-aware en walk-forward, coûts inclus.

    Returns: dict avec 'cost_aware' (SignalEvalResult OOS agrégé) et
    'avg_weights' (poids moyens appris). À comparer aux sorties de
    walk_forward_combine (ridge/IC, égal-poids, sources seules).
    """
    cost_model = cost_model or CostModel()
    sources = sorted(source_panels)
    common = returns.index
    for s in sources:
        common = common.intersection(source_panels[s].index)
    common = common.sort_values()
    returns = returns.loc[common]
    source_panels = {s: source_panels[s].loc[common] for s in sources}

    n = len(common)
    if n < (n_splits + 1) * 5:
        raise ValueError(f"Historique trop court ({n} dates) pour {n_splits} fenêtres.")

    fold = n // (n_splits + 1)
    parts: List[pd.DataFrame] = []
    weights_list: List[pd.Series] = []
    n_done = 0
    for i in range(1, n_splits + 1):
        tr = common[: fold * i]
        te = common[fold * i : (fold * (i + 1) if i < n_splits else n)]
        if len(te) < 5:
            continue
        comb = CostAwareCombiner(
            cost_model=cost_model, quantile=quantile, long_short=long_short,
            periods_per_year=periods_per_year,
        ).fit(_slice_panels(source_panels, tr), returns.loc[tr])
        weights_list.append(comb.weights_)
        parts.append(comb.predict(_slice_panels(source_panels, te)))
        n_done += 1

    oos = None
    if parts:
        panel = pd.concat(parts)
        oos = evaluate_signal(panel, returns.reindex(panel.index), cost_model=cost_model,
                              quantile=quantile, long_short=long_short, periods_per_year=periods_per_year)
    avg_weights = pd.concat(weights_list, axis=1).mean(axis=1) if weights_list else pd.Series(dtype=float)
    return {"cost_aware": oos, "avg_weights": avg_weights, "n_splits": n_done}

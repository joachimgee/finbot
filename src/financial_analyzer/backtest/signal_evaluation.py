"""Évaluation économique d'un signal cross-sectionnel, coûts inclus.

Ce module est la clé de voûte de la validation : il transforme un score de
signal (par date × actif) en métriques qui disent s'il est *significatif* —
Information Coefficient out-of-sample ET performance d'un portefeuille
long/short ajusté des coûts de transaction (commission + slippage).

Sans coûts ni évaluation out-of-sample, un signal « qui a l'air de marcher »
est indiscernable d'un sur-apprentissage. C'est ce que ce module rend mesurable.

Réutilise `ic_reporting.compute_cross_sectional_ic` pour la partie IC.

Exemple
-------
    >>> from financial_analyzer.backtest.signal_evaluation import (
    ...     CostModel, evaluate_signal, walk_forward_evaluate)
    >>> res = evaluate_signal(scores, returns, CostModel())
    >>> print(res.summary())
    >>> # Validation out-of-sample d'un combinateur (voir B) :
    >>> wf = walk_forward_evaluate(scores_by_source, returns, fit_predict=my_combiner)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np
import pandas as pd

from financial_analyzer.backtest.cost_aware import apply_no_trade_band
from financial_analyzer.backtest.ic_reporting import (
    compute_cross_sectional_ic,
    ic_summary,
)

__all__ = [
    "CostModel",
    "SignalEvalResult",
    "cross_sectional_weights",
    "evaluate_signal",
    "walk_forward_evaluate",
]


@dataclass
class CostModel:
    """Coût de transaction par unité de turnover (aller simple).

    Le turnover est mesuré en fraction de portefeuille rééquilibrée : passer de
    +0.10 à +0.04 sur un actif coûte |0.10 - 0.04| * cost_rate. commission et
    slippage sont en points de base (1 bp = 0.01 %).
    """

    commission_bps: float = 20.0  # 0.20 % — défaut aligné sur config (0.002)
    slippage_bps: float = 5.0  # 0.05 % — impact/écart moyen par ordre marché

    @property
    def cost_rate(self) -> float:
        """Coût total par unité de turnover (fraction, aller simple)."""
        return (self.commission_bps + self.slippage_bps) / 1e4

    @classmethod
    def alpaca_equities(cls) -> CostModel:
        """Modèle de coûts **calibré** pour Alpaca actions US.

        Calibration empirique (``scripts/calibrate_cost_model_alpaca.py``) sur des
        cotations bid/ask réelles de large-caps US liquides :

        * **commission = 0 bps** — Alpaca est sans commission sur les actions US
          (les frais réglementaires SEC/TAF côté vente sont < 0.3 bps, négligés).
        * **slippage ≈ 2.5 bps** (aller simple) — demi-spread effectif médian
          mesuré ≈ 1.45 bps + ~1 bp d'impact de marché. (Le spread effectif médian
          aller-retour mesuré est ≈ 2.9 bps.)

        C'est le modèle à utiliser par défaut pour toute validation ciblant
        l'exécution réelle sur Alpaca — bien plus fidèle que l'ancien réglage en
        dur (5 + 3 bps, dont une commission fictive) ou le défaut générique
        (20 + 5 bps).
        """
        return cls(commission_bps=0.0, slippage_bps=2.5)


@dataclass
class SignalEvalResult:
    """Résultat d'une évaluation de signal."""

    ic_mean: float
    ic_t_stat: float
    ic_hit_rate: float
    gross_sharpe: float
    net_sharpe: float
    gross_ann_return: float
    net_ann_return: float
    avg_turnover: float
    n_periods: int
    net_equity_curve: pd.Series = field(default_factory=lambda: pd.Series(dtype=float))

    def summary(self) -> str:
        return (
            f"IC={self.ic_mean:+.4f} (t={self.ic_t_stat:+.2f}, hit={self.ic_hit_rate:.0%}) | "
            f"Sharpe brut={self.gross_sharpe:+.2f} net={self.net_sharpe:+.2f} | "
            f"Rdt an. net={self.net_ann_return:+.1%} | turnover={self.avg_turnover:.2f}/pér. | "
            f"{self.n_periods} périodes"
        )

    def to_dict(self) -> Dict[str, float]:
        return {
            "ic_mean": self.ic_mean,
            "ic_t_stat": self.ic_t_stat,
            "ic_hit_rate": self.ic_hit_rate,
            "gross_sharpe": self.gross_sharpe,
            "net_sharpe": self.net_sharpe,
            "gross_ann_return": self.gross_ann_return,
            "net_ann_return": self.net_ann_return,
            "avg_turnover": self.avg_turnover,
            "n_periods": float(self.n_periods),
        }


def cross_sectional_weights(scores_row: pd.Series, quantile: float = 0.2, long_short: bool = True) -> pd.Series:
    """Convertit une ligne de scores (une date) en poids de portefeuille.

    Long sur le meilleur quantile, short sur le pire (si long_short), pondérés
    également, dollar-neutre, normalisés à somme des |poids| = 1.

    Retourne une Series alignée sur scores_row (0 pour les actifs non retenus).
    """
    s = scores_row.dropna()
    weights = pd.Series(0.0, index=scores_row.index)
    n = len(s)
    if n < 5:  # trop peu d'actifs pour un tri cross-sectionnel fiable
        return weights

    k = max(1, int(round(n * quantile)))
    ranked = s.sort_values()
    bottom = ranked.index[:k]
    top = ranked.index[-k:]

    if long_short:
        weights.loc[top] = 0.5 / k
        weights.loc[bottom] = -0.5 / k
    else:
        weights.loc[top] = 1.0 / k
    return weights


def _sharpe(returns: pd.Series, periods_per_year: int) -> float:
    r = returns.dropna()
    if len(r) < 2 or r.std(ddof=1) == 0:
        return 0.0
    return float(r.mean() / r.std(ddof=1) * np.sqrt(periods_per_year))


def _ann_return(returns: pd.Series, periods_per_year: int) -> float:
    r = returns.dropna()
    if r.empty:
        return 0.0
    return float(r.mean() * periods_per_year)


def evaluate_signal(
    scores: pd.DataFrame,
    returns: pd.DataFrame,
    cost_model: Optional[CostModel] = None,
    quantile: float = 0.2,
    long_short: bool = True,
    periods_per_year: int = 252,
    rebalance_every: int = 1,
    no_trade_band: float = 0.0,
) -> SignalEvalResult:
    """Évalue un signal cross-sectionnel, coûts inclus.

    Args:
        scores: DataFrame (dates × actifs). Le score à la date t est censé
            prédire le rendement de t -> t+1.
        returns: DataFrame (dates × actifs) de rendements simples par période
            (return[t] = close[t]/close[t-1] - 1).
        cost_model: modèle de coûts (défaut: CostModel()).
        quantile: fraction long/short de chaque côté (0.2 = top/bottom 20 %).
        long_short: True pour un portefeuille dollar-neutre long/short.
        periods_per_year: 252 pour du journalier (annualisation Sharpe).
        rebalance_every: nombre de périodes entre deux rééquilibrages. 1 (défaut)
            = rééquilibrage à chaque période (turnover maximal). N > 1 tient les
            poids N périodes, ce qui réduit le turnover et les coûts — utile pour
            un signal lent comme le momentum, sur-tradé en quotidien.
        no_trade_band: bande de non-transaction (cost-aware). 0 (défaut) = viser
            exactement le cible. > 0 : ne trader un actif que si son poids bouge de
            plus de ``no_trade_band`` — réduit le turnover (cf. ``cost_aware``).

    Returns:
        SignalEvalResult (IC, Sharpe brut/net, rendement net, turnover).
    """
    cost_model = cost_model or CostModel()
    rebalance_every = max(1, int(rebalance_every))

    # Aligner et décaler : le signal en t est évalué sur le rendement en t+1.
    scores, returns = scores.align(returns, join="inner")
    forward_returns = returns.shift(-1)

    # --- IC (qualité de tri, indépendant des coûts) ---
    ic = compute_cross_sectional_ic(scores, forward_returns)
    ics = ic_summary(ic)

    # --- Portefeuille long/short ajusté des coûts ---
    prev_w: Optional[pd.Series] = None
    gross_rets: List[float] = []
    net_rets: List[float] = []
    turnovers: List[float] = []
    idx: List[pd.Timestamp] = []

    steps = 0  # compteur de périodes retenues (hors dates sans rendement futur)
    for dt in scores.index:
        fwd = forward_returns.loc[dt]
        if fwd.isna().all():
            continue

        # Rééquilibrage seulement toutes les `rebalance_every` périodes ; sinon on
        # tient les poids précédents (aucun turnover, aucun coût entre-temps).
        if prev_w is None or steps % rebalance_every == 0:
            target = cross_sectional_weights(
                scores.loc[dt], quantile=quantile, long_short=long_short
            )
            if prev_w is None:
                turnover = float(target.abs().sum())  # mise en place initiale
            else:
                # Bande de non-transaction (cost-aware) : ne bouger que les poids
                # qui changent plus que la bande -> moins de turnover.
                if no_trade_band > 0:
                    target = apply_no_trade_band(target, prev_w, no_trade_band)
                aligned_prev = prev_w.reindex(target.index).fillna(0.0)
                turnover = float((target - aligned_prev).abs().sum())
            prev_w = target
        else:
            turnover = 0.0

        w = prev_w.reindex(fwd.index).fillna(0.0)
        gross = float((w * fwd.fillna(0.0)).sum())
        cost = turnover * cost_model.cost_rate

        gross_rets.append(gross)
        net_rets.append(gross - cost)
        turnovers.append(turnover)
        idx.append(dt)
        steps += 1

    gross_s = pd.Series(gross_rets, index=idx)
    net_s = pd.Series(net_rets, index=idx)

    net_equity = (1.0 + net_s).cumprod() if not net_s.empty else pd.Series(dtype=float)

    return SignalEvalResult(
        ic_mean=ics["mean"],
        ic_t_stat=ics["t_stat"],
        ic_hit_rate=ics["hit_rate"],
        gross_sharpe=_sharpe(gross_s, periods_per_year),
        net_sharpe=_sharpe(net_s, periods_per_year),
        gross_ann_return=_ann_return(gross_s, periods_per_year),
        net_ann_return=_ann_return(net_s, periods_per_year),
        avg_turnover=float(np.mean(turnovers)) if turnovers else 0.0,
        n_periods=len(net_s),
        net_equity_curve=net_equity,
    )


# Un fit_predict prend (scores_train, returns_train, scores_test) et renvoie un
# DataFrame de scores prédits alignés sur scores_test. Pour un signal brut, on
# passe l'identité (voir _identity_fit_predict).
FitPredict = Callable[[pd.DataFrame, pd.DataFrame, pd.DataFrame], pd.DataFrame]


def _identity_fit_predict(scores_train: pd.DataFrame, returns_train: pd.DataFrame, scores_test: pd.DataFrame) -> pd.DataFrame:
    """fit_predict trivial : renvoie le signal test tel quel (aucun apprentissage)."""
    return scores_test


def walk_forward_evaluate(
    scores: pd.DataFrame,
    returns: pd.DataFrame,
    fit_predict: Optional[FitPredict] = None,
    n_splits: int = 5,
    cost_model: Optional[CostModel] = None,
    quantile: float = 0.2,
    long_short: bool = True,
    periods_per_year: int = 252,
    rebalance_every: int = 1,
    no_trade_band: float = 0.0,
) -> Dict[str, object]:
    """Évaluation walk-forward strictement out-of-sample.

    Découpe le temps en n_splits fenêtres test contiguës ; pour chacune,
    `fit_predict` apprend sur tout le passé (expanding window) et produit les
    scores de la fenêtre test, évalués coûts inclus. Aucune information future
    ne fuit dans l'entraînement.

    Pour un signal brut, laisser fit_predict=None (identité) : on obtient la
    stabilité out-of-sample du signal. Pour le combinateur B, passer son
    fit_predict.

    Returns:
        dict avec 'oos' (SignalEvalResult agrégé sur la concat des fenêtres test),
        'per_window' (List[SignalEvalResult]) et 'n_splits'.
    """
    fit_predict = fit_predict or _identity_fit_predict
    cost_model = cost_model or CostModel()

    scores, returns = scores.align(returns, join="inner")
    dates = scores.index
    n = len(dates)
    if n < (n_splits + 1) * 5:
        raise ValueError(
            f"Historique trop court ({n} dates) pour {n_splits} fenêtres walk-forward."
        )

    # Première fenêtre d'entraînement = premier bloc ; puis test sur blocs suivants.
    fold_size = n // (n_splits + 1)
    per_window: List[SignalEvalResult] = []
    oos_scores_parts: List[pd.DataFrame] = []

    for i in range(1, n_splits + 1):
        train_end = fold_size * i
        test_end = fold_size * (i + 1) if i < n_splits else n
        train_idx = dates[:train_end]
        test_idx = dates[train_end:test_end]
        if len(test_idx) < 5:
            continue

        predicted = fit_predict(
            scores.loc[train_idx], returns.loc[train_idx], scores.loc[test_idx]
        )
        predicted = predicted.reindex(index=test_idx, columns=scores.columns)
        oos_scores_parts.append(predicted)

        res = evaluate_signal(
            predicted, returns.loc[test_idx], cost_model=cost_model,
            quantile=quantile, long_short=long_short, periods_per_year=periods_per_year,
            rebalance_every=rebalance_every, no_trade_band=no_trade_band,
        )
        per_window.append(res)

    # Agrégat OOS : évaluation sur la concaténation de toutes les fenêtres test.
    oos_scores = pd.concat(oos_scores_parts) if oos_scores_parts else pd.DataFrame()
    oos = evaluate_signal(
        oos_scores, returns.reindex(oos_scores.index), cost_model=cost_model,
        quantile=quantile, long_short=long_short, periods_per_year=periods_per_year,
        rebalance_every=rebalance_every, no_trade_band=no_trade_band,
    ) if not oos_scores.empty else None

    return {"oos": oos, "per_window": per_window, "n_splits": len(per_window)}

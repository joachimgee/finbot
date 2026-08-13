"""Détection de régime de marché par **HMM gaussien** (2 états), sans look-ahead.

`PORTFOLIO_PRO_RESEARCH` : détecter les régimes (calme/turbulent) et moduler
l'exposition — momentum en trend, prudence en stress. On modélise le rendement
marché par un HMM gaussien à 2 états latents (typiquement *calme/bull* à faible vol
et *turbulent/bear* à forte vol), estimé par Baum-Welch (EM) en numpy pur — pas de
dépendance (``hmmlearn`` absent).

⚠️ **Anti-look-ahead** : le décodage Viterbi/lissé (``predict``) utilise *toute* la
série (passé + futur) → interdit pour trader. On expose donc le **filtre avant**
(forward) : la probabilité d'état à t n'utilise que les rendements ≤ t. Pour une
série exploitable, on **gèle** le modèle sur une fenêtre d'apprentissage passée puis
on filtre en avant (causal).

Responsabilité unique : estimer le régime. Aucune décision de trading ici ;
l'overlay d'exposition (``exposure_scalar`` / le pipeline) le consomme.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.special import logsumexp

__all__ = [
    "GaussianHMM2",
    "fit_gaussian_hmm",
    "regime_risk_series",
]


class GaussianHMM2:
    """HMM gaussien à ``n_states`` états sur une série 1-D (rendements marché)."""

    def __init__(self, pi, trans, mu, var):
        self.pi = np.asarray(pi, float)
        self.trans = np.asarray(trans, float)
        self.mu = np.asarray(mu, float)
        self.var = np.asarray(var, float)

    @property
    def high_vol_state(self) -> int:
        """Indice de l'état le plus volatil (le régime « turbulent/risk-off »)."""
        return int(np.argmax(self.var))

    def _log_emission(self, x: np.ndarray) -> np.ndarray:
        # (T × K) log N(x_t ; mu_k, var_k)
        v = self.var[None, :]
        return -0.5 * np.log(2 * np.pi * v) - 0.5 * (x[:, None] - self.mu[None, :]) ** 2 / v

    def filtered_proba(self, x: np.ndarray) -> np.ndarray:
        """Probabilités d'état **filtrées** (causales) : ``P(état_t | x_{0..t})``.

        Forward pass normalisé uniquement — aucune information future. (T × K).
        """
        x = np.asarray(x, float)
        logb = self._log_emission(x)
        logt = np.log(self.trans + 1e-12)
        t_n = len(x)
        k = len(self.pi)
        out = np.zeros((t_n, k))
        log_alpha = np.log(self.pi + 1e-12) + logb[0]
        out[0] = np.exp(log_alpha - logsumexp(log_alpha))
        for t in range(1, t_n):
            log_alpha = logsumexp(log_alpha[:, None] + logt, axis=0) + logb[t]
            out[t] = np.exp(log_alpha - logsumexp(log_alpha))
        return out


def fit_gaussian_hmm(
    returns, n_states: int = 2, n_iter: int = 100, tol: float = 1e-4, seed: int = 0,
) -> GaussianHMM2:
    """Estime un HMM gaussien par Baum-Welch (EM). numpy pur, stable en log.

    Init déterministe par quantiles (états ordonnés du calme au volatil) pour une
    labellisation reproductible. Renvoie un :class:`GaussianHMM2`.
    """
    x = np.asarray(returns, float)
    x = x[~np.isnan(x)]
    if len(x) < 20:
        raise ValueError("Historique trop court pour estimer un HMM (< 20 points).")
    k = n_states
    # Init par quantiles : moyennes étalées, variances = variance globale.
    mu = np.quantile(x, np.linspace(0.25, 0.75, k))
    var = np.full(k, max(x.var(), 1e-8))
    trans = np.full((k, k), 0.1 / max(k - 1, 1))
    np.fill_diagonal(trans, 0.9)
    pi = np.full(k, 1.0 / k)
    model = GaussianHMM2(pi, trans, mu, var)

    prev_ll = -np.inf
    for _ in range(n_iter):
        logb = model._log_emission(x)
        logt = np.log(model.trans + 1e-12)
        t_n = len(x)
        # Forward
        log_alpha = np.zeros((t_n, k))
        log_alpha[0] = np.log(model.pi + 1e-12) + logb[0]
        for t in range(1, t_n):
            log_alpha[t] = logsumexp(log_alpha[t - 1][:, None] + logt, axis=0) + logb[t]
        ll = logsumexp(log_alpha[-1])
        # Backward
        log_beta = np.zeros((t_n, k))
        for t in range(t_n - 2, -1, -1):
            log_beta[t] = logsumexp(logt + (logb[t + 1] + log_beta[t + 1])[None, :], axis=1)
        # Posteriors gamma (T×K)
        log_gamma = log_alpha + log_beta
        log_gamma -= logsumexp(log_gamma, axis=1, keepdims=True)
        gamma = np.exp(log_gamma)
        # xi (transitions) agrégé sur t
        xi_sum = np.zeros((k, k))
        for t in range(t_n - 1):
            m = (log_alpha[t][:, None] + logt
                 + (logb[t + 1] + log_beta[t + 1])[None, :])
            m -= logsumexp(m)
            xi_sum += np.exp(m)
        # M-step
        pi = gamma[0] + 1e-12
        pi /= pi.sum()
        trans = xi_sum / xi_sum.sum(axis=1, keepdims=True).clip(1e-12)
        w = gamma.sum(axis=0).clip(1e-12)
        mu = (gamma * x[:, None]).sum(axis=0) / w
        var = (gamma * (x[:, None] - mu[None, :]) ** 2).sum(axis=0) / w
        var = var.clip(1e-10)
        model = GaussianHMM2(pi, trans, mu, var)
        if abs(ll - prev_ll) < tol:
            break
        prev_ll = ll
    return model


def regime_risk_series(
    prices: pd.DataFrame,
    warmup: int = 252,
    refit_every: int = 63,
    risk_off_factor: float = 0.5,
    seed: int = 0,
) -> pd.Series:
    """Série d'exposition ∈ ``[risk_off_factor, 1]`` pilotée par le régime, **causale**.

    Marché = rendement équipondéré de l'univers. Le HMM est ré-estimé tous les
    ``refit_every`` jours **sur le passé uniquement**, puis on filtre en avant : à t,
    ``exposition = 1 − (1 − risk_off_factor)·P(état turbulent | ≤ t)``. Pleine
    exposition en régime calme, réduite en régime volatil. Warm-up → exposition 1.0
    (pas de réduction fabriquée). Aucune fuite du futur.
    """
    if prices.empty:
        return pd.Series(dtype=float)
    mkt = prices.pct_change().mean(axis=1)
    idx = mkt.index
    mkt_v = mkt.to_numpy()
    exposure = np.ones(len(idx))
    model: GaussianHMM2 | None = None
    for i in range(len(idx)):
        if i < warmup:
            continue
        if model is None or (i - warmup) % refit_every == 0:
            train = mkt_v[max(0, i - warmup): i]  # passé strict (exclut t)
            train = train[~np.isnan(train)]
            try:
                model = fit_gaussian_hmm(train, seed=seed)
            except Exception:  # noqa: BLE001 - régime indisponible -> pleine exposition
                model = None
        if model is None:
            continue
        seq = mkt_v[max(0, i - warmup): i + 1]  # ≤ t (inclut t)
        seq = seq[~np.isnan(seq)]
        if len(seq) < 5:
            continue
        p_high = float(model.filtered_proba(seq)[-1, model.high_vol_state])
        exposure[i] = 1.0 - (1.0 - risk_off_factor) * p_high
    return pd.Series(exposure, index=idx)

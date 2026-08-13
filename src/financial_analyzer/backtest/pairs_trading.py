"""Stat-arb par paires (mean-reversion sur spreads cointégrés) — famille décorrélée.

Loi de Grinold-Kahn : la breadth vient de paris *indépendants*. Le momentum est une
famille ; le **stat-arb par paires** en est une **autre**, structurellement
décorrélée (on parie sur le *retour à la moyenne* de l'écart entre deux titres
cointégrés, pas sur une tendance).

Pipeline **walk-forward, sans look-ahead** :

1. **Formation** (fenêtre passée) : pré-filtre par corrélation, test de
   **cointégration** (Engle-Granger), ratio de couverture β (OLS) *gelé*, demi-vie
   de retour à la moyenne (AR(1)). On garde les meilleures paires.
2. **Trading** (fenêtre suivante) : spread = a − β·b ; **z-score glissant causal** ;
   short le spread si z > entrée, long si z < −entrée ; sortie quand |z| < exit,
   stop si |z| > stop. Dollar-neutre, coûts sur le turnover.

Responsabilité unique : produire la série de rendements nets de la stratégie paires.
Validation/décorrélation mesurées en aval (scripts) — via le portail comme tout signal.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "backtest_pairs",
    "find_cointegrated_pairs",
    "half_life",
    "hedge_ratio",
]


def hedge_ratio(a: pd.Series, b: pd.Series) -> float:
    """Ratio de couverture β : pente OLS de ``a`` sur ``b`` (avec constante)."""
    x = np.vstack([np.ones(len(b)), b.to_numpy()]).T
    beta = np.linalg.lstsq(x, a.to_numpy(), rcond=None)[0]
    return float(beta[1])


def half_life(spread: pd.Series) -> float:
    """Demi-vie de retour à la moyenne (Ornstein-Uhlenbeck via AR(1)).

    ``Δs_t = λ·s_{t-1} + c`` ; demi-vie ``= −ln 2 / λ`` (``+inf`` si non convergent).
    """
    s = pd.Series(spread).dropna()
    if len(s) < 10:
        return float("inf")
    lag = s.shift(1).dropna()
    ds = (s - s.shift(1)).dropna()
    lag, ds = lag.align(ds, join="inner")
    x = np.vstack([np.ones(len(lag)), lag.to_numpy()]).T
    lam = np.linalg.lstsq(x, ds.to_numpy(), rcond=None)[0][1]
    if lam >= 0:
        return float("inf")  # pas de retour à la moyenne
    return float(-np.log(2) / lam)


def find_cointegrated_pairs(
    prices: pd.DataFrame,
    *,
    pvalue_max: float = 0.05,
    corr_min: float = 0.7,
    max_pairs: int = 10,
    hl_min: float = 2.0,
    hl_max: float = 120.0,
) -> list[dict]:
    """Sélectionne des paires **cointégrées** (Engle-Granger) sur la fenêtre fournie.

    Pré-filtre par corrélation (rapide) puis test de cointégration ; garde les paires
    dont la demi-vie est raisonnable (ni trop rapide/bruit, ni trop lente). Renvoie
    une liste triée par p-value croissante : ``{a, b, beta, pvalue, half_life}``.
    """
    from statsmodels.tsa.stattools import coint

    px = prices.dropna(axis=1, how="any")
    cols = list(px.columns)
    if len(cols) < 2:
        return []
    corr = px.pct_change().corr()
    out: list[dict] = []
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            a_n, b_n = cols[i], cols[j]
            if abs(corr.loc[a_n, b_n]) < corr_min:
                continue
            a, b = px[a_n], px[b_n]
            try:
                _, pval, _ = coint(a, b)
            except Exception:  # noqa: BLE001 - paire dégénérée -> ignorée
                continue
            if pval > pvalue_max:
                continue
            beta = hedge_ratio(a, b)
            hl = half_life(a - beta * b)
            if not (hl_min <= hl <= hl_max):
                continue
            out.append({"a": a_n, "b": b_n, "beta": beta, "pvalue": pval, "half_life": hl})
    out.sort(key=lambda d: d["pvalue"])
    return out[:max_pairs]


def _pair_returns(
    a: pd.Series, b: pd.Series, beta: float,
    z_lookback: int, entry: float, exit_: float, stop: float,
) -> tuple[pd.Series, pd.Series]:
    """Rendements nets-de-signal d'une paire sur la fenêtre trading (dollar-neutre).

    z-score **causal** (moyenne/écart-type glissants décalés d'un pas). Machine à
    états flat/long/short. Le rendement à t utilise la position détenue à t−1.
    """
    spread = a - beta * b
    mean = spread.rolling(z_lookback).mean().shift(1)
    std = spread.rolling(z_lookback).std(ddof=1).shift(1)
    z = (spread - mean) / std
    r_a = a.pct_change()
    r_b = b.pct_change()
    gross = 1.0 + abs(beta)
    pair_ret = (r_a - beta * r_b) / gross  # rendement du spread (long a / short β·b)

    pos = 0
    positions = np.zeros(len(z))
    zv = z.to_numpy()
    for t in range(len(zv)):
        zt = zv[t]
        if not np.isfinite(zt):
            positions[t] = pos
            continue
        if pos == 0:
            if zt > entry:
                pos = -1          # spread trop haut -> short spread
            elif zt < -entry:
                pos = 1           # spread trop bas -> long spread
        elif abs(zt) < exit_ or abs(zt) > stop:
            pos = 0               # sortie (retour moyenne) ou stop (divergence)
        positions[t] = pos
    pos_s = pd.Series(positions, index=z.index)
    return (pos_s.shift(1) * pair_ret).fillna(0.0), pos_s


def backtest_pairs(
    prices: pd.DataFrame,
    *,
    form: int = 252,
    trade: int = 63,
    z_lookback: int = 21,
    entry: float = 2.0,
    exit_: float = 0.5,
    stop: float = 4.0,
    max_pairs: int = 10,
    cost_rate: float = 0.00025,
    **select_kwargs,
) -> dict:
    """Backtest walk-forward de la stratégie paires. Renvoie un dict de résultats.

    Sélection des paires **sur le passé** (fenêtre ``form``), trading sur la fenêtre
    ``trade`` suivante, roulé. Rendement du book = moyenne équipondérée des paires
    actives ; coûts sur le turnover (changements de position).
    """
    dates = prices.index
    book_rets = pd.Series(0.0, index=dates)
    n_pairs_hist: list[int] = []
    i = form
    while i + 1 < len(dates):
        end = min(i + trade, len(dates))
        form_px = prices.iloc[i - form: i]
        pairs = find_cointegrated_pairs(form_px, max_pairs=max_pairs, **select_kwargs)
        n_pairs_hist.append(len(pairs))
        if pairs:
            # Fenêtre trading + amorce z_lookback (pour un z-score défini dès le début).
            win = prices.iloc[max(0, i - z_lookback): end]
            legs = []
            for p in pairs:
                r, pos = _pair_returns(win[p["a"]], win[p["b"]], p["beta"],
                                       z_lookback, entry, exit_, stop)
                r = r.loc[dates[i]: dates[end - 1]]
                pos = pos.loc[dates[i]: dates[end - 1]]
                turn = pos.diff().abs().fillna(0.0)
                legs.append(r - turn * cost_rate)  # net de coûts sur le turnover
            if legs:
                book_rets.loc[dates[i]: dates[end - 1]] = pd.concat(legs, axis=1).mean(axis=1)
        i = end

    net = book_rets.loc[dates[form]:]
    sd = net.std(ddof=1)
    sharpe = float(net.mean() / sd * np.sqrt(252)) if sd > 0 else 0.0
    eq = (1.0 + net.fillna(0.0)).cumprod()
    maxdd = float(((eq / eq.cummax()) - 1.0).min() * 100.0) if len(eq) else 0.0
    return {
        "net_returns": net,
        "sharpe": sharpe,
        "max_drawdown_pct": maxdd,
        "ann_return_pct": float(net.mean() * 252 * 100.0),
        "avg_pairs": float(np.mean(n_pairs_hist)) if n_pairs_hist else 0.0,
        "n_windows": len(n_pairs_hist),
    }

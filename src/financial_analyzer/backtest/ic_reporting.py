from __future__ import annotations
from typing import Dict, Literal, Optional
import numpy as np
import pandas as pd


def compute_cross_sectional_ic(
    factor_scores: pd.DataFrame,
    forward_returns: pd.DataFrame,
    method: Literal["spearman", "pearson"] = "spearman",
) -> pd.Series:
    """
    Calcule l'IC cross-sectionnel par date entre scores factoriels et rendements futurs.

    Args:
        factor_scores: DataFrame (dates x actifs) de scores factorielles alignés
        forward_returns: DataFrame (dates x actifs) de rendements futurs alignés
        method: corrélation à utiliser (spearman ou pearson)

    Returns:
        Series indexée par date avec l'IC (correlation) cross-sectionnel
    """
    factors = factor_scores.reindex_like(forward_returns)
    ics = []
    dates = []
    for dt in forward_returns.index:
        f = factors.loc[dt]
        r = forward_returns.loc[dt]
        mask = ~(f.isna() | r.isna())
        f = f[mask]
        r = r[mask]
        if len(f) < 3:
            ics.append(np.nan)
            dates.append(dt)
            continue
        if method == "spearman":
            rho = f.rank().corr(r.rank())
        else:
            rho = f.corr(r)
        ics.append(float(rho) if rho is not None else np.nan)
        dates.append(dt)
    return pd.Series(ics, index=pd.Index(dates, name="date"))


def ic_summary(ic_series: pd.Series) -> Dict[str, float]:
    ic = ic_series.dropna()
    return {
        "mean": float(ic.mean()) if not ic.empty else np.nan,
        "std": float(ic.std(ddof=1)) if len(ic) > 1 else np.nan,
        "t_stat": float(ic.mean() / (ic.std(ddof=1) / np.sqrt(len(ic)))) if len(ic) > 2 and ic.std(ddof=1) > 0 else np.nan,
        "hit_rate": float((ic > 0).mean()) if not ic.empty else np.nan,
    }


def compute_ic_decay(
    factor_scores: pd.DataFrame,
    returns: pd.DataFrame,
    max_horizon: int = 5,
    method: Literal["spearman", "pearson"] = "spearman",
) -> pd.Series:
    """
    IC decay: IC(h) pour h=1..max_horizon (retours décalés de h périodes).
    """
    vals = []
    for h in range(1, int(max_horizon) + 1):
        fwd = returns.shift(-h)
        ic_h = compute_cross_sectional_ic(factor_scores, fwd, method=method)
        vals.append(ic_h.mean())
    return pd.Series(vals, index=pd.Index(range(1, max_horizon + 1), name="h"))


def generate_ic_report_html(ic: pd.Series, decay: Optional[pd.Series] = None) -> str:
    mean = ic.dropna().mean() if not ic.empty else np.nan
    hit = (ic.dropna() > 0).mean() if not ic.empty else np.nan
    rows = [f"<p>IC mean: {mean:.4f} | hit-rate: {hit:.2%}</p>"]
    if decay is not None and not decay.empty:
        tbl = "".join([f"<tr><td>{int(h)}</td><td>{val:.4f}</td></tr>" for h, val in decay.dropna().items()])
        rows.append(f"<table><thead><tr><th>H</th><th>IC</th></tr></thead><tbody>{tbl}</tbody></table>")
    return "\n".join(rows)

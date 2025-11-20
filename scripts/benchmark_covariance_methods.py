#!/usr/bin/env python3
"""
Benchmark covariance and returns estimators across universe sizes.

- Methods: sample (pandas), Ledoit-Wolf, OAS (Oracle Approximating Shrinkage)
- Returns estimators: mean-historical, exponentially-weighted
- Universe sizes: 50, 100, 250, 500, 1000
- Periods: 252, 504

Usage:
    python scripts/benchmark_covariance_methods.py --sizes 50,100,250 --periods 252 --seed 42

Notes:
- Runs offline with synthetic data; no network required.
- Focus on timing and numerical sanity (PSD and condition number range).
"""

from __future__ import annotations
import argparse
import time
from typing import List, Tuple
import numpy as np
import pandas as pd
from sklearn.covariance import ledoit_wolf, OAS


def gen_returns(n_periods: int, n_assets: int, seed: int = 42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    # Generate positive semi-definite covariance via random matrix
    A = rng.normal(size=(n_assets, n_assets))
    cov = A @ A.T / n_assets * 1e-4
    mu = rng.normal(0.0005, 0.0002, size=n_assets)
    rets = rng.multivariate_normal(mu, cov, size=n_periods)
    idx = pd.date_range("2020-01-01", periods=n_periods, freq="B")
    cols = [f"A{i:04d}" for i in range(n_assets)]
    return pd.DataFrame(rets, index=idx, columns=cols)


def est_cov_sample(X: np.ndarray) -> np.ndarray:
    return np.cov(X, rowvar=False)


def est_cov_ledoit_wolf(X: np.ndarray) -> np.ndarray:
    cov, _ = ledoit_wolf(X)
    return cov


def est_cov_oas(X: np.ndarray) -> np.ndarray:
    model = OAS().fit(X)
    return model.covariance_


def est_mu_hist(returns: pd.DataFrame) -> np.ndarray:
    return returns.mean().values


def est_mu_ewm(returns: pd.DataFrame, span: int = 60) -> np.ndarray:
    return returns.ewm(span=span).mean().iloc[-1].values


def cond_number(mat: np.ndarray) -> float:
    try:
        return float(np.linalg.cond(mat))
    except Exception:
        return float("inf")


def psd_check(mat: np.ndarray, tol: float = 1e-10) -> bool:
    try:
        # symmetric
        M = 0.5 * (mat + mat.T)
        eigs = np.linalg.eigvalsh(M)
        return bool(np.all(eigs >= -tol))
    except Exception:
        return False


def bench_one(returns: pd.DataFrame) -> List[Tuple[str, float, float, bool]]:
    X = returns.values
    results = []

    for name, fn in (
        ("sample", est_cov_sample),
        ("ledoit_wolf", est_cov_ledoit_wolf),
        ("oas", est_cov_oas),
    ):
        t0 = time.perf_counter()
        cov = fn(X)
        dt = time.perf_counter() - t0
        results.append((name, dt, cond_number(cov), psd_check(cov)))

    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", type=str, default="50,100,250,500,1000")
    parser.add_argument("--periods", type=int, default=252)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    sizes = [int(x) for x in args.sizes.split(",") if x.strip()]
    periods = args.periods

    print("\n=== Covariance Benchmark ===")
    print(f"Periods={periods}, Sizes={sizes}")

    for n in sizes:
        returns = gen_returns(periods, n, seed=args.seed)
        rows = bench_one(returns)
        print(f"\nN={n}")
        for name, dt, kappa, is_psd in rows:
            print(f"- {name:12s}  time={dt:7.3f}s  cond={kappa:10.2f}  psd={is_psd}")

    print("\nDone.")


if __name__ == "__main__":
    main()

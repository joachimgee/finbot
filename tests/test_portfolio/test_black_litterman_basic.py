import numpy as np
import pandas as pd
from financial_analyzer.portfolio.optimizer import PortfolioOptimizer
from financial_analyzer.portfolio.constraints import PortfolioConstraints


def _toy_returns(seed=0):
    rng = np.random.default_rng(seed)
    n = 200
    cols = ["A", "B", "C", "D"]
    ret = rng.normal(0.0005, 0.01, size=(n, len(cols)))
    df = pd.DataFrame(ret, columns=cols)
    return df


def test_black_litterman_increases_view_asset_weight():
    ret = _toy_returns()
    opt = PortfolioOptimizer(returns=ret, risk_free_rate=0.0)

    # Vue: activer B avec return attendu accru
    views = {"B": 0.20}  # 20% annuel
    res_base = opt._optimize_max_sharpe_mv()
    w_base = res_base["weights"]

    res_bl = opt.optimize_black_litterman(views=views, confidences={"B": 0.8}, tau=0.05)
    w_bl = res_bl["weights"]

    assert w_bl["B"] > w_base["B"]
    assert abs(w_bl.sum() - 1.0) < 1e-6


def test_black_litterman_respects_sector_caps():
    ret = _toy_returns()
    opt = PortfolioOptimizer(returns=ret, risk_free_rate=0.0)
    cons = PortfolioConstraints(sector_mapping={"A": "tech", "B": "tech", "C": "fin", "D": "fin"})
    cons.add_sector_constraint("tech", 0.30)
    opt.add_constraint(cons)

    views = {"A": 0.30, "B": 0.30}
    res_bl = opt.optimize_black_litterman(views=views, confidences={"A": 0.9, "B": 0.9})
    w_bl = res_bl["weights"]
    assert (w_bl[["A", "B"]].sum() - 0.30) <= 1e-3

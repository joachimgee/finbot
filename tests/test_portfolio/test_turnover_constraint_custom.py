import numpy as np
import pandas as pd
from financial_analyzer.portfolio.optimizer import PortfolioOptimizer
from financial_analyzer.portfolio.constraints import PortfolioConstraints


def test_turnover_constraint_limits_change():
    rng = np.random.default_rng(0)
    ret = pd.DataFrame(rng.normal(0.001, 0.01, size=(150, 4)), columns=["A","B","C","D"]) 
    opt = PortfolioOptimizer(returns=ret)
    # Première optimisation
    w0 = opt._optimize_max_sharpe_mv()["weights"]

    # Ajoute turnover <= 0.4
    cons = PortfolioConstraints()
    cons.add_turnover_limit(w0, max_turnover=0.4)
    opt.add_constraint(cons)

    w1 = opt._optimize_max_sharpe_mv()["weights"]
    turnover = float((w1 - w0).abs().sum())
    assert turnover <= 0.4005

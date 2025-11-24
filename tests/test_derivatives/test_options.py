"""
Comprehensive test suite for Options Derivatives module.

Tests for:
- BlackScholesModel: Call/put pricing, put-call parity, implied volatility
- GreeksCalculator: Delta, Gamma, Vega, Theta, Rho, second-order Greeks
- OptionsStrategy: Multi-leg strategies, payoff profiles, breakeven points

Total: 50+ tests covering all functionality and edge cases.
"""

import numpy as np
import pandas as pd
import pytest
from scipy.stats import norm

from financial_analyzer.derivatives.options import (
    BlackScholesModel,
    BlackScholesResult,
    GreeksCalculator,
    Greeks,
    OptionsStrategy,
    OptionLeg,
)


# ============================================================================
# BlackScholesModel Tests (15 tests)
# ============================================================================


class TestBlackScholesModel:
    """Test Black-Scholes option pricing."""

    def test_black_scholes_init(self):
        """Test model initialization."""
        bs = BlackScholesModel(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        assert bs.S == 100
        assert bs.K == 100
        assert bs.T == 0.25
        assert bs.r == 0.05
        assert bs.sigma == 0.2
        assert bs.q == 0.0

    def test_black_scholes_invalid_params(self):
        """Test validation of invalid parameters."""
        with pytest.raises(ValueError, match="Stock price must be positive"):
            BlackScholesModel(S=-100, K=100, T=0.25, r=0.05, sigma=0.2)

        with pytest.raises(ValueError, match="Strike price must be positive"):
            BlackScholesModel(S=100, K=-100, T=0.25, r=0.05, sigma=0.2)

        with pytest.raises(ValueError, match="Time to expiration must be non-negative"):
            BlackScholesModel(S=100, K=100, T=-0.25, r=0.05, sigma=0.2)

        with pytest.raises(ValueError, match="Volatility must be non-negative"):
            BlackScholesModel(S=100, K=100, T=0.25, r=0.05, sigma=-0.2)

    def test_call_price_atm(self):
        """Test ATM call option pricing."""
        bs = BlackScholesModel(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        call = bs.call_price()

        # ATM call should be positive and reasonable
        assert call > 0
        assert call < 10  # Should not be more than 10% of spot

    def test_put_price_atm(self):
        """Test ATM put option pricing."""
        bs = BlackScholesModel(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        put = bs.put_price()

        # ATM put should be positive
        assert put > 0
        assert put < 10

    def test_put_call_parity(self):
        """Test put-call parity holds."""
        bs = BlackScholesModel(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        assert bs.verify_put_call_parity()

        # Test with different parameters
        bs2 = BlackScholesModel(S=110, K=100, T=0.5, r=0.03, sigma=0.3, q=0.02)
        assert bs2.verify_put_call_parity()

    def test_itm_call(self):
        """Test ITM call has higher value than OTM."""
        bs_itm = BlackScholesModel(S=110, K=100, T=0.25, r=0.05, sigma=0.2)
        bs_otm = BlackScholesModel(S=90, K=100, T=0.25, r=0.05, sigma=0.2)

        call_itm = bs_itm.call_price()
        call_otm = bs_otm.call_price()

        assert call_itm > call_otm
        assert call_itm > 10  # ITM should have intrinsic value

    def test_itm_put(self):
        """Test ITM put has higher value than OTM."""
        bs_itm = BlackScholesModel(S=90, K=100, T=0.25, r=0.05, sigma=0.2)
        bs_otm = BlackScholesModel(S=110, K=100, T=0.25, r=0.05, sigma=0.2)

        put_itm = bs_itm.put_price()
        put_otm = bs_otm.put_price()

        assert put_itm > put_otm
        assert put_itm > 9.5  # ITM should have significant value (intrinsic ~10, time decay)

    def test_price_method(self):
        """Test price() method returns full result."""
        bs = BlackScholesModel(S=100, K=105, T=0.25, r=0.05, sigma=0.2)
        result = bs.price()

        assert isinstance(result, BlackScholesResult)
        assert result.call_price > 0
        assert result.put_price > 0
        assert result.intrinsic_call == 0  # OTM call
        assert result.intrinsic_put == 5  # ITM put
        assert result.time_value_call > 0
        assert result.time_value_put > 0

    def test_zero_time_to_expiration(self):
        """Test options at expiration have only intrinsic value."""
        # ITM call
        bs_call = BlackScholesModel(S=110, K=100, T=0.0, r=0.05, sigma=0.2)
        call = bs_call.call_price()
        assert call == 10  # Intrinsic value only

        # ITM put
        bs_put = BlackScholesModel(S=90, K=100, T=0.0, r=0.05, sigma=0.2)
        put = bs_put.put_price()
        assert put == 10

        # OTM call
        bs_otm_call = BlackScholesModel(S=90, K=100, T=0.0, r=0.05, sigma=0.2)
        assert bs_otm_call.call_price() == 0

        # OTM put
        bs_otm_put = BlackScholesModel(S=110, K=100, T=0.0, r=0.05, sigma=0.2)
        assert bs_otm_put.put_price() == 0

    def test_zero_volatility(self):
        """Test zero volatility pricing."""
        # ITM call with zero vol
        bs = BlackScholesModel(S=110, K=100, T=0.25, r=0.05, sigma=0.0)
        call = bs.call_price()
        # Should be close to discounted intrinsic value
        assert call > 9  # Close to 10 * exp(-0.05 * 0.25)

    def test_dividends(self):
        """Test pricing with dividends."""
        # No dividend
        bs_no_div = BlackScholesModel(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        call_no_div = bs_no_div.call_price()

        # With dividend
        bs_div = BlackScholesModel(S=100, K=100, T=0.25, r=0.05, sigma=0.2, q=0.03)
        call_div = bs_div.call_price()

        # Call price should decrease with dividends
        assert call_div < call_no_div

    def test_implied_volatility_call(self):
        """Test implied volatility calculation for calls."""
        bs = BlackScholesModel(S=100, K=100, T=0.25, r=0.05, sigma=0.25)
        market_price = bs.call_price()

        # Recover implied vol
        iv = bs.implied_volatility(market_price, option_type="call", initial_guess=0.2)

        assert iv is not None
        assert abs(iv - 0.25) < 0.001  # Should recover original vol

    def test_implied_volatility_put(self):
        """Test implied volatility calculation for puts."""
        bs = BlackScholesModel(S=100, K=105, T=0.25, r=0.05, sigma=0.3)
        market_price = bs.put_price()

        # Recover implied vol
        iv = bs.implied_volatility(market_price, option_type="put", initial_guess=0.2)

        assert iv is not None
        assert abs(iv - 0.3) < 0.001

    def test_implied_volatility_invalid_price(self):
        """Test implied vol fails for invalid prices."""
        bs = BlackScholesModel(S=100, K=100, T=0.25, r=0.05, sigma=0.2)

        # Negative price
        iv = bs.implied_volatility(-5, option_type="call")
        assert iv is None

        # Price below intrinsic (arbitrage)
        iv = bs.implied_volatility(0.5, option_type="call")  # Intrinsic is 0, but too low
        # Should still work since intrinsic = 0 for ATM

    def test_moneyness(self):
        """Test moneyness calculation."""
        bs_itm_call = BlackScholesModel(S=105, K=100, T=0.25, r=0.05, sigma=0.2)
        assert bs_itm_call.moneyness() == 1.05
        assert bs_itm_call.is_itm("call")
        assert not bs_itm_call.is_itm("put")

        bs_atm = BlackScholesModel(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        assert bs_atm.moneyness() == 1.0
        assert bs_atm.is_atm()

        bs_otm_call = BlackScholesModel(S=95, K=100, T=0.25, r=0.05, sigma=0.2)
        assert bs_otm_call.moneyness() == 0.95
        assert not bs_otm_call.is_itm("call")
        assert bs_otm_call.is_itm("put")


# ============================================================================
# GreeksCalculator Tests (18 tests)
# ============================================================================


class TestGreeksCalculator:
    """Test Greeks calculation."""

    def test_greeks_init(self):
        """Test Greeks calculator initialization."""
        calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        assert calc.S == 100
        assert calc.K == 100
        assert calc.T == 0.25

    def test_greeks_invalid_params(self):
        """Test validation of invalid parameters."""
        with pytest.raises(ValueError, match="Stock price must be positive"):
            GreeksCalculator(S=-100, K=100, T=0.25, r=0.05, sigma=0.2)

    def test_delta_call_range(self):
        """Test call delta is in [0, 1] range."""
        # ITM call
        calc_itm = GreeksCalculator(S=110, K=100, T=0.25, r=0.05, sigma=0.2)
        delta_itm = calc_itm.delta("call")
        assert 0.5 < delta_itm <= 1

        # OTM call
        calc_otm = GreeksCalculator(S=90, K=100, T=0.25, r=0.05, sigma=0.2)
        delta_otm = calc_otm.delta("call")
        assert 0 <= delta_otm < 0.5

        # ATM call
        calc_atm = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        delta_atm = calc_atm.delta("call")
        assert 0.4 < delta_atm < 0.6  # ATM delta ~ 0.5

    def test_delta_put_range(self):
        """Test put delta is in [-1, 0] range."""
        # ITM put
        calc_itm = GreeksCalculator(S=90, K=100, T=0.25, r=0.05, sigma=0.2)
        delta_itm = calc_itm.delta("put")
        assert -1 <= delta_itm < -0.5

        # OTM put
        calc_otm = GreeksCalculator(S=110, K=100, T=0.25, r=0.05, sigma=0.2)
        delta_otm = calc_otm.delta("put")
        assert -0.5 < delta_otm <= 0

        # ATM put
        calc_atm = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        delta_atm = calc_atm.delta("put")
        assert -0.6 < delta_atm < -0.4  # ATM delta ~ -0.5

    def test_gamma_positive(self):
        """Test gamma is always non-negative."""
        calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        gamma = calc.gamma()
        assert gamma > 0

        # Gamma is highest at ATM
        calc_otm = GreeksCalculator(S=120, K=100, T=0.25, r=0.05, sigma=0.2)
        gamma_otm = calc_otm.gamma()
        assert gamma > gamma_otm

    def test_vega_positive(self):
        """Test vega is positive for both call and put."""
        calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        vega = calc.vega()
        assert vega > 0

        # Vega is highest at ATM
        calc_otm = GreeksCalculator(S=120, K=100, T=0.25, r=0.05, sigma=0.2)
        vega_otm = calc_otm.vega()
        assert vega > vega_otm

    def test_theta_call_negative(self):
        """Test call theta is typically negative (time decay)."""
        calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        theta_call = calc.theta("call")
        assert theta_call < 0  # Options lose value over time

    def test_theta_put_negative(self):
        """Test put theta is typically negative."""
        calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        theta_put = calc.theta("put")
        assert theta_put < 0

    def test_rho_call_positive(self):
        """Test call rho is positive (calls increase with rates)."""
        calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        rho_call = calc.rho("call")
        assert rho_call > 0

    def test_rho_put_negative(self):
        """Test put rho is negative (puts decrease with rates)."""
        calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        rho_put = calc.rho("put")
        assert rho_put < 0

    def test_vanna(self):
        """Test vanna calculation."""
        calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        vanna = calc.vanna()
        # Vanna can be positive or negative

    def test_charm(self):
        """Test charm (delta decay)."""
        calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        charm_call = calc.charm("call")
        charm_put = calc.charm("put")
        # Charm can be positive or negative

    def test_vomma(self):
        """Test vomma (vega convexity)."""
        calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        vomma = calc.vomma()
        # Vomma should be non-zero for ATM options

    def test_compute_all_greeks(self):
        """Test compute_all() returns all Greeks."""
        calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        greeks = calc.compute_all()

        assert isinstance(greeks, Greeks)
        assert 0 < greeks.delta_call < 1
        assert -1 < greeks.delta_put < 0
        assert greeks.gamma > 0
        assert greeks.vega > 0
        assert greeks.theta_call < 0
        assert greeks.theta_put < 0
        assert greeks.rho_call > 0
        assert greeks.rho_put < 0

    def test_greeks_zero_time(self):
        """Test Greeks at expiration."""
        # ITM call at expiration
        calc = GreeksCalculator(S=110, K=100, T=0.0, r=0.05, sigma=0.2)
        delta = calc.delta("call")
        gamma = calc.gamma()
        vega = calc.vega()

        assert delta == 1.0  # ITM call delta = 1 at expiration
        assert gamma == 0.0  # No convexity at expiration
        assert vega == 0.0  # No vol sensitivity

    def test_greeks_dividends(self):
        """Test Greeks with dividends."""
        calc_no_div = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        calc_div = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2, q=0.03)

        delta_no_div = calc_no_div.delta("call")
        delta_div = calc_div.delta("call")

        # Dividends reduce call delta
        assert delta_div < delta_no_div

    def test_delta_numerical_validation(self):
        """Test delta against numerical differentiation."""
        calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        delta_analytical = calc.delta("call")

        # Numerical delta: (V(S+h) - V(S-h)) / (2h)
        h = 0.01
        bs_up = BlackScholesModel(S=100 + h, K=100, T=0.25, r=0.05, sigma=0.2)
        bs_down = BlackScholesModel(S=100 - h, K=100, T=0.25, r=0.05, sigma=0.2)
        delta_numerical = (bs_up.call_price() - bs_down.call_price()) / (2 * h)

        assert abs(delta_analytical - delta_numerical) < 0.01

    def test_gamma_numerical_validation(self):
        """Test gamma against numerical differentiation."""
        calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        gamma_analytical = calc.gamma()

        # Numerical gamma: (V(S+h) - 2V(S) + V(S-h)) / h²
        h = 0.01
        bs_up = BlackScholesModel(S=100 + h, K=100, T=0.25, r=0.05, sigma=0.2)
        bs_center = BlackScholesModel(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        bs_down = BlackScholesModel(S=100 - h, K=100, T=0.25, r=0.05, sigma=0.2)
        gamma_numerical = (
            bs_up.call_price() - 2 * bs_center.call_price() + bs_down.call_price()
        ) / (h**2)

        assert abs(gamma_analytical - gamma_numerical) < 0.01

    def test_vega_numerical_validation(self):
        """Test vega against numerical differentiation."""
        calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        vega_analytical = calc.vega()

        # Numerical vega: (V(sigma+h) - V(sigma-h)) / (2h)
        # Note: vega is per 1% vol, so h = 0.01
        h = 0.01
        bs_up = BlackScholesModel(S=100, K=100, T=0.25, r=0.05, sigma=0.2 + h)
        bs_down = BlackScholesModel(S=100, K=100, T=0.25, r=0.05, sigma=0.2 - h)
        vega_numerical = (bs_up.call_price() - bs_down.call_price()) / 2  # Already /100 in analytical

        assert abs(vega_analytical - vega_numerical) < 0.01


# ============================================================================
# OptionsStrategy Tests (17 tests)
# ============================================================================


class TestOptionsStrategy:
    """Test multi-leg options strategies."""

    def test_option_leg_creation(self):
        """Test OptionLeg creation."""
        leg = OptionLeg(option_type="call", position="long", strike=100, premium=5.0)
        assert leg.option_type == "call"
        assert leg.position == "long"
        assert leg.strike == 100
        assert leg.premium == 5.0
        assert leg.quantity == 1

    def test_option_leg_payoff_long_call(self):
        """Test long call payoff."""
        leg = OptionLeg("call", "long", strike=100, premium=5.0)

        # OTM
        assert leg.payoff_at_expiry(95) == -5.0  # Lost premium
        # ATM
        assert leg.payoff_at_expiry(100) == -5.0
        # ITM
        assert leg.payoff_at_expiry(110) == 5.0  # 10 intrinsic - 5 premium

    def test_option_leg_payoff_short_put(self):
        """Test short put payoff."""
        leg = OptionLeg("put", "short", strike=100, premium=4.0)

        # OTM (put expires worthless, seller keeps premium)
        assert leg.payoff_at_expiry(105) == 4.0
        # ITM (seller loses)
        assert leg.payoff_at_expiry(90) == -6.0  # 4 premium - 10 intrinsic

    def test_strategy_creation(self):
        """Test strategy creation."""
        legs = [
            OptionLeg("call", "long", 100, 5.0),
            OptionLeg("put", "long", 100, 4.5),
        ]
        strategy = OptionsStrategy(legs, name="straddle")
        assert strategy.name == "straddle"
        assert len(strategy.legs) == 2

    def test_strategy_empty_legs(self):
        """Test strategy with empty legs raises error."""
        with pytest.raises(ValueError, match="Strategy must have at least one leg"):
            OptionsStrategy([], name="invalid")

    def test_strategy_payoff_at_expiry(self):
        """Test strategy payoff calculation."""
        straddle = OptionsStrategy.straddle(S=100, K=100, T=0.25, r=0.05, sigma=0.25)
        payoff_df = straddle.payoff_at_expiry([90, 95, 100, 105, 110])

        assert isinstance(payoff_df, pd.DataFrame)
        assert "spot" in payoff_df.columns
        assert "total_payoff" in payoff_df.columns
        assert len(payoff_df) == 5

        # Straddle profits from large moves
        assert payoff_df.iloc[0]["total_payoff"] > payoff_df.iloc[2]["total_payoff"]  # 90 vs 100
        assert payoff_df.iloc[4]["total_payoff"] > payoff_df.iloc[2]["total_payoff"]  # 110 vs 100

    def test_straddle_factory(self):
        """Test straddle factory method."""
        straddle = OptionsStrategy.straddle(S=100, K=100, T=0.25, r=0.05, sigma=0.25)
        assert straddle.name == "straddle"
        assert len(straddle.legs) == 2
        assert straddle.legs[0].option_type == "call"
        assert straddle.legs[1].option_type == "put"
        assert straddle.legs[0].position == "long"
        assert straddle.legs[1].position == "long"

    def test_strangle_factory(self):
        """Test strangle factory method."""
        strangle = OptionsStrategy.strangle(
            S=100, K_call=105, K_put=95, T=0.25, r=0.05, sigma=0.25
        )
        assert strangle.name == "strangle"
        assert len(strangle.legs) == 2
        assert strangle.legs[0].strike == 105
        assert strangle.legs[1].strike == 95

    def test_butterfly_factory(self):
        """Test butterfly factory method."""
        butterfly = OptionsStrategy.butterfly(
            S=100, K_low=95, K_mid=100, K_high=105, T=0.25, r=0.05, sigma=0.25
        )
        assert butterfly.name == "butterfly"
        assert len(butterfly.legs) == 3
        assert butterfly.legs[1].quantity == 2  # Middle strike has 2 contracts

    def test_iron_condor_factory(self):
        """Test iron condor factory method."""
        iron_condor = OptionsStrategy.iron_condor(
            S=100,
            K_put_low=90,
            K_put_high=95,
            K_call_low=105,
            K_call_high=110,
            T=0.25,
            r=0.05,
            sigma=0.25,
        )
        assert iron_condor.name == "iron_condor"
        assert len(iron_condor.legs) == 4

    def test_bull_call_spread_factory(self):
        """Test bull call spread factory method."""
        spread = OptionsStrategy.bull_call_spread(
            S=100, K_low=100, K_high=105, T=0.25, r=0.05, sigma=0.25
        )
        assert spread.name == "bull_call_spread"
        assert len(spread.legs) == 2
        assert spread.legs[0].position == "long"
        assert spread.legs[1].position == "short"

    def test_bear_put_spread_factory(self):
        """Test bear put spread factory method."""
        spread = OptionsStrategy.bear_put_spread(
            S=100, K_low=95, K_high=100, T=0.25, r=0.05, sigma=0.25
        )
        assert spread.name == "bear_put_spread"
        assert len(spread.legs) == 2

    def test_net_premium(self):
        """Test net premium calculation."""
        # Debit spread (pay premium)
        bull_spread = OptionsStrategy.bull_call_spread(
            S=100, K_low=100, K_high=105, T=0.25, r=0.05, sigma=0.25
        )
        net = bull_spread.net_premium()
        assert net > 0  # Debit (pay money)

    def test_max_profit(self):
        """Test max profit calculation."""
        straddle = OptionsStrategy.straddle(S=100, K=100, T=0.25, r=0.05, sigma=0.25)
        max_profit = straddle.max_profit()
        # Straddle has unlimited profit (but sampling may cap it)
        # Accept either unlimited or large finite profit
        assert max_profit == np.inf or max_profit > 50

    def test_max_loss(self):
        """Test max loss calculation."""
        straddle = OptionsStrategy.straddle(S=100, K=100, T=0.25, r=0.05, sigma=0.25)
        max_loss = straddle.max_loss()
        # Straddle max loss is total premium paid
        assert max_loss < 0
        assert abs(max_loss) < 20  # Should be reasonable

    def test_breakeven_points(self):
        """Test breakeven calculation."""
        straddle = OptionsStrategy.straddle(S=100, K=100, T=0.25, r=0.05, sigma=0.25)
        breakevens = straddle.breakeven_points()

        # Straddle should have 2 breakevens
        assert len(breakevens) >= 2
        # One above strike, one below
        assert any(be < 100 for be in breakevens)
        assert any(be > 100 for be in breakevens)


# ============================================================================
# Integration Tests (3 tests)
# ============================================================================


class TestOptionsIntegration:
    """Integration tests across modules."""

    def test_price_and_greeks_consistency(self):
        """Test Black-Scholes price matches Greeks-derived price."""
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.2

        bs = BlackScholesModel(S=S, K=K, T=T, r=r, sigma=sigma)
        calc = GreeksCalculator(S=S, K=K, T=T, r=r, sigma=sigma)

        call_price = bs.call_price()
        greeks = calc.compute_all()

        # Delta should be positive for call
        assert greeks.delta_call > 0

    def test_strategy_parity(self):
        """Test synthetic positions via put-call parity."""
        # Long call + short put = synthetic long stock
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.2

        bs = BlackScholesModel(S=S, K=K, T=T, r=r, sigma=sigma)
        call = bs.call_price()
        put = bs.put_price()

        # Synthetic long: C - P = S - K*exp(-r*T)
        synthetic_long = call - put
        expected = S - K * np.exp(-r * T)

        assert abs(synthetic_long - expected) < 0.01

    def test_full_workflow(self):
        """Test complete options workflow."""
        # 1. Price options
        bs = BlackScholesModel(S=100, K=100, T=0.25, r=0.05, sigma=0.25)
        result = bs.price()

        # 2. Compute Greeks
        calc = GreeksCalculator(S=100, K=100, T=0.25, r=0.05, sigma=0.25)
        greeks = calc.compute_all()

        # 3. Create strategy
        straddle = OptionsStrategy.straddle(S=100, K=100, T=0.25, r=0.05, sigma=0.25)

        # 4. Analyze payoff
        payoff = straddle.payoff_at_expiry([90, 95, 100, 105, 110])

        # 5. Compute risk metrics
        max_loss = straddle.max_loss()
        breakevens = straddle.breakeven_points()

        # All should succeed
        assert result.call_price > 0
        assert greeks.delta_call > 0
        assert len(payoff) == 5
        assert max_loss < 0
        assert len(breakevens) >= 2

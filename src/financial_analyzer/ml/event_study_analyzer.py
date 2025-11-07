"""
Event study analyzer for news-driven abnormal returns.

Implements event study methodology to measure Cumulative Abnormal Returns (CAR)
around news events using the market model (CAPM).

Methodology follows academic standards:
- MacKinlay, A. C. (1997). "Event Studies in Economics and Finance."
  Journal of Economic Literature, 35(1), 13-39.
  https://www.jstor.org/stable/2729691
- Brown, S. J., & Warner, J. B. (1985). "Using daily stock returns: The case
  of event studies." Journal of Financial Economics, 14(1), 3-31.
  https://doi.org/10.1016/0304-405X(85)90042-X
- Fama, E. F., Fisher, L., Jensen, M. C., & Roll, R. (1969). "The adjustment
  of stock prices to new information." International Economic Review, 10(1), 1-21.

Event Study Process:
1. **Estimation Period**: Estimate normal returns using market model (CAPM):
   R_it = α + β * R_mt + ε_it
   where R_it is asset return, R_mt is market return
   
2. **Event Window**: Define window around event (e.g., [-5, +5] days)

3. **Abnormal Returns (AR)**: Actual return minus expected return:
   AR_it = R_it - (α̂ + β̂ * R_mt)
   
4. **Cumulative Abnormal Return (CAR)**: Sum of AR over event window:
   CAR_i = Σ AR_it for t in event window
   
5. **Average Abnormal Return (AAR)**: Average AR across all events

Example:
    >>> from financial_analyzer.ml.event_study_analyzer import EventStudyAnalyzer
    >>> import pandas as pd
    >>> 
    >>> # Define earnings announcement dates
    >>> event_dates = pd.to_datetime([
    ...     '2024-01-25', '2024-04-25', '2024-07-25'
    ... ], utc=True)
    >>> 
    >>> # Run event study
    >>> analyzer = EventStudyAnalyzer(
    ...     prices=aapl_prices,
    ...     market_returns=sp500_returns,
    ...     event_dates=event_dates,
    ...     estimation_window=252  # 1 year for beta estimation
    ... )
    >>> 
    >>> # Compute CAR
    >>> car_df = analyzer.compute_car(window_before=5, window_after=5)
    >>> print(f"Average CAR: {car_df['CAR'].mean():.2%}")
    Average CAR: +2.35%
    >>> 
    >>> # Plot CAR evolution
    >>> analyzer.plot_car(window_before=10, window_after=10, save_path='car_plot.png')
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LinearRegression

logger = logging.getLogger(__name__)


class EventStudyAnalyzer:
    """
    Analyze abnormal returns around news events using event study methodology.
    
    Implements the market model (CAPM) approach to estimate expected returns
    and measure abnormal returns (AR) and cumulative abnormal returns (CAR)
    around corporate events like earnings announcements, M&A, regulatory
    news, etc.
    
    Methodology Steps:
        1. **Estimate Market Model**: Use historical data to estimate α and β
           via OLS regression: R_asset = α + β * R_market + ε
           
        2. **Compute Abnormal Returns**: For each event, compute:
           AR_t = R_t - (α̂ + β̂ * R_market_t)
           
        3. **Aggregate Abnormal Returns**: Sum AR over event window → CAR
           Average AR across events → AAR
           
        4. **Statistical Testing**: Test if CAR is significantly different from 0
    
    Args:
        prices: Asset price series (DatetimeIndex). Used to compute returns.
        market_returns: Market benchmark return series (e.g., S&P 500).
                        Should cover estimation + event windows.
        event_dates: Dates of events to analyze (DatetimeIndex, UTC recommended).
        estimation_window: Number of days before first event to estimate β.
                           Default: 252 (approximately 1 trading year).
                 
    Raises:
        ValueError: If insufficient data for estimation, empty event_dates,
                    or data alignment issues
        TypeError: If inputs have incorrect types
        
    Example:
        >>> # Initialize analyzer with earnings dates
        >>> analyzer = EventStudyAnalyzer(
        ...     prices=aapl_prices,
        ...     market_returns=spy_returns,
        ...     event_dates=earnings_dates,
        ...     estimation_window=252
        ... )
        >>> 
        >>> # Check estimated beta
        >>> print(f"Asset beta: {analyzer.beta:.3f}")
        Asset beta: 1.150
        >>> 
        >>> # Compute CAR around events
        >>> car_df = analyzer.compute_car(window_before=5, window_after=5)
        >>> print(car_df[['event_date', 'CAR', 'AAR_post']])
        
        >>> # Test statistical significance
        >>> t_stat, p_value = analyzer.test_car_significance(car_df)
        >>> print(f"CAR t-statistic: {t_stat:.3f}, p-value: {p_value:.4f}")
    
    References:
        - MacKinlay (1997): Event Studies in Economics and Finance
        - Brown & Warner (1985): Using daily stock returns
        - Fama, Fisher, Jensen, & Roll (1969): Adjustment of stock prices
    """
    
    def __init__(
        self,
        prices: pd.Series,
        market_returns: pd.Series,
        event_dates: pd.DatetimeIndex,
        estimation_window: int = 252
    ) -> None:
        """Initialize event study analyzer.
        
        Args:
            prices: Asset price series (DatetimeIndex)
            market_returns: Market benchmark returns (DatetimeIndex)
            event_dates: Event dates (DatetimeIndex)
            estimation_window: Days for beta estimation (default: 252)
            
        Raises:
            ValueError: If inputs invalid or insufficient data
            TypeError: If inputs have incorrect types
            
        Example:
            >>> analyzer = EventStudyAnalyzer(
            ...     prices=prices_series,
            ...     market_returns=market_series,
            ...     event_dates=event_dates_index,
            ...     estimation_window=252
            ... )
        """
        # Type validation
        if not isinstance(prices, pd.Series):
            raise TypeError(
                f"prices must be pandas Series, got {type(prices).__name__}"
            )
        if not isinstance(market_returns, pd.Series):
            raise TypeError(
                f"market_returns must be pandas Series, got {type(market_returns).__name__}"
            )
        if not isinstance(event_dates, (pd.DatetimeIndex, pd.core.indexes.datetimes.DatetimeIndex)):
            # Try to convert
            try:
                event_dates = pd.DatetimeIndex(event_dates)
            except Exception as e:
                raise TypeError(
                    f"event_dates must be DatetimeIndex or convertible, got {type(event_dates).__name__}"
                ) from e
        
        self.prices = prices
        self.returns = prices.pct_change().dropna()
        self.market_returns = market_returns
        self.event_dates = event_dates
        
        # Validate and auto-adjust estimation_window if needed
        available_days = len(self.returns)
        if available_days < estimation_window:
            logger.warning(
                f"Insufficient data for estimation_window={estimation_window} days. "
                f"Auto-adjusting to {available_days} days (all available historical data). "
                f"Note: Beta estimate may be less reliable with fewer observations."
            )
            self.estimation_window = available_days
        else:
            self.estimation_window = estimation_window
        
        if len(event_dates) == 0:
            raise ValueError("event_dates cannot be empty")
        
        # Estimate beta (market model parameters)
        self.beta, self.alpha = self._estimate_market_model()
        
        # Store R-squared and residual std for diagnostics
        self.r_squared, self.residual_std = self._compute_model_diagnostics()
        
        logger.info(
            f"EventStudyAnalyzer initialized: "
            f"α={self.alpha:.4f}, β={self.beta:.4f}, R²={self.r_squared:.3f}, "
            f"{len(event_dates)} events"
        )
        
    def _estimate_market_model(self) -> Tuple[float, float]:
        """
        Estimate α and β using market model (CAPM) via OLS regression.
        
        Uses historical data from the estimation window to fit:
        R_asset = α + β * R_market + ε
        
        Returns:
            (beta, alpha): Tuple of estimated coefficients
            
        Note:
            Uses last N days for estimation to avoid look-ahead bias.
            N = estimation_window (default 252 days).
        """
        # Align returns and market returns
        df = pd.DataFrame({
            'asset': self.returns,
            'market': self.market_returns
        }).dropna()
        
        if len(df) < self.estimation_window:
            logger.warning(
                f"Using {len(df)} days for estimation (requested {self.estimation_window}). "
                f"Beta estimate may be less reliable."
            )
        
        # Use last N days for estimation (most recent historical data)
        df_estimation = df.tail(self.estimation_window)
        
        # OLS regression: y = β*X + α
        X = df_estimation['market'].values.reshape(-1, 1)
        y = df_estimation['asset'].values
        
        model = LinearRegression()
        model.fit(X, y)
        
        beta = float(model.coef_[0])
        alpha = float(model.intercept_)
        
        logger.debug(
            f"Market model estimated: R = {alpha:.4f} + {beta:.4f} * R_m "
            f"(n={len(df_estimation)} observations)"
        )
        
        return beta, alpha
    
    def _compute_model_diagnostics(self) -> Tuple[float, float]:
        """
        Compute R-squared and residual standard deviation for model diagnostics.
        
        Returns:
            (r_squared, residual_std): Model fit statistics
        """
        # Align data
        df = pd.DataFrame({
            'asset': self.returns,
            'market': self.market_returns
        }).dropna()
        
        df_estimation = df.tail(self.estimation_window)
        
        # Predicted returns
        predicted_returns = self.alpha + self.beta * df_estimation['market']
        
        # Residuals
        residuals = df_estimation['asset'] - predicted_returns
        
        # R-squared
        ss_res = np.sum(residuals ** 2)
        ss_tot = np.sum((df_estimation['asset'] - df_estimation['asset'].mean()) ** 2)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0.0
        
        # Residual standard deviation
        residual_std = float(np.std(residuals))
        
        return float(r_squared), residual_std
    
    def compute_abnormal_returns(self) -> pd.Series:
        """
        Compute abnormal returns (AR) for all dates.
        
        AR_t = R_t - (α̂ + β̂ * R_market_t)
        
        Abnormal return is the difference between actual return and
        expected return from the market model.
        
        Returns:
            Series of abnormal returns (DatetimeIndex)
            
        Example:
            >>> ar = analyzer.compute_abnormal_returns()
            >>> print(f"Mean AR: {ar.mean():.4f}")
            Mean AR: 0.0012
            >>> print(f"AR std: {ar.std():.4f}")
            AR std: 0.0245
            >>> 
            >>> # Find largest positive/negative AR
            >>> print(f"Max AR: {ar.max():.2%} on {ar.idxmax().date()}")
            >>> print(f"Min AR: {ar.min():.2%} on {ar.idxmin().date()}")
        """
        # Expected returns from market model
        expected_returns = self.alpha + self.beta * self.market_returns
        
        # Align with actual returns (inner join on dates)
        ar = self.returns - expected_returns
        ar = ar.dropna()
        
        logger.debug(
            f"Computed AR for {len(ar)} days: "
            f"mean={ar.mean():.4f}, std={ar.std():.4f}"
        )
        
        return ar
    
    def compute_car(
        self,
        window_before: int = 5,
        window_after: int = 5
    ) -> pd.DataFrame:
        """
        Compute Cumulative Abnormal Returns (CAR) around events.
        
        For each event:
        - Defines event window: [event_date - window_before, event_date + window_after]
        - Sums abnormal returns in window → CAR
        - Computes average AR before/after event → AAR_pre, AAR_post
        
        Args:
            window_before: Days before event to include (default: 5)
            window_after: Days after event to include (default: 5)
            
        Returns:
            DataFrame with columns:
            - event_date: Date of event
            - CAR: Cumulative abnormal return over event window
            - AAR_pre: Average abnormal return before event (not including event day)
            - AAR_post: Average abnormal return from event day onward
            - days_coverage: Actual number of trading days with data in window
            - t_stat: t-statistic for CAR significance
            
        Example:
            >>> car_df = analyzer.compute_car(window_before=3, window_after=7)
            >>> print(f"Average CAR: {car_df['CAR'].mean():.2%}")
            Average CAR: +2.35%
            >>> 
            >>> # Find events with largest CAR
            >>> top_events = car_df.nlargest(5, 'CAR')
            >>> print(top_events[['event_date', 'CAR', 't_stat']])
            
            >>> # Statistical significance
            >>> significant = car_df[car_df['t_stat'].abs() > 1.96]  # 95% confidence
            >>> print(f"{len(significant)}/{len(car_df)} events statistically significant")
        """
        ar = self.compute_abnormal_returns()
        
        results = []
        
        for event_date in self.event_dates:
            # Define event window
            start = event_date - pd.Timedelta(days=window_before)
            end = event_date + pd.Timedelta(days=window_after)
            
            # Get AR in window
            try:
                ar_window = ar.loc[start:end]
            except KeyError:
                logger.warning(
                    f"Event {event_date.date()} outside AR range "
                    f"({ar.index.min().date()} to {ar.index.max().date()}), skipping"
                )
                continue
            
            if len(ar_window) == 0:
                logger.warning(f"No AR data for event {event_date.date()}, skipping")
                continue
            
            # CAR = sum of AR over event window
            car = ar_window.sum()
            
            # Split pre/post event
            ar_pre = ar_window[ar_window.index < event_date]
            ar_post = ar_window[ar_window.index >= event_date]
            
            aar_pre = ar_pre.mean() if len(ar_pre) > 0 else np.nan
            aar_post = ar_post.mean() if len(ar_post) > 0 else np.nan
            
            # Compute t-statistic for CAR
            # t = CAR / (σ_AR * sqrt(L))
            # where L = length of event window
            t_stat = (
                car / (self.residual_std * np.sqrt(len(ar_window)))
                if self.residual_std > 0 and len(ar_window) > 0
                else np.nan
            )
            
            results.append({
                'event_date': event_date,
                'CAR': car,
                'AAR_pre': aar_pre,
                'AAR_post': aar_post,
                'days_coverage': len(ar_window),
                't_stat': t_stat
            })
        
        df = pd.DataFrame(results)
        
        if len(df) > 0:
            logger.info(
                f"CAR computed for {len(df)}/{len(self.event_dates)} events: "
                f"mean={df['CAR'].mean():.4f}, std={df['CAR'].std():.4f}, "
                f"significant={np.abs(df['t_stat'] > 1.96).sum()}/{len(df)}"
            )
        else:
            logger.warning("No events had sufficient data for CAR computation")
        
        return df
    
    def compute_aar_series(
        self,
        window_before: int = 5,
        window_after: int = 5
    ) -> pd.Series:
        """
        Compute Average Abnormal Return (AAR) series across all events.
        
        Aligns all events to "event time" (day 0 = event date) and averages
        AR across all events for each relative day.
        
        Useful for plotting AAR evolution around events.
        
        Args:
            window_before: Days before event (default: 5)
            window_after: Days after event (default: 5)
            
        Returns:
            Series with index = days relative to event (e.g., -5 to +5),
            values = average abnormal return across all events
            
        Example:
            >>> aar = analyzer.compute_aar_series(window_before=5, window_after=5)
            >>> print(aar)
            -5   -0.0012
            -4   -0.0008
            -3    0.0005
            -2    0.0018
            -1    0.0032
             0    0.0055  # Event day
             1    0.0042
             2    0.0028
            ...
            >>> 
            >>> # Plot AAR
            >>> import matplotlib.pyplot as plt
            >>> aar.plot(marker='o')
            >>> plt.axvline(0, color='red', linestyle='--', label='Event')
            >>> plt.xlabel('Days Relative to Event')
            >>> plt.ylabel('Average Abnormal Return')
            >>> plt.show()
        """
        ar = self.compute_abnormal_returns()
        
        # Collect AR for each event, aligned to event time
        event_ar_list = []
        
        for event_date in self.event_dates:
            start = event_date - pd.Timedelta(days=window_before)
            end = event_date + pd.Timedelta(days=window_after)
            
            try:
                ar_window = ar.loc[start:end].copy()
            except KeyError:
                logger.debug(f"Skipping event {event_date.date()} (outside AR range)")
                continue
            
            if len(ar_window) == 0:
                continue
            
            # Convert index to days relative to event
            # Positive = days after event, negative = days before
            ar_window.index = (ar_window.index - event_date).days
            
            event_ar_list.append(ar_window)
        
        if len(event_ar_list) == 0:
            logger.warning("No events with sufficient data for AAR series")
            return pd.Series(dtype=float)
        
        # Concatenate and group by relative day
        all_ar = pd.concat(event_ar_list)
        aar = all_ar.groupby(all_ar.index).mean()
        aar = aar.sort_index()
        
        logger.debug(
            f"AAR series computed: {len(event_ar_list)} events, "
            f"{len(aar)} relative days"
        )
        
        return aar
    
    def test_car_significance(
        self,
        car_df: pd.DataFrame
    ) -> Tuple[float, float]:
        """
        Test statistical significance of average CAR using t-test.
        
        Null hypothesis: Mean CAR = 0
        Alternative: Mean CAR ≠ 0
        
        Args:
            car_df: DataFrame from compute_car()
            
        Returns:
            (t_statistic, p_value): Two-sided t-test results
            
        Example:
            >>> car_df = analyzer.compute_car()
            >>> t_stat, p_value = analyzer.test_car_significance(car_df)
            >>> print(f"t-statistic: {t_stat:.3f}")
            >>> print(f"p-value: {p_value:.4f}")
            >>> if p_value < 0.05:
            ...     print("CAR is statistically significant at 95% confidence")
        """
        car_values = car_df['CAR'].dropna()
        
        if len(car_values) == 0:
            logger.warning("No CAR values for significance test")
            return np.nan, np.nan
        
        # One-sample t-test: H0: mean = 0
        t_stat, p_value = stats.ttest_1samp(car_values, 0)
        
        logger.info(
            f"CAR significance test: t={t_stat:.3f}, p={p_value:.4f}, "
            f"n={len(car_values)}, mean_CAR={car_values.mean():.4f}"
        )
        
        return float(t_stat), float(p_value)
    
    def plot_car(
        self,
        window_before: int = 5,
        window_after: int = 5,
        figsize: Tuple[int, int] = (12, 6),
        save_path: Optional[str] = None
    ) -> None:
        """
        Plot Cumulative Abnormal Returns (CAR) around events.
        
        Shows evolution of average CAR from window_before to window_after days
        relative to event date (day 0).
        
        Args:
            window_before: Days before event (default: 5)
            window_after: Days after event (default: 5)
            figsize: Figure size (width, height) in inches
            save_path: Path to save plot (optional). If None, displays interactively.
            
        Example:
            >>> # Display plot
            >>> analyzer.plot_car(window_before=10, window_after=10)
            >>> 
            >>> # Save to file
            >>> analyzer.plot_car(
            ...     window_before=5,
            ...     window_after=5,
            ...     figsize=(14, 7),
            ...     save_path='car_analysis.png'
            ... )
        """
        # Compute AAR series
        aar = self.compute_aar_series(window_before, window_after)
        
        if len(aar) == 0:
            logger.error("No data to plot (AAR series empty)")
            return
        
        # Cumulative sum → CAR
        car = aar.cumsum()
        
        # Create plot
        fig, ax = plt.subplots(figsize=figsize)
        
        # Plot CAR
        ax.plot(
            car.index,
            car.values,
            marker='o',
            linewidth=2,
            markersize=6,
            label='CAR',
            color='#2E86AB'
        )
        
        # Add event date line
        ax.axvline(
            0,
            color='red',
            linestyle='--',
            linewidth=2,
            label='Event Date',
            alpha=0.7
        )
        
        # Add zero line
        ax.axhline(0, color='black', linestyle='-', alpha=0.3, linewidth=1)
        
        # Labels and title
        ax.set_xlabel('Days Relative to Event', fontsize=12, fontweight='bold')
        ax.set_ylabel('Cumulative Abnormal Return', fontsize=12, fontweight='bold')
        ax.set_title(
            f'Event Study: CAR Around {len(self.event_dates)} Events '
            f'(β={self.beta:.2f}, R²={self.r_squared:.3f})',
            fontsize=14,
            fontweight='bold'
        )
        
        # Legend
        ax.legend(fontsize=11, loc='best')
        
        # Grid
        ax.grid(True, alpha=0.3, linestyle='--')
        
        # Format y-axis as percentage
        ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f'{y:.2%}'))
        
        # Tight layout
        plt.tight_layout()
        
        # Save or show
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            logger.info(f"Plot saved to {save_path}")
        else:
            plt.show()
        
        plt.close(fig)

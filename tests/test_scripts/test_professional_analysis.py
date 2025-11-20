from scripts.professional_analysis import shuffle_universe


def test_shuffle_universe_deterministic():
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]
    s1 = shuffle_universe(tickers, seed=123)
    s2 = shuffle_universe(tickers, seed=123)
    assert s1 == s2


def test_shuffle_universe_changes_order():
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]
    s1 = shuffle_universe(tickers, seed=1)
    s2 = shuffle_universe(tickers, seed=2)
    assert s1 != s2
    assert sorted(s1) == sorted(tickers)
    assert sorted(s2) == sorted(tickers)

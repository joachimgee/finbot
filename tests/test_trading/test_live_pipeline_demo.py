import sys
import types
import os
import pytest


def test_create_demo_pipeline_demo_mode_no_connect(monkeypatch):
    # Fake alpaca_trade_api to avoid dependency
    dummy = types.SimpleNamespace(REST=object)
    monkeypatch.setitem(sys.modules, 'alpaca_trade_api', dummy)

    # Ensure no real credentials → DEMO_KEY path
    monkeypatch.delenv('APCA_API_KEY_ID', raising=False)
    monkeypatch.delenv('APCA_API_SECRET_KEY', raising=False)
    monkeypatch.delenv('ALPACA_API_KEY', raising=False)
    monkeypatch.delenv('ALPACA_API_SECRET', raising=False)

    from financial_analyzer.trading.live_trading_pipeline import create_demo_pipeline

    pipeline = create_demo_pipeline(mode='paper')
    assert pipeline is not None
    # In demo mode we now mark broker as connected to allow pipeline use
    assert hasattr(pipeline.broker, 'connected')
    assert pipeline.broker.connected is True

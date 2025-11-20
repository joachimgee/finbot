import os
import sys
import types
import pytest


def test_alpaca_from_env_prefers_apca_env(monkeypatch):
    # Provide dummy alpaca_trade_api module to avoid ImportError
    dummy = types.SimpleNamespace(REST=object)
    monkeypatch.setitem(sys.modules, 'alpaca_trade_api', dummy)

    # Set both APCA_* and ALPACA_*; APCA_* should be preferred
    monkeypatch.setenv('APCA_API_KEY_ID', 'KEY_APCA')
    monkeypatch.setenv('APCA_API_SECRET_KEY', 'SECRET_APCA')
    monkeypatch.setenv('ALPACA_API_KEY', 'KEY_ALP')
    monkeypatch.setenv('ALPACA_API_SECRET', 'SECRET_ALP')
    monkeypatch.setenv('APCA_API_BASE_URL', 'https://paper-api.apca-test.example')

    from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter

    adapter = AlpacaAdapter.from_env(mode='paper')
    assert adapter.api_key == 'KEY_APCA'
    assert adapter.secret_key == 'SECRET_APCA'
    assert adapter.base_url == 'https://paper-api.apca-test.example'


def test_alpaca_from_env_fallback_alpaca_env(monkeypatch):
    # Provide dummy alpaca_trade_api module
    dummy = types.SimpleNamespace(REST=object)
    monkeypatch.setitem(sys.modules, 'alpaca_trade_api', dummy)

    # Ensure APCA_* absent; only ALPACA_* present
    monkeypatch.delenv('APCA_API_KEY_ID', raising=False)
    monkeypatch.delenv('APCA_API_SECRET_KEY', raising=False)
    monkeypatch.delenv('APCA_API_BASE_URL', raising=False)

    monkeypatch.setenv('ALPACA_API_KEY', 'KEY_ALP')
    monkeypatch.setenv('ALPACA_API_SECRET', 'SECRET_ALP')
    monkeypatch.setenv('ALPACA_PAPER_BASE_URL', 'https://paper-api.fallback.example')

    from financial_analyzer.trading.alpaca_adapter import AlpacaAdapter

    adapter = AlpacaAdapter.from_env(mode='paper')
    assert adapter.api_key == 'KEY_ALP'
    assert adapter.secret_key == 'SECRET_ALP'
    assert adapter.base_url == 'https://paper-api.fallback.example'

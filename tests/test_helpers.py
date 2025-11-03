"""
Tests pour le module utils.helpers
"""
import pytest
from datetime import datetime
from financial_analyzer.utils.helpers import (
    validate_ticker,
    validate_date,
    get_logger
)


def test_validate_ticker_success():
    """Test validation de ticker valide."""
    assert validate_ticker("aapl") == "AAPL"
    assert validate_ticker("MSFT") == "MSFT"
    assert validate_ticker(" GOOGL ") == "GOOGL"


def test_validate_ticker_failure():
    """Test validation de ticker invalide."""
    with pytest.raises(ValueError):
        validate_ticker("")
    
    with pytest.raises(ValueError):
        validate_ticker(None)
    
    with pytest.raises(ValueError):
        validate_ticker("AAPL@#$")


def test_validate_date_success():
    """Test validation de date valide."""
    assert validate_date("2023-01-01") == "2023-01-01"
    assert validate_date("2024-12-31") == "2024-12-31"


def test_validate_date_failure():
    """Test validation de date invalide."""
    with pytest.raises(ValueError):
        validate_date("2023/01/01")
    
    with pytest.raises(ValueError):
        validate_date("01-01-2023")
    
    with pytest.raises(ValueError):
        validate_date("invalid")


def test_get_logger():
    """Test création de logger."""
    logger = get_logger("test")
    assert logger is not None
    assert logger.name == "test"

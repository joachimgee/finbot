"""
Tests for IBAdapter (STUB - implement when IBAdapter is ready).

IBAdapter is not yet implemented. These tests verify that it raises
NotImplementedError as expected.
"""

from __future__ import annotations
import pytest
from financial_analyzer.trading.ib_adapter import IBAdapter


class TestIBAdapterStub:
    """Tests for IBAdapter stub implementation."""
    
    def test_ib_adapter_not_implemented(self):
        """Test that IBAdapter raises NotImplementedError on initialization."""
        with pytest.raises(NotImplementedError, match="IBAdapter not yet implemented"):
            adapter = IBAdapter(api_key='key', secret_key='secret')
    
    def test_ib_adapter_with_custom_params(self):
        """Test that IBAdapter raises NotImplementedError with custom params."""
        with pytest.raises(NotImplementedError, match="IBAdapter not yet implemented"):
            adapter = IBAdapter(
                api_key='key',
                secret_key='secret',
                mode='paper',
                host='127.0.0.1',
                port=7497,
                client_id=1
            )
    
    def test_error_message_contains_implementation_guide(self):
        """Test that error message contains implementation guide."""
        with pytest.raises(NotImplementedError) as exc_info:
            adapter = IBAdapter(api_key='key', secret_key='secret')
        
        error_message = str(exc_info.value)
        assert "Use AlpacaAdapter" in error_message
        assert "pip install ib_insync" in error_message
        assert "Implement all abstract methods" in error_message
        assert "Connect to IB Gateway/TWS" in error_message


# TODO: Implement full IBAdapter tests when IBAdapter is implemented
# 
# When implementing IBAdapter, add tests for:
# - Connection to IB Gateway/TWS
# - Order submission (market, limit, stop, etc.)
# - Order cancellation
# - Account information retrieval
# - Position tracking
# - Historical data fetching
# - Real-time data streaming
# - Contract management
# - Error handling (connection loss, invalid contracts, etc.)
# - Reconnection logic
# - Multiple account support (if applicable)
# 
# Example test structure:
# 
# class TestIBConnection:
#     """Tests for IB connection methods."""
#     
#     @pytest.fixture
#     def mock_ib():
#         """Mock ib_insync.IB client."""
#         with patch('ib_adapter.IB') as mock:
#             yield mock
#     
#     def test_connect_success(self, mock_ib):
#         """Test successful connection to IB Gateway."""
#         adapter = IBAdapter(host='127.0.0.1', port=7497, client_id=1)
#         adapter.connect()
#         
#         assert adapter.connected is True
#         mock_ib.return_value.connect.assert_called_once()
# 
# class TestIBOrders:
#     """Tests for IB order methods."""
#     
#     def test_submit_market_order(self, connected_adapter):
#         """Test market order submission."""
#         # ... implementation ...
#     
#     def test_submit_limit_order(self, connected_adapter):
#         """Test limit order submission."""
#         # ... implementation ...
# 
# And so on...

# tests/test_tools_instruments.py
from unittest.mock import MagicMock, patch
import pytest


@pytest.fixture
def mock_client():
    client = MagicMock()
    with patch("schwab_mcp.client._schwab_client", client):
        yield client


def test_search_instruments_calls_schwabdev(mock_client):
    """search_instruments calls client.instruments with symbol and projection."""
    mock_client.instruments.return_value.ok = True
    mock_client.instruments.return_value.json.return_value = []
    from schwab_mcp.tools.instruments import search_instruments
    search_instruments(symbol="AAPL", projection="symbol-search")
    mock_client.instruments.assert_called_once_with("AAPL", "symbol-search")


def test_search_instruments_regex(mock_client):
    """search_instruments passes regex projection correctly."""
    mock_client.instruments.return_value.ok = True
    mock_client.instruments.return_value.json.return_value = []
    from schwab_mcp.tools.instruments import search_instruments
    search_instruments(symbol="AAP.*", projection="symbol-regex")
    mock_client.instruments.assert_called_once_with("AAP.*", "symbol-regex")


def test_get_instrument_calls_schwabdev(mock_client):
    """get_instrument calls client.instrument_cusip with cusip."""
    mock_client.instrument_cusip.return_value.ok = True
    mock_client.instrument_cusip.return_value.json.return_value = {}
    from schwab_mcp.tools.instruments import get_instrument
    get_instrument(cusip="037833100")
    mock_client.instrument_cusip.assert_called_once_with("037833100")


def test_search_instruments_api_error(mock_client):
    """search_instruments returns error string on API failure."""
    mock_client.instruments.return_value.ok = False
    mock_client.instruments.return_value.status_code = 400
    mock_client.instruments.return_value.text = "Bad Request"
    from schwab_mcp.tools.instruments import search_instruments
    result = search_instruments(symbol="???", projection="symbol-search")
    assert "error" in result.lower() or "400" in result

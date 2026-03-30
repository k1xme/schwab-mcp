# tests/test_tools_market_data.py
import json
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.quotes.return_value.ok = True
    client.quotes.return_value.json.return_value = {"AAPL": {"lastPrice": 150.0}}
    with patch("schwab_mcp.client._schwab_client", client):
        yield client


def test_get_quotes_calls_schwabdev(mock_client):
    """get_quotes calls client.quotes with the given symbols."""
    from schwab_mcp.tools.market_data import get_quotes
    result = get_quotes(symbols=["AAPL", "MSFT"])
    mock_client.quotes.assert_called_once_with(
        ["AAPL", "MSFT"], fields=None, indicative=False
    )
    assert "AAPL" in result


def test_get_quotes_api_error(mock_client):
    """get_quotes returns error string on API failure."""
    mock_client.quotes.return_value.ok = False
    mock_client.quotes.return_value.status_code = 400
    mock_client.quotes.return_value.text = "Bad request"
    from schwab_mcp.tools.market_data import get_quotes
    result = get_quotes(symbols=["INVALID"])
    assert "error" in result.lower() or "400" in result


def test_get_option_chain_passes_all_params(mock_client):
    """get_option_chain passes all optional params to client.option_chains."""
    mock_client.option_chains.return_value.ok = True
    mock_client.option_chains.return_value.json.return_value = {}
    from schwab_mcp.tools.market_data import get_option_chain
    get_option_chain(
        symbol="AAPL",
        contract_type="CALL",
        strike_count=5,
        strike=150.0,
        range="OTM",
    )
    call_kwargs = mock_client.option_chains.call_args[1]
    assert call_kwargs["contractType"] == "CALL"
    assert call_kwargs["strikeCount"] == 5
    assert call_kwargs["strike"] == 150.0
    assert call_kwargs["range"] == "OTM"


def test_get_price_history_calls_schwabdev(mock_client):
    """get_price_history calls client.price_history with correct params."""
    mock_client.price_history.return_value.ok = True
    mock_client.price_history.return_value.json.return_value = {"candles": []}
    from schwab_mcp.tools.market_data import get_price_history
    get_price_history(symbol="SPY", period_type="month", period=1, frequency_type="daily", frequency=1)
    mock_client.price_history.assert_called_once()
    args = mock_client.price_history.call_args
    assert args[0][0] == "SPY"


def test_get_movers_calls_schwabdev(mock_client):
    """get_movers calls client.movers with the index symbol."""
    mock_client.movers.return_value.ok = True
    mock_client.movers.return_value.json.return_value = []
    from schwab_mcp.tools.market_data import get_movers
    get_movers(index="$SPX")
    mock_client.movers.assert_called_once_with("$SPX", sort=None, frequency=None)


def test_get_market_hours_calls_schwabdev(mock_client):
    """get_market_hours calls client.market_hours with markets list."""
    mock_client.market_hours.return_value.ok = True
    mock_client.market_hours.return_value.json.return_value = {}
    from schwab_mcp.tools.market_data import get_market_hours
    get_market_hours(markets=["equity", "option"])
    mock_client.market_hours.assert_called_once_with(["equity", "option"], date=None)


def test_get_option_expirations_calls_schwabdev(mock_client):
    """get_option_expirations calls client.option_expiration_chain."""
    mock_client.option_expiration_chain.return_value.ok = True
    mock_client.option_expiration_chain.return_value.json.return_value = {}
    from schwab_mcp.tools.market_data import get_option_expirations
    get_option_expirations(symbol="AAPL")
    mock_client.option_expiration_chain.assert_called_once_with("AAPL")


def test_get_option_chain_always_writes_file(mock_client, tmp_path):
    """Option chain always writes to file regardless of size."""
    chain_data = {"callExpDateMap": {"2026-04-17": {"150.0": [{"putCall": "CALL"}]}}}
    mock_client.option_chains.return_value.ok = True
    mock_client.option_chains.return_value.json.return_value = chain_data

    from schwab_mcp.tools.market_data import get_option_chain
    result = get_option_chain(symbol="SPX")
    assert "Option chain for SPX written to" in result
    assert str(tmp_path) in result
    assert "option-chain-SPX-" in result


def test_get_price_history_above_threshold_writes_file(mock_client, tmp_path):
    """More than 20 candles writes to file."""
    candles = [{"open": 100, "close": 101, "high": 102, "low": 99} for _ in range(21)]
    mock_client.price_history.return_value.ok = True
    mock_client.price_history.return_value.json.return_value = {"candles": candles, "symbol": "AAPL"}

    from schwab_mcp.tools.market_data import get_price_history
    result = get_price_history(symbol="AAPL", frequency_type="minute")
    assert "21 candles found" in result
    assert "price-history-AAPL-minute-" in result


def test_get_price_history_at_threshold_stays_inline(mock_client, tmp_path):
    """Exactly 20 candles stays inline."""
    candles = [{"open": 100} for _ in range(20)]
    mock_client.price_history.return_value.ok = True
    mock_client.price_history.return_value.json.return_value = {"candles": candles}

    from schwab_mcp.tools.market_data import get_price_history
    result = get_price_history(symbol="AAPL")
    assert '"open"' in result
    assert len(list(tmp_path.iterdir())) == 0


def test_get_price_history_no_frequency_type_context(mock_client, tmp_path):
    """When frequency_type is None, context is just the symbol."""
    candles = [{"open": 100} for _ in range(21)]
    mock_client.price_history.return_value.ok = True
    mock_client.price_history.return_value.json.return_value = {"candles": candles}

    from schwab_mcp.tools.market_data import get_price_history
    result = get_price_history(symbol="AAPL")
    assert "price-history-AAPL-" in result
    # Should NOT have a double dash (no frequency_type)
    assert "price-history-AAPL--" not in result


def test_get_quotes_above_threshold_writes_file(mock_client, tmp_path):
    """More than 5 symbols writes to file."""
    quotes = {f"SYM{i}": {"lastPrice": 100 + i} for i in range(6)}
    mock_client.quotes.return_value.ok = True
    mock_client.quotes.return_value.json.return_value = quotes

    from schwab_mcp.tools.market_data import get_quotes
    result = get_quotes(symbols=["SYM0", "SYM1", "SYM2", "SYM3", "SYM4", "SYM5"])
    assert "6 quotes found" in result
    assert "quotes-SYM0+5more-" in result


def test_get_quotes_at_threshold_stays_inline(mock_client, tmp_path):
    """Exactly 5 symbols stays inline."""
    quotes = {f"SYM{i}": {"lastPrice": 100 + i} for i in range(5)}
    mock_client.quotes.return_value.ok = True
    mock_client.quotes.return_value.json.return_value = quotes

    from schwab_mcp.tools.market_data import get_quotes
    result = get_quotes(symbols=["SYM0", "SYM1", "SYM2", "SYM3", "SYM4"])
    assert '"lastPrice"' in result
    assert len(list(tmp_path.iterdir())) == 0

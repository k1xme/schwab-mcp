# tests/test_tools_accounts.py
import json
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta, timezone


@pytest.fixture
def mock_client():
    client = MagicMock()
    with patch("schwab_mcp.client._schwab_client", client):
        yield client


@pytest.fixture(autouse=True)
def set_active_account(monkeypatch):
    import schwab_mcp.client as c
    monkeypatch.setattr(c, "_active_account_hash", "ACTIVEHASH1234")


def test_get_account_uses_active_account(mock_client):
    """get_account uses active account when account_hash is not provided."""
    mock_client.account_details.return_value.ok = True
    mock_client.account_details.return_value.json.return_value = {"type": "MARGIN"}
    from schwab_mcp.tools.accounts import get_account
    get_account()
    mock_client.account_details.assert_called_once_with("ACTIVEHASH1234", fields=None)


def test_get_account_with_positions(mock_client):
    """get_account passes fields='positions' when requested."""
    mock_client.account_details.return_value.ok = True
    mock_client.account_details.return_value.json.return_value = {}
    from schwab_mcp.tools.accounts import get_account
    get_account(fields="positions")
    mock_client.account_details.assert_called_with("ACTIVEHASH1234", fields="positions")


def test_get_transactions_validates_date_range(mock_client):
    """get_transactions rejects date ranges over 1 year."""
    from schwab_mcp.tools.accounts import get_transactions
    result = get_transactions(
        start_date="2024-01-01T00:00:00.000Z",
        end_date="2026-01-02T00:00:00.000Z",
        types="TRADE",
    )
    assert "1 year" in result.lower() or "error" in result.lower()
    mock_client.transactions.assert_not_called()


def test_get_transactions_calls_schwabdev(mock_client):
    """get_transactions calls client.transactions with correct params."""
    mock_client.transactions.return_value.ok = True
    mock_client.transactions.return_value.json.return_value = []
    from schwab_mcp.tools.accounts import get_transactions
    get_transactions(
        start_date="2026-01-01T00:00:00.000Z",
        end_date="2026-02-01T00:00:00.000Z",
        types="TRADE",
        symbol="AAPL",
    )
    mock_client.transactions.assert_called_once_with(
        "ACTIVEHASH1234",
        startDate="2026-01-01T00:00:00.000Z",
        endDate="2026-02-01T00:00:00.000Z",
        types="TRADE",
        symbol="AAPL",
    )


def test_get_transaction_calls_schwabdev(mock_client):
    """get_transaction calls client.transaction_details."""
    mock_client.transaction_details.return_value.ok = True
    mock_client.transaction_details.return_value.json.return_value = {"id": "TXN1"}
    from schwab_mcp.tools.accounts import get_transaction
    get_transaction(transaction_id="TXN1")
    mock_client.transaction_details.assert_called_once_with("ACTIVEHASH1234", "TXN1")


def test_get_preferences_calls_schwabdev(mock_client):
    """get_preferences calls client.preferences()."""
    mock_client.preferences.return_value.ok = True
    mock_client.preferences.return_value.json.return_value = {}
    from schwab_mcp.tools.accounts import get_preferences
    get_preferences()
    mock_client.preferences.assert_called_once()


def test_get_account_no_active_account_returns_error(mock_client, monkeypatch):
    """get_account returns error string when no account hash and no active account."""
    import schwab_mcp.client as c
    monkeypatch.setattr(c, "_active_account_hash", None)
    from schwab_mcp.tools.accounts import get_account
    result = get_account(account_hash=None)
    assert "error" in result.lower() or "set_active_account" in result
    mock_client.account_details.assert_not_called()


def test_get_transactions_above_threshold_writes_file(mock_client, tmp_path):
    """More than 10 transactions writes to file."""
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = [{"id": i} for i in range(11)]
    mock_client.transactions.return_value = mock_resp

    from schwab_mcp.tools.accounts import get_transactions
    result = get_transactions(
        start_date="2026-03-01T00:00:00.000Z",
        end_date="2026-03-22T00:00:00.000Z",
        types="TRADE",
    )
    assert "11 transactions found" in result
    assert str(tmp_path) in result


def test_get_transactions_at_threshold_stays_inline(mock_client, tmp_path):
    """Exactly 10 transactions stays inline."""
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = [{"id": i} for i in range(10)]
    mock_client.transactions.return_value = mock_resp

    from schwab_mcp.tools.accounts import get_transactions
    result = get_transactions(
        start_date="2026-03-01T00:00:00.000Z",
        end_date="2026-03-22T00:00:00.000Z",
        types="TRADE",
    )
    assert '"id"' in result
    assert len(list(tmp_path.iterdir())) == 0


def test_get_account_many_positions_writes_file(mock_client, tmp_path):
    """get_account with >10 positions writes to file."""
    positions = [{"symbol": f"SYM{i}"} for i in range(11)]
    account_data = {"securitiesAccount": {"positions": positions, "type": "MARGIN"}}
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = account_data
    mock_client.account_details.return_value = mock_resp

    from schwab_mcp.tools.accounts import get_account
    result = get_account(fields="positions")
    assert "11 positions found" in result
    assert str(tmp_path) in result


def test_get_account_few_positions_stays_inline(mock_client, tmp_path):
    """get_account with <=10 positions stays inline."""
    positions = [{"symbol": f"SYM{i}"} for i in range(5)]
    account_data = {"securitiesAccount": {"positions": positions, "type": "MARGIN"}}
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = account_data
    mock_client.account_details.return_value = mock_resp

    from schwab_mcp.tools.accounts import get_account
    result = get_account(fields="positions")
    assert '"symbol"' in result
    assert len(list(tmp_path.iterdir())) == 0


def test_get_account_no_positions_key_stays_inline(mock_client, tmp_path):
    """get_account without positions key stays inline (no crash)."""
    account_data = {"securitiesAccount": {"type": "MARGIN"}}
    mock_resp = MagicMock()
    mock_resp.ok = True
    mock_resp.json.return_value = account_data
    mock_client.account_details.return_value = mock_resp

    from schwab_mcp.tools.accounts import get_account
    result = get_account()
    assert '"type"' in result
    assert len(list(tmp_path.iterdir())) == 0

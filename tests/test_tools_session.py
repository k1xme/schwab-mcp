# tests/test_tools_session.py
import json
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def reset_active_account(monkeypatch):
    import schwab_mcp.client as c
    monkeypatch.setattr(c, "_active_account_hash", None)


@pytest.fixture
def mock_client():
    client = MagicMock()
    with patch("schwab_mcp.client._schwab_client", client):
        yield client


def test_set_active_account_stores_hash(mock_client):
    """set_active_account stores the hash and returns confirmation."""
    import schwab_mcp.client as c
    from schwab_mcp.tools.session import set_active_account

    result = set_active_account("HASH1234ABCD")
    assert c._active_account_hash == "HASH1234ABCD"
    assert "ABCD" in result  # last 4 chars shown


def test_get_active_account_when_none():
    """get_active_account returns helpful message when no account is set."""
    from schwab_mcp.tools.session import get_active_account

    result = get_active_account()
    assert "no active account" in result.lower()


def test_get_active_account_when_set(mock_client, monkeypatch):
    """get_active_account returns account details when active account is set."""
    import schwab_mcp.client as c
    monkeypatch.setattr(c, "_active_account_hash", "TESTHASH")

    mock_client.account_details.return_value.ok = True
    mock_client.account_details.return_value.json.return_value = {
        "securitiesAccount": {"type": "MARGIN", "accountNumber": "***1234"}
    }

    from schwab_mcp.tools.session import get_active_account
    result = get_active_account()
    assert "TESTHASH" in result or "1234" in result


def test_list_accounts_includes_hash_values(mock_client):
    """list_accounts merges hashValue from linked_accounts into each account."""
    mock_client.linked_accounts.return_value.ok = True
    mock_client.linked_accounts.return_value.json.return_value = [
        {"accountNumber": "***5678", "hashValue": "HASH5678ABCD"}
    ]
    mock_client.account_details_all.return_value.ok = True
    mock_client.account_details_all.return_value.json.return_value = [
        {"securitiesAccount": {"accountNumber": "***5678", "type": "CASH"}}
    ]

    from schwab_mcp.tools.session import list_accounts
    result = list_accounts()
    mock_client.linked_accounts.assert_called_once()
    mock_client.account_details_all.assert_called_once_with(fields="positions")
    assert "HASH5678ABCD" in result
    assert "5678" in result


def test_list_accounts_handles_hash_api_error(mock_client):
    """list_accounts surfaces error if linked_accounts call fails."""
    mock_client.linked_accounts.return_value.ok = False
    mock_client.linked_accounts.return_value.status_code = 401
    mock_client.linked_accounts.return_value.text = "Unauthorized"

    from schwab_mcp.tools.session import list_accounts
    result = list_accounts()
    assert "error" in result.lower() or "401" in result
    mock_client.account_details_all.assert_not_called()


def test_list_accounts_handles_details_api_error(mock_client):
    """list_accounts surfaces error if account_details_all call fails."""
    mock_client.linked_accounts.return_value.ok = True
    mock_client.linked_accounts.return_value.json.return_value = []
    mock_client.account_details_all.return_value.ok = False
    mock_client.account_details_all.return_value.status_code = 500
    mock_client.account_details_all.return_value.text = "Internal Server Error"

    from schwab_mcp.tools.session import list_accounts
    result = list_accounts()
    assert "error" in result.lower() or "500" in result

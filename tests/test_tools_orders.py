# tests/test_tools_orders.py
import json
import pytest
from unittest.mock import MagicMock, patch


SAMPLE_ORDER = {
    "orderType": "MARKET",
    "session": "NORMAL",
    "duration": "DAY",
    "orderStrategyType": "SINGLE",
    "orderLegCollection": [
        {"instruction": "BUY", "quantity": 1,
         "instrument": {"symbol": "AAPL", "assetType": "EQUITY"}}
    ],
}


@pytest.fixture
def mock_client():
    client = MagicMock()
    with patch("schwab_mcp.client._schwab_client", client):
        yield client


@pytest.fixture(autouse=True)
def set_active_account(monkeypatch):
    import schwab_mcp.client as c
    monkeypatch.setattr(c, "_active_account_hash", "TESTHASH1234")


def test_place_order_dry_run_does_not_call_api(mock_client):
    """place_order with confirmed=False returns summary without calling API."""
    from schwab_mcp.tools.orders import place_order
    result = place_order(order=SAMPLE_ORDER)
    mock_client.place_order.assert_not_called()
    assert "confirm" in result.lower() or "dry run" in result.lower() or "BUY" in result


def test_place_order_confirmed_calls_api(mock_client):
    """place_order with confirmed=True calls client.place_order."""
    mock_client.place_order.return_value.ok = True
    mock_client.place_order.return_value.status_code = 201
    mock_client.place_order.return_value.text = ""
    from schwab_mcp.tools.orders import place_order
    result = place_order(order=SAMPLE_ORDER, confirmed=True)
    mock_client.place_order.assert_called_once_with("TESTHASH1234", SAMPLE_ORDER)


def test_cancel_order_dry_run_does_not_call_api(mock_client):
    """cancel_order with confirmed=False returns summary without calling API."""
    from schwab_mcp.tools.orders import cancel_order
    result = cancel_order(order_id="ORD123")
    mock_client.cancel_order.assert_not_called()
    assert "ORD123" in result or "confirm" in result.lower()


def test_cancel_order_confirmed_calls_api(mock_client):
    """cancel_order with confirmed=True calls client.cancel_order."""
    mock_client.cancel_order.return_value.ok = True
    mock_client.cancel_order.return_value.status_code = 200
    mock_client.cancel_order.return_value.text = ""
    from schwab_mcp.tools.orders import cancel_order
    cancel_order(order_id="ORD123", confirmed=True)
    mock_client.cancel_order.assert_called_once_with("TESTHASH1234", "ORD123")


def test_replace_order_dry_run(mock_client):
    """replace_order with confirmed=False returns summary without calling API."""
    from schwab_mcp.tools.orders import replace_order
    result = replace_order(order_id="ORD123", order=SAMPLE_ORDER)
    mock_client.replace_order.assert_not_called()
    assert "confirm" in result.lower() or "ORD123" in result


def test_replace_order_confirmed_calls_api(mock_client):
    """replace_order with confirmed=True calls client.replace_order."""
    mock_client.replace_order.return_value.ok = True
    mock_client.replace_order.return_value.status_code = 201
    mock_client.replace_order.return_value.text = ""
    from schwab_mcp.tools.orders import replace_order
    replace_order(order_id="ORD123", order=SAMPLE_ORDER, confirmed=True)
    mock_client.replace_order.assert_called_once_with("TESTHASH1234", "ORD123", SAMPLE_ORDER)


def test_list_orders_validates_date_range(mock_client):
    """list_orders rejects date ranges over 1 year."""
    from schwab_mcp.tools.orders import list_orders
    result = list_orders(
        from_entered_time="2024-01-01T00:00:00.000Z",
        to_entered_time="2026-01-02T00:00:00.000Z",
    )
    assert "1 year" in result.lower() or "error" in result.lower()
    mock_client.account_orders.assert_not_called()


def test_list_orders_calls_schwabdev(mock_client):
    """list_orders calls account_orders with correct params."""
    mock_client.account_orders.return_value.ok = True
    mock_client.account_orders.return_value.json.return_value = []
    from schwab_mcp.tools.orders import list_orders
    list_orders(
        from_entered_time="2026-01-01T00:00:00.000Z",
        to_entered_time="2026-02-01T00:00:00.000Z",
        status="FILLED",
    )
    mock_client.account_orders.assert_called_once_with(
        "TESTHASH1234",
        fromEnteredTime="2026-01-01T00:00:00.000Z",
        toEnteredTime="2026-02-01T00:00:00.000Z",
        maxResults=None,
        status="FILLED",
    )


def test_list_all_orders_calls_schwabdev(mock_client):
    """list_all_orders calls account_orders_all."""
    mock_client.account_orders_all.return_value.ok = True
    mock_client.account_orders_all.return_value.json.return_value = []
    from schwab_mcp.tools.orders import list_all_orders
    list_all_orders(
        from_entered_time="2026-01-01T00:00:00.000Z",
        to_entered_time="2026-02-01T00:00:00.000Z",
    )
    mock_client.account_orders_all.assert_called_once()


def test_get_order_calls_schwabdev(mock_client):
    """get_order calls order_details."""
    mock_client.order_details.return_value.ok = True
    mock_client.order_details.return_value.json.return_value = {"orderId": "ORD1"}
    from schwab_mcp.tools.orders import get_order
    get_order(order_id="ORD1")
    mock_client.order_details.assert_called_once_with("TESTHASH1234", "ORD1")


def test_preview_order_calls_schwabdev(mock_client):
    """preview_order calls client.preview_order."""
    mock_client.preview_order.return_value.ok = True
    mock_client.preview_order.return_value.json.return_value = {}
    from schwab_mcp.tools.orders import preview_order
    preview_order(order=SAMPLE_ORDER)
    mock_client.preview_order.assert_called_once_with("TESTHASH1234", SAMPLE_ORDER)


def test_preview_order_surfaces_live_account_error(mock_client):
    """preview_order returns helpful message on 404 from live account."""
    mock_client.preview_order.return_value.ok = False
    mock_client.preview_order.return_value.status_code = 404
    mock_client.preview_order.return_value.text = "Not Found"
    from schwab_mcp.tools.orders import preview_order
    result = preview_order(order=SAMPLE_ORDER)
    assert "paper trading" in result.lower() or "confirmed=False" in result


def test_list_orders_defaults_to_today_when_no_dates(mock_client):
    """list_orders with no date args calls account_orders with today's UTC full day."""
    mock_client.account_orders.return_value.ok = True
    mock_client.account_orders.return_value.json.return_value = []
    from schwab_mcp.tools.orders import list_orders
    from datetime import timezone
    import datetime as dt_module

    fixed_date = dt_module.date(2026, 3, 22)
    mock_datetime = MagicMock()
    mock_datetime.now.return_value.date.return_value = fixed_date

    with patch("schwab_mcp.tools.orders.datetime", mock_datetime):
        list_orders()

    mock_datetime.now.assert_called_once_with(timezone.utc)
    mock_client.account_orders.assert_called_once_with(
        "TESTHASH1234",
        fromEnteredTime="2026-03-22T00:00:00.000Z",
        toEnteredTime="2026-03-22T23:59:59.999Z",
        maxResults=None,
        status=None,
    )


def test_list_orders_rejects_single_date_arg(mock_client):
    """list_orders with only one date arg returns an error without calling API."""
    from schwab_mcp.tools.orders import list_orders
    result = list_orders(from_entered_time="2026-03-22T00:00:00.000Z")
    assert "error" in result.lower()
    mock_client.account_orders.assert_not_called()


def test_list_orders_rejects_single_date_arg_to_only(mock_client):
    """list_orders with only to_entered_time returns an error without calling API."""
    from schwab_mcp.tools.orders import list_orders
    result = list_orders(to_entered_time="2026-03-22T23:59:59.999Z")
    assert "error" in result.lower()
    mock_client.account_orders.assert_not_called()


# --- Order summary annotation fixtures ---

EQUITY_ORDER = {
    "orderId": 99001,
    "orderType": "LIMIT",
    "complexOrderStrategyType": "NONE",
    "orderStrategyType": "SINGLE",
    "price": "150.00",
    "status": "FILLED",
    "closeTime": "2026-03-22T14:30:00+0000",
    "orderLegCollection": [
        {
            "instruction": "BUY",
            "quantity": 100,
            "instrument": {"symbol": "AAPL", "assetType": "EQUITY"},
        }
    ],
}

OPTION_ORDER = {
    "orderId": 99002,
    "orderType": "LIMIT",
    "complexOrderStrategyType": "NONE",
    "orderStrategyType": "SINGLE",
    "price": 0.10,
    "status": "WORKING",
    "enteredTime": "2026-03-22T09:00:00+0000",
    "orderLegCollection": [
        {
            "instruction": "BUY_TO_OPEN",
            "quantity": 3,
            "instrument": {
                "symbol": "AAPL  240517P00190000",
                "assetType": "OPTION",
            },
        }
    ],
}

VERTICAL_SPREAD_ORDER = {
    "orderId": 99003,
    "orderType": "NET_DEBIT",
    "complexOrderStrategyType": "VERTICAL",
    "orderStrategyType": "SINGLE",
    "price": "0.10",
    "status": "FILLED",
    "closeTime": "2026-03-22T10:14:32+0000",
    "orderLegCollection": [
        {
            "instruction": "BUY_TO_OPEN",
            "quantity": 2,
            "instrument": {
                "symbol": "XYZ   240315P00045000",
                "assetType": "OPTION",
            },
        },
        {
            "instruction": "SELL_TO_OPEN",
            "quantity": 2,
            "instrument": {
                "symbol": "XYZ   240315P00043000",
                "assetType": "OPTION",
            },
        },
    ],
}

OCO_ORDER = {
    "orderId": 99004,
    "orderStrategyType": "OCO",
    "status": "WORKING",
    "enteredTime": "2026-03-22T11:00:00+0000",
    "childOrderStrategies": [
        {
            "orderType": "LIMIT",
            "orderStrategyType": "SINGLE",
            "price": "45.97",
            "orderLegCollection": [
                {
                    "instruction": "SELL",
                    "quantity": 2,
                    "instrument": {"symbol": "XYZ", "assetType": "EQUITY"},
                }
            ],
        },
        {
            "orderType": "STOP_LIMIT",
            "orderStrategyType": "SINGLE",
            "price": "37.00",
            "stopPrice": "37.03",
            "orderLegCollection": [
                {
                    "instruction": "SELL",
                    "quantity": 2,
                    "instrument": {"symbol": "XYZ", "assetType": "EQUITY"},
                }
            ],
        },
    ],
}

STOP_LIMIT_ORDER = {
    "orderId": 99005,
    "orderType": "STOP_LIMIT",
    "complexOrderStrategyType": "NONE",
    "orderStrategyType": "SINGLE",
    "price": "37.00",
    "stopPrice": "37.03",
    "status": "WORKING",
    "enteredTime": "2026-03-22T09:30:00+0000",
    "orderLegCollection": [
        {
            "instruction": "SELL",
            "quantity": 10,
            "instrument": {"symbol": "XYZ", "assetType": "EQUITY"},
        }
    ],
}

TRAILING_STOP_ORDER = {
    "orderId": 99006,
    "orderType": "TRAILING_STOP",
    "complexOrderStrategyType": "NONE",
    "orderStrategyType": "SINGLE",
    "stopPriceOffset": 10,
    "status": "WORKING",
    "enteredTime": "2026-03-22T09:45:00+0000",
    "orderLegCollection": [
        {
            "instruction": "SELL",
            "quantity": 10,
            "instrument": {"symbol": "XYZ", "assetType": "EQUITY"},
        }
    ],
}


def test_format_order_summary_equity():
    """Single equity order produces correct summary line."""
    from schwab_mcp.tools.orders import _format_order_summary

    result = _format_order_summary(EQUITY_ORDER)
    assert result == (
        "Order #99001 | SINGLE | BUY 100x AAPL"
        " | LIMIT $150.00 | FILLED | 2026-03-22T14:30:00+0000"
    )


def test_format_order_summary_option():
    """Single option order with numeric price."""
    from schwab_mcp.tools.orders import _format_order_summary

    result = _format_order_summary(OPTION_ORDER)
    assert result == (
        "Order #99002 | SINGLE | BUY_TO_OPEN 3x AAPL  240517P00190000"
        " | LIMIT $0.10 | WORKING | 2026-03-22T09:00:00+0000"
    )


def test_format_order_summary_vertical_spread():
    """Multi-leg order shows both legs and complexOrderStrategyType."""
    from schwab_mcp.tools.orders import _format_order_summary

    result = _format_order_summary(VERTICAL_SPREAD_ORDER)
    assert result == (
        "Order #99003 | VERTICAL"
        " | BUY_TO_OPEN 2x XYZ   240315P00045000"
        " / SELL_TO_OPEN 2x XYZ   240315P00043000"
        " | NET_DEBIT $0.10 | FILLED | 2026-03-22T10:14:32+0000"
    )


def test_format_order_summary_oco():
    """OCO order with no orderLegCollection shows child count."""
    from schwab_mcp.tools.orders import _format_order_summary

    result = _format_order_summary(OCO_ORDER)
    assert result == (
        "Order #99004 | OCO | 2 child orders"
        " | WORKING | 2026-03-22T11:00:00+0000"
    )


def test_format_order_summary_stop_limit():
    """STOP_LIMIT order shows both price and stopPrice."""
    from schwab_mcp.tools.orders import _format_order_summary

    result = _format_order_summary(STOP_LIMIT_ORDER)
    assert result == (
        "Order #99005 | SINGLE | SELL 10x XYZ"
        " | STOP_LIMIT $37.00 stop $37.03 | WORKING | 2026-03-22T09:30:00+0000"
    )


def test_format_order_summary_trailing_stop():
    """TRAILING_STOP order shows stopPriceOffset."""
    from schwab_mcp.tools.orders import _format_order_summary

    result = _format_order_summary(TRAILING_STOP_ORDER)
    assert result == (
        "Order #99006 | SINGLE | SELL 10x XYZ"
        " | TRAILING_STOP offset $10.00 | WORKING | 2026-03-22T09:45:00+0000"
    )


def test_format_order_summary_missing_fields():
    """Missing optional fields are omitted gracefully."""
    from schwab_mcp.tools.orders import _format_order_summary

    minimal_order = {
        "orderId": 99007,
        "orderType": "MARKET",
        "orderStrategyType": "SINGLE",
        "status": "FILLED",
        "orderLegCollection": [
            {
                "instruction": "BUY",
                "quantity": 5,
                "instrument": {"symbol": "TSLA", "assetType": "EQUITY"},
            }
        ],
    }
    result = _format_order_summary(minimal_order)
    # No price segment (MARKET), no time (missing both closeTime and enteredTime)
    assert result == "Order #99007 | SINGLE | BUY 5x TSLA | MARKET | FILLED"


def test_format_orders_response_list():
    """List of orders: each gets summary line + JSON block."""
    from schwab_mcp.tools.orders import _format_orders_response

    resp = MagicMock()
    resp.ok = True
    resp.status_code = 200
    resp.text = "not empty"
    resp.json.return_value = [EQUITY_ORDER, OPTION_ORDER]

    result = _format_orders_response(resp)
    # Both summary lines present
    assert "Order #99001" in result
    assert "Order #99002" in result
    # Raw JSON preserved
    assert '"orderId": 99001' in result
    assert '"orderId": 99002' in result
    # Summary comes before JSON for each order
    idx_summary1 = result.index("Order #99001")
    idx_json1 = result.index('"orderId": 99001')
    assert idx_summary1 < idx_json1


def test_format_orders_response_single():
    """Single order dict (from get_order): gets summary line + JSON."""
    from schwab_mcp.tools.orders import _format_orders_response

    resp = MagicMock()
    resp.ok = True
    resp.status_code = 200
    resp.text = "not empty"
    resp.json.return_value = EQUITY_ORDER

    result = _format_orders_response(resp)
    assert result.startswith("Order #99001")
    assert '"orderId": 99001' in result


def test_format_orders_response_empty_list():
    """Empty order list returns friendly message."""
    from schwab_mcp.tools.orders import _format_orders_response

    resp = MagicMock()
    resp.ok = True
    resp.status_code = 200
    resp.text = "[]"
    resp.json.return_value = []

    result = _format_orders_response(resp)
    assert result == "No orders found."


def test_format_orders_response_error():
    """Non-OK response returns error string."""
    from schwab_mcp.tools.orders import _format_orders_response

    resp = MagicMock()
    resp.ok = False
    resp.status_code = 401
    resp.text = "Unauthorized"

    result = _format_orders_response(resp)
    assert "Error (401)" in result
    assert "Unauthorized" in result


def test_format_orders_response_above_threshold_writes_file(tmp_path):
    """More than 10 orders writes to file, returns count + path."""
    from schwab_mcp.tools.orders import _format_orders_response

    orders = [{"orderId": i, "orderType": "MARKET", "status": "FILLED"} for i in range(11)]
    resp = MagicMock()
    resp.ok = True
    resp.status_code = 200
    resp.text = "not empty"
    resp.json.return_value = orders

    result = _format_orders_response(resp)
    assert "11 orders found" in result
    assert str(tmp_path) in result
    assert "orders-" in result
    # Should NOT contain raw JSON
    assert '"orderId"' not in result


def test_format_orders_response_at_threshold_stays_inline(tmp_path):
    """Exactly 10 orders stays inline with summary annotations."""
    from schwab_mcp.tools.orders import _format_orders_response

    orders = [{"orderId": i, "orderType": "MARKET", "status": "FILLED",
               "orderStrategyType": "SINGLE",
               "orderLegCollection": [{"instruction": "BUY", "quantity": 1,
                                        "instrument": {"symbol": "AAPL"}}]}
              for i in range(10)]
    resp = MagicMock()
    resp.ok = True
    resp.status_code = 200
    resp.text = "not empty"
    resp.json.return_value = orders

    result = _format_orders_response(resp)
    # Should contain inline JSON (summary + JSON blocks)
    assert '"orderId"' in result
    # No files written
    assert len(list(tmp_path.iterdir())) == 0


def test_list_all_orders_above_threshold_uses_all_context(mock_client, tmp_path):
    """list_all_orders writes file with 'all' in filename."""
    orders = [{"orderId": i} for i in range(11)]
    mock_client.account_orders_all.return_value.ok = True
    mock_client.account_orders_all.return_value.status_code = 200
    mock_client.account_orders_all.return_value.text = "not empty"
    mock_client.account_orders_all.return_value.json.return_value = orders

    from schwab_mcp.tools.orders import list_all_orders
    result = list_all_orders(
        from_entered_time="2026-03-01T00:00:00.000Z",
        to_entered_time="2026-03-22T00:00:00.000Z",
    )
    assert "orders-all-" in result

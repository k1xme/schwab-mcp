# src/schwab_mcp/tools/orders.py
import json
import logging
from datetime import datetime, timezone

from schwab_mcp._mcp import mcp
from schwab_mcp.client import get_schwab_client, try_resolve_account_hash
from schwab_mcp.tools._response import _ok_or_error, _maybe_write_to_file

logger = logging.getLogger("schwab_mcp.tools.orders")

_ONE_YEAR_SECONDS = 365 * 24 * 3600


def _parse_iso(date_str: str) -> datetime:
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


def _validate_date_range(from_str: str, to_str: str) -> str | None:
    """Return error string if range exceeds 1 year, else None."""
    try:
        start = _parse_iso(from_str)
        end = _parse_iso(to_str)
        if (end - start).total_seconds() > _ONE_YEAR_SECONDS:
            return "Error: Date range exceeds the Schwab API maximum of 1 year."
    except ValueError as e:
        return f"Error: Invalid date format. Use YYYY-MM-DDTHH:mm:ss.000Z. Details: {e}"
    return None


def _dry_run_summary(action: str, account_hash: str, **details) -> str:
    lines = [
        f"DRY RUN — {action}",
        f"Account: ...{account_hash[-4:]}",
    ]
    for k, v in details.items():
        lines.append(f"{k}: {json.dumps(v, indent=2) if isinstance(v, dict) else v}")
    lines.append("\nTo execute, call this tool again with confirmed=True.")
    return "\n".join(lines)


def _format_order_summary(order: dict) -> str:
    """Build a pipe-delimited summary line for a single order."""
    parts: list[str] = []

    # Order ID
    order_id = order.get("orderId")
    if order_id is not None:
        parts.append(f"Order #{order_id}")

    # Strategy type
    complex_type = order.get("complexOrderStrategyType")
    if complex_type and complex_type != "NONE":
        parts.append(complex_type)
    else:
        strategy = order.get("orderStrategyType")
        if strategy:
            parts.append(strategy)

    # Legs or child count
    legs = order.get("orderLegCollection")
    if legs:
        leg_strs = []
        for leg in legs:
            instr = leg.get("instruction", "")
            qty = leg.get("quantity", "")
            symbol = leg.get("instrument", {}).get("symbol", "")
            leg_strs.append(f"{instr} {qty}x {symbol}")
        parts.append(" / ".join(leg_strs))
    else:
        children = order.get("childOrderStrategies", [])
        if children:
            parts.append(f"{len(children)} child orders")

    # Order type + price
    order_type = order.get("orderType")
    if order_type:
        price = order.get("price")
        stop_price = order.get("stopPrice")
        offset = order.get("stopPriceOffset")

        if order_type == "TRAILING_STOP" and offset is not None:
            parts.append(f"TRAILING_STOP offset ${float(offset):.2f}")
        elif price is not None and stop_price is not None:
            parts.append(
                f"{order_type} ${float(price):.2f} stop ${float(stop_price):.2f}"
            )
        elif stop_price is not None:
            parts.append(f"{order_type} ${float(stop_price):.2f}")
        elif price is not None:
            parts.append(f"{order_type} ${float(price):.2f}")
        else:
            parts.append(order_type)

    # Status
    status = order.get("status")
    if status:
        parts.append(status)

    # Time
    time = order.get("closeTime") or order.get("enteredTime")
    if time:
        parts.append(time)

    return " | ".join(parts)


def _format_orders_response(resp, context: str = "") -> str:
    """Format an order-listing HTTP response with summary annotations."""
    if not resp.ok:
        return f"Error ({resp.status_code}): {resp.text}"
    if resp.status_code in (200, 201) and not resp.text.strip():
        return f"Success (HTTP {resp.status_code})"
    try:
        data = resp.json()
    except Exception:
        return resp.text

    if isinstance(data, list):
        if not data:
            return "No orders found."
        orders = data
    else:
        orders = [data]

    # Check compression threshold
    filed = _maybe_write_to_file("orders", context, orders, len(orders), threshold=10, noun="orders")
    if filed:
        return filed

    blocks = []
    for order in orders:
        summary = _format_order_summary(order)
        order_json = json.dumps(order, indent=2)
        blocks.append(f"{summary}\n\n{order_json}")
    return "\n\n".join(blocks)


@mcp.tool()
def list_orders(
    from_entered_time: str | None = None,
    to_entered_time: str | None = None,
    account_hash: str | None = None,
    max_results: int | None = None,
    status: str | None = None,
) -> str:
    """List orders for an account within a date range.

    Date range is optional. Omit both from_entered_time and to_entered_time to
    return today's orders (UTC full day: 00:00:00.000Z – 23:59:59.999Z).
    Both must be provided together or not at all — providing exactly one is an error.
    When provided, use format: "YYYY-MM-DDTHH:mm:ss.SSSZ". Max range: 1 year.

    Args:
        from_entered_time: Start time. Omit (with to_entered_time) to default to today.
        to_entered_time: End time. Omit (with from_entered_time) to default to today.
        account_hash: Encrypted account hash. Defaults to active account.
        max_results: Limit number of orders returned (default 3000).
        status: Filter by order status. Values: "AWAITING_PARENT_ORDER",
            "AWAITING_CONDITION", "AWAITING_STOP_CONDITION",
            "AWAITING_MANUAL_REVIEW", "ACCEPTED", "AWAITING_UR_OUT",
            "PENDING_ACTIVATION", "QUEUED", "WORKING", "REJECTED",
            "PENDING_CANCEL", "CANCELED", "PENDING_REPLACE", "REPLACED",
            "FILLED", "EXPIRED", "NEW", "AWAITING_RELEASE_TIME",
            "PENDING_ACKNOWLEDGEMENT", "PENDING_RECALL", "UNKNOWN".
    """
    # All-or-nothing: both provided, both omitted, or error
    if (from_entered_time is None) != (to_entered_time is None):
        return (
            "Error: Provide both from_entered_time and to_entered_time, "
            "or omit both to default to today."
        )

    if from_entered_time is None:
        today = datetime.now(timezone.utc).date()
        from_entered_time = f"{today}T00:00:00.000Z"
        to_entered_time = f"{today}T23:59:59.999Z"
    else:
        err = _validate_date_range(from_entered_time, to_entered_time)
        if err:
            return err

    hash_, err = try_resolve_account_hash(account_hash)
    if err:
        return err
    logger.info("list_orders called, account_hash=...%s", hash_[-4:])
    client = get_schwab_client()
    resp = client.account_orders(
        hash_,
        fromEnteredTime=from_entered_time,
        toEnteredTime=to_entered_time,
        maxResults=max_results,
        status=status,
    )
    return _format_orders_response(resp)


@mcp.tool()
def list_all_orders(
    from_entered_time: str,
    to_entered_time: str,
    max_results: int | None = None,
    status: str | None = None,
) -> str:
    """List orders across ALL linked accounts within a date range.

    Max 1-year range. Rate limit: 120 API requests per minute.

    Args:
        from_entered_time: Start time: "YYYY-MM-DDTHH:mm:ss.SSSZ".
        to_entered_time: End time: same format.
        max_results: Limit number of orders returned (default 3000).
        status: Filter by order status (same values as list_orders).
    """
    err = _validate_date_range(from_entered_time, to_entered_time)
    if err:
        return err
    logger.info("list_all_orders called")
    client = get_schwab_client()
    resp = client.account_orders_all(
        fromEnteredTime=from_entered_time,
        toEnteredTime=to_entered_time,
        maxResults=max_results,
        status=status,
    )
    return _format_orders_response(resp, context="all")


@mcp.tool()
def get_order(
    order_id: str,
    account_hash: str | None = None,
) -> str:
    """Get full details for a single order by ID.

    Args:
        order_id: Order ID from list_orders.
        account_hash: Encrypted account hash. Defaults to active account.
    """
    hash_, err = try_resolve_account_hash(account_hash)
    if err:
        return err
    logger.info("get_order called, order_id=%s", order_id)
    client = get_schwab_client()
    resp = client.order_details(hash_, order_id)
    return _format_orders_response(resp)


@mcp.tool()
def preview_order(
    order: dict,
    account_hash: str | None = None,
) -> str:
    """Simulate order placement without executing. Paper trading accounts only.

    On live accounts, the Schwab API returns an error. In that case, use
    place_order with confirmed=False to see a dry-run summary instead.

    Args:
        order: Schwab order object. See place_order for schema details.
        account_hash: Encrypted account hash. Defaults to active account.
    """
    hash_, err = try_resolve_account_hash(account_hash)
    if err:
        return err
    logger.info("preview_order called, account_hash=...%s", hash_[-4:])
    client = get_schwab_client()
    resp = client.preview_order(hash_, order)
    if not resp.ok and resp.status_code == 404:
        return (
            "Error (404): preview_order is only supported on paper trading accounts. "
            "Use place_order with confirmed=False to see a dry-run summary instead."
        )
    return _ok_or_error(resp)


@mcp.tool()
def place_order(
    order: dict,
    account_hash: str | None = None,
    confirmed: bool = False,
) -> str:
    """Submit an order to Schwab. Requires confirmed=True to execute.

    When confirmed=False (default), returns a dry-run summary of the order
    without submitting. Call again with confirmed=True to execute.

    Order schema example (equity market buy):
        {
            "orderType": "MARKET",
            "session": "NORMAL",
            "duration": "DAY",
            "orderStrategyType": "SINGLE",
            "orderLegCollection": [{
                "instruction": "BUY",
                "quantity": 1,
                "instrument": {"symbol": "AAPL", "assetType": "EQUITY"}
            }]
        }

    Common orderType values: "MARKET", "LIMIT", "STOP", "STOP_LIMIT".
    Common session values: "NORMAL", "AM" (pre-market), "PM" (after-hours).
    Common duration values: "DAY", "GOOD_TILL_CANCEL", "FILL_OR_KILL".

    Args:
        order: Schwab order object dict.
        account_hash: Encrypted account hash. Defaults to active account.
        confirmed: Must be True to actually submit. Default False (dry run).
    """
    hash_, err = try_resolve_account_hash(account_hash)
    if err:
        return err
    if not confirmed:
        return _dry_run_summary("Place Order", hash_, order=order)
    logger.info("place_order CONFIRMED, account_hash=...%s", hash_[-4:])
    client = get_schwab_client()
    resp = client.place_order(hash_, order)
    return _ok_or_error(resp)


@mcp.tool()
def cancel_order(
    order_id: str,
    account_hash: str | None = None,
    confirmed: bool = False,
) -> str:
    """Cancel an open order. Requires confirmed=True to execute.

    When confirmed=False (default), returns a dry-run summary without canceling.

    Args:
        order_id: Order ID to cancel (from list_orders).
        account_hash: Encrypted account hash. Defaults to active account.
        confirmed: Must be True to actually cancel. Default False (dry run).
    """
    hash_, err = try_resolve_account_hash(account_hash)
    if err:
        return err
    if not confirmed:
        return _dry_run_summary("Cancel Order", hash_, order_id=order_id)
    logger.info("cancel_order CONFIRMED, order_id=%s, account_hash=...%s", order_id, hash_[-4:])
    client = get_schwab_client()
    resp = client.cancel_order(hash_, order_id)
    return _ok_or_error(resp)


@mcp.tool()
def replace_order(
    order_id: str,
    order: dict,
    account_hash: str | None = None,
    confirmed: bool = False,
) -> str:
    """Cancel an existing order and create a replacement. Requires confirmed=True.

    When confirmed=False (default), returns a dry-run summary.

    Args:
        order_id: Order ID to replace (from list_orders).
        order: New order object to submit in place of the existing order.
        account_hash: Encrypted account hash. Defaults to active account.
        confirmed: Must be True to actually replace. Default False (dry run).
    """
    hash_, err = try_resolve_account_hash(account_hash)
    if err:
        return err
    if not confirmed:
        return _dry_run_summary("Replace Order", hash_, order_id=order_id, new_order=order)
    logger.info("replace_order CONFIRMED, order_id=%s, account_hash=...%s", order_id, hash_[-4:])
    client = get_schwab_client()
    resp = client.replace_order(hash_, order_id, order)
    return _ok_or_error(resp)

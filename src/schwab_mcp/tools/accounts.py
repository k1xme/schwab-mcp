# src/schwab_mcp/tools/accounts.py
import json
import logging
from datetime import datetime, timezone

from schwab_mcp._mcp import mcp
from schwab_mcp.client import get_schwab_client, try_resolve_account_hash
from schwab_mcp.tools._response import _ok_or_error, _maybe_write_to_file

logger = logging.getLogger("schwab_mcp.tools.accounts")

_ONE_YEAR_SECONDS = 365 * 24 * 3600


def _parse_iso(date_str: str) -> datetime:
    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))


@mcp.tool()
def get_account(
    account_hash: str | None = None,
    fields: str | None = None,
) -> str:
    """Get balances and positions for an account.

    Args:
        account_hash: Encrypted account hash. Defaults to active account.
        fields: Pass "positions" to include position data; omit for balances only.
    """
    hash_, err = try_resolve_account_hash(account_hash)
    if err:
        return err
    logger.info("get_account called, account_hash=...%s", hash_[-4:])
    client = get_schwab_client()
    resp = client.account_details(hash_, fields=fields)
    if not resp.ok:
        return f"Error ({resp.status_code}): {resp.text}"
    try:
        data = resp.json()
    except Exception:
        return resp.text
    positions = data.get("securitiesAccount", {}).get("positions", [])
    if positions:
        filed = _maybe_write_to_file("account", "", data, len(positions), threshold=10, noun="positions")
        if filed:
            return filed
    return json.dumps(data, indent=2)


@mcp.tool()
def get_transactions(
    start_date: str,
    end_date: str,
    types: str,
    account_hash: str | None = None,
    symbol: str | None = None,
) -> str:
    """Get transaction history for an account.

    Max 1-year date range, max 3,000 results.

    Args:
        start_date: Format: "YYYY-MM-DDTHH:mm:ss.SSSZ".
        end_date: Format: "YYYY-MM-DDTHH:mm:ss.SSSZ".
        types: Comma-separated transaction types: "TRADE",
            "RECEIVE_AND_DELIVER", "DIVIDEND_OR_INTEREST", "ACH_RECEIPT",
            "ACH_DISBURSEMENT", "CASH_RECEIPT", "CASH_DISBURSEMENT",
            "ELECTRONIC_FUND", "WIRE_OUT", "WIRE_IN", "JOURNAL",
            "MEMORANDUM", "MARGIN_CALL", "MONEY_MARKET", "SMA_ADJUSTMENT".
        account_hash: Encrypted account hash. Defaults to active account.
        symbol: Filter results to a specific symbol. Special symbols
            like "/" or "$" must be URL-encoded.
    """
    try:
        start = _parse_iso(start_date)
        end = _parse_iso(end_date)
        if (end - start).total_seconds() > _ONE_YEAR_SECONDS:
            return "Error: Date range exceeds the Schwab API maximum of 1 year."
    except ValueError as e:
        return f"Error: Invalid date format. Use YYYY-MM-DDTHH:mm:ss.000Z. Details: {e}"

    hash_, err = try_resolve_account_hash(account_hash)
    if err:
        return err
    logger.info("get_transactions called, account_hash=...%s", hash_[-4:])
    client = get_schwab_client()
    resp = client.transactions(
        hash_,
        startDate=start_date,
        endDate=end_date,
        types=types,
        symbol=symbol,
    )
    if not resp.ok:
        return f"Error ({resp.status_code}): {resp.text}"
    try:
        data = resp.json()
    except Exception:
        return resp.text
    if isinstance(data, list):
        filed = _maybe_write_to_file("transactions", "", data, len(data), threshold=10, noun="transactions")
        if filed:
            return filed
    return json.dumps(data, indent=2)


@mcp.tool()
def get_transaction(
    transaction_id: str,
    account_hash: str | None = None,
) -> str:
    """Get details for a single transaction by ID.

    Args:
        transaction_id: Transaction ID from get_transactions.
        account_hash: Encrypted account hash. Defaults to active account.
    """
    hash_, err = try_resolve_account_hash(account_hash)
    if err:
        return err
    logger.info("get_transaction called, id=%s", transaction_id)
    client = get_schwab_client()
    resp = client.transaction_details(hash_, transaction_id)
    return _ok_or_error(resp)


@mcp.tool()
def get_preferences() -> str:
    """Get user preferences and streaming connection info.

    Returns streamer info, offer CD keys, and preference settings.
    """
    logger.info("get_preferences called")
    client = get_schwab_client()
    resp = client.preferences()
    return _ok_or_error(resp)

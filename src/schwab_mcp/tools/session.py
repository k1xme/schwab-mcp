# src/schwab_mcp/tools/session.py
import json
import logging
from schwab_mcp._mcp import mcp
from schwab_mcp.client import (
    get_schwab_client,
    get_active_account_hash,
    set_active_account_hash,
    try_resolve_account_hash,
)

logger = logging.getLogger("schwab_mcp.tools.session")


@mcp.tool()
def list_accounts() -> str:
    """List all linked Schwab accounts with balances, positions, and account hashes.

    Returns account type, number, balances, and the encrypted account_hash
    needed for account-specific tools. Use set_active_account to set a default.
    """
    logger.info("list_accounts called")
    client = get_schwab_client()

    hashes_resp = client.linked_accounts()
    if not hashes_resp.ok:
        return f"Error fetching account hashes ({hashes_resp.status_code}): {hashes_resp.text}"
    hash_map = {
        entry["accountNumber"]: entry["hashValue"]
        for entry in hashes_resp.json()
    }

    resp = client.account_details_all(fields="positions")
    if not resp.ok:
        return f"Error fetching accounts ({resp.status_code}): {resp.text}"

    accounts = resp.json()
    for account in accounts:
        acct_num = account.get("securitiesAccount", {}).get("accountNumber")
        if acct_num and acct_num in hash_map:
            account["securitiesAccount"]["hashValue"] = hash_map[acct_num]

    return json.dumps(accounts, indent=2)


@mcp.tool()
def set_active_account(account_hash: str) -> str:
    """Set the active account for this session.

    After calling this, all account-specific tools will use this account
    by default when account_hash is not explicitly provided.

    Args:
        account_hash: The encrypted account hash from list_accounts.
    """
    set_active_account_hash(account_hash)
    logger.info("Active account set to account_hash=...%s", account_hash[-4:])
    return f"Active account set to ...{account_hash[-4:]}."


@mcp.tool()
def get_active_account() -> str:
    """Return the currently active account hash and its details.

    Returns a message if no active account has been set.
    """
    account_hash = get_active_account_hash()
    if account_hash is None:
        return (
            "No active account set. "
            "Call list_accounts to see available accounts, "
            "then call set_active_account with the desired account_hash."
        )
    logger.info("get_active_account called, account_hash=...%s", account_hash[-4:])
    client = get_schwab_client()
    resp = client.account_details(account_hash, fields="positions")
    if not resp.ok:
        return (
            f"Active account is ...{account_hash[-4:]}, "
            f"but fetching details failed ({resp.status_code}): {resp.text}"
        )
    data = resp.json()
    data["_active_account_hash"] = account_hash
    return json.dumps(data, indent=2)

---
name: account
description: Use when user asks about Schwab account balances, positions, transactions, setting the active account, or account preferences
---

# Schwab Account

## Tool Map

| Intent | Tool | Key params |
|---|---|---|
| List all accounts + hashes | `list_accounts` | — |
| Set default account | `set_active_account` | `account_hash` |
| Get active account details | `get_active_account` | — |
| Get balances / positions | `get_account` | `account_hash`, `fields` |
| List transactions | `get_transactions` | `start_date`, `end_date`, `types` |
| Get one transaction | `get_transaction` | `transaction_id`, `account_hash` |
| User preferences | `get_preferences` | — |

## Account Hash Resolution

All account-specific tools accept `account_hash=None` and fall back to the active account stored in `~/.schwab-mcp/state.json` (persisted across sessions).

**If no active account is set:** call `list_accounts` → pick the hash → call `set_active_account`.

**Workflow for first-time / unknown account:**
1. `list_accounts` — response includes `hashValue` in each `securitiesAccount` object
2. `set_active_account(account_hash=<hashValue>)` — persists for future sessions
3. Proceed with account-specific tools

Never pass account number as `account_hash`. Always use `hashValue` from `list_accounts`.

## Subagent Invocation

Always invoke `get_account` and `get_transactions` via a **general-purpose subagent** (`Agent` tool). This keeps API responses — and any temp file contents — out of the main conversation context, saving tokens.

The subagent should:
1. Call the tool with the user's parameters (include this skill's guidance in the prompt)
2. If the response references a temp file, read it with the `Read` tool
3. Fulfill the user's request (summarize, analyze, etc.)
4. Return only the concise final answer — never the raw JSON

## Large Response Compression

Tools that can return large responses automatically write full JSON to a temp file and return a summary with the file path instead. Use the `Read` tool to access the file when full data is needed (e.g., for analysis or plotting).

| Tool | Writes to file when | File format |
|---|---|---|
| `get_account` | >10 positions | **dict** — `{"securitiesAccount": {...}}` |
| `get_transactions` | >10 transactions | **list** — `[{txn1}, {txn2}, ...]` |

## get_account

```
get_account(fields="positions")   # balances + all positions
get_account()                     # balances only
```

Response key fields: `currentBalances.liquidationValue`, `currentBalances.cashBalance`, `positions[].marketValue`, `positions[].instrument.symbol`

## get_transactions

Date format: `"YYYY-MM-DDTHH:mm:ss.000Z"`. Max range: 1 year. Max results: 3,000.

`types` is a **comma-separated string** (not a list):

| Value | Meaning |
|---|---|
| `TRADE` | Buy/sell executions |
| `DIVIDEND_OR_INTEREST` | Dividends, interest |
| `RECEIVE_AND_DELIVER` | Transfers in/out |
| `ACH_RECEIPT` / `ACH_DISBURSEMENT` | ACH deposits/withdrawals |
| `CASH_RECEIPT` / `CASH_DISBURSEMENT` | Cash receipts/disbursements |
| `ELECTRONIC_FUND` | Electronic fund transfers |
| `WIRE_IN` / `WIRE_OUT` | Wire transfers |
| `JOURNAL` | Journal entries |
| `MEMORANDUM` | Memo entries |
| `MARGIN_CALL` | Margin calls |
| `MONEY_MARKET` | Money market transactions |
| `SMA_ADJUSTMENT` | SMA adjustments |

Special symbols like `"/"` or `"$"` in the `symbol` filter must be URL-encoded.

Example — get all trades for the last 30 days:
```
get_transactions(
    start_date="2026-02-19T00:00:00.000Z",
    end_date="2026-03-21T23:59:59.000Z",
    types="TRADE"
)
```

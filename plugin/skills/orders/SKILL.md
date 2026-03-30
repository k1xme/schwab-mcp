---
name: orders
description: Use when user asks to place, view, cancel, modify, or preview stock/option orders on Schwab accounts via the schwab MCP server
---

# Schwab Orders

## Tool Map

| Intent | Tool | Key params |
|---|---|---|
| Place / modify order | `place_order` | `order`, `account_hash`, `confirmed` |
| View one order | `get_order` | `order_id`, `account_hash` |
| List account orders | `list_orders` | `from_entered_time`, `to_entered_time`, `status` |
| List all accounts | `list_all_orders` | same as above, no `account_hash` |
| Cancel order | `cancel_order` | `order_id`, `confirmed` |
| Replace order | `replace_order` | `order_id`, `order`, `confirmed` |

## Safety Pattern — Always Two Steps

Every mutating tool (`place_order`, `cancel_order`, `replace_order`) defaults to **dry run** (`confirmed=False`). Always:

1. Call with `confirmed=False` → show user the summary
2. Only call again with `confirmed=True` after user explicitly approves

Never skip step 1. Never pass `confirmed=True` on first call.

## Account Hash Resolution

All tools accept `account_hash=None` and fall back to the active account. Omit `account_hash` unless the user specifies a different account. If you get an error about no active account, call `get_active_account` first.

## Order JSON Schemas

### Equity — Market Buy
```json
{
    "orderType": "MARKET",
    "session": "NORMAL",
    "duration": "DAY",
    "orderStrategyType": "SINGLE",
    "orderLegCollection": [{
        "instruction": "BUY",
        "quantity": 10,
        "instrument": {"symbol": "AMD", "assetType": "EQUITY"}
    }]
}
```

### Equity — Limit Buy
```json
{
    "orderType": "LIMIT",
    "session": "NORMAL",
    "duration": "DAY",
    "orderStrategyType": "SINGLE",
    "price": "10.00",
    "orderLegCollection": [{
        "instruction": "BUY",
        "quantity": 4,
        "instrument": {"symbol": "INTC", "assetType": "EQUITY"}
    }]
}
```
`price` is a **string**, not a number.

### Equity — Sell (limit, GTC)
Same as limit buy but `"instruction": "SELL"` and `"duration": "GOOD_TILL_CANCEL"`.

### Options — Buy to Open
```json
{
    "orderType": "LIMIT",
    "session": "NORMAL",
    "price": 0.10,
    "duration": "GOOD_TILL_CANCEL",
    "orderStrategyType": "SINGLE",
    "complexOrderStrategyType": "NONE",
    "orderLegCollection": [{
        "instruction": "BUY_TO_OPEN",
        "quantity": 3,
        "instrument": {"symbol": "AAPL  240517P00190000", "assetType": "OPTION"}
    }]
}
```

### Options — Sell to Open
Same but `"instruction": "SELL_TO_OPEN"`.

**Option symbol format:** `"UNDERLYING  YYMMDD[C/P]STRIKE"` — underlying padded to 6 chars with spaces, then 6-digit date, then C/P, then strike × 1000 zero-padded to 8 digits.
Example: AAPL May 17 2024 $190 put → `"AAPL  240517P00190000"`

### Vertical Spread
```json
{
    "orderType": "NET_DEBIT",
    "session": "NORMAL",
    "price": "0.10",
    "duration": "DAY",
    "orderStrategyType": "SINGLE",
    "orderLegCollection": [
        {"instruction": "BUY_TO_OPEN",  "quantity": 2, "instrument": {"symbol": "XYZ   240315P00045000", "assetType": "OPTION"}},
        {"instruction": "SELL_TO_OPEN", "quantity": 2, "instrument": {"symbol": "XYZ   240315P00043000", "assetType": "OPTION"}}
    ]
}
```
Use `NET_DEBIT` for debit spreads, `NET_CREDIT` for credit spreads.

### Trailing Stop
```json
{
    "orderType": "TRAILING_STOP",
    "session": "NORMAL",
    "duration": "DAY",
    "orderStrategyType": "SINGLE",
    "complexOrderStrategyType": "NONE",
    "stopPriceLinkBasis": "BID",
    "stopPriceLinkType": "VALUE",
    "stopPriceOffset": 10,
    "orderLegCollection": [{
        "instruction": "SELL",
        "quantity": 10,
        "instrument": {"symbol": "XYZ", "assetType": "EQUITY"}
    }]
}
```

### OCO (One-Cancels-Other)
```json
{
    "orderStrategyType": "OCO",
    "childOrderStrategies": [
        {
            "orderType": "LIMIT", "session": "NORMAL", "price": "45.97",
            "duration": "DAY", "orderStrategyType": "SINGLE",
            "orderLegCollection": [{"instruction": "SELL", "quantity": 2, "instrument": {"symbol": "XYZ", "assetType": "EQUITY"}}]
        },
        {
            "orderType": "STOP_LIMIT", "session": "NORMAL", "price": "37.00", "stopPrice": "37.03",
            "duration": "DAY", "orderStrategyType": "SINGLE",
            "orderLegCollection": [{"instruction": "SELL", "quantity": 2, "instrument": {"symbol": "XYZ", "assetType": "EQUITY"}}]
        }
    ]
}
```

### TRIGGER (buy then auto-sell)
```json
{
    "orderType": "LIMIT", "session": "NORMAL", "price": "34.97",
    "duration": "DAY", "orderStrategyType": "TRIGGER",
    "orderLegCollection": [{"instruction": "BUY", "quantity": 10, "instrument": {"symbol": "XYZ", "assetType": "EQUITY"}}],
    "childOrderStrategies": [{
        "orderType": "LIMIT", "session": "NORMAL", "price": "42.03",
        "duration": "DAY", "orderStrategyType": "SINGLE",
        "orderLegCollection": [{"instruction": "SELL", "quantity": 10, "instrument": {"symbol": "XYZ", "assetType": "EQUITY"}}]
    }]
}
```

### TRIGGER — Credit Spread with Auto-Close Child
Opens a vertical credit spread; once filled, a child order activates to close the spread at a target debit price (e.g., stop-loss or take-profit).

**Workflow:** Get quotes for both legs → calculate spread mid credit → build TRIGGER with child close order.

```json
{
    "orderType": "NET_CREDIT",
    "session": "NORMAL",
    "price": "1.25",
    "duration": "DAY",
    "orderStrategyType": "TRIGGER",
    "orderLegCollection": [
        {"instruction": "SELL_TO_OPEN", "quantity": 1, "instrument": {"symbol": "SPXW  260330P06140000", "assetType": "OPTION"}},
        {"instruction": "BUY_TO_OPEN",  "quantity": 1, "instrument": {"symbol": "SPXW  260330P06110000", "assetType": "OPTION"}}
    ],
    "childOrderStrategies": [{
        "orderType": "NET_DEBIT",
        "session": "NORMAL",
        "price": "2.50",
        "duration": "DAY",
        "orderStrategyType": "SINGLE",
        "orderLegCollection": [
            {"instruction": "BUY_TO_CLOSE",  "quantity": 1, "instrument": {"symbol": "SPXW  260330P06140000", "assetType": "OPTION"}},
            {"instruction": "SELL_TO_CLOSE", "quantity": 1, "instrument": {"symbol": "SPXW  260330P06110000", "assetType": "OPTION"}}
        ]
    }]
}
```
- Parent: `NET_CREDIT` spread opens the position. Child: `NET_DEBIT` spread closes it.
- The child activates immediately after the parent fills — it is a **standing limit order**, not a stop. It will fill as soon as the spread can be closed at the specified debit or better.
- **Limitation:** Schwab API does not support `STOP` order types on multi-leg spreads. To approximate a stop-loss, use a `NET_DEBIT` child at the max debit you're willing to pay. Be aware this will fill immediately if the spread is already at or below that debit when the parent fills.
- For a true stop-loss based on the underlying's price (e.g., "close if SPX hits 6300"), this cannot be expressed in a single API order. Handle it programmatically or via Schwab's platform UI.

## Subagent Invocation

Always invoke `list_orders`, `list_all_orders`, and `get_order` via a **general-purpose subagent** (`Agent` tool). This keeps API responses — and any temp file contents — out of the main conversation context, saving tokens.

The subagent should:
1. Call the tool with the user's parameters (include this skill's guidance in the prompt)
2. If the response references a temp file, read it with the `Read` tool
3. Fulfill the user's request (summarize, analyze, etc.)
4. Return only the concise final answer — never the raw JSON

**Do NOT use subagents for mutating tools** (`place_order`, `cancel_order`, `replace_order`). These require the two-step safety pattern with user confirmation in the main conversation.

## Large Response Compression

When `list_orders` or `list_all_orders` returns >10 orders, the full JSON is written to a temp file and only a count + file path is returned. Use the `Read` tool to access the file when full data is needed (e.g., for analysis or plotting). Responses with ≤10 orders are returned inline with summary annotations.

**Temp file format:** The file contains a JSON **list** of order dicts — `[{order1}, {order2}, ...]`. It is NOT a dict. Do not use `data["key"]` on it; iterate the list directly.

## Looking Up Order IDs

When the user asks to cancel or replace an order but doesn't provide an `order_id`:
1. Call `list_orders()` with no arguments — it defaults to today's orders
2. Show the results to the user and ask which order to cancel/replace
3. Proceed with `cancel_order` or `replace_order` once the user identifies the order

## Timestamps

All timestamps in Schwab API order responses (`closeTime`, `enteredTime`, etc.) are in **UTC** with `+0000` offset (e.g., `"2026-03-20T14:18:33+0000"`). Convert to Eastern with `.astimezone(ZoneInfo("America/New_York"))` when displaying to the user.

## Listing Orders

`list_orders` date range is optional. Omit both `from_entered_time` and `to_entered_time` to get today's orders. When providing a custom range, use format: `"YYYY-MM-DDTHH:mm:ss.000Z"` (ISO 8601, UTC). Max range: 1 year.

Valid `status` values: `AWAITING_PARENT_ORDER`, `AWAITING_CONDITION`, `AWAITING_STOP_CONDITION`, `AWAITING_MANUAL_REVIEW`, `ACCEPTED`, `AWAITING_UR_OUT`, `PENDING_ACTIVATION`, `QUEUED`, `WORKING`, `REJECTED`, `PENDING_CANCEL`, `CANCELED`, `PENDING_REPLACE`, `REPLACED`, `FILLED`, `EXPIRED`, `NEW`, `AWAITING_RELEASE_TIME`, `PENDING_ACKNOWLEDGEMENT`, `PENDING_RECALL`, `UNKNOWN`.

`max_results` defaults to 3000. Rate limit: 120 API requests per minute.

## Key Field Values

| Field | Common values |
|---|---|
| `session` | `NORMAL`, `AM` (pre-market), `PM` (after-hours), `SEAMLESS` |
| `duration` | `DAY`, `GOOD_TILL_CANCEL`, `FILL_OR_KILL` |
| `orderType` | `MARKET`, `LIMIT`, `STOP`, `STOP_LIMIT`, `TRAILING_STOP`, `NET_DEBIT`, `NET_CREDIT` |
| `instruction` (equity) | `BUY`, `SELL`, `BUY_TO_COVER`, `SELL_SHORT` |
| `instruction` (option) | `BUY_TO_OPEN`, `BUY_TO_CLOSE`, `SELL_TO_OPEN`, `SELL_TO_CLOSE` |
| `assetType` | `EQUITY`, `OPTION` |

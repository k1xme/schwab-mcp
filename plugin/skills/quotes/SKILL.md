---
name: quotes
description: Use when user asks for stock prices, quotes, price history, charts, OHLCV data, or option chains on Schwab
---

# Schwab Quotes & Market Data

## Tool Map

| Intent | Tool | Key params |
|---|---|---|
| Real-time quote(s) | `get_quotes` | `symbols` (list) |
| Historical OHLCV candles | `get_price_history` | `symbol`, `period_type`, `period`, `frequency_type`, `frequency` |
| Available option expirations | `get_option_expirations` | `symbol` |
| Option chain | `get_option_chain` | `symbol`, `contract_type`, `strike_count`, `from_date`, `to_date` |

## Subagent Invocation

Always invoke `get_quotes`, `get_price_history`, and `get_option_chain` via a **general-purpose subagent** (`Agent` tool). This keeps API responses — and any temp file contents — out of the main conversation context, saving tokens.

The subagent should:
1. Call the tool with the user's parameters (include this skill's guidance in the prompt)
2. If the response references a temp file, read it with the `Read` tool
3. Fulfill the user's request (summarize, analyze, plot, etc.)
4. Return only the concise final answer — never the raw JSON

For option chains, the subagent should call `get_option_expirations` first, then `get_option_chain`.

## Large Response Compression

Tools that can return large responses automatically write full JSON to a temp file and return a summary with the file path instead. Use the `Read` tool to access the file when full data is needed (e.g., for analysis or plotting).

| Tool | Writes to file when | File format |
|---|---|---|
| `get_quotes` | >5 symbols | **dict** — `{"AAPL": {...}, "MSFT": {...}}` |
| `get_price_history` | >20 candles | **dict** — `{"symbol": "...", "candles": [...]}` |
| `get_option_chain` | always | **dict** — `{"symbol": "...", "callExpDateMap": {...}, ...}` |

## get_quotes

`symbols` is a **list of strings** or a comma-separated string:
```
get_quotes(symbols=["AAPL", "MSFT", "SPY"])
get_quotes(symbols="AAPL,AMD")
```

`fields`: `"all"` (default), `"quote"`, `"fundamental"`

`indicative`: Set `True` for indicative (non-tradable) quotes. Default `False`.

Key response fields per symbol: `lastPrice`, `bidPrice`, `askPrice`, `totalVolume`, `netChange`, `netPercentChange`, `52WkHigh`, `52WkLow`

## get_price_history

Valid combinations:

| `period_type` | Valid `period` (default) | Valid `frequency_type` | Valid `frequency` |
|---|---|---|---|
| `day` | 1, 2, 3, 4, 5, 10 (10) | `minute` | 1, 5, 10, 15, 30 |
| `month` | 1, 2, 3, 6 (1) | `daily`, `weekly` | 1 |
| `year` | 1, 2, 3, 5, 10, 15, 20 (1) | `daily`, `weekly`, `monthly` | 1 |
| `ytd` | 1 (1) | `daily`, `weekly` | 1 |

`start_date`/`end_date`: accept datetime string or UNIX epoch ms. Setting `start_date` overrides `period`.

Examples:
```
# 10 days of 5-minute candles
get_price_history(symbol="AAPL", period_type="day", period=10,
                  frequency_type="minute", frequency=5)

# 1 year of daily candles
get_price_history(symbol="AAPL", period_type="year", period=1,
                  frequency_type="daily", frequency=1)

# Custom date range (overrides period)
get_price_history(symbol="AAPL", start_date="2026-01-01", end_date="2026-03-21",
                  frequency_type="daily", frequency=1)
```

Response: `candles` array with `open`, `high`, `low`, `close`, `volume`, `datetime` (epoch ms)

## get_option_chain

**Always call `get_option_expirations` first** to confirm available dates, then filter with `from_date`/`to_date`.

```
# All calls and puts, nearest 5 strikes, next 30 days
get_option_chain(symbol="AAPL", strike_count=5,
                 from_date="2026-03-21", to_date="2026-04-21")

# Only puts, OTM, specific expiration
get_option_chain(symbol="AAPL", contract_type="PUT",
                 range="OTM", from_date="2026-04-17", to_date="2026-04-17")
```

`contract_type`: `"CALL"`, `"PUT"`, `"ALL"` (default)
`range`: `"ITM"`, `"NTM"`, `"OTM"`, `"SAK"`, `"SBK"`, `"SNK"`, `"ALL"`
`strategy`: `"SINGLE"` (default), `"ANALYTICAL"`, `"COVERED"`, `"VERTICAL"`, `"CALENDAR"`, `"STRANGLE"`, `"STRADDLE"`, `"BUTTERFLY"`, `"CONDOR"`, `"DIAGONAL"`, `"COLLAR"`, `"ROLL"`
`entitlement`: `"PN"` (PayingPro), `"NP"` (NonPro), `"PP"` (NonPayingPro)

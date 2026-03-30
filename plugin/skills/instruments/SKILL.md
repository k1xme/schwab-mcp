---
name: instruments
description: Use when user asks to look up a stock symbol, find a company by name, get fundamental data, or look up an instrument by CUSIP on Schwab
---

# Schwab Instruments

## Tool Map

| Intent | Tool | Key params |
|---|---|---|
| Find symbol / company / fundamentals | `search_instruments` | `symbol`, `projection` |
| Look up by CUSIP | `get_instrument` | `cusip` |

## search_instruments

`projection` controls search mode:

| `projection` | `symbol` arg meaning | Returns |
|---|---|---|
| `"symbol-search"` | Exact symbol (e.g. `"AAPL"`) | Matching instruments |
| `"symbol-regex"` | Regex on symbol (e.g. `"AAP.*"`) | Matching instruments |
| `"desc-search"` | Keyword in description (e.g. `"apple"`) | Matching instruments |
| `"desc-regex"` | Regex on description | Matching instruments |
| `"search"` | Search by symbol or description | Matching instruments |
| `"fundamental"` | Exact symbol (e.g. `"AAPL"`) | Fundamental data (P/E, EPS, div yield, etc.) |

Examples:
```
# Look up AAPL fundamentals
search_instruments(symbol="AAPL", projection="fundamental")

# Find all symbols starting with "AAP"
search_instruments(symbol="AAP.*", projection="symbol-regex")

# Search by company name
search_instruments(symbol="apple", projection="desc-search")
```

## get_instrument

Requires the 9-character CUSIP identifier. Use `search_instruments` first to find the CUSIP if unknown.

```
get_instrument(cusip="037833100")   # Apple Inc.
```

Response includes `symbol`, `description`, `exchange`, `assetType`, `cusip`

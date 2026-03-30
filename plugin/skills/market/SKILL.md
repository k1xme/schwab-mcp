---
name: market
description: Use when user asks about market hours, trading sessions, top movers, gainers, or losers on Schwab
---

# Schwab Market Data

## Tool Map

| Intent | Tool | Key params |
|---|---|---|
| Trading session hours | `get_market_hours` | `markets`, `date` |
| Top movers / gainers / losers | `get_movers` | `index`, `sort`, `frequency` |

## get_market_hours

`markets` is a **list of strings**:
```
get_market_hours(markets=["equity", "option"])
get_market_hours(markets=["equity"], date="2026-03-21")
```

Valid markets: `"equity"`, `"option"`, `"bond"`, `"future"`, `"forex"`

Response includes `isOpen`, `sessionHours.regularMarket[].start/end`, `sessionHours.preMarket`, `sessionHours.postMarket`

## get_movers

Only available during market hours. Returns top N movers within an index.

```
get_movers(index="$SPX", sort="PERCENT_CHANGE_UP")
get_movers(index="NASDAQ", sort="VOLUME", frequency=5)
```

| Param | Values |
|---|---|
| `index` | `"$COMPX"` (NASDAQ), `"$SPX"` (S&P 500), `"$DJI"` (Dow), `"NYSE"`, `"NASDAQ"`, `"OTCBB"`, `"INDEX_ALL"`, `"EQUITY_ALL"`, `"OPTION_ALL"`, `"OPTION_PUT"`, `"OPTION_CALL"` |
| `sort` | `"VOLUME"`, `"TRADES"`, `"PERCENT_CHANGE_UP"`, `"PERCENT_CHANGE_DOWN"` |
| `frequency` | `0`, `1`, `5`, `10`, `30`, `60` (minutes; 0 = all day) |

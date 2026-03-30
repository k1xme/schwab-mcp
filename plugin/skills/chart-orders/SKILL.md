---
name: chart-orders
description: Use when user asks to plot, chart, or visualize their filled orders on a price chart for a symbol — supports single-day intraday or multi-day date ranges
---

# Chart Filled Orders on Price

Plot filled option/equity orders as markers on a symbol's candlestick chart. Supports single-day intraday or multi-day date ranges.

## Workflow

1. **Fetch orders** — `list_orders(from_entered_time, to_entered_time, status="FILLED")`
2. **Fetch candles** — `get_price_history(symbol, frequency_type="minute", frequency=5, start_date, end_date)`
3. **Run chart script** — `.venv/bin/python plugin/skills/schwab-chart-orders/chart_orders.py`

## Gotchas

| Pitfall | Fix |
|---|---|
| `get_price_history` rejects ISO dates | Pass **epoch milliseconds** for `start_date`/`end_date` |
| Orders response is huge (>50KB) | It auto-saves to a file (JSON **list**, not dict); read that file path from the result |
| Candle response spans 2 trading days | The chart script filters to the target date automatically |
| After-hours flat candles compress y-axis | The chart script strips them |
| Order times are UTC | Schwab API returns `closeTime`/`enteredTime` in UTC (e.g., `"2026-03-20T14:18:33+0000"`). The script converts to ET internally — do **not** pre-convert |
| `plotly.min.js` missing | Run the one-time curl setup (see bottom of this file) |
| `matplotlib` not installed | Only needed for `--format png`; run with `.venv/bin/python` |
| Multi-day chart too dense | Use larger candle frequency (`frequency=15` or `30`) for ranges > 5 days |

## Step-by-Step

### 1. Convert target date to epoch ms

```python
python3 -c "
from datetime import datetime, timezone
d = datetime(YYYY, M, D, tzinfo=timezone.utc)
print(int(d.timestamp() * 1000))
print(int((d.timestamp() + 86400) * 1000))
"
```

### 2. Fetch data (parallel)

```
list_orders(from_entered_time="YYYY-MM-DDT00:00:00.000Z",
            to_entered_time="YYYY-MM-DDT23:59:59.999Z",
            status="FILLED")

get_price_history(symbol="$SPX",
                  frequency_type="minute", frequency=5,
                  start_date="<epoch_ms>", end_date="<epoch_ms+86400000>")
```

For multi-day requests, use the full date range for both calls and increase candle frequency:

```
list_orders(from_entered_time="YYYY-MM-DDT00:00:00.000Z",
            to_entered_time="YYYY-MM-DDT23:59:59.999Z",
            status="FILLED")

get_price_history(symbol="$SPX",
                  frequency_type="minute", frequency=15,
                  start_date="<start_epoch_ms>", end_date="<end_epoch_ms>")
```

### 3. Parse orders from saved file

The orders tmp file is a **JSON list** of order dicts (not a dict). Read and filter for the target underlying symbol:

```python
import json
with open(orders_file) as f:
    orders = json.load(f)  # list of order dicts
# filter by underlying symbol in orderLegCollection
orders = [
    o for o in orders
    if any(
        symbol.upper() in leg.get("instrument", {}).get("symbol", "").upper()
        for leg in o.get("orderLegCollection", [])
    )
]
```

### 4. Generate chart

```bash
.venv/bin/python plugin/skills/schwab-chart-orders/chart_orders.py \
  --candles-file candles.json \
  --orders-file orders.json \
  --symbol SPX \
  --date 2026-03-20
```

Output: `plugin/skills/schwab-chart-orders/chart.html` (interactive Plotly chart, open in browser)

For static PNG: add `--format png --output chart.png`

For multi-day chart (omit `--date` — script infers date range from candle data):

```bash
.venv/bin/python plugin/skills/schwab-chart-orders/chart_orders.py \
  --candles-file candles.json \
  --orders-file orders.json \
  --symbol SPX
```

Multi-day charts show day separators with date labels and remove overnight gaps. Use larger candle frequencies for wider ranges (e.g., `frequency=15` for 5+ days).

The script handles: filtering candles to the target date (single-day) or stripping after-hours per day (multi-day), classifying orders (buy/sell/spread), mapping fill times to price, candlestick rendering, hover tooltips, zoom/pan, legend toggle, and click-to-view order details.

### Setup: Plotly.js (one-time)

```bash
curl -o plugin/skills/schwab-chart-orders/plotly.min.js \
  https://cdn.plot.ly/plotly-2.35.0.min.js
```

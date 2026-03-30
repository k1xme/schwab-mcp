#!/usr/bin/env python3
"""Plot filled orders on a price chart.

Usage (interactive HTML, single day):
    python chart_orders.py \\
        --candles-file candles.json \\
        --orders-file orders.json \\
        --symbol SPX \\
        --date 2026-03-20

Usage (interactive HTML, multi-day — omit --date):
    python chart_orders.py \\
        --candles-file candles.json \\
        --orders-file orders.json \\
        --symbol SPX

Usage (static PNG, single day only):
    python chart_orders.py \\
        --candles-file candles.json \\
        --orders-file orders.json \\
        --symbol SPX \\
        --date 2026-03-20 \\
        --format png --output chart.png

Input formats:
    candles.json: Schwab get_price_history response JSON (full response with
                  "candles" array, or just the array itself).
    orders.json:  Array of order dicts, each with at minimum:
                  orderId, orderType, price, closeTime, legs[{instruction,
                  quantity, symbol}], and optionally complexOrderStrategyType.

Single-day mode (--date provided): filters candles to the target date, strips
after-hours flat bars. Multi-day mode (--date omitted): uses all candles, strips
after-hours per day, removes overnight gaps, adds day separators.

HTML output renders an interactive Plotly candlestick chart with hover tooltips,
zoom/pan, legend toggle, and click-to-view order details. PNG output renders a
static matplotlib chart (single-day only).
"""

import argparse
import os
import json
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from itertools import groupby
from pathlib import Path

ET = ZoneInfo("America/New_York")


# ---------------------------------------------------------------------------
# Candle helpers
# ---------------------------------------------------------------------------

def load_candles(path: str) -> list[dict]:
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, dict):
        # Full Schwab response: {"symbol": ..., "candles": [...]}
        return data.get("candles", [])
    return data  # bare array


def filter_candles_to_date(candles: list[dict], target: str) -> list[dict]:
    """Keep only candles whose datetime falls on *target* (YYYY-MM-DD) in ET."""
    target_date = datetime.strptime(target, "%Y-%m-%d").date()
    out = []
    for c in candles:
        dt = datetime.fromtimestamp(c["datetime"] / 1000, tz=timezone.utc).astimezone(ET)
        if dt.date() == target_date:
            out.append(c)
    return out


def strip_afterhours_flat(candles: list[dict]) -> list[dict]:
    """Remove trailing flat candles where O=H=L=C (after-hours padding)."""
    if len(candles) < 3:
        return candles
    last_real = len(candles) - 1
    for i in range(len(candles) - 1, -1, -1):
        c = candles[i]
        if not (c["open"] == c["high"] == c["low"] == c["close"]):
            last_real = i
            break
    # keep one extra candle past the last real one for the closing bar
    return candles[: last_real + 2] if last_real + 2 <= len(candles) else candles


def _strip_afterhours_per_day(candles: list[dict]) -> list[dict]:
    """Group candles by ET date, strip flat trailing candles per day (strict, no extra bar)."""

    def _date_key(c):
        return datetime.fromtimestamp(c["datetime"] / 1000, tz=timezone.utc).astimezone(ET).date()

    result = []
    for _, group in groupby(candles, key=_date_key):
        day_candles = list(group)
        last_real = -1
        for i in range(len(day_candles) - 1, -1, -1):
            c = day_candles[i]
            if not (c["open"] == c["high"] == c["low"] == c["close"]):
                last_real = i
                break
        if last_real >= 0:
            result.extend(day_candles[: last_real + 1])
    return result


# ---------------------------------------------------------------------------
# Order helpers
# ---------------------------------------------------------------------------

def load_orders(path: str) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def parse_order_time(t: str) -> datetime:
    return datetime.strptime(t, "%Y-%m-%dT%H:%M:%S%z").astimezone(ET)


def strike_label(symbol: str) -> str:
    """Extract strike and C/P from OCC symbol like 'SPXW  260320P06480000'."""
    sym = symbol.strip()
    try:
        strike = int(sym[-8:]) / 1000
    except ValueError:
        return sym  # Not an option symbol, return as-is
    cp = "P" if "P" in sym[6:] else "C"
    return f"{strike:.0f}{cp}"


def classify_orders(orders: list[dict], candle_times_ms, closes, use_index=False):
    """Return (buys, sells, spreads, raw_orders).

    buys/sells: list of (dt, price, label) — or (index, price, label, dt_str) when use_index=True
    spreads: list of (dt, price, label, is_debit) — or (index, price, label, is_debit, dt_str)
    raw_orders: dict with keys 'buys', 'sells', 'spreads'
    """

    def spx_at(order_ms):
        best = 0
        for i, ct in enumerate(candle_times_ms):
            if ct <= order_ms:
                best = i
        return best

    buys, sells, spreads = [], [], []
    raw = {"buys": [], "sells": [], "spreads": []}

    for o in orders:
        ct = o.get("closeTime")
        if not ct:
            continue
        dt = parse_order_time(ct)
        dt_ms = int(dt.timestamp() * 1000)
        best_idx = spx_at(dt_ms)
        price = closes[best_idx]
        legs = o.get("legs") or o.get("orderLegCollection", [])
        if not legs:
            continue
        # Normalize: raw API nests symbol under instrument
        for lg in legs:
            if "symbol" not in lg and "instrument" in lg:
                lg["symbol"] = lg["instrument"].get("symbol", "")

        first = best_idx if use_index else dt
        dt_str = dt.strftime("%Y-%m-%d %H:%M")

        if len(legs) > 1:
            parts = []
            for lg in legs:
                short = lg["instruction"].replace("_TO_OPEN", "").replace("_TO_CLOSE", "")
                parts.append(f"{short} {int(lg['quantity'])}x {strike_label(lg['symbol'])}")
            order_type = o.get("orderType", "")
            is_debit = "DEBIT" in order_type
            if use_index:
                spreads.append((first, price, " / ".join(parts), is_debit, dt_str))
            else:
                spreads.append((first, price, " / ".join(parts), is_debit))
            raw["spreads"].append(o)
        else:
            lg = legs[0]
            lbl = f"{int(lg['quantity'])}x {strike_label(lg['symbol'])} @${o.get('price', '?')}"
            if "BUY" in lg["instruction"]:
                if use_index:
                    buys.append((first, price, lbl, dt_str))
                else:
                    buys.append((first, price, lbl))
                raw["buys"].append(o)
            else:
                if use_index:
                    sells.append((first, price, lbl, dt_str))
                else:
                    sells.append((first, price, lbl))
                raw["sells"].append(o)

    return buys, sells, spreads, raw


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def _format_date_title(date_str: str) -> str:
    """Convert YYYY-MM-DD to 'Month D, YYYY'."""
    dt = datetime.strptime(date_str, "%Y-%m-%d")
    return dt.strftime("%B %d, %Y").replace(" 0", " ")


def _format_date_range(candles: list[dict]) -> str:
    """Infer min/max dates from candle timestamps (in ET) and return formatted range.

    Rules:
    - Single day: "Mar 20, 2026"
    - Same month: "Mar 16\u201322, 2026"
    - Cross-month: "Feb 28 \u2013 Mar 5, 2026"
    - Cross-year: "Dec 29, 2025 \u2013 Jan 2, 2026"
    """
    dates = [
        datetime.fromtimestamp(c["datetime"] / 1000, tz=timezone.utc).astimezone(ET).date()
        for c in candles
    ]
    min_d, max_d = min(dates), max(dates)

    def _fmt_day(d):
        return d.strftime("%b ") + str(d.day)

    if min_d == max_d:
        return f"{_fmt_day(min_d)}, {min_d.year}"
    elif min_d.year != max_d.year:
        return f"{_fmt_day(min_d)}, {min_d.year} \u2013 {_fmt_day(max_d)}, {max_d.year}"
    elif min_d.month != max_d.month:
        return f"{_fmt_day(min_d)} \u2013 {_fmt_day(max_d)}, {max_d.year}"
    else:
        return f"{_fmt_day(min_d)}\u2013{max_d.day}, {max_d.year}"


def _build_day_separators(candles: list[dict]) -> tuple[list[dict], list[dict]]:
    """Return (shapes, annotations) for Plotly layout marking trading day boundaries.

    Each new trading day (except the first) gets a vertical dashed line and a date label.
    Candles are assumed to be in chronological order; indices are sequential (0, 1, 2...).
    """
    shapes, annotations = [], []
    prev_date = None
    for i, c in enumerate(candles):
        dt = datetime.fromtimestamp(c["datetime"] / 1000, tz=timezone.utc).astimezone(ET)
        cur_date = dt.date()
        if prev_date is not None and cur_date != prev_date:
            shapes.append({
                "type": "line",
                "x0": i, "x1": i,
                "y0": 0, "y1": 1,
                "xref": "x", "yref": "paper",
                "line": {"color": "#ccc", "width": 1, "dash": "dash"},
                "opacity": 0.6,
            })
            label = dt.strftime("%b ") + str(dt.day)
            annotations.append({
                "x": i,
                "y": 1.0,
                "xref": "x", "yref": "paper",
                "text": label,
                "showarrow": False,
                "font": {"size": 10, "color": "#888"},
                "yshift": 10,
            })
        prev_date = cur_date
    return shapes, annotations


def _build_candlestick_trace(candles, use_index=False):
    """Return a Plotly candlestick trace dict.

    When use_index=True, x-axis uses sequential integers and time labels
    are in the 'text' field for hover display.
    """
    time_labels = [
        datetime.fromtimestamp(c["datetime"] / 1000, tz=timezone.utc)
        .astimezone(ET).strftime("%Y-%m-%d %H:%M")
        for c in candles
    ]

    trace = {
        "type": "candlestick",
        "x": list(range(len(candles))) if use_index else time_labels,
        "open": [c["open"] for c in candles],
        "high": [c["high"] for c in candles],
        "low": [c["low"] for c in candles],
        "close": [c["close"] for c in candles],
        "increasing": {"line": {"color": "#00C853"}},
        "decreasing": {"line": {"color": "#FF1744"}},
        "name": "Price",
        "showlegend": False,
    }

    if use_index:
        trace["text"] = time_labels
        trace["hovertemplate"] = (
            "Open: %{open}<br>High: %{high}<br>Low: %{low}<br>"
            "Close: %{close}<br>Time: %{text}<extra></extra>"
        )

    return trace


def _build_order_traces(buys, sells, spreads, use_index=False):
    """Return list of Plotly scatter trace dicts for order markers.

    When use_index=True:
    - buys/sells tuples are (index, price, label, dt_str)
    - spreads tuples are (index, price, label, is_debit, dt_str)
    - x-values are integers, dt_str goes into customdata for hover
    """
    traces = []

    def _make_trace(items, name_prefix, color, symbol_marker, size):
        if not items:
            return
        if use_index:
            xs = [item[0] for item in items]
            dt_strs = [item[-1] for item in items]
            customdata = [[ds] for ds in dt_strs]
        else:
            xs = [item[0].strftime("%Y-%m-%d %H:%M") for item in items]
            customdata = None

        prices = [item[1] for item in items]
        labels = [item[2] for item in items]

        if use_index:
            hovertemplate = (
                f"<b>{name_prefix.upper()}</b><br>%{{text}}<br>"
                "Time: %{customdata[0]}<br>Price: %{y:.2f}<extra></extra>"
            )
        else:
            hovertemplate = (
                f"<b>{name_prefix.upper()}</b><br>%{{text}}<br>"
                "Time: %{x}<br>Price: %{y:.2f}<extra></extra>"
            )

        trace = {
            "type": "scatter",
            "mode": "markers",
            "x": xs,
            "y": prices,
            "text": labels,
            "hovertemplate": hovertemplate,
            "marker": {
                "symbol": symbol_marker,
                "size": size,
                "color": color,
                "line": {"color": "black", "width": 1},
            },
            "name": f"{name_prefix} ({len(items)})",
        }
        if customdata is not None:
            trace["customdata"] = customdata
        traces.append(trace)

    _make_trace(buys, "Buy", "#00C853", "triangle-up", 14)
    _make_trace(sells, "Sell", "#FF1744", "triangle-down", 14)

    # Split spreads into buy (debit) and sell (credit)
    if use_index:
        buy_spreads = [s for s in spreads if s[3]]   # is_debit=True
        sell_spreads = [s for s in spreads if not s[3]]
    else:
        buy_spreads = [s for s in spreads if s[3]]
        sell_spreads = [s for s in spreads if not s[3]]
    _make_trace(buy_spreads, "Buy Spread", "#00C853", "diamond", 12)
    _make_trace(sell_spreads, "Sell Spread", "#FF1744", "diamond", 12)

    return traces


def _build_spread_pair_lines(spreads, raw_spreads, use_index=False):
    """Match opening (debit) and closing (credit) spreads by leg symbols, return line traces.

    Returns a list of Plotly scatter traces — one per matched pair, drawn as a
    dashed line connecting the buy-spread marker to the sell-spread marker.
    """
    def _symbol_key(raw_order):
        """Frozenset of leg symbols for matching."""
        return frozenset(lg.get("symbol", "") for lg in (raw_order.get("legs") or raw_order.get("orderLegCollection", [])))

    # Separate into buy (debit) and sell (credit) with their indices
    buy_entries = []  # (spread_tuple, raw_order)
    sell_entries = []
    for s, r in zip(spreads, raw_spreads):
        is_debit = s[3]
        if is_debit:
            buy_entries.append((s, r))
        else:
            sell_entries.append((s, r))

    # Match by symbol key — first open with first close (chronological)
    sell_used = set()
    pairs = []
    for bs, br in buy_entries:
        bkey = _symbol_key(br)
        for j, (ss, sr) in enumerate(sell_entries):
            if j in sell_used:
                continue
            if _symbol_key(sr) == bkey:
                pairs.append((bs, ss))
                sell_used.add(j)
                break

    if not pairs:
        return []

    # Build one line trace for all pairs using None gaps
    xs, ys = [], []
    for bs, ss in pairs:
        if use_index:
            x0, x1 = bs[0], ss[0]
        else:
            x0 = bs[0].strftime("%Y-%m-%d %H:%M")
            x1 = ss[0].strftime("%Y-%m-%d %H:%M")
        xs.extend([x0, x1, None])
        ys.extend([bs[1], ss[1], None])

    return [{
        "type": "scatter",
        "mode": "lines",
        "x": xs,
        "y": ys,
        "line": {"color": "#888", "width": 1, "dash": "dot"},
        "showlegend": True,
        "name": f"Spread Pair ({len(pairs)})",
        "hoverinfo": "skip",
    }]


def _html_template(traces_json, layout_json, order_details_json, trace_categories_json, symbol, date_str, plotly_path, output, title_override=None):
    """Return complete HTML string for the interactive chart.

    Args:
        traces_json: JSON string of Plotly trace array
        layout_json: JSON string of Plotly layout dict
        order_details_json: JSON string of {"buys": [...], "sells": [...], "spreads": [...]}
        trace_categories_json: JSON string like ["buys", "sells", "spreads"] matching
                               the order of scatter traces (after the candlestick trace)
        symbol: Symbol label for title
        date_str: Target date YYYY-MM-DD (may be None in multi-day mode)
        plotly_path: Path to plotly.min.js
        title_override: Pre-formatted title string (used in multi-day mode)
    """
    if title_override is not None:
        page_title = title_override
    else:
        page_title = f"{symbol} Orders \u2014 {_format_date_title(date_str)}"
    # Use relative path from output file to plotly.min.js (works cross-platform, including WSL)
    try:
        output_dir = Path(output).resolve().parent if output else plotly_path.parent
        plotly_uri = os.path.relpath(plotly_path, output_dir)
    except ValueError:
        # Different drives on Windows — fall back to absolute file:// URI
        plotly_uri = plotly_path.as_uri()

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{page_title}</title>
<script src="{plotly_uri}"></script>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
         margin: 0; padding: 20px; background: #fafafa; }}
  #chart {{ width: 100%; height: 70vh; }}
  #detail-panel {{ display: none; margin-top: 16px; padding: 16px; background: #fff;
                   border: 1px solid #ddd; border-radius: 8px; font-size: 14px; }}
  #detail-panel h3 {{ margin: 0 0 8px 0; }}
  .leg {{ padding: 4px 0; border-bottom: 1px solid #eee; }}
  .leg:last-child {{ border-bottom: none; }}
  .dismiss {{ float: right; cursor: pointer; color: #999; font-size: 18px; }}
  .dismiss:hover {{ color: #333; }}
</style>
</head>
<body>
<div id="chart"></div>
<div id="detail-panel">
  <span class="dismiss" onclick="document.getElementById('detail-panel').style.display='none'">&times;</span>
  <div id="detail-content"></div>
</div>
<script>
var traces = {traces_json};
var layout = {layout_json};
var orderDetails = {order_details_json};
var categories = {trace_categories_json};

Plotly.newPlot('chart', traces, layout, {{responsive: true, displayModeBar: true}});

function esc(s) {{ var d = document.createElement('div'); d.textContent = String(s); return d.innerHTML; }}

var chartEl = document.getElementById('chart');
chartEl.on('plotly_click', function(data) {{
  var pt = data.points[0];
  var traceIdx = pt.curveNumber;
  var ptIdx = pt.pointNumber;

  // Curve 0 is candlestick — skip
  if (traceIdx === 0) return;

  if (traceIdx - 1 >= categories.length) return;
  var cat = categories[traceIdx - 1];
  var details = orderDetails[cat];
  if (!details || ptIdx >= details.length) return;

  var order = details[ptIdx];
  var panel = document.getElementById('detail-panel');
  var content = document.getElementById('detail-content');

  var html = '<h3>Order #' + esc(order.orderId) + '</h3>';
  html += '<p><b>Type:</b> ' + esc(order.orderType || 'N/A');
  if (order.complexOrderStrategyType) {{
    html += ' (' + esc(order.complexOrderStrategyType) + ')';
  }}
  html += '</p>';
  html += '<p><b>Price:</b> $' + esc(order.price || 'N/A') + '</p>';
  html += '<p><b>Filled:</b> ' + esc(order.closeTime || 'N/A') + '</p>';
  html += '<p><b>Legs:</b></p>';
  if (order.legs) {{
    order.legs.forEach(function(leg) {{
      html += '<div class="leg">' + esc(leg.instruction) + ' ' + esc(leg.quantity) + 'x ' + esc(leg.symbol) + '</div>';
    }});
  }}

  content.innerHTML = html;
  panel.style.display = 'block';
}});

chartEl.on('plotly_doubleclick', function() {{
  document.getElementById('detail-panel').style.display = 'none';
}});
</script>
</body>
</html>"""


def plot_chart(candles, buys, sells, spreads, symbol, date_str, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt

    candle_dts = [
        datetime.fromtimestamp(c["datetime"] / 1000, tz=timezone.utc).astimezone(ET)
        for c in candles
    ]
    closes = [c["close"] for c in candles]
    highs = [c["high"] for c in candles]
    lows = [c["low"] for c in candles]

    fig, ax = plt.subplots(figsize=(20, 10))

    _draw_price(ax, candle_dts, closes, highs, lows)
    _scatter(ax, buys, sells, spreads, marker_size=100, annotate=True)
    ax.set_xlabel("Time (ET)")
    ax.set_ylabel(f"{symbol} Price")
    ax.legend(loc="upper right", fontsize=9)
    ax.grid(True, alpha=0.25, linestyle="--")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=ET))
    ax.xaxis.set_major_locator(mdates.HourLocator(tz=ET))

    title_date = _format_date_title(date_str)
    fig.suptitle(
        f"{symbol} 5-min Chart with Filled Option Orders \u2014 {title_date}",
        fontsize=16,
        fontweight="bold",
        y=1.01,
    )
    fig.autofmt_xdate()
    plt.tight_layout()
    plt.savefig(output, dpi=150, bbox_inches="tight")
    print(f"Chart saved to {output}")


def _draw_price(ax, dts, closes, highs, lows):
    ax.fill_between(dts, lows, highs, alpha=0.12, color="#4a86c8")
    ax.plot(dts, closes, color="#2962FF", linewidth=1.5, label="Close", zorder=2)


def _scatter(ax, buys, sells, spreads, marker_size=100, annotate=False):
    if buys:
        ts, ps, ls = zip(*buys)
        ax.scatter(ts, ps, marker="^", color="#00C853", s=marker_size,
                   zorder=5, edgecolors="black", linewidths=0.5,
                   label=f"Buy ({len(buys)})")
        if annotate:
            _annotate_group(ax, ts, ps, ls, color="#00C853", below=True)

    if sells:
        ts, ps, ls = zip(*sells)
        ax.scatter(ts, ps, marker="v", color="#FF1744", s=marker_size,
                   zorder=5, edgecolors="black", linewidths=0.5,
                   label=f"Sell ({len(sells)})")
        if annotate:
            _annotate_group(ax, ts, ps, ls, color="#FF1744", below=False)

    if spreads:
        ts = [s[0] for s in spreads]
        ps = [s[1] for s in spreads]
        ls = [s[2] for s in spreads]
        ds = [s[3] for s in spreads]
        ax.scatter(ts, ps, marker="D", color="#FF9100", s=int(marker_size * 0.8),
                   zorder=5, edgecolors="black", linewidths=0.5,
                   label=f"Spreads ({len(spreads)})")
        if annotate:
            _annotate_spreads(ax, ts, ps, ls, ds)


def _annotate_group(ax, times, prices, labels, color, below):
    for i, (t, p, lbl) in enumerate(zip(times, prices, labels)):
        oy = (-20 - (i % 2) * 14) if below else (14 + (i % 2) * 14)
        ax.annotate(
            lbl, (t, p), textcoords="offset points", xytext=(8, oy),
            fontsize=7, ha="left", color=color, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      alpha=0.9, edgecolor=color, linewidth=0.5),
        )


def _annotate_spreads(ax, times, prices, labels, is_debits):
    offsets = [-25, 18, -40, 32, -55, 46, -70, 60]
    for i, (t, p, lbl, is_debit) in enumerate(zip(times, prices, labels, is_debits)):
        color = "#00C853" if is_debit else "#FF1744"
        bg = "#E8F5E9" if is_debit else "#FFEBEE"
        ax.annotate(
            lbl, (t, p), textcoords="offset points",
            xytext=(5, offsets[i % len(offsets)]),
            fontsize=6, ha="left", color=color, fontweight="bold",
            bbox=dict(boxstyle="round,pad=0.3", facecolor=bg,
                      alpha=0.9, edgecolor=color, linewidth=0.5),
            arrowprops=dict(arrowstyle="->", color=color, lw=0.8),
        )


# ---------------------------------------------------------------------------
# Interactive (Plotly) chart
# ---------------------------------------------------------------------------

def plot_interactive(candles, buys, sells, spreads, raw_orders, symbol, date_str, output):
    """Generate interactive Plotly HTML chart and write to output file."""
    plotly_path = Path(__file__).parent / "plotly.min.js"
    multi_day = date_str is None
    use_index = multi_day

    if multi_day:
        date_range = _format_date_range(candles)
        title_text = f"{symbol} Orders \u2014 {date_range}"
        title_override = title_text
    else:
        title_date = _format_date_title(date_str)
        title_text = f"{symbol} 5-min Chart with Filled Option Orders \u2014 {title_date}"
        title_override = None

    # Build traces
    traces = [_build_candlestick_trace(candles, use_index=use_index)]
    trace_categories = []

    order_traces = _build_order_traces(buys, sells, spreads, use_index=use_index)
    if buys:
        trace_categories.append("buys")
    if sells:
        trace_categories.append("sells")
    # Spreads are split into buy (debit) and sell (credit) traces
    buy_spreads_raw = [raw_orders["spreads"][i] for i, s in enumerate(spreads) if s[3]]
    sell_spreads_raw = [raw_orders["spreads"][i] for i, s in enumerate(spreads) if not s[3]]
    if buy_spreads_raw:
        trace_categories.append("buy_spreads")
    if sell_spreads_raw:
        trace_categories.append("sell_spreads")
    raw_orders = {**raw_orders, "buy_spreads": buy_spreads_raw, "sell_spreads": sell_spreads_raw}

    traces.extend(order_traces)

    # Add spread pair connecting lines
    pair_lines = _build_spread_pair_lines(spreads, raw_orders["spreads"], use_index=use_index)
    traces.extend(pair_lines)

    # Layout
    layout = {
        "title": {
            "text": title_text,
            "font": {"size": 16},
        },
        "xaxis": {
            "title": "Time (ET)",
            "rangeslider": {"visible": not multi_day},
            "type": "category",
        },
        "yaxis": {
            "title": f"{symbol} Price",
        },
        "legend": {
            "orientation": "h",
            "yanchor": "bottom",
            "y": 1.02,
            "xanchor": "right",
            "x": 1,
        },
        "hovermode": "closest",
        "plot_bgcolor": "#fafafa",
    }

    # Multi-day: add day separators and tick labels
    if multi_day:
        shapes, day_annotations = _build_day_separators(candles)
        layout["shapes"] = shapes
        layout.setdefault("annotations", []).extend(day_annotations)

        # Build tick labels: every Nth candle, suppress near day separators
        separator_indices = {s["x0"] for s in shapes}
        n = len(candles)
        step = max(1, n // 40)
        tickvals, ticktext = [], []
        for i in range(0, n, step):
            if any(abs(i - si) <= 2 for si in separator_indices):
                continue
            dt = datetime.fromtimestamp(
                candles[i]["datetime"] / 1000, tz=timezone.utc
            ).astimezone(ET)
            tickvals.append(i)
            ticktext.append(dt.strftime("%H:%M"))
        layout["xaxis"]["tickvals"] = tickvals
        layout["xaxis"]["ticktext"] = ticktext

    # Serialize for embedding
    def _safe_json(obj):
        return json.dumps(obj).replace("</", r"<\/")

    traces_json = _safe_json(traces)
    layout_json = _safe_json(layout)
    order_details_json = _safe_json(raw_orders)
    trace_categories_json = _safe_json(trace_categories)

    html = _html_template(traces_json, layout_json, order_details_json,
                          trace_categories_json, symbol, date_str, plotly_path, output,
                          title_override=title_override)

    with open(output, "w") as f:
        f.write(html)
    print(f"Interactive chart saved to {output}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--candles-file", required=True, help="Candles JSON file")
    p.add_argument("--orders-file", required=True, help="Orders JSON array file")
    p.add_argument("--symbol", default="SPX", help="Symbol label for title")
    p.add_argument("--date", default=None, help="Target date YYYY-MM-DD (omit for multi-day)")
    p.add_argument("--format", choices=["html", "png"], default="html",
                   help="Output format (default: html)")
    p.add_argument("--output", default=None,
                   help="Output file path (default: chart.html or chart.png)")
    args = p.parse_args()

    if args.output is None:
        script_dir = Path(__file__).parent
        if args.format == "html":
            args.output = str(script_dir / "chart.html")
        else:
            args.output = "chart.png"

    if args.format == "html":
        plotly_path = Path(__file__).parent / "plotly.min.js"
        if not plotly_path.exists():
            print(
                "Error: plotly.min.js not found.\n"
                "Download it with:\n"
                "  curl -o plugin/skills/schwab-chart-orders/plotly.min.js "
                "https://cdn.plot.ly/plotly-2.35.0.min.js",
                file=sys.stderr,
            )
            sys.exit(1)

    if args.format == "png" and args.date is None:
        print("Error: --date is required for PNG format", file=sys.stderr)
        sys.exit(1)

    candles = load_candles(args.candles_file)

    if args.date:
        candles = filter_candles_to_date(candles, args.date)
        if not candles:
            print(f"No candles found for {args.date}", file=sys.stderr)
            sys.exit(1)
        candles = strip_afterhours_flat(candles)
        use_index = False
    else:
        candles = _strip_afterhours_per_day(candles)
        if not candles:
            print("No candles found in data", file=sys.stderr)
            sys.exit(1)
        use_index = True

    orders = load_orders(args.orders_file)
    candle_times_ms = [c["datetime"] for c in candles]
    closes = [c["close"] for c in candles]

    buys, sells, spreads, raw_orders = classify_orders(
        orders, candle_times_ms, closes, use_index=use_index
    )
    total = len(buys) + len(sells) + len(spreads)
    print(f"Candles: {len(candles)}, Orders: {total} "
          f"({len(buys)} buy, {len(sells)} sell, {len(spreads)} spread)")

    if args.format == "png":
        plot_chart(candles, buys, sells, spreads, args.symbol, args.date, args.output)
    else:
        plot_interactive(candles, buys, sells, spreads, raw_orders,
                         args.symbol, args.date, args.output)


if __name__ == "__main__":
    main()

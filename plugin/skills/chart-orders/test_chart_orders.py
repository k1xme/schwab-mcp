"""Tests for chart_orders multi-day features."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from chart_orders import _strip_afterhours_per_day, _format_date_range, _build_day_separators, ET, classify_orders, _build_candlestick_trace, _build_order_traces
from datetime import datetime, timezone

_plotly_available = (Path(__file__).parent / "plotly.min.js").exists()


def _candle(year, month, day, hour, minute, o, h, l, c):
    """Helper: build a candle dict with epoch ms datetime."""
    dt = datetime(year, month, day, hour, minute, tzinfo=ET)
    return {"datetime": int(dt.timestamp() * 1000), "open": o, "high": h, "low": l, "close": c}


def test_strip_afterhours_per_day_removes_flat_tails():
    """Flat trailing candles are removed from each day independently."""
    candles = [
        _candle(2026, 3, 20, 9, 30, 100, 102, 99, 101),
        _candle(2026, 3, 20, 9, 35, 101, 103, 100, 102),
        _candle(2026, 3, 20, 16, 0, 102, 102, 102, 102),
        _candle(2026, 3, 20, 16, 5, 102, 102, 102, 102),
        _candle(2026, 3, 21, 9, 30, 200, 202, 199, 201),
        _candle(2026, 3, 21, 9, 35, 201, 203, 200, 202),
        _candle(2026, 3, 21, 16, 0, 202, 202, 202, 202),
    ]
    result = _strip_afterhours_per_day(candles)
    assert len(result) == 4
    assert result[0]["open"] == 100
    assert result[1]["open"] == 101
    assert result[2]["open"] == 200
    assert result[3]["open"] == 201


def test_strip_afterhours_per_day_no_flat():
    candles = [
        _candle(2026, 3, 20, 9, 30, 100, 102, 99, 101),
        _candle(2026, 3, 21, 9, 30, 200, 202, 199, 201),
    ]
    result = _strip_afterhours_per_day(candles)
    assert len(result) == 2


def test_strip_afterhours_per_day_single_day():
    candles = [
        _candle(2026, 3, 20, 9, 30, 100, 102, 99, 101),
        _candle(2026, 3, 20, 9, 35, 101, 103, 100, 102),
        _candle(2026, 3, 20, 16, 0, 102, 102, 102, 102),
    ]
    result = _strip_afterhours_per_day(candles)
    assert len(result) == 2


def test_format_date_range_same_month():
    candles = [
        _candle(2026, 3, 16, 9, 30, 100, 102, 99, 101),
        _candle(2026, 3, 22, 9, 30, 200, 202, 199, 201),
    ]
    assert _format_date_range(candles) == "Mar 16\u201322, 2026"


def test_format_date_range_cross_month():
    candles = [
        _candle(2026, 2, 28, 9, 30, 100, 102, 99, 101),
        _candle(2026, 3, 5, 9, 30, 200, 202, 199, 201),
    ]
    assert _format_date_range(candles) == "Feb 28 \u2013 Mar 5, 2026"


def test_format_date_range_cross_year():
    candles = [
        _candle(2025, 12, 29, 9, 30, 100, 102, 99, 101),
        _candle(2026, 1, 2, 9, 30, 200, 202, 199, 201),
    ]
    assert _format_date_range(candles) == "Dec 29, 2025 \u2013 Jan 2, 2026"


def test_format_date_range_single_day():
    candles = [
        _candle(2026, 3, 20, 9, 30, 100, 102, 99, 101),
        _candle(2026, 3, 20, 10, 0, 101, 103, 100, 102),
    ]
    assert _format_date_range(candles) == "Mar 20, 2026"


def test_build_day_separators_two_days():
    candles = [
        _candle(2026, 3, 20, 9, 30, 100, 102, 99, 101),
        _candle(2026, 3, 20, 9, 35, 101, 103, 100, 102),
        _candle(2026, 3, 21, 9, 30, 200, 202, 199, 201),
        _candle(2026, 3, 21, 9, 35, 201, 203, 200, 202),
    ]
    shapes, annotations = _build_day_separators(candles)
    assert len(shapes) == 1
    assert shapes[0]["x0"] == 2
    assert shapes[0]["x1"] == 2
    assert shapes[0]["line"]["dash"] == "dash"
    assert len(annotations) == 1
    assert "Mar" in annotations[0]["text"]
    assert "21" in annotations[0]["text"]
    assert annotations[0]["x"] == 2


def test_build_day_separators_three_days():
    candles = [
        _candle(2026, 3, 20, 9, 30, 100, 102, 99, 101),
        _candle(2026, 3, 21, 9, 30, 200, 202, 199, 201),
        _candle(2026, 3, 22, 9, 30, 300, 302, 299, 301),
    ]
    shapes, annotations = _build_day_separators(candles)
    assert len(shapes) == 2
    assert len(annotations) == 2


def test_build_day_separators_single_day():
    candles = [
        _candle(2026, 3, 20, 9, 30, 100, 102, 99, 101),
        _candle(2026, 3, 20, 9, 35, 101, 103, 100, 102),
    ]
    shapes, annotations = _build_day_separators(candles)
    assert len(shapes) == 0
    assert len(annotations) == 0


def _make_test_candles_and_orders():
    """Create minimal candle and order data for classify_orders tests."""
    candles = [
        _candle(2026, 3, 20, 9, 30, 5800, 5810, 5790, 5805),
        _candle(2026, 3, 20, 9, 35, 5805, 5815, 5800, 5810),
        _candle(2026, 3, 21, 9, 30, 5900, 5910, 5890, 5905),
    ]
    candle_times_ms = [c["datetime"] for c in candles]
    closes = [c["close"] for c in candles]
    orders = [
        {
            "orderId": 1, "orderType": "LIMIT", "price": 2.50,
            "closeTime": "2026-03-20T09:32:00-0400",
            "legs": [{"instruction": "BUY_TO_OPEN", "quantity": 1, "symbol": "SPXW  260320C05800000"}],
        },
        {
            "orderId": 2, "orderType": "LIMIT", "price": 3.00,
            "closeTime": "2026-03-21T09:31:00-0400",
            "legs": [{"instruction": "SELL_TO_CLOSE", "quantity": 1, "symbol": "SPXW  260320C05800000"}],
        },
    ]
    return candles, candle_times_ms, closes, orders


def test_classify_orders_default_returns_datetime():
    _, candle_times_ms, closes, orders = _make_test_candles_and_orders()
    buys, sells, spreads, raw = classify_orders(orders, candle_times_ms, closes)
    assert len(buys) == 1
    assert len(sells) == 1
    assert hasattr(buys[0][0], "strftime")
    assert hasattr(sells[0][0], "strftime")


def test_classify_orders_use_index_returns_int_and_dt_str():
    _, candle_times_ms, closes, orders = _make_test_candles_and_orders()
    buys, sells, spreads, raw = classify_orders(orders, candle_times_ms, closes, use_index=True)
    assert len(buys) == 1
    assert len(sells) == 1
    assert isinstance(buys[0][0], int)
    assert isinstance(sells[0][0], int)
    assert buys[0][0] == 0  # 09:32 maps to candle 0 (9:30)
    assert sells[0][0] == 2  # 09:31 day 2 maps to candle 2
    assert "2026-03-20" in buys[0][-1]
    assert "2026-03-21" in sells[0][-1]


def test_classify_orders_use_index_spreads():
    candles = [_candle(2026, 3, 20, 9, 30, 5800, 5810, 5790, 5805)]
    candle_times_ms = [candles[0]["datetime"]]
    closes = [candles[0]["close"]]
    orders = [{
        "orderId": 3, "orderType": "NET_DEBIT", "price": 1.50,
        "closeTime": "2026-03-20T09:32:00-0400",
        "complexOrderStrategyType": "VERTICAL",
        "legs": [
            {"instruction": "BUY_TO_OPEN", "quantity": 1, "symbol": "SPXW  260320C05800000"},
            {"instruction": "SELL_TO_OPEN", "quantity": 1, "symbol": "SPXW  260320C05810000"},
        ],
    }]
    buys, sells, spreads, raw = classify_orders(orders, candle_times_ms, closes, use_index=True)
    assert len(spreads) == 1
    assert isinstance(spreads[0][0], int)
    assert spreads[0][0] == 0
    assert spreads[0][3] is True  # is_debit
    assert "2026-03-20" in spreads[0][4]  # dt_str


def test_build_candlestick_trace_default():
    candles = [
        _candle(2026, 3, 20, 9, 30, 100, 102, 99, 101),
        _candle(2026, 3, 20, 9, 35, 101, 103, 100, 102),
    ]
    trace = _build_candlestick_trace(candles)
    assert trace["type"] == "candlestick"
    assert isinstance(trace["x"][0], str)
    assert "2026-03-20" in trace["x"][0]
    assert "hovertemplate" not in trace


def test_build_candlestick_trace_use_index():
    candles = [
        _candle(2026, 3, 20, 9, 30, 100, 102, 99, 101),
        _candle(2026, 3, 20, 9, 35, 101, 103, 100, 102),
        _candle(2026, 3, 21, 9, 30, 200, 202, 199, 201),
    ]
    trace = _build_candlestick_trace(candles, use_index=True)
    assert trace["x"] == [0, 1, 2]
    assert "text" in trace
    assert len(trace["text"]) == 3
    assert "09:30" in trace["text"][0]
    assert "hovertemplate" in trace
    assert "%{text}" in trace["hovertemplate"]


def test_build_order_traces_default():
    dt = datetime(2026, 3, 20, 9, 32, tzinfo=ET)
    buys = [(dt, 5805.0, "1x 5800C @$2.50")]
    sells = []
    spreads = []
    traces = _build_order_traces(buys, sells, spreads)
    assert len(traces) == 1
    assert "2026-03-20" in traces[0]["x"][0]
    assert "%{x}" in traces[0]["hovertemplate"]


def test_build_order_traces_use_index():
    buys = [(0, 5805.0, "1x 5800C @$2.50", "2026-03-20 09:32")]
    sells = [(2, 5905.0, "1x 5800C @$3.00", "2026-03-21 09:31")]
    spreads = []
    traces = _build_order_traces(buys, sells, spreads, use_index=True)
    assert len(traces) == 2
    assert traces[0]["x"] == [0]
    assert traces[0]["customdata"] == [["2026-03-20 09:32"]]
    assert "%{customdata[0]}" in traces[0]["hovertemplate"]
    assert traces[1]["x"] == [2]


def test_build_order_traces_use_index_spreads():
    buys = []
    sells = []
    spreads = [(1, 5810.0, "BUY 1x 5800C / SELL 1x 5810C", True, "2026-03-20 09:35")]
    traces = _build_order_traces(buys, sells, spreads, use_index=True)
    assert len(traces) == 1
    assert traces[0]["x"] == [1]
    assert traces[0]["customdata"] == [["2026-03-20 09:35"]]


@pytest.mark.skipif(not _plotly_available, reason="plotly.min.js not available")
def test_integration_multiday_html(tmp_path):
    """End-to-end: multi-day candles + orders → HTML file with day separators."""
    candles_data = {
        "candles": [
            _candle(2026, 3, 20, 9, 30, 5800, 5810, 5790, 5805),
            _candle(2026, 3, 20, 9, 35, 5805, 5815, 5800, 5810),
            _candle(2026, 3, 20, 16, 0, 5810, 5810, 5810, 5810),  # flat after-hours
            _candle(2026, 3, 21, 9, 30, 5900, 5910, 5890, 5905),
            _candle(2026, 3, 21, 9, 35, 5905, 5915, 5900, 5910),
            _candle(2026, 3, 22, 9, 30, 5950, 5960, 5940, 5955),
        ]
    }
    orders_data = [
        {
            "orderId": 1, "orderType": "LIMIT", "price": 2.50,
            "closeTime": "2026-03-20T09:32:00-0400",
            "legs": [{"instruction": "BUY_TO_OPEN", "quantity": 1,
                       "symbol": "SPXW  260320C05800000"}],
        },
        {
            "orderId": 2, "orderType": "LIMIT", "price": 3.00,
            "closeTime": "2026-03-21T09:31:00-0400",
            "legs": [{"instruction": "SELL_TO_CLOSE", "quantity": 1,
                       "symbol": "SPXW  260320C05800000"}],
        },
    ]

    candles_file = tmp_path / "candles.json"
    orders_file = tmp_path / "orders.json"
    output_file = tmp_path / "chart.html"

    candles_file.write_text(json.dumps(candles_data))
    orders_file.write_text(json.dumps(orders_data))

    script = str(Path(__file__).parent / "chart_orders.py")
    result = subprocess.run(
        [sys.executable, script,
         "--candles-file", str(candles_file),
         "--orders-file", str(orders_file),
         "--symbol", "SPX",
         "--output", str(output_file)],
        capture_output=True, text=True,
    )

    assert result.returncode == 0, f"stderr: {result.stderr}"
    assert output_file.exists()

    html = output_file.read_text()
    assert "Mar 21" in html or "Mar\\ 21" in html or "Mar 21" in html.replace("\\", "")
    assert "Mar 20" in html
    assert "Plotly.newPlot" in html


@pytest.mark.skipif(not _plotly_available, reason="plotly.min.js not available")
def test_integration_singleday_still_works(tmp_path):
    """Single-day mode with --date still works as before."""
    candles_data = {
        "candles": [
            _candle(2026, 3, 20, 9, 30, 5800, 5810, 5790, 5805),
            _candle(2026, 3, 20, 9, 35, 5805, 5815, 5800, 5810),
        ]
    }
    orders_data = [{
        "orderId": 1, "orderType": "LIMIT", "price": 2.50,
        "closeTime": "2026-03-20T09:32:00-0400",
        "legs": [{"instruction": "BUY_TO_OPEN", "quantity": 1,
                   "symbol": "SPXW  260320C05800000"}],
    }]

    candles_file = tmp_path / "candles.json"
    orders_file = tmp_path / "orders.json"
    output_file = tmp_path / "chart.html"

    candles_file.write_text(json.dumps(candles_data))
    orders_file.write_text(json.dumps(orders_data))

    script = str(Path(__file__).parent / "chart_orders.py")
    result = subprocess.run(
        [sys.executable, script,
         "--candles-file", str(candles_file),
         "--orders-file", str(orders_file),
         "--symbol", "SPX",
         "--date", "2026-03-20",
         "--output", str(output_file)],
        capture_output=True, text=True,
    )

    assert result.returncode == 0, f"stderr: {result.stderr}"
    html = output_file.read_text()
    assert "March 20, 2026" in html


def test_integration_png_requires_date(tmp_path):
    """PNG format requires --date (multi-day not supported for PNG)."""
    candles_file = tmp_path / "candles.json"
    orders_file = tmp_path / "orders.json"
    candles_file.write_text("[]")
    orders_file.write_text("[]")

    script = str(Path(__file__).parent / "chart_orders.py")
    result = subprocess.run(
        [sys.executable, script,
         "--candles-file", str(candles_file),
         "--orders-file", str(orders_file),
         "--format", "png"],
        capture_output=True, text=True,
    )
    assert result.returncode != 0
    assert "required for PNG" in result.stderr

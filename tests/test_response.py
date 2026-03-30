# tests/test_response.py
import json
import os
from unittest.mock import MagicMock


def test_ok_or_error_success():
    """Successful response returns indented JSON."""
    from schwab_mcp.tools._response import _ok_or_error

    resp = MagicMock()
    resp.ok = True
    resp.status_code = 200
    resp.text = '{"key": "value"}'
    resp.json.return_value = {"key": "value"}
    result = _ok_or_error(resp)
    assert result == json.dumps({"key": "value"}, indent=2)


def test_ok_or_error_error():
    """Error response returns error string."""
    from schwab_mcp.tools._response import _ok_or_error

    resp = MagicMock()
    resp.ok = False
    resp.status_code = 401
    resp.text = "Unauthorized"
    result = _ok_or_error(resp)
    assert result == "Error (401): Unauthorized"


def test_ok_or_error_empty_201():
    """Empty 201 returns success string."""
    from schwab_mcp.tools._response import _ok_or_error

    resp = MagicMock()
    resp.ok = True
    resp.status_code = 201
    resp.text = "  "
    result = _ok_or_error(resp)
    assert result == "Success (HTTP 201)"


def test_maybe_write_to_file_below_threshold():
    """Returns None when item_count <= threshold."""
    from schwab_mcp.tools._response import _maybe_write_to_file

    result = _maybe_write_to_file("orders", "", [1, 2, 3], item_count=3, threshold=10)
    assert result is None


def test_maybe_write_to_file_at_threshold():
    """Returns None when item_count == threshold (boundary)."""
    from schwab_mcp.tools._response import _maybe_write_to_file

    result = _maybe_write_to_file("orders", "", list(range(10)), item_count=10, threshold=10)
    assert result is None


def test_maybe_write_to_file_above_threshold(tmp_path, monkeypatch):
    """Writes file and returns summary when item_count > threshold."""
    import schwab_mcp.tools._response as mod
    monkeypatch.setattr(mod, "_TMP_DIR", str(tmp_path))

    from schwab_mcp.tools._response import _maybe_write_to_file

    data = [{"id": i} for i in range(11)]
    result = _maybe_write_to_file("orders", "", data, item_count=11, threshold=10, noun="orders")

    assert result is not None
    assert "11 orders found" in result
    assert str(tmp_path) in result
    assert result.endswith(".json")

    # Verify file was written with correct content
    filepath = result.split("Full data: ")[1]
    with open(filepath) as f:
        written = json.load(f)
    assert written == data


def test_maybe_write_to_file_context_in_filename(tmp_path, monkeypatch):
    """Context string appears in the filename."""
    import schwab_mcp.tools._response as mod
    monkeypatch.setattr(mod, "_TMP_DIR", str(tmp_path))

    from schwab_mcp.tools._response import _maybe_write_to_file

    result = _maybe_write_to_file("option-chain", "SPX", {"calls": {}}, item_count=1, threshold=0)
    assert "option-chain-SPX-" in result


def test_maybe_write_to_file_creates_directory(tmp_path, monkeypatch):
    """Creates the output directory if it doesn't exist."""
    import schwab_mcp.tools._response as mod
    subdir = tmp_path / "nested" / "dir"
    monkeypatch.setattr(mod, "_TMP_DIR", str(subdir))

    from schwab_mcp.tools._response import _maybe_write_to_file

    result = _maybe_write_to_file("test", "", {"x": 1}, item_count=1, threshold=0)
    assert result is not None
    assert subdir.exists()


def test_maybe_write_to_file_default_noun(tmp_path, monkeypatch):
    """Default noun is 'items'."""
    import schwab_mcp.tools._response as mod
    monkeypatch.setattr(mod, "_TMP_DIR", str(tmp_path))

    from schwab_mcp.tools._response import _maybe_write_to_file

    result = _maybe_write_to_file("test", "", [1, 2], item_count=2, threshold=0)
    assert "2 items found" in result

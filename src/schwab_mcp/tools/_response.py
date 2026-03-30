# src/schwab_mcp/tools/_response.py
import json
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

_TMP_DIR = "/tmp/schwab-mcp"


def _maybe_write_to_file(
    tool_name: str,
    context: str,
    data: Any,
    item_count: int,
    threshold: int,
    noun: str = "items",
) -> str | None:
    """Write data to file if item_count > threshold.

    Returns the summary string if written to file, or None if below threshold
    (caller should return inline JSON as usual).
    """
    if item_count <= threshold:
        return None

    os.makedirs(_TMP_DIR, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
    suffix = uuid4().hex[:4]
    ctx = f"-{context}" if context else ""
    filename = f"{tool_name}{ctx}-{now}-{suffix}.json"
    filepath = os.path.join(_TMP_DIR, filename)

    with open(filepath, "w") as f:
        json.dump(data, f)

    return f"{item_count} {noun} found. Full data: {filepath}"


def _write_to_file(tool_name: str, context: str, data: Any) -> str:
    """Unconditionally write data to a temp file. Returns the filepath."""
    os.makedirs(_TMP_DIR, exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S")
    suffix = uuid4().hex[:4]
    ctx = f"-{context}" if context else ""
    filename = f"{tool_name}{ctx}-{now}-{suffix}.json"
    filepath = os.path.join(_TMP_DIR, filename)

    with open(filepath, "w") as f:
        json.dump(data, f)

    return filepath


def _ok_or_error(resp) -> str:
    if not resp.ok:
        return f"Error ({resp.status_code}): {resp.text}"
    if resp.status_code in (200, 201) and not resp.text.strip():
        return f"Success (HTTP {resp.status_code})"
    try:
        return json.dumps(resp.json(), indent=2)
    except Exception:
        return resp.text

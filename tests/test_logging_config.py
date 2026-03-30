import logging
import os
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest


def test_setup_logging_creates_handler(tmp_path):
    """setup_logging installs a RotatingFileHandler to the log file."""
    from schwab_mcp.logging_config import setup_logging

    log_file = tmp_path / "test.log"
    setup_logging(log_file=log_file, level="INFO")

    root_logger = logging.getLogger("schwab_mcp")
    handler_types = [type(h).__name__ for h in root_logger.handlers]
    assert "RotatingFileHandler" in handler_types


def test_setup_logging_creates_parent_dir(tmp_path):
    """setup_logging creates the log directory if it does not exist."""
    from schwab_mcp.logging_config import setup_logging

    log_file = tmp_path / "subdir" / "schwab-mcp.log"
    setup_logging(log_file=log_file, level="INFO")
    assert log_file.parent.exists()


def test_setup_logging_fatal_on_permission_error(tmp_path):
    """setup_logging exits with SystemExit if directory cannot be created."""
    from schwab_mcp.logging_config import setup_logging

    log_file = tmp_path / "schwab-mcp.log"
    with patch("pathlib.Path.mkdir", side_effect=PermissionError("denied")):
        with pytest.raises(SystemExit):
            setup_logging(log_file=log_file, level="INFO")


def test_redaction_filter_masks_account_hash():
    """RedactionFilter masks account_hash to last 4 chars in log records."""
    from schwab_mcp.logging_config import RedactionFilter

    f = RedactionFilter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="Processing account_hash=ABCDEF1234", args=(), exc_info=None
    )
    f.filter(record)
    assert "ABCDEF1234" not in record.msg
    assert "1234" in record.msg


def test_redaction_filter_masks_app_key():
    """RedactionFilter replaces app_key value with [REDACTED]."""
    from schwab_mcp.logging_config import RedactionFilter

    f = RedactionFilter()
    record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="app_key=mysecretkey123", args=(), exc_info=None
    )
    f.filter(record)
    assert "mysecretkey123" not in record.msg
    assert "[REDACTED]" in record.msg

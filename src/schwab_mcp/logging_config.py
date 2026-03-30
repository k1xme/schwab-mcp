import logging
import logging.handlers
import re
import sys
from pathlib import Path


def _mask_account_hash_match(m: re.Match) -> str:
    value = m.group(2)
    return m.group(1) + "..." + value[-4:]


class RedactionFilter(logging.Filter):
    """Redacts sensitive values from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = _redact(str(record.msg))
        record.args = ()  # prevent re-interpolation revealing raw values
        return True


def _redact(text: str) -> str:
    text = re.sub(
        r"(app_(?:key|secret)=)\S+",
        r"\1[REDACTED]",
        text,
    )
    text = re.sub(
        r"(account_hash=)([A-Za-z0-9]{5,})",
        lambda m: m.group(1) + "..." + m.group(2)[-4:],
        text,
    )
    return text


def setup_logging(
    log_file: Path | None = None,
    level: str = "INFO",
) -> None:
    """Configure rotating file logging for schwab_mcp.

    Args:
        log_file: Path to log file. Defaults to ~/.schwab-mcp/schwab-mcp.log.
        level: Log level string (INFO or DEBUG).
    Raises:
        SystemExit: If the log directory cannot be created.
    """
    if log_file is None:
        log_file = Path.home() / ".schwab-mcp" / "schwab-mcp.log"

    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(
            f"FATAL: Cannot create log directory {log_file.parent}: {e}. "
            "Check permissions.",
            file=sys.stderr,
        )
        sys.exit(1)

    logger = logging.getLogger("schwab_mcp")
    logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove existing handlers to avoid duplicates on re-init
    logger.handlers.clear()

    handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MB
        backupCount=3,
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    )
    handler.addFilter(RedactionFilter())
    logger.addHandler(handler)
    logger.propagate = False

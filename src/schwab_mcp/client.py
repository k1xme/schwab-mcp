import sys
import json
import logging
from pathlib import Path

import schwabdev
from dotenv import dotenv_values

logger = logging.getLogger("schwab_mcp.client")

_schwab_client: schwabdev.Client | None = None
_active_account_hash: str | None = None

_DEFAULT_ENV_FILE = Path.home() / ".schwab-mcp" / ".env"
_DEFAULT_TOKENS_DB = Path.home() / ".schwab-mcp" / "tokens.db"
_DEFAULT_STATE_FILE = Path.home() / ".schwab-mcp" / "state.json"


def init_client(env_file: Path | None = None) -> None:
    """Initialize the schwabdev client from .env credentials.

    Raises:
        SystemExit: If required env vars are missing.
    """
    global _schwab_client

    env_path = env_file or _DEFAULT_ENV_FILE
    config = dotenv_values(env_path)

    app_key = config.get("SCHWAB_APP_KEY")
    app_secret = config.get("SCHWAB_APP_SECRET")
    callback_url = config.get("SCHWAB_CALLBACK_URL", "https://127.0.0.1:8182")

    missing = [k for k, v in [
        ("SCHWAB_APP_KEY", app_key),
        ("SCHWAB_APP_SECRET", app_secret),
    ] if not v]

    if missing:
        print(
            f"FATAL: Missing required credentials in {env_path}: {', '.join(missing)}",
            file=sys.stderr,
        )
        sys.exit(1)

    tokens_db = str(_DEFAULT_TOKENS_DB)
    _schwab_client = schwabdev.Client(
        app_key, app_secret, callback_url, tokens_db=tokens_db
    )
    logger.info("schwabdev client initialized")
    _load_state()


def get_schwab_client() -> schwabdev.Client:
    """Return the initialized schwabdev client.

    Raises:
        RuntimeError: If init_client has not been called.
    """
    if _schwab_client is None:
        raise RuntimeError(
            "Schwab client not initialized. "
            "This is a bug — init_client() should be called at server startup."
        )
    return _schwab_client


def _load_state() -> None:
    """Load persisted state from disk into module variables."""
    global _active_account_hash
    try:
        data = json.loads(_DEFAULT_STATE_FILE.read_text())
        _active_account_hash = data.get("active_account_hash")
        if _active_account_hash:
            logger.info("Restored active account hash ...%s", _active_account_hash[-4:])
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning("Failed to load state file: %s", e)


def _save_state() -> None:
    """Persist current state to disk."""
    try:
        _DEFAULT_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _DEFAULT_STATE_FILE.write_text(
            json.dumps({"active_account_hash": _active_account_hash})
        )
    except Exception as e:
        logger.warning("Failed to save state file: %s", e)


def get_active_account_hash() -> str | None:
    """Return the currently active account hash, or None if not set."""
    return _active_account_hash


def set_active_account_hash(account_hash: str) -> None:
    """Set the active account hash and persist it to disk."""
    global _active_account_hash
    _active_account_hash = account_hash
    logger.info("Active account set to account_hash=...%s", account_hash[-4:])
    _save_state()


def resolve_account_hash(account_hash: str | None) -> str:
    """Return account_hash if provided, else the active account hash.

    Raises:
        ValueError: If neither is available.
    """
    if account_hash is not None:
        return account_hash
    if _active_account_hash is not None:
        return _active_account_hash
    raise ValueError(
        "No account specified and no active account set. "
        "Call set_active_account first, or provide account_hash explicitly."
    )


def try_resolve_account_hash(account_hash: str | None) -> tuple[str | None, str | None]:
    """Return (resolved_hash, None) on success or (None, error_string) on failure.

    All tool functions should use this instead of calling resolve_account_hash directly.
    """
    try:
        return resolve_account_hash(account_hash), None
    except ValueError as e:
        return None, f"Error: {e}"

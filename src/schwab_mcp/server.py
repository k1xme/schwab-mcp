import os
import sys
import logging
from pathlib import Path

logger = logging.getLogger("schwab_mcp.server")


def serve() -> None:
    """Start the MCP server over Streamable HTTP."""
    from schwab_mcp.logging_config import setup_logging
    from schwab_mcp.client import init_client
    from schwab_mcp._mcp import mcp

    setup_logging()
    init_client()

    # Import tool modules to trigger @mcp.tool() decorator registration
    import schwab_mcp.tools.session       # noqa: F401
    import schwab_mcp.tools.market_data   # noqa: F401
    import schwab_mcp.tools.accounts      # noqa: F401
    import schwab_mcp.tools.orders        # noqa: F401
    import schwab_mcp.tools.instruments   # noqa: F401

    host = os.environ.get("SCHWAB_MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("SCHWAB_MCP_PORT", "8099"))
    mcp.settings.host = host
    mcp.settings.port = port

    logger.info("Starting schwab-mcp server on %s:%d", host, port)
    mcp.run(transport="streamable-http")


def auth() -> None:
    """Run interactive OAuth flow to obtain/refresh tokens."""
    from schwab_mcp.logging_config import setup_logging
    from schwab_mcp.client import init_client, get_schwab_client

    setup_logging()

    # Ensure state dir exists before running auth
    state_dir = Path.home() / ".schwab-mcp"
    state_dir.mkdir(parents=True, exist_ok=True)

    init_client()
    client = get_schwab_client()

    # schwabdev performs auth automatically on client init if tokens are missing.
    # If tokens already exist and are valid, we just confirm that.
    try:
        resp = client.linked_accounts()
        if resp.ok:
            print("Tokens are valid. No re-authentication needed.")
        else:
            print(f"Auth check failed with status {resp.status_code}. "
                  "You may need to delete ~/.schwab-mcp/tokens.db and re-run.")
    except Exception as e:
        print(f"Auth error: {e}")
        sys.exit(1)


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"

    if cmd == "serve":
        serve()
    elif cmd == "auth":
        auth()
    else:
        print(f"Unknown command: {cmd}. Use 'serve' or 'auth'.", file=sys.stderr)
        sys.exit(1)

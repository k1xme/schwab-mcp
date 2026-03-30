import sys
import pytest
from unittest.mock import patch

# Import at module level so patches target the already-bound names
import schwab_mcp.server as server


def test_main_serve_calls_serve(monkeypatch):
    """main() with 'serve' arg calls serve()."""
    monkeypatch.setattr(sys, "argv", ["schwab-mcp", "serve"])
    with patch.object(server, "serve") as mock_serve:
        server.main()
        mock_serve.assert_called_once()


def test_main_auth_calls_auth(monkeypatch):
    """main() with 'auth' arg calls auth()."""
    monkeypatch.setattr(sys, "argv", ["schwab-mcp", "auth"])
    with patch.object(server, "auth") as mock_auth:
        server.main()
        mock_auth.assert_called_once()


def test_main_unknown_command_exits(monkeypatch):
    """main() with unknown command exits with non-zero code."""
    monkeypatch.setattr(sys, "argv", ["schwab-mcp", "bogus"])
    with pytest.raises(SystemExit) as exc:
        server.main()
    assert exc.value.code != 0


def test_main_default_is_serve(monkeypatch):
    """main() with no args defaults to serve."""
    monkeypatch.setattr(sys, "argv", ["schwab-mcp"])
    with patch.object(server, "serve") as mock_serve:
        server.main()
        mock_serve.assert_called_once()


@patch("schwab_mcp.client.init_client")
@patch("schwab_mcp.logging_config.setup_logging")
def test_serve_uses_streamable_http_transport(mock_logging, mock_client, monkeypatch):
    """serve() calls mcp.run() with streamable-http transport and default host/port."""
    from schwab_mcp._mcp import mcp

    monkeypatch.delenv("SCHWAB_MCP_HOST", raising=False)
    monkeypatch.delenv("SCHWAB_MCP_PORT", raising=False)

    with patch.object(mcp, "run") as mock_run:
        server.serve()
        mock_run.assert_called_once_with(transport="streamable-http")
        assert mcp.settings.host == "127.0.0.1"
        assert mcp.settings.port == 8099


@patch("schwab_mcp.client.init_client")
@patch("schwab_mcp.logging_config.setup_logging")
def test_serve_reads_host_port_from_env(mock_logging, mock_client, monkeypatch):
    """serve() reads SCHWAB_MCP_HOST and SCHWAB_MCP_PORT from environment."""
    from schwab_mcp._mcp import mcp

    monkeypatch.setenv("SCHWAB_MCP_HOST", "192.168.1.100")
    monkeypatch.setenv("SCHWAB_MCP_PORT", "9999")

    with patch.object(mcp, "run") as mock_run:
        server.serve()
        mock_run.assert_called_once_with(transport="streamable-http")
        assert mcp.settings.host == "192.168.1.100"
        assert mcp.settings.port == 9999

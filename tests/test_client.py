import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path


def test_resolve_account_hash_uses_explicit(monkeypatch):
    """resolve_account_hash returns explicit hash when provided."""
    import schwab_mcp.client as c
    monkeypatch.setattr(c, "_active_account_hash", "OTHER")
    assert c.resolve_account_hash("EXPLICIT") == "EXPLICIT"


def test_resolve_account_hash_uses_active(monkeypatch):
    """resolve_account_hash falls back to active account when hash omitted."""
    import schwab_mcp.client as c
    monkeypatch.setattr(c, "_active_account_hash", "ACTIVE1234")
    assert c.resolve_account_hash(None) == "ACTIVE1234"


def test_resolve_account_hash_raises_when_none(monkeypatch):
    """resolve_account_hash raises ValueError when no hash and no active account."""
    import schwab_mcp.client as c
    monkeypatch.setattr(c, "_active_account_hash", None)
    with pytest.raises(ValueError, match="set_active_account"):
        c.resolve_account_hash(None)


def test_set_active_account_hash(monkeypatch, tmp_path):
    """set_active_account_hash stores the hash in module state and persists it."""
    import schwab_mcp.client as c
    state_file = tmp_path / "state.json"
    monkeypatch.setattr(c, "_active_account_hash", None)
    monkeypatch.setattr(c, "_DEFAULT_STATE_FILE", state_file)
    c.set_active_account_hash("NEWHASH")
    assert c._active_account_hash == "NEWHASH"
    assert state_file.exists()
    import json
    assert json.loads(state_file.read_text())["active_account_hash"] == "NEWHASH"


def test_load_state_restores_hash(monkeypatch, tmp_path):
    """_load_state reads active_account_hash from state.json."""
    import json
    import schwab_mcp.client as c
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"active_account_hash": "RESTORED_HASH"}))
    monkeypatch.setattr(c, "_active_account_hash", None)
    monkeypatch.setattr(c, "_DEFAULT_STATE_FILE", state_file)
    c._load_state()
    assert c._active_account_hash == "RESTORED_HASH"


def test_load_state_handles_missing_file(monkeypatch, tmp_path):
    """_load_state is a no-op when state.json does not exist."""
    import schwab_mcp.client as c
    monkeypatch.setattr(c, "_active_account_hash", None)
    monkeypatch.setattr(c, "_DEFAULT_STATE_FILE", tmp_path / "nonexistent.json")
    c._load_state()
    assert c._active_account_hash is None


def test_get_schwab_client_raises_before_init(monkeypatch):
    """get_schwab_client raises RuntimeError if init_client was not called."""
    import schwab_mcp.client as c
    monkeypatch.setattr(c, "_schwab_client", None)
    with pytest.raises(RuntimeError, match="not initialized"):
        c.get_schwab_client()


def test_init_client_loads_env_and_creates_client(tmp_path, monkeypatch):
    """init_client reads .env credentials and instantiates schwabdev.Client."""
    import schwab_mcp.client as c

    env_file = tmp_path / ".env"
    env_file.write_text(
        "SCHWAB_APP_KEY=testkey\n"
        "SCHWAB_APP_SECRET=testsecret\n"
        "SCHWAB_CALLBACK_URL=https://127.0.0.1:8182\n"
    )
    monkeypatch.setattr(c, "_schwab_client", None)
    monkeypatch.setattr(c, "_DEFAULT_STATE_FILE", tmp_path / "state.json")

    mock_client = MagicMock()
    with patch("schwabdev.Client", return_value=mock_client) as MockClient:
        c.init_client(env_file=env_file)
        MockClient.assert_called_once()
        call_kwargs = MockClient.call_args
        assert call_kwargs[0][0] == "testkey"
        assert call_kwargs[0][1] == "testsecret"

    assert c._schwab_client is mock_client


def test_init_client_raises_on_missing_env(tmp_path, monkeypatch):
    """init_client raises SystemExit if .env file is missing required keys."""
    import schwab_mcp.client as c

    env_file = tmp_path / ".env"
    env_file.write_text("SCHWAB_APP_KEY=testkey\n")  # missing SECRET
    monkeypatch.setattr(c, "_schwab_client", None)

    with pytest.raises(SystemExit):
        c.init_client(env_file=env_file)


def test_try_resolve_account_hash_success(monkeypatch):
    """try_resolve_account_hash returns (hash, None) when hash is available."""
    import schwab_mcp.client as c
    monkeypatch.setattr(c, "_active_account_hash", None)
    hash_, err = c.try_resolve_account_hash("EXPLICIT")
    assert hash_ == "EXPLICIT"
    assert err is None


def test_try_resolve_account_hash_error(monkeypatch):
    """try_resolve_account_hash returns (None, error) when no hash available."""
    import schwab_mcp.client as c
    monkeypatch.setattr(c, "_active_account_hash", None)
    hash_, err = c.try_resolve_account_hash(None)
    assert hash_ is None
    assert "set_active_account" in err

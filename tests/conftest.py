# tests/conftest.py
import pytest


@pytest.fixture(autouse=True)
def _redirect_tmp_dir(tmp_path, monkeypatch):
    """Redirect _TMP_DIR to tmp_path for all tests to avoid writing to real /tmp."""
    import schwab_mcp.tools._response as mod
    monkeypatch.setattr(mod, "_TMP_DIR", str(tmp_path))

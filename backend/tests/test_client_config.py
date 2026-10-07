"""Guards against the config silently not loading (a missing Docker
mount once meant no tax was charged and branding was ignored)."""

from app.core.client_config import _CONFIG_PATH, client_config


def test_client_config_file_is_actually_loaded():
    assert _CONFIG_PATH.exists(), f"client.config.json not found at {_CONFIG_PATH}"
    # Keys that exist only in the real file, never in _DEFAULTS:
    assert "tagline" in client_config
    assert client_config["online_tax"]["rates_by_state"], "no online tax states configured"

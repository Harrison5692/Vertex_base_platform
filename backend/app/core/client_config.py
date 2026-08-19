"""
Loads client.config.json — the one file a new deployment actually
needs to edit for basic branding (app name, color, what each tier
is called). Read once at import time; restart the backend to pick
up changes.

Lives at the project root (not inside backend/) so both the backend
and, if ever needed, other tooling can find it without duplicating
the values in two places.
"""

import json
from pathlib import Path

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "client.config.json"

_DEFAULTS = {
    "app_name": "Vertex Base",
    "primary_color": "#1a9c8f",
    "tier_labels": {"1": "Client", "2": "Staff", "3": "Manager"},
}


def load_client_config() -> dict:
    if not _CONFIG_PATH.exists():
        return _DEFAULTS
    try:
        with open(_CONFIG_PATH) as f:
            data = json.load(f)
        return {**_DEFAULTS, **data}
    except (json.JSONDecodeError, OSError):
        return _DEFAULTS


client_config = load_client_config()

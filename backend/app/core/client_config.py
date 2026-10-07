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
import logging
from pathlib import Path

logger = logging.getLogger("app.config")

_CONFIG_PATH = Path(__file__).resolve().parents[3] / "client.config.json"

_DEFAULTS = {
    "app_name": "Vertex Base",
    "primary_color": "#1a9c8f",
    "tier_labels": {"1": "Client", "2": "Staff", "3": "Manager"},
    # In-person (walk-in POS) tax rate. Online orders use online_tax.
    "tax_rate": 0.0,
    # Retail vertical — see core/pricing.py for exactly how these apply.
    "shipping": {
        "allowed_countries": ["US"],
        "tiers": [{"under": 10, "rate": 5}, {"under": 50, "rate": 10}],
        "free_shipping_at": 50,
    },
    "online_tax": {"rates_by_state": {}, "tax_shipping": True},
}


def load_client_config() -> dict:
    # Falling back to defaults silently once hid a missing Docker mount
    # (no tax charged, branding ignored) — so it's always logged now.
    if not _CONFIG_PATH.exists():
        logger.warning(
            "client.config.json NOT FOUND at %s — running on built-in defaults "
            "(no online tax, default branding). Check the docker-compose mount.",
            _CONFIG_PATH,
        )
        return _DEFAULTS
    try:
        with open(_CONFIG_PATH) as f:
            data = json.load(f)
        logger.info("Loaded client config from %s", _CONFIG_PATH)
        return {**_DEFAULTS, **data}
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(
            "client.config.json at %s could not be read (%s) — using defaults", _CONFIG_PATH, exc
        )
        return _DEFAULTS


client_config = load_client_config()

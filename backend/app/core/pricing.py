"""
Shipping and tax — computed server-side only, from client.config.json.

Pure functions, no database or request objects, so the exact numbers a
customer gets charged are unit-testable in isolation (see
tests/test_pricing.py). Checkout and the /transactions/quote endpoint
both call compute_totals() — the cart page displays the same numbers
the server will actually charge, rather than re-implementing the math
in the browser and hoping the two agree.

Config shape (all keys optional — missing keys fall back to the
defaults in core/client_config.py):

    "tax_rate": 0.0825,                 # in-person (walk-in POS) sales
    "shipping": {
      "allowed_countries": ["US"],
      "tiers": [{"under": 10, "rate": 5}, {"under": 50, "rate": 10}],
      "free_shipping_at": 50            # null = never free
    },
    "online_tax": {
      "rates_by_state": {"TX": 0.0825}, # states you collect tax in
      "tax_shipping": true              # whether shipping is taxable
    }

Shipping tiers: free_shipping_at is checked first; otherwise the first
tier whose "under" the subtotal is below wins; a subtotal above every
tier (with no free threshold) pays the highest tier's rate.

Online tax: charged only when the destination state is listed in
rates_by_state — a seller generally only collects where they have
nexus. One flat rate per state is correct for an origin-based state
like Texas (an in-state seller charges its own local rate to every
in-state buyer). Each client should confirm their own obligations;
this just applies whatever their config says.

Money is rounded to cents with ROUND_HALF_UP via Decimal at every
step that produces a charged amount — float math alone produces
things like 8.250000000000002 on a receipt or a Stripe amount.
"""

import re
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

US_STATES = frozenset(
    {
        "AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "HI", "ID",
        "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO",
        "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA",
        "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    }
)

_COUNTRY_ALIASES = {
    "US": "US",
    "USA": "US",
    "U.S.": "US",
    "U.S.A.": "US",
    "UNITED STATES": "US",
    "UNITED STATES OF AMERICA": "US",
}


class PricingError(ValueError):
    """A destination this store can't ship to / price — surfaced as a 422."""


@dataclass(frozen=True)
class Totals:
    subtotal: float  # merchandise, BEFORE any discount
    discount: float  # dollars taken off the subtotal (0 if no code)
    shipping: float
    tax: float
    total: float
    # How much more the customer would need to add for free shipping —
    # None when already free or when the store has no free threshold.
    free_shipping_remaining: float | None


def cents(value: float | Decimal) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def normalize_country(country: str | None) -> str | None:
    if not country:
        return None
    key = country.strip().upper()
    return _COUNTRY_ALIASES.get(key, key)


def normalize_state(state: str | None) -> str | None:
    if not state:
        return None
    return state.strip().upper()


def validate_destination(country: str | None, state: str | None, config: dict) -> tuple[str, str]:
    """Returns the normalized (country, state) or raises PricingError."""
    allowed = [normalize_country(c) for c in config.get("shipping", {}).get("allowed_countries", ["US"])]
    norm_country = normalize_country(country)
    if norm_country not in allowed:
        raise PricingError(f"Sorry, we only ship to: {', '.join(allowed)}")
    norm_state = normalize_state(state)
    if not norm_state:
        raise PricingError("A shipping state is required")
    if norm_country == "US" and norm_state not in US_STATES:
        raise PricingError(f"'{state}' isn't a valid US state code (e.g. TX)")
    return norm_country, norm_state


_US_ZIP = re.compile(r"^\d{5}(-\d{4})?$")


def validate_postal_code(country: str, postal_code: str | None) -> str:
    code = (postal_code or "").strip()
    if not code:
        raise PricingError("A ZIP code is required")
    if country == "US" and not _US_ZIP.match(code):
        raise PricingError("Enter a 5-digit ZIP code (like 77002)")
    return code


def validate_street_line(line1: str | None) -> str:
    """Catches obviously incomplete input ("John", "my house") — not a
    real-address check (that's USPS address verification, later).
    Nearly every deliverable US address has a number in line 1,
    PO boxes included ("PO Box 123")."""
    line = (line1 or "").strip()
    if not line:
        raise PricingError("Address line 1 is required")
    if not any(ch.isdigit() for ch in line):
        raise PricingError("Include the street number in address line 1 (like 123 Main St)")
    return line


def shipping_for_subtotal(subtotal: float, config: dict) -> float:
    shipping_cfg = config.get("shipping", {})
    free_at = shipping_cfg.get("free_shipping_at")
    if free_at is not None and subtotal >= free_at:
        return 0.0
    tiers = sorted(shipping_cfg.get("tiers", []), key=lambda t: t["under"])
    if not tiers:
        return 0.0
    for tier in tiers:
        if subtotal < tier["under"]:
            return cents(tier["rate"])
    return cents(tiers[-1]["rate"])


def compute_totals(
    subtotal: float,
    *,
    online: bool,
    state: str | None,
    config: dict,
    tax_override: float | None = None,
    discount: float = 0.0,
) -> Totals:
    """online=False is a walk-in POS sale: no shipping, the store's
    in-person tax_rate. tax_override is only ever passed through for
    staff (e.g. a tax-exempt sale) — the caller decides that, not
    this function.

    discount comes off the subtotal FIRST; shipping tiers, the free
    shipping threshold and tax all use the discounted amount (see
    models/discount_code.py for why)."""
    subtotal = cents(subtotal)
    discount = min(cents(discount), subtotal) if discount > 0 else 0.0
    net = cents(Decimal(str(subtotal)) - Decimal(str(discount)))
    free_remaining = None

    if online:
        shipping = shipping_for_subtotal(net, config)
        tax_cfg = config.get("online_tax", {})
        rates = {normalize_state(k): v for k, v in tax_cfg.get("rates_by_state", {}).items()}
        rate = rates.get(normalize_state(state), 0.0)
        taxable = net + (shipping if tax_cfg.get("tax_shipping", True) else 0.0)
        free_at = config.get("shipping", {}).get("free_shipping_at")
        if free_at is not None and net < free_at:
            free_remaining = cents(free_at - net)
    else:
        shipping = 0.0
        rate = config.get("tax_rate", 0.0)
        taxable = net

    tax = cents(tax_override) if tax_override is not None else cents(Decimal(str(taxable)) * Decimal(str(rate)))
    total = cents(Decimal(str(net)) + Decimal(str(shipping)) + Decimal(str(tax)))
    return Totals(
        subtotal=subtotal,
        discount=discount,
        shipping=shipping,
        tax=tax,
        total=total,
        free_shipping_remaining=free_remaining,
    )

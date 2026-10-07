"""Pure pricing math — no database needed."""

import pytest

from app.core.pricing import (
    PricingError,
    compute_totals,
    shipping_for_subtotal,
    validate_destination,
    validate_postal_code,
)

CONFIG = {
    "tax_rate": 0.0825,
    "shipping": {
        "allowed_countries": ["US"],
        "tiers": [{"under": 10, "rate": 5}, {"under": 50, "rate": 10}],
        "free_shipping_at": 50,
    },
    "online_tax": {"rates_by_state": {"TX": 0.0825}, "tax_shipping": True},
}


@pytest.mark.parametrize(
    ("subtotal", "expected"),
    [
        (0.01, 5.0),
        (9.99, 5.0),
        (10.00, 10.0),  # boundary: $10 exactly is the $10 tier
        (49.99, 10.0),
        (50.00, 0.0),  # boundary: $50 exactly ships free
        (250.00, 0.0),
    ],
)
def test_shipping_tiers(subtotal, expected):
    assert shipping_for_subtotal(subtotal, CONFIG) == expected


def test_no_free_threshold_uses_highest_tier():
    cfg = {"shipping": {"tiers": [{"under": 10, "rate": 5}, {"under": 50, "rate": 10}]}}
    assert shipping_for_subtotal(500, cfg) == 10.0


def test_tiers_order_in_config_doesnt_matter():
    cfg = {"shipping": {"tiers": [{"under": 50, "rate": 10}, {"under": 10, "rate": 5}]}}
    assert shipping_for_subtotal(5, cfg) == 5.0


def test_online_texas_taxes_subtotal_plus_shipping():
    t = compute_totals(20.00, online=True, state="TX", config=CONFIG)
    assert t.shipping == 10.0
    assert t.tax == 2.48  # (20 + 10) * 0.0825 = 2.475 -> rounds half up
    assert t.total == 32.48
    assert t.free_shipping_remaining == 30.0


def test_online_out_of_state_no_tax():
    t = compute_totals(20.00, online=True, state="CA", config=CONFIG)
    assert t.tax == 0.0
    assert t.total == 30.0


def test_tax_shipping_false_taxes_subtotal_only():
    cfg = {**CONFIG, "online_tax": {"rates_by_state": {"TX": 0.0825}, "tax_shipping": False}}
    t = compute_totals(20.00, online=True, state="TX", config=cfg)
    assert t.tax == 1.65


def test_free_shipping_order():
    t = compute_totals(60.00, online=True, state="TX", config=CONFIG)
    assert t.shipping == 0.0
    assert t.tax == 4.95
    assert t.total == 64.95
    assert t.free_shipping_remaining is None


def test_walk_in_sale_no_shipping_in_store_rate():
    t = compute_totals(20.00, online=False, state=None, config=CONFIG)
    assert t.shipping == 0.0
    assert t.tax == 1.65
    assert t.total == 21.65


def test_tax_override():
    t = compute_totals(20.00, online=False, state=None, config=CONFIG, tax_override=0)
    assert t.tax == 0.0
    assert t.total == 20.0


def test_rounding_never_leaks_float_noise():
    t = compute_totals(0.1 + 0.2, online=True, state="TX", config=CONFIG)
    assert t.subtotal == 0.3
    assert str(t.total) == "5.74"  # 0.30 + 5 shipping + tax (5.30 * 0.0825 = 0.437 -> 0.44)


@pytest.mark.parametrize("country", ["US", "us", "USA", "United States", " united states of america "])
def test_country_aliases(country):
    assert validate_destination(country, "tx", CONFIG) == ("US", "TX")


def test_rejects_other_countries():
    with pytest.raises(PricingError, match="only ship to"):
        validate_destination("Canada", "ON", CONFIG)


def test_rejects_bad_state():
    with pytest.raises(PricingError, match="valid US state"):
        validate_destination("US", "Texas", CONFIG)
    with pytest.raises(PricingError, match="required"):
        validate_destination("US", "", CONFIG)


@pytest.mark.parametrize("code", ["77002", "77002-1234", " 77002 "])
def test_valid_zip(code):
    assert validate_postal_code("US", code) == code.strip()


@pytest.mark.parametrize("code", ["", "7700", "ABCDE", "77002-12"])
def test_invalid_zip(code):
    with pytest.raises(PricingError):
        validate_postal_code("US", code)

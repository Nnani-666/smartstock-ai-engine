from __future__ import annotations

"""Unit tests for safety stock service."""

from app.services.safety_stock import (
    calculate_extended_safety_stock,
    calculate_safety_stock,
    resolve_service_level,
)


def test_safety_stock_unit_test_anchor():
    """Verify prescribed unit-test anchor: SL=0.95, sigma_d=10, L=9 yields SS=50."""
    ss = calculate_safety_stock(service_level=0.95, sigma_d=10.0, lead_time_days=9.0)
    assert ss == 50


def test_service_level_override():
    """Verify that a requested service level overrides the default ABC class service level."""
    # Default for A is 0.98
    default_sl = resolve_service_level("A", requested_service_level=None)
    assert default_sl == 0.98

    # Overridden with 0.90
    overridden_sl = resolve_service_level("A", requested_service_level=0.90)
    assert overridden_sl == 0.90


def test_extended_safety_stock():
    """Verify extended safety stock calculation accounting for lead-time variability."""
    # When lead_time_std is 0, extended formula equals primary formula
    ss_primary = calculate_safety_stock(0.95, 10.0, 9.0)
    ss_ext_zero_std = calculate_extended_safety_stock(
        service_level=0.95,
        sigma_d=10.0,
        lead_time_days=9.0,
        d_bar=20.0,
        lead_time_std=0.0,
    )
    assert ss_primary == ss_ext_zero_std

    # With lead_time_std > 0, safety stock must increase
    ss_ext_with_std = calculate_extended_safety_stock(
        service_level=0.95,
        sigma_d=10.0,
        lead_time_days=9.0,
        d_bar=20.0,
        lead_time_std=1.5,
    )
    assert ss_ext_with_std > ss_primary

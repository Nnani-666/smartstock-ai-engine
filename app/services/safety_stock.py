from __future__ import annotations

"""Safety stock calculation service conforming to prescribed academic formulas."""

import math

from scipy import stats

from app.config import DEFAULT_SERVICE_LEVELS


def calculate_z_value(service_level: float) -> float:
    """Calculate Z-score for a given service level using inverse standard normal CDF.
    
    Args:
        service_level: Float between 0.50 and 0.999.
        
    Returns:
        Z-score value.
    """
    return float(stats.norm.ppf(service_level))


def calculate_safety_stock(
    service_level: float,
    sigma_d: float,
    lead_time_days: float,
) -> int:
    """Calculate standard safety stock using primary formula: SS = ceil(Z * sigma_d * sqrt(L)).
    
    Unit-test anchor: service_level=0.95, sigma_d=10, L=9 -> SS=ceil(1.64485 * 10 * 3) = 50.
    
    Args:
        service_level: Service level target (e.g. 0.95).
        sigma_d: Daily demand standard deviation over 90 days.
        lead_time_days: Lead time L in days (>= 0).
        
    Returns:
        Integer safety stock rounded up.
    """
    if lead_time_days <= 0 or sigma_d <= 0 or service_level <= 0:
        return 0
    z = calculate_z_value(service_level)
    ss = z * sigma_d * math.sqrt(lead_time_days)
    return math.ceil(ss)


def calculate_extended_safety_stock(
    service_level: float,
    sigma_d: float,
    lead_time_days: float,
    d_bar: float,
    lead_time_std: float,
) -> int:
    """Calculate extended safety stock accounting for lead time variability.
    
    Formula: SS_ext = ceil(Z * sqrt(L * sigma_d^2 + d_bar^2 * sigma_L^2))
    
    Args:
        service_level: Service level target.
        sigma_d: Daily demand standard deviation.
        lead_time_days: Mean lead time L in days.
        d_bar: Mean daily forecast.
        lead_time_std: Standard deviation of lead time.
        
    Returns:
        Integer extended safety stock rounded up.
    """
    if lead_time_days <= 0 or service_level <= 0:
        return 0
    z = calculate_z_value(service_level)
    variance_term = (lead_time_days * (sigma_d ** 2)) + ((d_bar ** 2) * (lead_time_std ** 2))
    if variance_term <= 0:
        return 0
    ss_ext = z * math.sqrt(variance_term)
    return math.ceil(ss_ext)


def resolve_service_level(abc_class: str | None, requested_service_level: float | None) -> float:
    """Resolve service level: request override takes precedence, else defaults by ABC class."""
    if requested_service_level is not None:
        return float(requested_service_level)
    if abc_class in DEFAULT_SERVICE_LEVELS:
        return DEFAULT_SERVICE_LEVELS[abc_class]
    return 0.95

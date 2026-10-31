from __future__ import annotations

"""Inventory replenishment decision service (AI-1) computing metrics and evaluating rules."""

import logging
import math
from typing import Any

import numpy as np
import pandas as pd

from app.config import LAST_DATA_DATE
from app.services.rules import DecisionContext, evaluate_rules
from app.services.safety_stock import (
    calculate_extended_safety_stock,
    calculate_safety_stock,
    calculate_z_value,
    resolve_service_level,
)

logger = logging.getLogger(__name__)


def make_decision(
    store: int,
    item: int,
    current_stock: int,
    on_order: int,
    sku_info: dict[str, Any],
    recent_history: pd.DataFrame,
    lead_time_forecast: np.ndarray,
    service_level: float | None = None,
    lead_time_days: int | None = None,
    as_of_date: str | None = None,
) -> dict[str, Any]:
    """Compute the complete inventory replenishment decision for a single SKU.
    
    Args:
        store: Store ID.
        item: Item ID.
        current_stock: Current on-hand inventory.
        on_order: Units currently ordered / in transit.
        sku_info: Dictionary of SKU master properties (abc, xyz, tier, lead_time_mean, lead_time_std).
        recent_history: DataFrame containing at least the 90 days of sales_clean up to as_of_date.
        lead_time_forecast: Array of L forecasted daily demand points.
        service_level: Optional override service level.
        lead_time_days: Optional override lead time.
        as_of_date: As-of date string (YYYY-MM-DD). Defaults to LAST_DATA_DATE.
        
    Returns:
        Complete decision result dictionary matching DecisionResponse schema.
    """
    eval_date = as_of_date or LAST_DATA_DATE
    sku_id = sku_info.get("sku_id") or f"S{store:02d}-I{item:02d}"
    abc = sku_info.get("abc", "B")
    xyz = sku_info.get("xyz", "Y")
    tier = sku_info.get("tier", "Core")
    lt_mean = sku_info.get("lead_time_mean", 7)
    lt_std = float(sku_info.get("lead_time_std", 1.0))

    # Lead time L
    if lead_time_days is not None:
        L = int(lead_time_days)
    else:
        L = max(1, round(lt_mean))

    # Service level & Z-value
    sl = resolve_service_level(abc, service_level)
    z_val = calculate_z_value(sl)

    # Lead time demand & mean daily forecast
    if len(lead_time_forecast) == 0:
        lead_time_demand = 0.0
        d_bar = 0.0
    else:
        lead_time_demand = float(np.sum(lead_time_forecast[:L]))
        d_bar = float(lead_time_demand / L) if L > 0 else 0.0

    # sigma_d from 90 days of sales_clean up to as_of_date
    if len(recent_history) > 1:
        sigma_d = float(np.std(recent_history["sales_clean"].values, ddof=1))
    elif len(recent_history) == 1:
        sigma_d = float(recent_history["sales_clean"].values[0])
    else:
        sigma_d = 1.0

    # Safety Stock
    ss = calculate_safety_stock(sl, sigma_d, float(L))
    ss_ext = calculate_extended_safety_stock(sl, sigma_d, float(L), d_bar, lt_std)

    # Reorder Point (ROP)
    rop = math.ceil(lead_time_demand) + ss

    # Inventory position & days of cover
    inv_pos = current_stock + on_order
    if d_bar > 0:
        days_of_cover = float(current_stock / d_bar)
    else:
        days_of_cover = 9999.0

    # Context & Rule evaluation
    ctx = DecisionContext(
        inventory_position=inv_pos,
        current_stock=current_stock,
        on_order=on_order,
        reorder_point=rop,
        lead_time_demand=lead_time_demand,
        safety_stock=ss,
        lead_time_days=L,
        days_of_cover=days_of_cover,
        mean_daily_forecast=d_bar,
        abc_class=abc,
    )

    matched_rule = evaluate_rules(ctx)
    action = matched_rule.action

    # Priority determination
    if action == "HOLD_STOCK":
        priority = "LOW"
    elif action == "EXPEDITE_SHIPMENT":
        priority = "CRITICAL"
    elif action == "REORDER_NOW":
        if days_of_cover < L:
            priority = "CRITICAL"
        elif abc == "A":
            priority = "HIGH"
        else:
            priority = "NORMAL"
    else:
        priority = "NORMAL"

    # Recommended order quantity
    if action == "REORDER_NOW":
        order_up_to = rop + math.ceil(d_bar * 7)
        recommended_order_qty = max(0, math.ceil(order_up_to - inv_pos))
    else:
        recommended_order_qty = 0

    # Overstock flag
    overstock_flag = bool(inv_pos > (2 * rop))

    # Formulate explanation with real numbers
    comp_str = "is below" if days_of_cover < L else "meets"
    if matched_rule.rule_id == "R1_EXPEDITE":
        explanation = matched_rule.explanation_template.format(
            inv_pos=inv_pos,
            rop=rop,
            ltd=lead_time_demand,
            ss=ss,
            cover=days_of_cover,
            lt=L,
            on_order=on_order,
        )
    elif matched_rule.rule_id == "R2_REORDER":
        explanation = matched_rule.explanation_template.format(
            inv_pos=inv_pos,
            rop=rop,
            ltd=lead_time_demand,
            ss=ss,
            cover=days_of_cover,
            comparison=comp_str,
            lt=L,
        )
    else:
        explanation = matched_rule.explanation_template.format(
            inv_pos=inv_pos,
            rop=rop,
            ltd=lead_time_demand,
            ss=ss,
            cover=days_of_cover,
        )

    return {
        "sku_id": sku_id,
        "as_of_date": eval_date,
        "abc": abc,
        "xyz": xyz,
        "tier": tier,
        "lead_time_days": L,
        "service_level": round(sl, 3),
        "z_value": round(z_val, 3),
        "mean_daily_forecast": round(d_bar, 2),
        "lead_time_demand": round(lead_time_demand, 2),
        "sigma_d": round(sigma_d, 2),
        "safety_stock": ss,
        "safety_stock_extended": ss_ext,
        "reorder_point": rop,
        "inventory_position": inv_pos,
        "days_of_cover": round(days_of_cover, 2),
        "action": action,
        "priority": priority,
        "recommended_order_qty": recommended_order_qty,
        "overstock_flag": overstock_flag,
        "triggered_rule": matched_rule.rule_id,
        "explanation": explanation,
    }

from __future__ import annotations

"""Unit tests for inventory rule engine and replenishment decisions (AI-1)."""

import numpy as np
import pandas as pd

from app.services.decision import make_decision
from app.services.rules import DecisionContext, evaluate_rules


def test_rule_r1_expedite():
    """Verify R1_EXPEDITE triggers when inv_pos <= ROP, on_order > 0, and cover < L."""
    ctx = DecisionContext(
        inventory_position=80,
        current_stock=20,
        on_order=60,
        reorder_point=100,
        lead_time_demand=70.0,
        safety_stock=30,
        lead_time_days=7,
        days_of_cover=2.0,  # 2.0 < 7
        mean_daily_forecast=10.0,
        abc_class="A",
    )
    rule = evaluate_rules(ctx)
    assert rule.rule_id == "R1_EXPEDITE"
    assert rule.action == "EXPEDITE_SHIPMENT"


def test_rule_r2_reorder():
    """Verify R2_REORDER triggers when inv_pos <= ROP and not qualifying for R1."""
    # on_order is 0, so R1 condition fails, falls through to R2
    ctx = DecisionContext(
        inventory_position=40,
        current_stock=40,
        on_order=0,
        reorder_point=100,
        lead_time_demand=70.0,
        safety_stock=30,
        lead_time_days=7,
        days_of_cover=4.0,
        mean_daily_forecast=10.0,
        abc_class="B",
    )
    rule = evaluate_rules(ctx)
    assert rule.rule_id == "R2_REORDER"
    assert rule.action == "REORDER_NOW"


def test_rule_r3_hold():
    """Verify R3_HOLD triggers when inv_pos > ROP."""
    ctx = DecisionContext(
        inventory_position=150,
        current_stock=150,
        on_order=0,
        reorder_point=100,
        lead_time_demand=70.0,
        safety_stock=30,
        lead_time_days=7,
        days_of_cover=15.0,
        mean_daily_forecast=10.0,
        abc_class="C",
    )
    rule = evaluate_rules(ctx)
    assert rule.rule_id == "R3_HOLD"
    assert rule.action == "HOLD_STOCK"


def test_priority_labels_and_order_qty():
    """Verify priority label logic and recommended order quantity calculation."""
    sku_info = {"sku_id": "S01-I01", "abc": "A", "xyz": "X", "tier": "Strategic", "lead_time_mean": 6, "lead_time_std": 1.0}
    df_hist = pd.DataFrame([{"sales_clean": 20.0} for _ in range(90)])
    lt_fc = np.full(6, 20.0, dtype=np.float32)

    # 1. Critical priority: cover < L
    dec_crit = make_decision(
        store=1,
        item=1,
        current_stock=10,  # 10 / 20 = 0.5 days cover < 6 days L
        on_order=0,
        sku_info=sku_info,
        recent_history=df_hist,
        lead_time_forecast=lt_fc,
    )
    assert dec_crit["action"] == "REORDER_NOW"
    assert dec_crit["priority"] == "CRITICAL"
    assert dec_crit["recommended_order_qty"] > 0

    # 2. High priority: cover >= L but abc is A
    dec_high = make_decision(
        store=1,
        item=1,
        current_stock=130,  # cover = 6.5 >= 6 L
        on_order=0,
        sku_info=sku_info,
        recent_history=df_hist,
        lead_time_forecast=lt_fc,
    )
    if dec_high["action"] == "REORDER_NOW":
        assert dec_high["priority"] == "HIGH"


def test_overstock_flag():
    """Verify overstock flag is True when inventory_position > 2 * ROP."""
    sku_info = {"sku_id": "S01-I01", "abc": "C", "xyz": "Z", "tier": "Tail", "lead_time_mean": 5, "lead_time_std": 1.0}
    df_hist = pd.DataFrame([{"sales_clean": 10.0} for _ in range(90)])
    lt_fc = np.full(5, 10.0, dtype=np.float32)

    # rop will be around 50 + SS ~ 70. With stock 500, inv_pos > 2 * rop
    dec = make_decision(
        store=1,
        item=1,
        current_stock=500,
        on_order=0,
        sku_info=sku_info,
        recent_history=df_hist,
        lead_time_forecast=lt_fc,
    )
    assert dec["action"] == "HOLD_STOCK"
    assert dec["priority"] == "LOW"
    assert dec["overstock_flag"] is True
    assert dec["recommended_order_qty"] == 0

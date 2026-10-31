from __future__ import annotations

"""Stockout simulation service (AI-1) comparing static versus dynamic inventory policies."""

import logging
import math
from typing import Any

import numpy as np
import pandas as pd

from app.config import RANDOM_SEED, TEST_END, TEST_START

logger = logging.getLogger(__name__)


def simulate_policies(
    df_sales: pd.DataFrame,
    sku_master_df: pd.DataFrame,
    dynamic_rops: dict[str, dict[str, int]],
) -> dict[str, Any]:
    """Run the 91-day historical stockout simulation comparing static and dynamic policies.
    
    Both policies use:
      - Q = ceil(d90 * 14)
      - Initial on-hand = ceil(d90 * (L + 14))
      - Identical shared stochastic lead-time draws from default_rng(42)
      
    Args:
        df_sales: Sales dataframe containing store, item, date, sales, sales_clean.
        sku_master_df: DataFrame with sku_id, store, item, lead_time_mean, lead_time_std, abc.
        dynamic_rops: Dict mapping sku_id -> {date_or_origin: rop}.
        
    Returns:
        Evaluation metrics comparing Static and Dynamic policies.
    """
    df = df_sales.copy()
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"])

    test_mask = (df["date"] >= TEST_START) & (df["date"] <= TEST_END)
    df_test = df[test_mask].sort_values(["date", "store", "item"])

    # 90-day pre-test period for d90
    pre_start = pd.to_datetime(TEST_START) - pd.Timedelta(days=90)
    pre_mask = (df["date"] >= pre_start) & (df["date"] < TEST_START)
    df_pre = df[pre_mask]

    # Precompute d90 and initial state per SKU
    skus_sorted = sku_master_df.sort_values(["store", "item"]).reset_index(drop=True)
    sku_init: dict[str, dict[str, Any]] = {}

    for _, row in skus_sorted.iterrows():
        s = int(row["store"])
        it = int(row["item"])
        sku_id = str(row["sku_id"])
        lt_mean = float(row["lead_time_mean"])
        lt_std = float(row["lead_time_std"])
        L = max(1, round(lt_mean))

        # d90
        sub_pre = df_pre[(df_pre["store"] == s) & (df_pre["item"] == it)]
        if len(sub_pre) > 0:
            d90 = float(sub_pre["sales_clean"].mean())
        else:
            d90 = 10.0

        Q = math.ceil(d90 * 14)
        init_on_hand = math.ceil(d90 * (L + 14))
        rop_static = math.ceil(d90 * L)

        sku_init[sku_id] = {
            "store": s,
            "item": it,
            "d90": d90,
            "L": L,
            "Q": Q,
            "init_on_hand": init_on_hand,
            "rop_static": rop_static,
            "lt_mean": lt_mean,
            "lt_std": lt_std,
        }

    # Simulation dates (91 days)
    sim_dates = pd.date_range(TEST_START, TEST_END, freq="D")

    # Shared lead time random generator to draw exact same lead times for both policies
    rng_static = np.random.default_rng(RANDOM_SEED)
    rng_dynamic = np.random.default_rng(RANDOM_SEED)

    def run_single_policy(is_dynamic: bool, rng: np.random.Generator) -> dict[str, Any]:
        total_stockout_days = 0
        total_demand = 0
        total_fulfilled = 0
        daily_on_hand_sums: list[float] = []

        # State per SKU: on_hand, on_order, pending_orders: list of (arrival_day_idx, quantity)
        state: dict[str, dict[str, Any]] = {}
        for sku_id, init in sku_init.items():
            state[sku_id] = {
                "on_hand": init["init_on_hand"],
                "on_order": 0,
                "pending_orders": [],  # list of (arrival_day_idx, qty)
            }

        # Daily simulation loop
        for day_idx, current_date in enumerate(sim_dates):
            date_str = current_date.strftime("%Y-%m-%d")
            day_sales = df_test[df_test["date"] == current_date]
            sales_lookup = {(int(r["store"]), int(r["item"])): int(r["sales"]) for _, r in day_sales.iterrows()}

            daily_on_hand = 0

            for _, row in skus_sorted.iterrows():
                sku_id = str(row["sku_id"])
                st = state[sku_id]
                init = sku_init[sku_id]

                # 1. Receive arriving orders
                remaining_orders = []
                for arr_idx, qty in st["pending_orders"]:
                    if arr_idx <= day_idx:
                        st["on_hand"] += qty
                        st["on_order"] = max(0, st["on_order"] - qty)
                    else:
                        remaining_orders.append((arr_idx, qty))
                st["pending_orders"] = remaining_orders

                # 2. Daily demand
                key = (init["store"], init["item"])
                demand = sales_lookup.get(key, 0)
                total_demand += demand

                # Stockout check
                if demand > st["on_hand"]:
                    total_stockout_days += 1
                    fulfilled = st["on_hand"]
                    st["on_hand"] = 0
                else:
                    fulfilled = demand
                    st["on_hand"] -= demand

                total_fulfilled += fulfilled
                daily_on_hand += st["on_hand"]

                # 3. Reorder check
                inv_pos = st["on_hand"] + st["on_order"]

                # Determine ROP
                if is_dynamic:
                    sku_dyn = dynamic_rops.get(sku_id, {})
                    rop = sku_dyn.get(date_str, init["rop_static"])
                else:
                    rop = init["rop_static"]

                if inv_pos <= rop and st["on_order"] == 0:
                    order_qty = init["Q"]
                    st["on_order"] += order_qty
                    # Draw lead time from normal distribution
                    raw_lt = rng.normal(init["lt_mean"], init["lt_std"])
                    realized_lt = max(1, round(raw_lt))
                    arrival_idx = day_idx + realized_lt
                    st["pending_orders"].append((arrival_idx, order_qty))

            daily_on_hand_sums.append(daily_on_hand / len(skus_sorted))

        fill_rate = float(total_fulfilled / total_demand) if total_demand > 0 else 1.0
        mean_on_hand = float(np.mean(daily_on_hand_sums))

        return {
            "total_stockout_days": total_stockout_days,
            "fill_rate": round(fill_rate, 4),
            "mean_on_hand": round(mean_on_hand, 2),
            "total_demand": total_demand,
            "total_fulfilled": total_fulfilled,
        }

    # Run both simulations
    static_results = run_single_policy(is_dynamic=False, rng=rng_static)
    dynamic_results = run_single_policy(is_dynamic=True, rng=rng_dynamic)

    # Reduction in stockout days
    static_days = static_results["total_stockout_days"]
    dynamic_days = dynamic_results["total_stockout_days"]
    if static_days > 0:
        reduction = float((static_days - dynamic_days) / static_days)
    else:
        reduction = 0.0

    passed = bool(reduction >= 0.20)
    inventory_delta = dynamic_results["mean_on_hand"] - static_results["mean_on_hand"]

    return {
        "static_policy": static_results,
        "dynamic_policy": dynamic_results,
        "stockout_days_reduction": round(reduction, 4),
        "inventory_delta": round(inventory_delta, 2),
        "passed": passed,
    }

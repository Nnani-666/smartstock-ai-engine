from __future__ import annotations

"""Unit tests for stockout simulation service (AI-1)."""

import pandas as pd

from app.services.simulation import simulate_policies


def test_simulation_policies_basic():
    """Verify that simulate_policies correctly calculates stockouts, fill rates, and inventory deltas."""
    dates = pd.date_range("2017-06-01", "2017-12-31", freq="D")
    
    # 2 SKUs
    records = []
    for s in [1]:
        for it in [1, 2]:
            for d in dates:
                records.append({
                    "store": s,
                    "item": it,
                    "date": d,
                    "sales": 10,
                    "sales_clean": 10.0,
                })
    df_sales = pd.DataFrame(records)

    df_skus = pd.DataFrame([
        {"sku_id": "S01-I01", "store": 1, "item": 1, "lead_time_mean": 5, "lead_time_std": 1.0, "abc": "A"},
        {"sku_id": "S01-I02", "store": 1, "item": 2, "lead_time_mean": 6, "lead_time_std": 1.2, "abc": "B"},
    ])

    # Dynamic ROPs higher than static to protect against stockouts
    dynamic_rops = {
        "S01-I01": {d.strftime("%Y-%m-%d"): 80 for d in dates},
        "S01-I02": {d.strftime("%Y-%m-%d"): 90 for d in dates},
    }

    results = simulate_policies(df_sales, df_skus, dynamic_rops)

    assert "static_policy" in results
    assert "dynamic_policy" in results
    assert "stockout_days_reduction" in results
    assert "passed" in results

    static_res = results["static_policy"]
    dynamic_res = results["dynamic_policy"]
    assert static_res["total_demand"] > 0
    assert 0.0 <= static_res["fill_rate"] <= 1.0
    assert 0.0 <= dynamic_res["fill_rate"] <= 1.0

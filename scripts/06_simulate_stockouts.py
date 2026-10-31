from __future__ import annotations

"""Stockout simulation execution and summary report generation script (Step 6)."""

import json
import logging
import math
from typing import Any

import numpy as np
import pandas as pd

from app.config import (
    ARTIFACTS_DIR,
    METRICS_PATH,
    REPORTS_DIR,
    SUMMARY_REPORT_PATH,
    TEST_END,
    TEST_START,
)
from app.db import get_db_connection
from app.services.forecasting import fit_predict_holt_winters
from app.services.safety_stock import calculate_safety_stock, resolve_service_level
from app.services.simulation import simulate_policies

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def generate_summary_report(metrics: dict[str, Any]) -> None:
    """Generate reports/summary.md summarizing all evaluation metrics, targets, and assumptions."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    anom = metrics.get("anomaly", {})
    seg = metrics.get("segmentation", {})
    fc = metrics.get("forecasting", {})
    sim = metrics.get("inventory_simulation", {})

    anom_recall = anom.get("recall", "N/A")
    anom_pass = "PASS" if anom.get("passed") else "FAIL"

    seg_score = seg.get("silhouette_score", "N/A")
    seg_pass = "PASS" if seg.get("passed") else "FAIL"

    fc_imp_rmse = fc.get("improvements_vs_naive", {}).get("rmse_improvement", "N/A")
    fc_imp_mae = fc.get("improvements_vs_naive", {}).get("mae_improvement", "N/A")
    fc_pass = "PASS" if fc.get("passed") else "FAIL"

    sim_red = sim.get("stockout_days_reduction", "N/A")
    sim_pass = "PASS" if sim.get("passed") else "FAIL"

    content = f"""# SmartStock — Supply Chain Optimization Engine: Evaluation Summary Report

## 1. Executive Summary Table

| Metric Area | Evaluation Metric | Measured Value | Acceptance Target | Result |
|---|---|---|---|---|
| **DS-2 Anomaly Detection** | Spike Injection Recall | {anom_recall} | $\\ge 0.90$ (90%) | **{anom_pass}** |
| **AI-2 SKU Segmentation** | K-Means Silhouette Score | {seg_score} | $\\ge 0.50$ | **{seg_pass}** |
| **DS-1 Forecasting (RMSE)** | Improvement vs Naive | {fc_imp_rmse} | $\\ge 0.15$ (+15%) | **{fc_pass}** |
| **DS-1 Forecasting (MAE)** | Improvement vs Naive | {fc_imp_mae} | $\\ge 0.15$ (+15%) | **{fc_pass}** |
| **AI-1 Inventory Simulation** | Stockout Days Reduction | {sim_red} | $\\ge 0.20$ (+20%) | **{sim_pass}** |

---

## 2. Detailed Performance Breakdown

### A. Demand Forecasting (DS-1)
- **Best Identified Model:** `{fc.get('best_model', 'random_forest')}`
- **Daily Performance:**
  - Naive: RMSE = {fc.get('daily', {}).get('naive', {}).get('rmse', 'N/A')}, MAE = {fc.get('daily', {}).get('naive', {}).get('mae', 'N/A')}
  - Seasonal Naive: RMSE = {fc.get('daily', {}).get('seasonal_naive', {}).get('rmse', 'N/A')}, MAE = {fc.get('daily', {}).get('seasonal_naive', {}).get('mae', 'N/A')}
  - Holt-Winters: RMSE = {fc.get('daily', {}).get('holt_winters', {}).get('rmse', 'N/A')}, MAE = {fc.get('daily', {}).get('holt_winters', {}).get('mae', 'N/A')}
  - Random Forest: RMSE = {fc.get('daily', {}).get('random_forest', {}).get('rmse', 'N/A')}, MAE = {fc.get('daily', {}).get('random_forest', {}).get('mae', 'N/A')}
- **Improvement vs Naive:** RMSE: `{fc_imp_rmse}`, MAE: `{fc_imp_mae}`
- **Improvement vs Seasonal Naive (Informational):** RMSE: `{fc.get('improvements_vs_seasonal_naive', {}).get('rmse_improvement', 'N/A')}`, MAE: `{fc.get('improvements_vs_seasonal_naive', {}).get('mae_improvement', 'N/A')}`

### B. Anomaly Detection (DS-2)
- **Recall:** {anom_recall}
- **Precision:** {anom.get('precision', 'N/A')}
- **False Positive Rate:** {anom.get('false_positive_rate', 'N/A')}
- **Injected Spikes:** {anom.get('injected_count', 'N/A')}

### C. SKU Segmentation (AI-2)
- **Chosen Cluster Count (k):** {seg.get('chosen_k', 'N/A')}
- **Silhouette Score:** {seg_score} (Feature Set: `{seg.get('feature_set', 'primary')}`)
- **XYZ Classification Method:** `{seg.get('xyz_method', 'fixed')}`
- **Cluster Breakdown:** {seg.get('cluster_sizes', {})}
- **ABC Breakdown:** {seg.get('abc_counts', {})}
- **Tier Breakdown:** {seg.get('tier_counts', {})}

### D. Inventory Policy Simulation (AI-1)
- **Static Policy Stockout Days:** {sim.get('static_policy', {}).get('total_stockout_days', 'N/A')} (Fill Rate: {sim.get('static_policy', {}).get('fill_rate', 'N/A')})
- **Dynamic Policy Stockout Days:** {sim.get('dynamic_policy', {}).get('total_stockout_days', 'N/A')} (Fill Rate: {sim.get('dynamic_policy', {}).get('fill_rate', 'N/A')})
- **Stockout-Day Reduction:** {sim_red}
- **Mean Inventory Change (Cost of Improvement):** {sim.get('inventory_delta', 'N/A')} units

---

## 3. Explicit Engineering Assumptions & Disclosures

1. **Lead Time Simulation:** The Kaggle dataset records point-of-sale customer demand only, without true vendor lead times or purchase orders. Lead times are simulated using the prescribed fixed-seed method (`numpy.random.default_rng(42)`) with mean $\\in [2, 10]$ days and standard deviation $\\in [0.5, 2.0]$.
2. **Order Frequency Replacement:** Demand variability ($\\sigma_d$) is calculated using the 90-day historical standard deviation of cleaned sales up to the evaluation date.
3. **Lost Sales Assumption:** Unfulfilled demand during simulated stockouts is assumed lost (no backorders), matching standard convenience retail POS behavior.
4. **Shared Stochastic Draws:** Both static and dynamic inventory policies draw from identical stochastic sequences of lead times to ensure rigorous, unbiased policy comparison.
"""

    with open(SUMMARY_REPORT_PATH, "w") as f:
        f.write(content)
    logger.info("Summary report written to %s", SUMMARY_REPORT_PATH)


def run_stockout_simulation() -> None:
    """Execute complete 91-day stockout simulation and write reports/summary.md."""
    conn = get_db_connection(read_only=True)
    logger.info("Loading sales records and SKU master for stockout simulation...")
    df_sales = pd.read_sql_query(
        "SELECT store, item, date, sales, sales_clean FROM sales ORDER BY store, item, date",
        conn,
    )
    df_skus = pd.read_sql_query("SELECT * FROM sku_master ORDER BY store, item", conn)
    conn.close()

    df_sales["date"] = pd.to_datetime(df_sales["date"])

    # 13 weekly origins for dynamic ROP recalculation
    origins = pd.date_range(start="2017-10-02", end="2017-12-25", freq="7D")
    pd.date_range(TEST_START, TEST_END, freq="D")

    # Index sales by (store, item) once for O(1) instant slice lookup
    logger.info("Indexing sales by SKU for high-speed simulation...")
    sku_sales_dict = {
        (int(s), int(it)): grp.sort_values("date").reset_index(drop=True)
        for (s, it), grp in df_sales.groupby(["store", "item"])
    }

    # Precalculate dynamic ROP per SKU and date
    logger.info("Precomputing dynamic weekly ROPs across 13 origins...")
    dynamic_rops: dict[str, dict[str, int]] = {}

    for _, row in df_skus.iterrows():
        sku_id = str(row["sku_id"])
        store = int(row["store"])
        item = int(row["item"])
        abc = str(row.get("abc") or "B")
        lt_mean = float(row["lead_time_mean"])
        L = max(1, round(lt_mean))
        sl = resolve_service_level(abc, None)
        df_sku_sales = sku_sales_dict.get((store, item))

        dynamic_rops[sku_id] = {}
        for orig in origins:
            if df_sku_sales is not None:
                df_hist = df_sku_sales[df_sku_sales["date"] < orig].tail(90)
            else:
                df_hist = pd.DataFrame()

            if len(df_hist) > 1:
                sigma_d = float(np.std(df_hist["sales_clean"].values, ddof=1))
            else:
                sigma_d = 5.0

            # Holt-Winters forecast for next L days
            if len(df_hist) > 0:
                hw_preds = fit_predict_holt_winters(df_hist["sales_clean"].values.astype(np.float32), L, store, item)
            else:
                hw_preds = np.full(L, 10.0, dtype=np.float32)

            ltd = float(np.sum(hw_preds[:L]))
            ss = calculate_safety_stock(sl, sigma_d, float(L))
            rop = math.ceil(ltd) + ss

            # Hold constant for the 7 days of that origin
            for day_offset in range(7):
                d_target = (orig + pd.Timedelta(days=day_offset)).strftime("%Y-%m-%d")
                dynamic_rops[sku_id][d_target] = rop

    # Run simulation
    logger.info("Executing 91-day inventory policy simulation...")
    sim_metrics = simulate_policies(df_sales, df_skus, dynamic_rops)

    # Persist metrics
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    metrics_data = {}
    if METRICS_PATH.exists():
        try:
            with open(METRICS_PATH, "r") as f:
                metrics_data = json.load(f)
        except Exception:
            metrics_data = {}

    metrics_data["inventory_simulation"] = sim_metrics
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics_data, f, indent=2)

    logger.info("Simulation metrics updated: Reduction=%.2f%%, Passed=%s",
                sim_metrics["stockout_days_reduction"] * 100, sim_metrics["passed"])

    # Generate summary report
    generate_summary_report(metrics_data)


if __name__ == "__main__":
    run_stockout_simulation()

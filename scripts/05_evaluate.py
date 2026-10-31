from __future__ import annotations

"""Rolling-origin forecasting evaluation script (Step 5)."""

import argparse
import json
import logging
from typing import Any

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from app.config import (
    ARTIFACTS_DIR,
    METRICS_PATH,
    MODEL_PATH,
)
from app.db import get_db_connection
from app.services.forecasting import (
    fit_predict_holt_winters,
    forecast_naive,
    forecast_rf_single_series,
    forecast_seasonal_naive,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_evaluation(series_limit: int | None = None) -> dict[str, Any]:
    """Execute 13-origin rolling evaluation across naive, seasonal_naive, holt_winters, and random_forest."""
    conn = get_db_connection(read_only=True)
    logger.info("Loading sales records from supply_chain.db...")
    df = pd.read_sql_query(
        "SELECT store, item, date, sales, sales_clean FROM sales ORDER BY store, item, date",
        conn,
    )
    conn.close()

    df["date"] = pd.to_datetime(df["date"])

    # Load Random Forest model
    rf_model = None
    if MODEL_PATH.exists():
        rf_model = joblib.load(MODEL_PATH)
        logger.info("Loaded Random Forest model for evaluation.")

    # Distinct series
    all_series = df[["store", "item"]].drop_duplicates().sort_values(["store", "item"]).values
    if series_limit is not None and series_limit > 0:
        all_series = all_series[:series_limit]
        logger.info("Restricting evaluation to first %d series...", len(all_series))

    # 13 rolling origins: 2017-10-02 every 7 days through 2017-12-25
    origins = pd.date_range(start="2017-10-02", end="2017-12-25", freq="7D")
    logger.info("Running evaluation across %d origins and %d series...", len(origins), len(all_series))

    # Storage for predictions and actuals
    # keys: 'naive', 'seasonal_naive', 'holt_winters', 'random_forest'
    preds_daily = {"naive": [], "seasonal_naive": [], "holt_winters": [], "random_forest": []}
    actuals_daily = []

    preds_weekly = {"naive": [], "seasonal_naive": [], "holt_winters": [], "random_forest": []}
    actuals_weekly = []

    for origin in origins:
        origin.strftime("%Y-%m-%d")
        # 7-day test window
        h_dates = pd.date_range(origin, periods=7, freq="D")
        
        for store, item in all_series:
            # Data strictly before origin
            df_hist = df[(df["store"] == store) & (df["item"] == item) & (df["date"] < origin)].sort_values("date")
            # Actual sales for the 7 days
            df_actual = df[(df["store"] == store) & (df["item"] == item) & (df["date"].isin(h_dates))].sort_values("date")

            if len(df_actual) < 7:
                continue

            y_actual = df_actual["sales"].values.astype(np.float64)
            history_vals = df_hist["sales_clean"].values.astype(np.float32)

            # 1. Naive
            p_naive = forecast_naive(history_vals, 7)
            # 2. Seasonal Naive
            p_snaive = forecast_seasonal_naive(history_vals, 7)
            # 3. Holt-Winters
            p_hw = fit_predict_holt_winters(history_vals, 7, store=int(store), item=int(item))
            # 4. Random Forest
            if rf_model is not None:
                p_rf = forecast_rf_single_series(
                    rf_model, df_hist, 7, int(store), int(item), df_hist["date"].max()
                )
            else:
                p_rf = p_hw

            actuals_daily.extend(y_actual)
            preds_daily["naive"].extend(p_naive)
            preds_daily["seasonal_naive"].extend(p_snaive)
            preds_daily["holt_winters"].extend(p_hw)
            preds_daily["random_forest"].extend(p_rf)

            actuals_weekly.append(float(np.sum(y_actual)))
            preds_weekly["naive"].append(float(np.sum(p_naive)))
            preds_weekly["seasonal_naive"].append(float(np.sum(p_snaive)))
            preds_weekly["holt_winters"].append(float(np.sum(p_hw)))
            preds_weekly["random_forest"].append(float(np.sum(p_rf)))

    # Compute metrics
    results: dict[str, Any] = {"daily": {}, "weekly": {}}

    for model_name in ["naive", "seasonal_naive", "holt_winters", "random_forest"]:
        # Daily
        p_d = np.array(preds_daily[model_name])
        a_d = np.array(actuals_daily)
        rmse_d = float(np.sqrt(mean_squared_error(a_d, p_d)))
        mae_d = float(mean_absolute_error(a_d, p_d))
        results["daily"][model_name] = {"rmse": round(rmse_d, 3), "mae": round(mae_d, 3)}

        # Weekly
        p_w = np.array(preds_weekly[model_name])
        a_w = np.array(actuals_weekly)
        rmse_w = float(np.sqrt(mean_squared_error(a_w, p_w)))
        mae_w = float(mean_absolute_error(a_w, p_w))
        results["weekly"][model_name] = {"rmse": round(rmse_w, 3), "mae": round(mae_w, 3)}

    # Determine best model between holt_winters and random_forest by daily RMSE
    hw_rmse = results["daily"]["holt_winters"]["rmse"]
    rf_rmse = results["daily"]["random_forest"]["rmse"]
    best_name = "random_forest" if rf_rmse <= hw_rmse else "holt_winters"
    results["best_model"] = best_name

    # Improvements versus naive
    base_rmse = results["daily"]["naive"]["rmse"]
    base_mae = results["daily"]["naive"]["mae"]
    best_rmse = results["daily"][best_name]["rmse"]
    best_mae = results["daily"][best_name]["mae"]

    rmse_imp = float((base_rmse - best_rmse) / base_rmse)
    mae_imp = float((base_mae - best_mae) / base_mae)

    # Improvements versus seasonal naive
    snaive_rmse = results["daily"]["seasonal_naive"]["rmse"]
    snaive_mae = results["daily"]["seasonal_naive"]["mae"]
    snaive_rmse_imp = float((snaive_rmse - best_rmse) / snaive_rmse) if snaive_rmse > 0 else 0.0
    snaive_mae_imp = float((snaive_mae - best_mae) / snaive_mae) if snaive_mae > 0 else 0.0

    passed = bool((rmse_imp >= 0.15) and (mae_imp >= 0.15))

    results["improvements_vs_naive"] = {
        "rmse_improvement": round(rmse_imp, 4),
        "mae_improvement": round(mae_imp, 4),
    }
    results["improvements_vs_seasonal_naive"] = {
        "rmse_improvement": round(snaive_rmse_imp, 4),
        "mae_improvement": round(snaive_mae_imp, 4),
    }
    results["passed"] = passed

    logger.info("Evaluation results: Best=%s (RMSE=%.3f, MAE=%.3f), Imp vs Naive: RMSE=+%.1f%%, MAE=+%.1f%%, Passed=%s",
                best_name, best_rmse, best_mae, rmse_imp * 100, mae_imp * 100, passed)

    # Persist to metrics.json
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    metrics_data = {}
    if METRICS_PATH.exists():
        try:
            with open(METRICS_PATH, "r") as f:
                metrics_data = json.load(f)
        except Exception:
            metrics_data = {}

    metrics_data["forecasting"] = results
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics_data, f, indent=2)

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate forecasting models across rolling origins")
    parser.add_argument("--series-limit", type=int, default=None, help="Limit number of series for fast testing")
    args = parser.parse_args()

    run_evaluation(series_limit=args.series_limit)

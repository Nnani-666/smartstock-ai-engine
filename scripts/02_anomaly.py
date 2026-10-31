from __future__ import annotations

"""Anomaly detection execution and spike injection evaluation script (Step 2)."""

import json
import logging

import pandas as pd

from app.config import (
    ARTIFACTS_DIR,
    METRICS_PATH,
    TRAIN_END,
)
from app.db import get_db_connection
from app.services.anomaly import (
    compute_group_statistics,
    detect_anomalies,
    evaluate_injection,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_anomaly_pipeline() -> None:
    """Execute anomaly detection pipeline on supply_chain.db."""
    conn = get_db_connection(read_only=False)
    logger.info("Loading sales records from supply_chain.db...")
    df = pd.read_sql_query("SELECT store, item, date, sales FROM sales ORDER BY store, item, date", conn)
    df["date"] = pd.to_datetime(df["date"])
    df["weekday"] = df["date"].dt.weekday

    # 1. Fit stats up to TRAIN_END
    logger.info("Fitting group statistics up to TRAIN_END (%s)...", TRAIN_END)
    df_train = df[df["date"] <= TRAIN_END]
    stats_dict = compute_group_statistics(df_train)

    # 2. Detect anomalies on all rows
    logger.info("Detecting anomalies across all historical rows...")
    df_detected = detect_anomalies(df, stats_dict)

    # 3. Persist flags and sales_clean to sales table
    logger.info("Updating sales table with anomaly flags and cleaned sales...")
    update_data = [
        (
            float(r.sales_clean),
            float(r.z_score),
            int(r.z_flag),
            int(r.iqr_flag),
            int(r.is_anomaly),
            int(r.store),
            int(r.item),
            r.date.strftime("%Y-%m-%d"),
        )
        for r in df_detected.itertuples()
    ]

    cursor = conn.cursor()
    cursor.executemany(
        """
        UPDATE sales SET
            sales_clean = ?,
            z_score = ?,
            z_flag = ?,
            iqr_flag = ?,
            is_anomaly = ?
        WHERE store = ? AND item = ? AND date = ?;
        """,
        update_data,
    )
    conn.commit()
    conn.close()

    # 4. Spike injection evaluation
    logger.info("Running spike injection evaluation test...")
    eval_metrics = evaluate_injection(df)

    # 5. Persist metrics to artifacts/metrics.json
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    metrics_data = {}
    if METRICS_PATH.exists():
        try:
            with open(METRICS_PATH, "r") as f:
                metrics_data = json.load(f)
        except Exception:
            metrics_data = {}

    metrics_data["anomaly"] = eval_metrics
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics_data, f, indent=2)

    logger.info("Anomaly metrics saved to %s: %s", METRICS_PATH, eval_metrics)


if __name__ == "__main__":
    run_anomaly_pipeline()

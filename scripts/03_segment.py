from __future__ import annotations

"""SKU Segmentation pipeline execution script (Step 3)."""

import json
import logging

import pandas as pd

from app.config import (
    ARTIFACTS_DIR,
    METRICS_PATH,
    SEGMENTS_PATH,
    TRAIN_END,
)
from app.db import get_db_connection
from app.services.segmentation import run_segmentation

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_segmentation_pipeline() -> None:
    """Execute SKU segmentation and persist clusters, classifications, and metrics."""
    conn = get_db_connection(read_only=False)
    logger.info("Loading training sales up to %s from supply_chain.db...", TRAIN_END)
    df_train = pd.read_sql_query(
        "SELECT store, item, date, sales_clean FROM sales WHERE date <= ? ORDER BY store, item, date",
        conn,
        params=[TRAIN_END],
    )

    logger.info("Running ABC, XYZ, and KMeans clustering...")
    df_sku, seg_metrics = run_segmentation(df_train)

    # 1. Update sku_master in database
    logger.info("Updating sku_master table with segmentation results...")
    update_data = [
        (
            float(r.mean_daily),
            float(r.cv),
            float(r.seasonality_amp),
            int(r.cluster),
            str(r.abc),
            str(r.xyz),
            str(r.tier),
            int(r.store),
            int(r.item),
        )
        for r in df_sku.itertuples()
    ]

    cursor = conn.cursor()
    cursor.executemany(
        """
        UPDATE sku_master SET
            mean_daily = ?,
            cv = ?,
            seasonality_amp = ?,
            cluster = ?,
            abc = ?,
            xyz = ?,
            tier = ?
        WHERE store = ? AND item = ?;
        """,
        update_data,
    )
    conn.commit()
    conn.close()

    # 2. Persist segments.json
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(SEGMENTS_PATH, "w") as f:
        json.dump(seg_metrics, f, indent=2)
    logger.info("Segments saved to %s", SEGMENTS_PATH)

    # 3. Persist to metrics.json
    metrics_data = {}
    if METRICS_PATH.exists():
        try:
            with open(METRICS_PATH, "r") as f:
                metrics_data = json.load(f)
        except Exception:
            metrics_data = {}

    metrics_data["segmentation"] = seg_metrics
    with open(METRICS_PATH, "w") as f:
        json.dump(metrics_data, f, indent=2)

    logger.info("Segmentation metrics updated in %s", METRICS_PATH)


if __name__ == "__main__":
    run_segmentation_pipeline()

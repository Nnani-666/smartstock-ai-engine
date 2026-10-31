from __future__ import annotations

"""Data ingestion script (Step 1).

Validates raw dataset, initializes SQLite database, computes simulated lead times,
and loads raw sales records into supply_chain.db.
"""

import argparse
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from app.config import (
    EXPECTED_END_DATE,
    EXPECTED_START_DATE,
    ITEM_COUNT,
    RANDOM_SEED,
    RAW_DATA_PATH,
    STORE_COUNT,
    TOTAL_EXPECTED_ROWS,
)
from app.db import get_db_connection, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def generate_synthetic_data() -> pd.DataFrame:
    """Generate deterministic synthetic dataset for pipeline testing if raw data is absent."""
    logger.info("Generating synthetic Kaggle dataset (500 series, 2013-2017)...")
    dates = pd.date_range(EXPECTED_START_DATE, EXPECTED_END_DATE, freq="D")
    rng = np.random.default_rng(RANDOM_SEED)
    records = []

    for s in range(1, STORE_COUNT + 1):
        for it in range(1, ITEM_COUNT + 1):
            base_sales = 15 + (s * 2) + (it % 10)
            daily_noise = rng.poisson(lam=base_sales, size=len(dates))
            for d, sales_val in zip(dates, daily_noise):
                records.append({
                    "date": d.strftime("%Y-%m-%d"),
                    "store": s,
                    "item": it,
                    "sales": int(sales_val),
                })

    df = pd.DataFrame(records)
    RAW_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(RAW_DATA_PATH, index=False)
    logger.info("Saved synthetic dataset to %s (%d rows)", RAW_DATA_PATH, len(df))
    return df


def validate_and_ingest(csv_path: Path, allow_synthetic: bool = False) -> None:
    """Validate raw sales CSV and ingest into supply_chain.db."""
    if not csv_path.exists():
        if allow_synthetic:
            df = generate_synthetic_data()
        else:
            logger.error(
                "Raw dataset not found at %s.\n"
                "Please place the Kaggle Store Item Demand Forecasting dataset at data/raw/train.csv\n"
                "or run with --synthetic to generate deterministic test data.",
                csv_path,
            )
            sys.exit(1)
    else:
        logger.info("Reading raw dataset from %s...", csv_path)
        df = pd.read_csv(csv_path)

    # 1. Validation checks
    logger.info("Validating dataset integrity...")
    if len(df) != TOTAL_EXPECTED_ROWS:
        msg = f"Expected {TOTAL_EXPECTED_ROWS} rows, got {len(df)}"
        if not allow_synthetic:
            raise ValueError(msg)
        logger.warning(msg)

    if df[["date", "store", "item", "sales"]].isnull().any().any():
        raise ValueError("Dataset contains null values")

    min_date = df["date"].min()
    max_date = df["date"].max()
    if min_date != EXPECTED_START_DATE or max_date != EXPECTED_END_DATE:
        msg = f"Expected date range {EXPECTED_START_DATE} to {EXPECTED_END_DATE}, got {min_date} to {max_date}"
        if not allow_synthetic:
            raise ValueError(msg)
        logger.warning(msg)

    if (df["store"] < 1).any() or (df["store"] > STORE_COUNT).any():
        raise ValueError(f"Store IDs must be between 1 and {STORE_COUNT}")

    if (df["item"] < 1).any() or (df["item"] > ITEM_COUNT).any():
        raise ValueError(f"Item IDs must be between 1 and {ITEM_COUNT}")

    if (df["sales"] < 0).any() or not pd.api.types.is_integer_dtype(df["sales"]):
        raise ValueError("Sales column must contain non-negative integers")

    logger.info("Validation passed successfully.")

    # 2. Database Initialization
    conn = get_db_connection(read_only=False)
    init_db(conn)

    # 3. Simulate Lead Times
    logger.info("Simulating fixed-seed lead times for 500 SKUs...")
    rng = np.random.default_rng(RANDOM_SEED)
    sku_master_records = []

    for s in range(1, STORE_COUNT + 1):
        for it in range(1, ITEM_COUNT + 1):
            sku_id = f"S{s:02d}-I{it:02d}"
            lt_mean = int(rng.integers(2, 11))  # 2 to 10 inclusive
            lt_std = round(float(rng.uniform(0.5, 2.0)), 2)
            sku_master_records.append((sku_id, s, it, lt_mean, lt_std))

    cursor = conn.cursor()
    cursor.executemany(
        """
        INSERT INTO sku_master (sku_id, store, item, lead_time_mean, lead_time_std)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(store, item) DO UPDATE SET
            lead_time_mean = excluded.lead_time_mean,
            lead_time_std = excluded.lead_time_std;
        """,
        sku_master_records,
    )

    # 4. Insert Sales records
    logger.info("Loading sales records into supply_chain.db...")
    df["sales_clean"] = df["sales"].astype(float)
    df["z_score"] = None
    df["z_flag"] = 0
    df["iqr_flag"] = 0
    df["is_anomaly"] = 0

    sales_records = [
        (
            int(r.store),
            int(r.item),
            str(r.date),
            int(r.sales),
            float(r.sales_clean),
            None,
            0,
            0,
            0,
        )
        for r in df.itertuples()
    ]

    cursor.executemany(
        """
        INSERT OR REPLACE INTO sales (store, item, date, sales, sales_clean, z_score, z_flag, iqr_flag, is_anomaly)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        sales_records,
    )

    conn.commit()
    conn.close()
    logger.info("Ingestion complete. Database populated successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest Kaggle demand forecasting dataset into SQLite")
    parser.add_argument("--synthetic", action="store_true", help="Generate synthetic data if train.csv is missing")
    args = parser.parse_args()

    validate_and_ingest(RAW_DATA_PATH, allow_synthetic=args.synthetic)

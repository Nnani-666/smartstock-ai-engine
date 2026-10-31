from __future__ import annotations

"""Random Forest model training script (Step 4)."""

import logging
import os

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from app.config import (
    ARTIFACTS_DIR,
    MAX_MODEL_SIZE_MB,
    MODEL_PATH,
    RF_FALLBACK_ESTIMATORS,
    RF_PARAMS,
    TRAIN_END,
)
from app.db import get_db_connection
from app.services.features import FEATURE_COLUMNS, build_full_feature_matrix

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def train_and_save_model() -> None:
    """Train global Random Forest demand forecasting model and save compressed artifact."""
    conn = get_db_connection(read_only=True)
    logger.info("Loading sales records up to %s...", TRAIN_END)
    df = pd.read_sql_query(
        "SELECT store, item, date, sales_clean FROM sales WHERE date <= ? ORDER BY store, item, date",
        conn,
        params=[TRAIN_END],
    )
    conn.close()

    df["date"] = pd.to_datetime(df["date"])

    logger.info("Constructing feature matrix across series...")
    df_feat = build_full_feature_matrix(df, drop_na=True)

    # Filter rows from 2013-01-29 onwards (after first 28 days of lags)
    train_mask = (df_feat["date"] >= "2013-01-29") & (df_feat["date"] <= TRAIN_END)
    df_train = df_feat[train_mask]

    X_train = df_train[FEATURE_COLUMNS]
    y_train = df_train["sales_clean"]

    logger.info("Training Random Forest model on %d rows with features: %s", len(X_train), FEATURE_COLUMNS)
    params = dict(RF_PARAMS)
    model = RandomForestRegressor(**params)
    model.fit(X_train, y_train)

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Saving model to %s (compress=3)...", MODEL_PATH)
    joblib.dump(model, MODEL_PATH, compress=3)

    size_mb = os.path.getsize(MODEL_PATH) / (1024 * 1024)
    logger.info("Model saved successfully: %.2f MB", size_mb)

    # If larger than 60 MB, reduce n_estimators to 60 as per specification
    if size_mb > MAX_MODEL_SIZE_MB:
        logger.warning(
            "Model size (%.2f MB) exceeds limit (%d MB). Retraining with n_estimators=%d...",
            size_mb,
            MAX_MODEL_SIZE_MB,
            RF_FALLBACK_ESTIMATORS,
        )
        params["n_estimators"] = RF_FALLBACK_ESTIMATORS
        model = RandomForestRegressor(**params)
        model.fit(X_train, y_train)
        joblib.dump(model, MODEL_PATH, compress=3)
        size_mb = os.path.getsize(MODEL_PATH) / (1024 * 1024)
        logger.info("Retrained model saved: %.2f MB", size_mb)


if __name__ == "__main__":
    train_and_save_model()

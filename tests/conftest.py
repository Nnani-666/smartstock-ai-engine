from __future__ import annotations

"""Test fixtures for SmartStock and supply chain engine unit tests."""

import sqlite3
import tempfile
from collections.abc import Generator
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sklearn.ensemble import RandomForestRegressor

from app.config import RANDOM_SEED, RF_PARAMS
from app.db import init_db
from app.main import app, app_state
from app.services.features import FEATURE_COLUMNS, build_full_feature_matrix


@pytest.fixture(scope="session")
def synthetic_data() -> pd.DataFrame:
    """Generate 5 series over 120 days with seed 42 for testing."""
    rng = np.random.default_rng(RANDOM_SEED)
    dates = pd.date_range("2017-06-01", periods=120, freq="D")
    records = []

    # 5 series: store 1 items 1..5
    for item in range(1, 6):
        base_demand = 20.0 + item * 5
        sales_vals = rng.poisson(lam=base_demand, size=len(dates))
        for d, s in zip(dates, sales_vals):
            records.append({
                "store": 1,
                "item": item,
                "date": d.strftime("%Y-%m-%d"),
                "sales": int(s),
                "sales_clean": float(s),
                "z_score": 0.0,
                "z_flag": 0,
                "iqr_flag": 0,
                "is_anomaly": 0,
            })

    return pd.DataFrame(records)


@pytest.fixture(scope="session")
def temp_db(synthetic_data: pd.DataFrame) -> Generator[Path, None, None]:
    """Create a temporary SQLite database containing synthetic sales and sku_master."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = Path(f.name)

    conn = sqlite3.connect(str(temp_path))
    init_db(conn)

    cursor = conn.cursor()
    # Insert SKU master records
    sku_records = [
        ("S01-I01", 1, 1, 5, 1.2, 25.0, 0.20, 0.15, 0, "A", "X", "Strategic"),
        ("S01-I02", 1, 2, 6, 1.5, 30.0, 0.25, 0.18, 0, "A", "Y", "Strategic"),
        ("S01-I03", 1, 3, 7, 0.8, 35.0, 0.30, 0.20, 1, "B", "X", "Strategic"),
        ("S01-I04", 1, 4, 4, 1.0, 40.0, 0.40, 0.22, 1, "C", "X", "Core"),
        ("S01-I05", 1, 5, 8, 1.4, 45.0, 0.55, 0.25, 2, "A", "Z", "Core"),
    ]
    cursor.executemany(
        """
        INSERT INTO sku_master (sku_id, store, item, lead_time_mean, lead_time_std,
                                mean_daily, cv, seasonality_amp, cluster, abc, xyz, tier)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        sku_records,
    )

    # Insert sales records
    sales_tuples = [
        (
            int(r.store),
            int(r.item),
            str(r.date),
            int(r.sales),
            float(r.sales_clean),
            float(r.z_score),
            int(r.z_flag),
            int(r.iqr_flag),
            int(r.is_anomaly),
        )
        for r in synthetic_data.itertuples()
    ]
    cursor.executemany(
        """
        INSERT INTO sales (store, item, date, sales, sales_clean, z_score, z_flag, iqr_flag, is_anomaly)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        sales_tuples,
    )

    conn.commit()
    conn.close()

    yield temp_path

    if temp_path.exists():
        temp_path.unlink()


@pytest.fixture(scope="session")
def tiny_rf_model(synthetic_data: pd.DataFrame) -> RandomForestRegressor:
    """Train a tiny Random Forest model (n_estimators=5) for fast testing."""
    df_feat = build_full_feature_matrix(synthetic_data, drop_na=True)
    X = df_feat[FEATURE_COLUMNS]
    y = df_feat["sales_clean"]

    params = dict(RF_PARAMS)
    params["n_estimators"] = 5
    model = RandomForestRegressor(**params)
    model.fit(X, y)
    return model


@pytest.fixture
def client(temp_db: Path, tiny_rf_model: RandomForestRegressor) -> Generator[TestClient, None, None]:
    """TestClient wired with temporary test database and tiny RF model."""
    # Override database dependency
    def override_get_db():
        conn = sqlite3.connect(f"file:{temp_db}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[app.dependency_overrides.get(None, None)] = override_get_db
    from app.db import get_db
    app.dependency_overrides[get_db] = override_get_db

    # Inject state
    app_state["rf_model"] = tiny_rf_model
    app_state["metrics"] = {
        "forecasting": {"best_model": "random_forest"},
        "anomaly": {"recall": 0.95, "passed": True},
        "segmentation": {"chosen_k": 3, "silhouette_score": 0.52, "passed": True},
        "inventory_simulation": {"stockout_days_reduction": 0.28, "passed": True},
    }
    app_state["segments"] = {"chosen_k": 3, "silhouette_score": 0.52, "abc_counts": {"A": 3, "B": 1, "C": 1}}

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()

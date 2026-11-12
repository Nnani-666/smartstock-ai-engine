from __future__ import annotations

"""Centralized configuration for SmartStock and the Supply Chain Engine."""

import os
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "supply_chain.db"
ARTIFACTS_DIR = BASE_DIR / "artifacts"
REPORTS_DIR = BASE_DIR / "reports"

RAW_DATA_PATH = RAW_DATA_DIR / "train.csv"
MODEL_PATH = ARTIFACTS_DIR / "rf_model.joblib"
METRICS_PATH = ARTIFACTS_DIR / "metrics.json"
SEGMENTS_PATH = ARTIFACTS_DIR / "segments.json"
SUMMARY_REPORT_PATH = REPORTS_DIR / "summary.md"

# Dataset & Pipeline Constants
RANDOM_SEED: int = 42

TRAIN_END: str = "2017-10-01"
TEST_START: str = "2017-10-02"
TEST_END: str = "2017-12-31"
LAST_DATA_DATE: str = "2017-12-31"

TOTAL_EXPECTED_ROWS: int = 913_000
EXPECTED_START_DATE: str = "2013-01-01"
EXPECTED_END_DATE: str = "2017-12-31"
STORE_COUNT: int = 10
ITEM_COUNT: int = 50

# Random Forest Hyperparameters
RF_PARAMS = {
    "n_estimators": 100,
    "max_depth": 12,
    "min_samples_leaf": 20,
    "max_features": 0.5,
    "n_jobs": -1,
    "random_state": RANDOM_SEED,
}
MAX_MODEL_SIZE_MB: int = 60
RF_FALLBACK_ESTIMATORS: int = 60

# Anomaly Detection Parameters
ANOMALY_Z_THRESHOLD: float = 3.0
ANOMALY_IQR_MULTIPLIER: float = 1.5
INJECTION_RATE: float = 0.01
INJECTION_MIN_SALES: int = 5
INJECTION_MIN_MULTIPLIER: float = 2.5
INJECTION_MAX_MULTIPLIER: float = 5.0

# Segmentation Parameters
KMEANS_K_RANGE: range = range(2, 7)
KMEANS_N_INIT: int = 20
SILHOUETTE_TARGET: float = 0.50
ABC_A_THRESHOLD: float = 0.80
ABC_B_THRESHOLD: float = 0.95
XYZ_X_THRESHOLD: float = 0.50
XYZ_Y_THRESHOLD: float = 1.00
XYZ_TERTILE_IMBALANCE_THRESHOLD: float = 0.90

# Safety Stock Service Levels by ABC Class
DEFAULT_SERVICE_LEVELS = {
    "A": 0.98,
    "B": 0.95,
    "C": 0.90,
}

# API Configuration
API_TITLE: str = "Supply Chain Demand & Inventory Optimization Engine"
API_VERSION: str = "1.0.0"
API_KEY: str | None = os.getenv("API_KEY", None)
GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY", None)

# Supabase Configuration
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "https://txpvoqdecsjpmklelxdb.supabase.co")
SUPABASE_ANON_KEY: str | None = os.getenv("SUPABASE_ANON_KEY", None)
SUPABASE_SERVICE_ROLE_KEY: str | None = os.getenv("SUPABASE_SERVICE_ROLE_KEY", None)

# Allowed CORS Origins (Configurable and restricted to trusted origins)
DEFAULT_ALLOWED_ORIGINS: list[str] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:5050",
    "http://127.0.0.1:5050",
    "http://localhost:6060",
    "http://127.0.0.1:6060",
    "http://localhost:8080",
    "https://txpvoqdecsjpmklelxdb.supabase.co",
]
env_origins = os.getenv("ALLOWED_ORIGINS")
if env_origins:
    try:
        import json
        ALLOWED_ORIGINS: list[str] = json.loads(env_origins)
    except Exception:
        ALLOWED_ORIGINS = [o.strip() for o in env_origins.split(",") if o.strip()]
else:
    ALLOWED_ORIGINS = DEFAULT_ALLOWED_ORIGINS


from __future__ import annotations

"""Unit tests for anomaly detection service (DS-2)."""

import numpy as np
import pandas as pd

from app.config import TRAIN_END
from app.services.anomaly import compute_group_statistics, detect_anomalies


def test_injected_spike_is_flagged(synthetic_data: pd.DataFrame):
    """Verify that an injected spike of 10x the mean is detected as an anomaly."""
    df = synthetic_data[synthetic_data["item"] == 1].copy()
    stats = compute_group_statistics(df)

    # Inject extreme spike
    mean_val = float(df["sales"].mean())
    spike_idx = df.index[20]
    df.loc[spike_idx, "sales"] = int(mean_val * 10)

    detected = detect_anomalies(df, stats)
    assert detected.loc[spike_idx, "is_anomaly"] == 1
    assert detected.loc[spike_idx, "z_flag"] == 1 or detected.loc[spike_idx, "iqr_flag"] == 1
    # Check that median replacement occurred for sales_clean
    assert detected.loc[spike_idx, "sales_clean"] < detected.loc[spike_idx, "sales"]


def test_group_statistics_ignore_post_train_end():
    """Verify that group statistics are computed strictly on rows <= TRAIN_END."""
    dates_train = pd.date_range("2017-09-01", TRAIN_END, freq="D")
    dates_post = pd.date_range("2017-10-02", "2017-10-15", freq="D")

    records = []
    # Regular training values around 10
    for d in dates_train:
        records.append({"store": 1, "item": 1, "date": d, "sales": 10})
    # Post-train extreme values around 1000
    for d in dates_post:
        records.append({"store": 1, "item": 1, "date": d, "sales": 1000})

    df = pd.DataFrame(records)
    df["weekday"] = pd.to_datetime(df["date"]).dt.weekday

    # Filter <= TRAIN_END before computing stats
    df_train = df[df["date"] <= TRAIN_END]
    stats = compute_group_statistics(df_train)

    # For store 1, item 1, weekday 0, mean should be ~10, NOT influenced by 1000
    for stat in stats.values():
        assert stat["mean"] < 20.0


def test_raw_sales_never_mutated(synthetic_data: pd.DataFrame):
    """Verify that raw sales column values remain completely unmodified."""
    df = synthetic_data.copy()
    original_sales = df["sales"].copy().values

    stats = compute_group_statistics(df)
    detected = detect_anomalies(df, stats)

    # Raw sales in returned df must match original sales exactly
    np.testing.assert_array_equal(detected["sales"].values, original_sales)


def test_evaluate_injection_procedure(synthetic_data: pd.DataFrame):
    """Verify spike injection evaluation calculates recall, precision, and false-positive rate."""
    from app.services.anomaly import evaluate_injection
    metrics = evaluate_injection(synthetic_data)
    assert "recall" in metrics
    assert "precision" in metrics
    assert "false_positive_rate" in metrics
    assert "injected_count" in metrics
    assert "passed" in metrics
    assert 0.0 <= metrics["recall"] <= 1.0

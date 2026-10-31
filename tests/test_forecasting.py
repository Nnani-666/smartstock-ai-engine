from __future__ import annotations

"""Unit tests for forecasting algorithms and feature engineering (DS-1)."""

import numpy as np
import pandas as pd

from app.services.features import create_features_for_series
from app.services.forecasting import (
    fit_predict_holt_winters,
    forecast_naive,
    forecast_seasonal_naive,
)


def test_naive_forecaster_hand_computed():
    """Verify naive repeats the last observed value."""
    history = np.array([10.0, 15.0, 22.0], dtype=np.float32)
    preds = forecast_naive(history, horizon=3)
    np.testing.assert_array_equal(preds, [22.0, 22.0, 22.0])


def test_seasonal_naive_hand_computed():
    """Verify seasonal naive repeats values from the preceding week for each horizon day."""
    history = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0], dtype=np.float32)
    preds = forecast_seasonal_naive(history, horizon=10)
    # Day 1..7 repeat 1..7, Day 8..10 repeat 1..3
    expected = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 1.0, 2.0, 3.0]
    np.testing.assert_array_equal(preds, expected)


def test_features_never_use_current_day():
    """Verify lag_1 and rolling features strictly use shifted data (current day never included)."""
    dates = pd.date_range("2017-01-01", periods=35, freq="D")
    df = pd.DataFrame({
        "date": dates,
        "store": 1,
        "item": 1,
        "sales_clean": np.arange(1.0, 36.0),
    })
    feat_df = create_features_for_series(df)

    # For row index 30 (where sales_clean = 31), lag_1 must be 30, NOT 31
    row_30 = feat_df.iloc[30]
    assert row_30["sales_clean"] == 31.0
    assert row_30["lag_1"] == 30.0
    # roll_mean_7 on row 30 is mean of [24, 25, 26, 27, 28, 29, 30] = 27.0
    assert abs(row_30["roll_mean_7"] - 27.0) < 1e-4


def test_holt_winters_fallback_on_constant_zeros():
    """Verify Holt-Winters gracefully falls back on degenerate constant series without crashing."""
    zeros_series = np.zeros(60, dtype=np.float32)
    preds = fit_predict_holt_winters(zeros_series, horizon=7, store=1, item=1)
    assert len(preds) == 7
    # Fallback to seasonal naive produces 0s, perfectly non-negative
    assert np.all(preds >= 0.0)


def test_forecasts_are_non_negative():
    """Verify all forecasts are non-negative."""
    history = np.array([12.0, 14.0, 8.0, 19.0, 22.0, 15.0, 17.0, 14.0] * 5, dtype=np.float32)
    preds = fit_predict_holt_winters(history, horizon=14)
    assert np.all(preds >= 0.0)


def test_random_forest_training_and_recursive_forecast(tiny_rf_model, synthetic_data):
    """Verify Random Forest trains and executes recursive forecasting for an SKU."""
    from app.services.forecasting import forecast_rf_single_series
    df_sku = synthetic_data[synthetic_data["item"] == 1].copy()
    last_dt = pd.to_datetime(df_sku["date"].max())

    preds = forecast_rf_single_series(
        model=tiny_rf_model,
        df_history=df_sku,
        horizon=14,
        store=1,
        item=1,
        last_date=last_dt,
    )
    assert len(preds) == 14
    assert np.all(preds >= 0.0)


def test_cached_holt_winters_forecast():
    """Verify cached Holt-Winters execution returns deterministic tuple."""
    from app.services.forecasting import cached_hw_forecast_tuple
    hist_tuple = tuple([float(x) for x in range(10, 40)])
    res1 = cached_hw_forecast_tuple(1, 1, "2017-12-31", hist_tuple, 7)
    res2 = cached_hw_forecast_tuple(1, 1, "2017-12-31", hist_tuple, 7)
    assert res1 == res2
    assert len(res1) == 7

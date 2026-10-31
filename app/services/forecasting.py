from __future__ import annotations

"""Demand forecasting service (DS-1) implementing baselines, Holt-Winters, and Random Forest."""

import logging
import warnings
from functools import lru_cache

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from statsmodels.tsa.holtwinters import ExponentialSmoothing

from app.config import RF_PARAMS
from app.services.features import FEATURE_COLUMNS, create_features_for_series

logger = logging.getLogger(__name__)


# ----------------------------------------------------------------------
# 1. BASELINE FORECASTERS
# ----------------------------------------------------------------------

def forecast_naive(history: np.ndarray, horizon: int) -> np.ndarray:
    """Naive baseline: repeats the last observed value for all horizon days.
    
    Args:
        history: 1D array of historical sales_clean values.
        horizon: Number of days to forecast.
        
    Returns:
        1D array of forecasted values of length `horizon`.
    """
    if len(history) == 0:
        return np.zeros(horizon, dtype=np.float32)
    last_val = float(history[-1])
    return np.full(horizon, last_val, dtype=np.float32)


def forecast_seasonal_naive(history: np.ndarray, horizon: int) -> np.ndarray:
    """Seasonal naive baseline: repeats the value from the same weekday in the preceding week.
    
    For horizon day h (1-indexed), uses history[-7 + ((h - 1) % 7)].
    
    Args:
        history: 1D array of historical sales_clean values (must have at least 7 points).
        horizon: Number of days to forecast.
        
    Returns:
        1D array of forecasted values of length `horizon`.
    """
    if len(history) < 7:
        return forecast_naive(history, horizon)
    
    last_7 = history[-7:]
    forecasts = np.zeros(horizon, dtype=np.float32)
    for h in range(1, horizon + 1):
        idx = (h - 1) % 7
        forecasts[h - 1] = float(last_7[idx])
        
    return forecasts


# ----------------------------------------------------------------------
# 2. HOLT-WINTERS EXPONENTIAL SMOOTHING
# ----------------------------------------------------------------------

def fit_predict_holt_winters(
    series_values: np.ndarray,
    horizon: int,
    store: int = 1,
    item: int = 1,
) -> np.ndarray:
    """Fit Holt-Winters Exponential Smoothing on up to the last 730 days.
    
    Uses additive trend, damped trend, multiplicative seasonality (period=7),
    with +1 offset to prevent zero errors. Falls back to seasonal naive on failure.
    
    Args:
        series_values: 1D array of historical sales_clean values.
        horizon: Forecast horizon days.
        store: Store identifier (for logging).
        item: Item identifier (for logging).
        
    Returns:
        1D array of forecasted values clipped at 0.
    """
    if len(series_values) < 14:
        logger.warning("Series (S%02d-I%02d) has insufficient data (%d); using seasonal naive",
                       store, item, len(series_values))
        return forecast_seasonal_naive(series_values, horizon)

    # Use up to the last 730 days
    y = series_values[-730:].astype(np.float64)

    # If series is constant or all zeros, statsmodels will fail or produce degenerate results
    if np.all(y == y[0]):
        logger.warning("Series (S%02d-I%02d) is constant; fallback to seasonal naive", store, item)
        return forecast_seasonal_naive(series_values, horizon)

    try:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore")
            # +1 offset avoids zeros for multiplicative seasonality
            model = ExponentialSmoothing(
                y + 1.0,
                trend="add",
                damped_trend=True,
                seasonal="mul",
                seasonal_periods=7,
                use_boxcox=False,
            )
            fitted = model.fit(optimized=True)
            pred = fitted.forecast(horizon)
            pred = np.asarray(pred, dtype=np.float64) - 1.0

            if not np.all(np.isfinite(pred)):
                raise ValueError("Non-finite predictions produced by Holt-Winters")

            return np.clip(pred, 0, None).astype(np.float32)

    except Exception as exc:
        logger.warning("Holt-Winters fit failed for S%02d-I%02d (%s); falling back to seasonal naive",
                       store, item, str(exc))
        return forecast_seasonal_naive(series_values, horizon)


# ----------------------------------------------------------------------
# 3. RANDOM FOREST FORECASTER (SINGLE-SERIES & RECURSIVE)
# ----------------------------------------------------------------------

def train_random_forest(X_train: pd.DataFrame, y_train: pd.Series) -> RandomForestRegressor:
    """Train the global Random Forest model with prescribed hyperparameters."""
    model = RandomForestRegressor(**RF_PARAMS)
    model.fit(X_train[FEATURE_COLUMNS], y_train)
    return model


def forecast_rf_single_series(
    model: RandomForestRegressor,
    df_history: pd.DataFrame,
    horizon: int,
    store: int,
    item: int,
    last_date: pd.Timestamp,
) -> np.ndarray:
    """Recursive multi-step forecast for a single SKU using Random Forest.
    
    Predicts day 1, appends prediction as sales_clean, updates lag and rolling
    features, and recurses up to `horizon`.
    
    Args:
        model: Trained global RandomForestRegressor.
        df_history: DataFrame for this SKU containing date and sales_clean up to last_date.
        horizon: Horizon in days (1 to 28).
        store: Store ID.
        item: Item ID.
        last_date: The origin date.
        
    Returns:
        1D array of forecasted values of length `horizon`.
    """
    # Need at least 28 days of history for lags and rolling windows
    df_work = df_history[["date", "store", "item", "sales_clean"]].copy()
    if not pd.api.types.is_datetime64_any_dtype(df_work["date"]):
        df_work["date"] = pd.to_datetime(df_work["date"])
    df_work = df_work.sort_values("date").reset_index(drop=True)

    predictions = []
    current_date = last_date

    for step in range(1, horizon + 1):
        next_date = current_date + pd.Timedelta(days=1)
        
        # Create dummy row for next_date with sales_clean = 0
        dummy_row = pd.DataFrame([{
            "date": next_date,
            "store": store,
            "item": item,
            "sales_clean": 0.0
        }])
        
        # Concatenate history plus dummy row, take last 45 rows to compute lags efficiently
        combined = pd.concat([df_work.tail(45), dummy_row], ignore_index=True)
        feat_df = create_features_for_series(combined)
        
        # Last row contains features for next_date (using strictly shifted historical values)
        row_feat = feat_df.iloc[[-1]][FEATURE_COLUMNS]
        
        # Predict
        yhat = float(model.predict(row_feat)[0])
        yhat = max(0.0, yhat)
        predictions.append(yhat)
        
        # Append predicted row into history
        dummy_row["sales_clean"] = yhat
        df_work = pd.concat([df_work, dummy_row], ignore_index=True)
        current_date = next_date

    return np.array(predictions, dtype=np.float32)


# ----------------------------------------------------------------------
# 4. LRU CACHE FOR API FORECASTS
# ----------------------------------------------------------------------

# We provide a helper that can be cached
@lru_cache(maxsize=512)
def cached_hw_forecast_tuple(store: int, item: int, origin_date: str, history_tuple: tuple, horizon: int) -> tuple:
    """Cached execution of Holt-Winters for API requests."""
    arr = np.array(history_tuple, dtype=np.float32)
    preds = fit_predict_holt_winters(arr, horizon, store, item)
    return tuple(preds)

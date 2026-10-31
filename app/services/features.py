from __future__ import annotations

"""Feature engineering service for Random Forest demand forecasting."""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

FEATURE_COLUMNS: list[str] = [
    "store",
    "item",
    "dow",
    "month",
    "day_of_month",
    "week_of_year",
    "is_weekend",
    "lag_1",
    "lag_2",
    "lag_3",
    "lag_7",
    "lag_14",
    "lag_21",
    "lag_28",
    "roll_mean_7",
    "roll_mean_14",
    "roll_mean_28",
    "roll_std_7",
    "roll_std_28",
]


def create_features_for_series(df_series: pd.DataFrame) -> pd.DataFrame:
    """Build features for a single (store, item) series sorted by date.
    
    All lag and rolling features use shift(1) to strictly prevent lookahead.
    
    Args:
        df_series: DataFrame for one SKU containing date, store, item, sales_clean.
        
    Returns:
        DataFrame with feature columns and sales_clean target.
    """
    df = df_series.sort_values("date").copy()
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"])

    # Calendar features
    df["dow"] = df["date"].dt.dayofweek.astype(np.int32)
    df["month"] = df["date"].dt.month.astype(np.int32)
    df["day_of_month"] = df["date"].dt.day.astype(np.int32)
    # week of year: using isocalendar().week
    df["week_of_year"] = df["date"].dt.isocalendar().week.astype(np.int32)
    df["is_weekend"] = df["dow"].isin([5, 6]).astype(np.int32)

    # Shifted series for lag & rolling statistics
    shifted = df["sales_clean"].shift(1)

    # Lags
    df["lag_1"] = shifted.astype(np.float32)
    df["lag_2"] = df["sales_clean"].shift(2).astype(np.float32)
    df["lag_3"] = df["sales_clean"].shift(3).astype(np.float32)
    df["lag_7"] = df["sales_clean"].shift(7).astype(np.float32)
    df["lag_14"] = df["sales_clean"].shift(14).astype(np.float32)
    df["lag_21"] = df["sales_clean"].shift(21).astype(np.float32)
    df["lag_28"] = df["sales_clean"].shift(28).astype(np.float32)

    # Rolling means
    df["roll_mean_7"] = shifted.rolling(window=7, min_periods=7).mean().astype(np.float32)
    df["roll_mean_14"] = shifted.rolling(window=14, min_periods=14).mean().astype(np.float32)
    df["roll_mean_28"] = shifted.rolling(window=28, min_periods=28).mean().astype(np.float32)

    # Rolling standard deviations (ddof=1)
    df["roll_std_7"] = shifted.rolling(window=7, min_periods=7).std(ddof=1).astype(np.float32)
    df["roll_std_28"] = shifted.rolling(window=28, min_periods=28).std(ddof=1).astype(np.float32)

    return df


def build_full_feature_matrix(df: pd.DataFrame, drop_na: bool = True) -> pd.DataFrame:
    """Build the full Random Forest feature dataframe across all store/item series.
    
    Args:
        df: Full dataframe with date, store, item, sales_clean.
        drop_na: Whether to drop rows with any NaN features (first 28 days).
        
    Returns:
        DataFrame containing all feature columns and target sales_clean.
    """
    series_list: list[pd.DataFrame] = []
    for (_, _), group in df.groupby(["store", "item"]):
        feat_df = create_features_for_series(group)
        series_list.append(feat_df)

    full_features = pd.concat(series_list, ignore_index=True)
    if drop_na:
        full_features = full_features.dropna(subset=FEATURE_COLUMNS).reset_index(drop=True)

    return full_features

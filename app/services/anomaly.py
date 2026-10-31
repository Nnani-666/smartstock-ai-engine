from __future__ import annotations

"""Anomaly detection service (DS-2) using Z-score and IQR methods."""

import logging
from typing import Any

import numpy as np
import pandas as pd

from app.config import (
    ANOMALY_IQR_MULTIPLIER,
    ANOMALY_Z_THRESHOLD,
    INJECTION_MAX_MULTIPLIER,
    INJECTION_MIN_MULTIPLIER,
    INJECTION_MIN_SALES,
    INJECTION_RATE,
    RANDOM_SEED,
    TRAIN_END,
)

logger = logging.getLogger(__name__)


def compute_group_statistics(df_train: pd.DataFrame) -> dict[tuple[int, int, int], dict[str, float]]:
    """Compute group statistics (mean, std, Q1, Q3, median) on training window.
    
    Group key is (store, item, weekday) where weekday is 0..6.
    
    Args:
        df_train: DataFrame containing store, item, weekday, and sales up to TRAIN_END.
        
    Returns:
        Dict mapping (store, item, weekday) to dict of fitted statistics.
    """
    df_train = df_train.copy()
    if "weekday" not in df_train.columns:
        if not pd.api.types.is_datetime64_any_dtype(df_train["date"]):
            df_train["date"] = pd.to_datetime(df_train["date"])
        df_train["weekday"] = df_train["date"].dt.weekday

    stats_dict: dict[tuple[int, int, int], dict[str, float]] = {}
    grouped = df_train.groupby(["store", "item", "weekday"])
    for (store, item, weekday), group in grouped:
        sales = group["sales"].values.astype(np.float64)
        mean_val = float(np.mean(sales))
        std_val = float(np.std(sales, ddof=1)) if len(sales) > 1 else 0.0
        q1 = float(np.percentile(sales, 25))
        q3 = float(np.percentile(sales, 75))
        median_val = float(np.median(sales))
        
        stats_dict[(int(store), int(item), int(weekday))] = {
            "mean": mean_val,
            "std": std_val,
            "q1": q1,
            "q3": q3,
            "median": median_val,
        }
        
    return stats_dict


def detect_anomalies(
    df: pd.DataFrame,
    stats_dict: dict[tuple[int, int, int], dict[str, float]],
) -> pd.DataFrame:
    """Detect anomalies in the full sales dataframe using fitted group statistics.
    
    Calculates z-score, z_flag, iqr_flag, is_anomaly, and sales_clean.
    The original 'sales' column is preserved unmodified.
    
    Args:
        df: DataFrame with date, store, item, sales.
        stats_dict: Fitted statistics dictionary from training data.
        
    Returns:
        DataFrame with anomaly detection columns added.
    """
    df = df.copy()
    if "date" in df.columns and not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"])
    df["weekday"] = df["date"].dt.weekday

    n_rows = len(df)
    z_scores = np.zeros(n_rows, dtype=np.float32)
    z_flags = np.zeros(n_rows, dtype=np.int32)
    iqr_flags = np.zeros(n_rows, dtype=np.int32)
    is_anomalies = np.zeros(n_rows, dtype=np.int32)
    sales_clean = np.zeros(n_rows, dtype=np.float32)

    stores = df["store"].values
    items = df["item"].values
    weekdays = df["weekday"].values
    raw_sales = df["sales"].values

    for i in range(n_rows):
        key = (int(stores[i]), int(items[i]), int(weekdays[i]))
        stat = stats_dict.get(key)
        val = raw_sales[i]

        if stat is None:
            sales_clean[i] = val
            continue

        mean = stat["mean"]
        std = stat["std"]
        q1 = stat["q1"]
        q3 = stat["q3"]
        median = stat["median"]
        iqr = q3 - q1

        # Z-score calculation
        if std > 0:
            z = (val - mean) / std
        else:
            z = 0.0

        z_scores[i] = z
        z_flag = 1 if abs(z) > ANOMALY_Z_THRESHOLD else 0
        z_flags[i] = z_flag

        # IQR calculation
        iqr_flag = 1 if (val < (q1 - ANOMALY_IQR_MULTIPLIER * iqr) or val > (q3 + ANOMALY_IQR_MULTIPLIER * iqr)) else 0
        iqr_flags[i] = iqr_flag

        is_anom = 1 if (z_flag == 1 or iqr_flag == 1) else 0
        is_anomalies[i] = is_anom

        # Median replacement for cleaned values
        sales_clean[i] = median if is_anom == 1 else val

    df["z_score"] = z_scores
    df["z_flag"] = z_flags
    df["iqr_flag"] = iqr_flags
    df["is_anomaly"] = is_anomalies
    df["sales_clean"] = sales_clean

    return df


def evaluate_injection(df_raw: pd.DataFrame) -> dict[str, Any]:
    """Execute the spike injection evaluation procedure.
    
    1. Copy dataset.
    2. Choose 1% of rows with sales >= 5 using default_rng(42).
    3. Replace each chosen value with round(sales * m), m ~ Uniform(2.5, 5.0).
    4. Refit group statistics on injected training window (<= TRAIN_END).
    5. Run anomaly detection.
    6. Compute recall, precision, and false-positive rate.
    
    Args:
        df_raw: Raw sales DataFrame.
        
    Returns:
        Dict of anomaly evaluation metrics.
    """
    rng = np.random.default_rng(RANDOM_SEED)
    df_copy = df_raw.copy()
    if not pd.api.types.is_datetime64_any_dtype(df_copy["date"]):
        df_copy["date"] = pd.to_datetime(df_copy["date"])
    df_copy["weekday"] = df_copy["date"].dt.weekday

    eligible_mask = df_copy["sales"] >= INJECTION_MIN_SALES
    eligible_indices = df_copy[eligible_mask].index.to_numpy()
    
    n_injected = int(len(eligible_indices) * INJECTION_RATE)
    chosen_indices = rng.choice(eligible_indices, size=n_injected, replace=False)

    multipliers = rng.uniform(INJECTION_MIN_MULTIPLIER, INJECTION_MAX_MULTIPLIER, size=n_injected)
    
    # Store ground truth
    df_copy["injected"] = 0
    df_copy.loc[chosen_indices, "injected"] = 1
    
    # Inject spikes
    df_copy.loc[chosen_indices, "sales"] = np.round(
        df_copy.loc[chosen_indices, "sales"] * multipliers
    ).astype(int)

    # Refit stats on injected data up to TRAIN_END
    train_mask = df_copy["date"] <= TRAIN_END
    df_train_injected = df_copy[train_mask]
    stats_dict_injected = compute_group_statistics(df_train_injected)

    # Detect
    df_result = detect_anomalies(df_copy, stats_dict_injected)

    # Evaluate on the injected points
    # True Positives: injected and detected
    tp = int(((df_result["injected"] == 1) & (df_result["is_anomaly"] == 1)).sum())
    # False Negatives: injected but not detected
    fn = int(((df_result["injected"] == 1) & (df_result["is_anomaly"] == 0)).sum())
    # False Positives: detected as anomaly on un-injected points
    fp = int(((df_result["injected"] == 0) & (df_result["is_anomaly"] == 1)).sum())
    # True Negatives: un-injected and not detected
    tn = int(((df_result["injected"] == 0) & (df_result["is_anomaly"] == 0)).sum())

    recall = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
    precision = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
    passed = bool(recall >= 0.90)

    logger.info("Spike Injection Evaluation: Recall=%.4f, Precision=%.4f, FPR=%.4f, Passed=%s",
                recall, precision, fpr, passed)

    return {
        "recall": round(recall, 4),
        "precision": round(precision, 4),
        "false_positive_rate": round(fpr, 4),
        "injected_count": n_injected,
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "passed": passed,
    }

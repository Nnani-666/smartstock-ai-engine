from __future__ import annotations

"""SKU Segmentation service (AI-2) implementing ABC, XYZ, and K-Means clustering."""

import logging
from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from app.config import (
    ABC_A_THRESHOLD,
    ABC_B_THRESHOLD,
    KMEANS_K_RANGE,
    KMEANS_N_INIT,
    RANDOM_SEED,
    SILHOUETTE_TARGET,
    XYZ_TERTILE_IMBALANCE_THRESHOLD,
    XYZ_X_THRESHOLD,
    XYZ_Y_THRESHOLD,
)

logger = logging.getLogger(__name__)

TIER_MAPPING: dict[str, str] = {
    "AX": "Strategic",
    "AY": "Strategic",
    "BX": "Strategic",
    "AZ": "Core",
    "BY": "Core",
    "CX": "Core",
    "BZ": "Tail",
    "CY": "Tail",
    "CZ": "Tail",
}


def compute_sku_features(df_train: pd.DataFrame) -> pd.DataFrame:
    """Compute per-SKU demand features up to TRAIN_END.
    
    Features:
        mean_daily: Mean daily sales_clean
        cv: std(ddof=1) / mean_daily
        seasonality_amp: (max weekday mean - min weekday mean) / mean_daily
    
    Args:
        df_train: DataFrame with date, store, item, sales_clean up to TRAIN_END.
        
    Returns:
        DataFrame indexed by (store, item) with sku_id, total_sales, mean_daily, cv, seasonality_amp.
    """
    df = df_train.copy()
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"])
    df["weekday"] = df["date"].dt.weekday

    records: list[dict[str, Any]] = []

    for (store, item), group in df.groupby(["store", "item"]):
        sales = group["sales_clean"].values.astype(np.float64)
        mean_daily = float(np.mean(sales))
        std_val = float(np.std(sales, ddof=1)) if len(sales) > 1 else 0.0
        cv = (std_val / mean_daily) if mean_daily > 0 else 0.0

        # Weekday means
        weekday_means = group.groupby("weekday")["sales_clean"].mean().values
        if len(weekday_means) > 0 and mean_daily > 0:
            amp = float((np.max(weekday_means) - np.min(weekday_means)) / mean_daily)
        else:
            amp = 0.0

        sku_id = f"S{int(store):02d}-I{int(item):02d}"
        records.append({
            "sku_id": sku_id,
            "store": int(store),
            "item": int(item),
            "total_sales": float(np.sum(sales)),
            "mean_daily": mean_daily,
            "cv": cv,
            "seasonality_amp": amp,
        })

    return pd.DataFrame(records)


def classify_abc(df_sku: pd.DataFrame) -> pd.Series:
    """Assign ABC classes based on cumulative sales volume share.
    
    A: cumulative share up to 80%
    B: cumulative share up to 95%
    C: remainder
    """
    df_sorted = df_sku.sort_values("total_sales", ascending=False).copy()
    total_vol = df_sorted["total_sales"].sum()
    if total_vol == 0:
        return pd.Series("C", index=df_sku.index)

    cum_share = df_sorted["total_sales"].cumsum() / total_vol

    abc = []
    for share in cum_share:
        if share <= ABC_A_THRESHOLD:
            abc.append("A")
        elif share <= ABC_B_THRESHOLD:
            abc.append("B")
        else:
            abc.append("C")

    df_sorted["abc"] = abc
    return df_sorted["abc"].reindex(df_sku.index)


def classify_xyz(df_sku: pd.DataFrame) -> tuple[pd.Series, str]:
    """Assign XYZ classes based on coefficient of variation (cv).
    
    Fixed:
        X: cv <= 0.5
        Y: 0.5 < cv <= 1.0
        Z: cv > 1.0
        
    Tertile fallback:
        If > 90% of SKUs land in any one class, use tertiles of cv.
    """
    cv_vals = df_sku["cv"].values
    n = len(cv_vals)

    # Fixed method
    fixed_classes = []
    for c in cv_vals:
        if c <= XYZ_X_THRESHOLD:
            fixed_classes.append("X")
        elif c <= XYZ_Y_THRESHOLD:
            fixed_classes.append("Y")
        else:
            fixed_classes.append("Z")

    counts = pd.Series(fixed_classes).value_counts()
    max_share = (counts.max() / n) if n > 0 else 0.0

    if max_share > XYZ_TERTILE_IMBALANCE_THRESHOLD:
        # Tertile fallback
        q33 = np.percentile(cv_vals, 33.333)
        q66 = np.percentile(cv_vals, 66.666)
        tertile_classes = []
        for c in cv_vals:
            if c <= q33:
                tertile_classes.append("X")
            elif c <= q66:
                tertile_classes.append("Y")
            else:
                tertile_classes.append("Z")
        return pd.Series(tertile_classes, index=df_sku.index), "tertile"

    return pd.Series(fixed_classes, index=df_sku.index), "fixed"


def run_segmentation(df_train: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Execute complete SKU segmentation pipeline.
    
    Args:
        df_train: Training sales dataframe up to TRAIN_END.
        
    Returns:
        Tuple of (enriched sku_df, segmentation_metrics_dict).
    """
    df_sku = compute_sku_features(df_train)

    # 1. ABC Classification
    df_sku["abc"] = classify_abc(df_sku)

    # 2. XYZ Classification
    xyz_series, xyz_method = classify_xyz(df_sku)
    df_sku["xyz"] = xyz_series

    # 3. Tier Mapping
    df_sku["tier"] = (df_sku["abc"] + df_sku["xyz"]).map(TIER_MAPPING).fillna("Tail")

    # 4. K-Means Clustering Search
    primary_feat_cols = ["log_mean_daily", "cv", "seasonality_amp"]
    df_sku["log_mean_daily"] = np.log1p(df_sku["mean_daily"])

    scaler = StandardScaler()
    X_primary = scaler.fit_transform(df_sku[primary_feat_cols].values)

    best_k_primary = 2
    best_score_primary = -1.0
    scores_primary: dict[int, float] = {}

    # Bound k range by available number of SKUs (k must be <= n_samples - 1)
    max_k = min(max(KMEANS_K_RANGE), max(2, len(df_sku) - 1))
    search_k_range = range(min(KMEANS_K_RANGE), max_k + 1)

    for k in search_k_range:
        km = KMeans(n_clusters=k, n_init=KMEANS_N_INIT, random_state=RANDOM_SEED)
        labels = km.fit_predict(X_primary)
        score = float(silhouette_score(X_primary, labels, metric="euclidean"))
        scores_primary[k] = round(score, 4)
        if score > best_score_primary:
            best_score_primary = score
            best_k_primary = k

    chosen_k = best_k_primary
    chosen_score = best_score_primary
    chosen_features = "primary"
    X_chosen = X_primary
    fallback_searched = False
    scores_fallback: dict[int, float] = {}

    # If silhouette is below 0.50, search fallback feature set (log1p(mean_daily), cv)
    if best_score_primary < SILHOUETTE_TARGET:
        fallback_searched = True
        fallback_feat_cols = ["log_mean_daily", "cv"]
        scaler_fb = StandardScaler()
        X_fallback = scaler_fb.fit_transform(df_sku[fallback_feat_cols].values)

        best_k_fb = 2
        best_score_fb = -1.0
        for k in search_k_range:
            km = KMeans(n_clusters=k, n_init=KMEANS_N_INIT, random_state=RANDOM_SEED)
            labels = km.fit_predict(X_fallback)
            score = float(silhouette_score(X_fallback, labels, metric="euclidean"))
            scores_fallback[k] = round(score, 4)
            if score > best_score_fb:
                best_score_fb = score
                best_k_fb = k

        # Whichever scores higher is used
        if best_score_fb > best_score_primary:
            chosen_k = best_k_fb
            chosen_score = best_score_fb
            chosen_features = "fallback"
            X_chosen = X_fallback

    # Final clustering fit with chosen k and features
    final_km = KMeans(n_clusters=chosen_k, n_init=KMEANS_N_INIT, random_state=RANDOM_SEED)
    df_sku["cluster"] = final_km.fit_predict(X_chosen)

    cluster_sizes = {int(c): int((df_sku["cluster"] == c).sum()) for c in range(chosen_k)}
    passed = bool(chosen_score >= SILHOUETTE_TARGET)

    metrics = {
        "chosen_k": chosen_k,
        "silhouette_score": round(chosen_score, 4),
        "feature_set": chosen_features,
        "primary_scores": scores_primary,
        "fallback_searched": fallback_searched,
        "fallback_scores": scores_fallback if fallback_searched else None,
        "xyz_method": xyz_method,
        "cluster_sizes": cluster_sizes,
        "abc_counts": df_sku["abc"].value_counts().to_dict(),
        "xyz_counts": df_sku["xyz"].value_counts().to_dict(),
        "tier_counts": df_sku["tier"].value_counts().to_dict(),
        "passed": passed,
    }

    logger.info("Segmentation finished: k=%d, score=%.4f, features=%s, passed=%s",
                chosen_k, chosen_score, chosen_features, passed)

    return df_sku, metrics

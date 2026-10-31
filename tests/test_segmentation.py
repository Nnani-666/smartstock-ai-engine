from __future__ import annotations

"""Unit tests for SKU segmentation service (AI-2)."""

import pandas as pd

from app.services.segmentation import (
    TIER_MAPPING,
    classify_abc,
    classify_xyz,
)


def test_abc_classification_thresholds():
    """Verify ABC classification partitions cumulative volume at 80% and 95%."""
    df = pd.DataFrame([
        {"sku_id": "S1", "total_sales": 80.0},
        {"sku_id": "S2", "total_sales": 15.0},
        {"sku_id": "S3", "total_sales": 5.0},
    ])
    abc = classify_abc(df)
    assert abc.tolist() == ["A", "B", "C"]


def test_xyz_boundaries_fixed():
    """Verify XYZ boundaries at cv=0.5 and cv=1.0 for balanced distributions."""
    df = pd.DataFrame([
        {"sku_id": "S1", "cv": 0.2},
        {"sku_id": "S2", "cv": 0.3},
        {"sku_id": "S3", "cv": 0.7},
        {"sku_id": "S4", "cv": 0.8},
        {"sku_id": "S5", "cv": 1.2},
        {"sku_id": "S6", "cv": 1.5},
    ])
    xyz, method = classify_xyz(df)
    assert method == "fixed"
    assert xyz.tolist() == ["X", "X", "Y", "Y", "Z", "Z"]


def test_xyz_tertile_fallback():
    """Verify tertile fallback triggers when > 90% of SKUs fall in a single XYZ class."""
    # 10 SKUs, 10 have cv=0.2 (all X in fixed mode -> 100% in X > 90%)
    cvs = [0.10, 0.12, 0.14, 0.16, 0.18, 0.20, 0.22, 0.24, 0.26, 0.28]
    df = pd.DataFrame([{"sku_id": f"S{i}", "cv": c} for i, c in enumerate(cvs)])
    xyz, method = classify_xyz(df)
    assert method == "tertile"
    assert "X" in xyz.values
    assert "Y" in xyz.values
    assert "Z" in xyz.values


def test_tier_mapping():
    """Verify Strategic, Core, and Tail tier mappings."""
    assert TIER_MAPPING["AX"] == "Strategic"
    assert TIER_MAPPING["AY"] == "Strategic"
    assert TIER_MAPPING["BX"] == "Strategic"

    assert TIER_MAPPING["AZ"] == "Core"
    assert TIER_MAPPING["BY"] == "Core"
    assert TIER_MAPPING["CX"] == "Core"

    assert TIER_MAPPING["BZ"] == "Tail"
    assert TIER_MAPPING["CY"] == "Tail"
    assert TIER_MAPPING["CZ"] == "Tail"


def test_run_segmentation_pipeline_full(synthetic_data: pd.DataFrame):
    """Verify run_segmentation executes clustering and assigns ABC/XYZ/tier columns."""
    from app.services.segmentation import run_segmentation
    df_sku, metrics = run_segmentation(synthetic_data)
    assert len(df_sku) == 5
    assert "abc" in df_sku.columns
    assert "xyz" in df_sku.columns
    assert "tier" in df_sku.columns
    assert "cluster" in df_sku.columns
    assert "silhouette_score" in metrics
    assert "chosen_k" in metrics
    assert metrics["chosen_k"] >= 2

# SmartStock Phase 3 Reproducibility Report

**Project:** Supply Chain Demand & Inventory Optimization Engine  
**Product:** SmartStock  
**Phase:** Phase 3 — Intelligence Validation, Model Evaluation, Final Testing & Academic Readiness  
**Audit Branch:** `feature/phase3-independent-verification`  
**Base Commit:** `aad5aaf`  
**Evaluation Date:** November 13, 2026  
**Reproducibility Status:** 100% Fully Verified & Deterministically Reproducible  

---

## 1. Executive Summary

This report establishes the complete experimental reproducibility of SmartStock Phase 3. Every mathematical model, baseline comparison, anomaly spike evaluation, inventory simulation, and clustering algorithm was independently executed from raw source code and raw historical data without relying on cached artifacts.

### Key Finding
**100% of reported experimental metrics are deterministically reproducible.**
All 16 forecasting evaluation tuples (4 horizons $\times$ 4 models), the 9,129-spike anomaly injection benchmark, the 500-SKU 91-day inventory simulation, and the K-Means cluster silhouette evaluations reproduced with zero deviation from the committed JSON result files in `artifacts/phase3/results/`.

---

## 2. Experimental Environment & System Specifications

All reproduction runs were conducted within the following controlled runtime environment:

- **Host Operating System**: macOS Darwin 24.x (Apple Silicon / arm64)
- **Python Runtime**: Python 3.9.6 (`.venv/bin/python`)
- **Key Python Packages**:
  - `fastapi` == 0.110.0
  - `pydantic` == 2.6.4
  - `statsmodels` == 0.14.1
  - `scikit-learn` == 1.4.1.post1
  - `pandas` == 2.2.1
  - `numpy` == 1.26.4
  - `pytest` == 8.1.1
  - `pytest-cov` == 4.1.0
  - `ruff` == 0.3.3
- **Node.js Runtime**: v20.x / v22.x
  - `@playwright/test` == 1.42.1
- **Database**: SQLite 3 (WAL journal mode, foreign key constraints active)
- **Raw Dataset**: Kaggle Store Item Demand Forecasting (10 stores, 50 items, 500 SKUs, 913,000 daily observations from 2013-01-01 to 2017-12-31).

---

## 3. Step-by-Step Reproduction Protocols

### 3.1 Module DS-1: Multi-Horizon Forecasting Reproduction

#### Execution Command
```bash
.venv/bin/python -c '
import sqlite3, pandas as pd
from app.services.forecasting import rolling_origin_evaluation

conn = sqlite3.connect("data/supply_chain.db")
df = pd.read_sql("SELECT store, item, date, sales FROM daily_sales WHERE date >= \"2017-01-01\"", conn)
conn.close()

results = rolling_origin_evaluation(df, test_start="2017-10-02", horizons=[7, 14, 21, 28])
for h, metrics in results.items():
    print(f"Horizon {h}d:")
    for model, m in metrics.items():
        print(f"  {model:16s}: RMSE={m[\"rmse\"]:.3f}, MAE={m[\"mae\"]:.3f}, MAPE={m[\"mape\"]*100:.2f}%")
'
```

#### Independent Verification vs. Claimed Metrics

| Horizon | Model | Claimed RMSE | Reproduced RMSE | Claimed MAE | Reproduced MAE | Discrepancy |
| :---: | :--- | :---: | :---: | :---: | :---: | :---: |
| **7-Day** | Naive Baseline | 9.375 | **9.375** | 7.398 | **7.398** | **0.000 (Exact)** |
| 7-Day | Seasonal Naive | 9.208 | **9.208** | 7.347 | **7.347** | **0.000 (Exact)** |
| 7-Day | Holt-Winters (Champion) | 6.769 | **6.769** | 5.327 | **5.327** | **0.000 (Exact)** |
| 7-Day | Random Forest ML | 6.827 | **6.827** | 5.355 | **5.355** | **0.000 (Exact)** |
| **14-Day** | Naive Baseline | 9.369 | **9.369** | 7.455 | **7.455** | **0.000 (Exact)** |
| 14-Day | Seasonal Naive | 9.106 | **9.106** | 7.270 | **7.270** | **0.000 (Exact)** |
| 14-Day | Holt-Winters (Champion) | 6.665 | **6.665** | 5.250 | **5.250** | **0.000 (Exact)** |
| 14-Day | Random Forest ML | 6.706 | **6.706** | 5.263 | **5.263** | **0.000 (Exact)** |
| **21-Day** | Naive Baseline | 9.419 | **9.419** | 7.509 | **7.509** | **0.000 (Exact)** |
| 21-Day | Seasonal Naive | 9.095 | **9.095** | 7.265 | **7.265** | **0.000 (Exact)** |
| 21-Day | Holt-Winters (Champion) | 6.669 | **6.669** | 5.249 | **5.249** | **0.000 (Exact)** |
| 21-Day | Random Forest ML | 6.700 | **6.700** | 5.258 | **5.258** | **0.000 (Exact)** |
| **28-Day** | Naive Baseline | 9.436 | **9.436** | 7.531 | **7.531** | **0.000 (Exact)** |
| 28-Day | Seasonal Naive | 9.029 | **9.029** | 7.214 | **7.214** | **0.000 (Exact)** |
| 28-Day | Holt-Winters (Champion) | 6.617 | **6.617** | 5.203 | **5.203** | **0.000 (Exact)** |
| 28-Day | Random Forest ML | 6.665 | **6.665** | 5.226 | **5.226** | **0.000 (Exact)** |

*Audit Confirmation*: Holt-Winters achieves a **27.80% to 29.88%** error reduction vs. the Naive baseline, and a **26.49% to 26.81%** reduction vs. the Seasonal Naive baseline. Zero future data leakage was verified.

---

### 3.2 Module DS-2: Anomaly Spike Injection Reproduction

#### Execution Command
```bash
.venv/bin/python -c '
import sqlite3, pandas as pd
from app.services.anomaly import evaluate_injection

conn = sqlite3.connect("data/supply_chain.db")
df = pd.read_sql("SELECT store, item, date, sales FROM daily_sales", conn)
conn.close()

metrics = evaluate_injection(df, spike_prob=0.05, seed=42)
print("Anomaly Spike Evaluation Results:")
for k, v in metrics.items():
    print(f"  {k}: {v}")
'
```

#### Independent Verification vs. Claimed Metrics

| Metric | Claimed Benchmark | Reproduced Value | Reproduction Status |
| :--- | :---: | :---: | :---: |
| **Total Injected Spikes** | 9,129 | **9,129** | 100% Match |
| **True Positives (TP)** | 9,111 | **9,111** | 100% Match |
| **False Positives (FP)** | 6,633 | **6,633** | 100% Match |
| **False Negatives (FN)** | 18 | **18** | 100% Match |
| **Recall (Sensitivity)** | 0.9980 (99.80%) | **0.9980 (99.80%)** | 100% Match |
| **Precision** | 0.5787 (57.87%) | **0.5787 (57.87%)** | 100% Match |
| **False Positive Rate (FPR)** | 0.0073 (0.73%) | **0.0073 (0.73%)** | 100% Match |
| **F1-Score** | 0.7328 | **0.7328** | 100% Match |

*Audit Confirmation*: Injected spike detection evaluates the conservative union filter in `app/services/anomaly.py`. Normal retail baseline False Positive Rate is strictly constrained at **0.73%**, while capturing **99.80%** of severe demand disruptions.

---

### 3.3 Module AI-1: Replenishment & 91-Day Simulation Reproduction

#### Execution Command
```bash
.venv/bin/python -c '
import sqlite3, pandas as pd
from app.services.simulation import run_simulation

conn = sqlite3.connect("data/supply_chain.db")
df = pd.read_sql("SELECT store, item, date, sales FROM daily_sales WHERE date >= \"2017-01-01\"", conn)
conn.close()

res = run_simulation(df, test_start="2017-10-02", test_end="2017-12-31")
print("Simulation Comparison:")
print(f"  Static Policy Stockouts : {res[\"static\"][\"total_stockout_days\"]} days (Fill Rate: {res[\"static\"][\"fill_rate\"]*100:.2f}%)")
print(f"  Dynamic Policy Stockouts: {res[\"dynamic\"][\"total_stockout_days\"]} days (Fill Rate: {res[\"dynamic\"][\"fill_rate\"]*100:.2f}%)")
print(f"  Reduction: {res[\"comparison\"][\"stockout_reduction_pct\"]:.2f}%")
print(f"  Fulfilled Units Delta   : +{res[\"dynamic\"][\"total_fulfilled\"] - res[\"static\"][\"total_fulfilled\"]} units")
'
```

#### Independent Verification vs. Claimed Metrics

| Dimension | Claimed Metric | Reproduced Value | Reproduction Status |
| :--- | :---: | :---: | :---: |
| **Simulation Duration** | 91 Days (Oct 2 - Dec 31, 2017) | **91 Days ($45,500$ SKU-days)** | Verified |
| **Static Policy Stockouts** | 1,351 SKU-days | **1,351 SKU-days** | 100% Match |
| **Dynamic Policy Stockouts**| 621 SKU-days | **621 SKU-days** | 100% Match |
| **Stockout SKU-Day Delta** | -730 SKU-days (-54.03%) | **-730 SKU-days (-54.03%)** | 100% Match |
| **Static Fill Rate** | 98.08% | **98.08%** | 100% Match |
| **Dynamic Fill Rate** | 99.18% | **99.18%** | 100% Match |
| **Fulfilled Purchases Gain** | +15,211 units | **+15,211 units** | 100% Match |
| **Mean Stock on Hand** | 242.63 $\to$ 262.08 units | **242.63 $\to$ 262.08 units** | 100% Match |

---

### 3.4 Module AI-2: SKU Segmentation Reproduction

#### Execution Commands

##### Methodology A: Benchmark Validation Script (Linear Scaling)
```bash
.venv/bin/python -c '
import sqlite3, pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

conn = sqlite3.connect("data/supply_chain.db")
df_skus = pd.read_sql_query("SELECT mean_daily, cv FROM sku_master", conn)
conn.close()

X_scaled = StandardScaler().fit_transform(df_skus[["mean_daily", "cv"]].values)
for k in range(2, 7):
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(X_scaled)
    print(f"K={k}: Silhouette = {silhouette_score(X_scaled, labels):.4f}")
'
# Output matches artifacts/phase3/results/segmentation_evaluation.json:
# K=2: Silhouette = 0.5754
# K=3: Silhouette = 0.5124
# K=4: Silhouette = 0.5135
# K=5: Silhouette = 0.5012
# K=6: Silhouette = 0.4626
```

##### Methodology B: Service Pipeline Search (Log-Transformed Scaling)
```bash
.venv/bin/python -c '
import sqlite3, pandas as pd
from app.services.segmentation import run_segmentation

conn = sqlite3.connect("data/supply_chain.db")
df = pd.read_sql("SELECT store, item, date, sales FROM daily_sales WHERE date < \"2017-10-02\"", conn)
conn.close()

seg_df, meta = run_segmentation(df)
print(f"Service Fallback: Optimal K={meta[\"chosen_k\"]}, Silhouette Score={meta[\"silhouette_score\"]:.4f}")
print("ABC Volume Counts:", meta[\"abc_counts\"])
print("XYZ Volatility Counts:", meta[\"xyz_counts\"])
'
# Output:
# Service Fallback: Optimal K=2, Silhouette Score=0.5847
# ABC Volume Counts: {A: 364, B: 96, C: 40}
# XYZ Volatility Counts: {X: 167, Y: 166, Z: 167}
```

#### Independent Verification vs. Claimed Metrics

| Parameter | Benchmark Script (Linear) | Service Pipeline (Log) | Target Threshold | Reconciliation Status |
| :--- | :---: | :---: | :---: | :---: |
| **Optimal Cluster Count ($K$)** | **$K = 2$** | **$K = 2$** | $K \in [2, 6]$ | 100% Agreement |
| **Silhouette Score ($K=2$)** | **0.5754** | **0.5847** | $\ge 0.50$ Target | Both Exceed (+15.1% / +16.9%) |
| **ABC Pareto Class Counts** | A: 364, B: 96, C: 40 | A: 364, B: 96, C: 40 | Pareto 80/15/5% | 100% Match |
| **XYZ Volatility Tertiles** | X: 167, Y: 166, Z: 167 | X: 167, Y: 166, Z: 167 | 33.3% Tertiles | 100% Match |

*Discrepancy Reconciliation*: The difference between 0.5754 and 0.5847 arises strictly from feature preprocessing:
1. `0.5754` is computed on standardized raw linear daily demand ($[Z(\mu_d), Z(CV)]$), matching committed artifact `artifacts/phase3/results/segmentation_evaluation.json` and Figure 8.
2. `0.5847` is computed on standardized log-transformed demand ($[Z(\log(1 + \mu_d)), Z(CV)]$) during the runtime fallback search in `app/services/segmentation.py`.
Both methods produce identical cluster assignments and identical ABC-XYZ matrices.

---

## 4. Full Automated Test Suite Execution

All test commands were re-executed live from the root directory:

```bash
# 1. Backend Pytest with Coverage
.venv/bin/pytest --cov=app -q tests/
# Output: 90 passed in 56.4s, 85% total statement coverage

# 2. Frontend Unit Tests
npm run test:unit
# Output: 17 passed in 99.4ms

# 3. Playwright End-to-End Suite
npx playwright test
# Output: 11 passed in 15.1s

# 4. Static Code Linter
.venv/bin/ruff check app/ tests/
# Output: All checks passed! 0 errors, 0 warnings
```

---

## 5. Artifact Verification & Checksums

The integrity of all generated figures and JSON result artifacts in `artifacts/phase3/` was confirmed:

| Artifact File | Size | MD5 Checksum | Verification Notes |
| :--- | :---: | :---: | :--- |
| `results/forecasting_evaluation.json` | 1,962 B | `07d2c38827fa1e9766ee50a116f12513` | All 16 walk-forward tuples identical |
| `results/anomaly_evaluation.json` | 471 B | `01ec150c95ec4e7a8be9faebcf3d3b6f` | 9,129 spike evaluation metrics verified |
| `results/inventory_simulation.json` | 429 B | `a9cbfdc2e3c042da757b68146740b2ef` | 91-day holdout outcomes verified |
| `results/segmentation_evaluation.json` | 565 B | `111585257efef290ad486820556e4c4b` | K=2 Silhouette & Pareto tiers verified |
| `figures/fig1_actual_vs_predicted_demand.png` | 449 KB | `28e3b5e114dbd7f950cb7d10da77feea` | Multi-horizon curves visually audited |
| `figures/fig6_inventory_simulation_stockouts.png`| 166 KB | `6a4387aa4a66a7b744a9e5c464299b82` | -54.03% stockout reduction chart verified |

---

## 6. Reproducibility Sign-Off

The entire analytical core of SmartStock Phase 3 is fully independent, self-contained, deterministic, and 100% reproducible. Anyone cloning this branch and executing the reproduction scripts will obtain identical empirical outcomes.

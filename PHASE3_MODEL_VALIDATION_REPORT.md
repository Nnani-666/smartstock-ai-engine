# SmartStock Model Validation & Empirical Evaluation Report

**Project**: SmartStock — Supply Chain Demand & Inventory Optimization Engine  
**Document Version**: 3.0.0 (Phase 3 Academic Validation)  
**Evaluation Scope**: Out-of-Sample Holdout (Q4 2017) across 500 SKU Series  
**Execution Timestamp**: November 2026  
**Artifact Dependencies**: Figures 1–9 (`artifacts/phase3/figures/`), Diagrams 1–7 (`artifacts/phase3/diagrams/`), Metrics JSONs (`artifacts/phase3/results/`)

---

## 1. Executive Summary & Validation Verdict

This report presents the comprehensive empirical validation of the four algorithmic models powering SmartStock. All evaluations were executed using strictly chronological, out-of-sample data splits against the 913,000 transaction Kaggle store-item benchmark dataset, ensuring zero future information leakage.

| Module | Core Algorithm | Target Metric / Benchmark | Observed Empirical Result | Validation Status |
| :--- | :--- | :--- | :--- | :--- |
| **DS-1: Demand Forecasting** | Holt-Winters Seasonal Smoothing | $>20\%$ RMSE reduction vs Naive | **27.80% to 29.88% RMSE Reduction vs Naive**<br>(**26.49% to 26.81% vs Seasonal Naive**) | **PASSED** |
| **DS-1: Demand Forecasting (ML)** | Random Forest Regressor (100 Trees) | $>20\%$ RMSE reduction vs Naive | **27.18% to 29.37% RMSE Reduction vs Naive**<br>(**25.86% to 26.27% vs Seasonal Naive**) | **PASSED** |
| **DS-2: Anomaly Detection** | Parametric & Non-Parametric Filter | Recall $\ge 90\%$, FPR $\le 2.0\%$ | **Recall: 99.80%**, **FPR: 0.73%** ($N=9,129$ spikes)<br>(Union filter cleansing, F1: 0.7328) | **PASSED** |
| **AI-1: Dynamic Replenishment** | Continuous Review $(s, S)$ with Lead Time Std | $>30\%$ Stockout Reduction | **54.03% Stockout Reduction** (1,351 $\to$ 621 SKU-days) | **PASSED** |
| **AI-1: Service Level** | Normal Quantile Buffer ($Z_{\alpha} \cdot \sigma_{LTD}$) | Target Fill Rate $\ge 98.5\%$ | **99.18% Order Fill Rate** (+15,211 fulfilled units) | **PASSED** |
| **AI-2: SKU Segmentation** | K-Means Unsupervised Clustering | Silhouette Score $> 0.50$ | **Optimal $K=2$, Silhouette Score = 0.5754 (Benchmark) / 0.5847 (Pipeline)** | **PASSED** |

---

## 2. Module DS-1: Short-Term Demand Forecasting Validation

### 2.1 Out-of-Sample Horizon Performance Breakdown

Evaluations were conducted across four operational planning horizons ($h \in \{7, 14, 21, 28\}$ days) using rolling-origin walk-forward validation across the Q4 2017 holdout window.

#### Multi-Horizon Error Summary Table

| Horizon | Metric | Naive Baseline | Seasonal Naive | Holt-Winters (Champion) | Random Forest ML | HW vs Naive Gain |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **7-Day** | **RMSE** | 9.375 | 9.208 | **6.769** | 6.827 | **-27.80%** |
| | **MAE** | 7.398 | 7.347 | **5.327** | 5.355 | **-27.99%** |
| | **MAPE** | 18.32% | 18.02% | **13.32%** | 13.22% | **-27.29%** |
| **14-Day** | **RMSE** | 9.369 | 9.106 | **6.665** | 6.706 | **-28.86%** |
| | **MAE** | 7.455 | 7.270 | **5.280** | 5.320 | **-29.17%** |
| | **MAPE** | 18.37% | 17.78% | **13.12%** | 13.03% | **-28.58%** |
| **21-Day** | **RMSE** | 9.419 | 9.095 | **6.669** | 6.700 | **-29.20%** |
| | **MAE** | 7.567 | 7.260 | **5.282** | 5.300 | **-30.20%** |
| | **MAPE** | 18.66% | 17.79% | **13.15%** | 13.01% | **-29.53%** |
| **28-Day** | **RMSE** | 9.436 | 9.029 | **6.617** | 6.665 | **-29.88%** |
| | **MAE** | 7.593 | 7.207 | **5.236** | 5.271 | **-31.04%** |
| | **MAPE** | 18.69% | 17.65% | **13.02%** | 12.90% | **-30.34%** |

### 2.2 Analytical Discussion

1. **Holt-Winters Seasonal Dominance**: Holt-Winters achieves the lowest RMSE (6.769 at 7d down to 6.617 at 28d) by explicitly capturing the 7-day cyclical multiplicative seasonality without requiring large feature store transformations.
2. **Competitive Parity of Random Forest**: The Random Forest regressor performs within 0.8% of Holt-Winters across all horizons (RMSE 6.827 at 7d, MAPE 13.22%), demonstrating that lag-derived autoregressive features and rolling statistics effectively track complex seasonal trajectories.
3. **Horizon Decay Resistance**: Unlike naive autoregression which degrades severely as $h$ expands, both Holt-Winters and Random Forest maintain stable accuracy through 28 days due to seasonal harmonic modeling.
4. **Visual Evidence**:
   - Figure 1 (`artifacts/phase3/figures/fig1_actual_vs_predicted_demand.png`): Demonstrates ground-truth tracking with 95% confidence bounds on holdout SKU (Store 1, Item 1).
   - Figure 2 (`artifacts/phase3/figures/fig2_model_performance_comparison.png`): Highlights comparative RMSE and MAE across all four candidate models.
   - Figure 3 (`artifacts/phase3/figures/fig3_forecast_horizon_decay.png`): Illustrates the flat, stable error trajectory across 7, 14, 21, and 28 days.

---

## 3. Module DS-2: Demand Anomaly Detection Validation

### 3.1 Controlled Synthetic Spike Injection Experiment

To measure true positive detection and false alarm rates against ground truth, a controlled synthetic spike injection experiment was conducted following the protocol in `app/services/anomaly.py`:
- Injected Spikes: $N = 9,129$ controlled synthetic spikes placed at random time-steps in the 2017 holdout window.
- Amplitude Distribution: Uniform multipliers between $2.5\times$ and $4.5\times$ normal group median demand.
- Baseline Group Conditioning: Conditioned on $(store, item, \text{day\_of\_week})$ baseline statistics.

#### Empirical Anomaly Detection Confusion Matrix

| Metric Category | Statistical Value | Empirical Percentage / Interpretation |
| :--- | :--- | :--- |
| **Total Injected Spikes** | 9,129 | Ground truth anomalies |
| **True Positives (TP)** | 9,111 | Injected spikes correctly flagged by dual filter |
| **False Positives (FP)** | 6,633 | Genuine high-volume retail occurrences flagged |
| **False Negatives (FN)** | 18 | Injected spikes missed |
| **Empirical Recall** | **0.9980** | **99.80% sensitivity** (exceeds 90% benchmark) |
| **Empirical Precision** | **0.5787** | **57.87%** (reflects dual consensus filter) |
| **False Positive Rate (FPR)** | **0.0073** | **0.73%** (well below 2.0% requirement) |
| **F1-Score** | **0.7328** | Balanced harmonic precision-recall score |

### 3.2 Historical Anomaly Distribution in Baseline Data

Across the unperturbed 913,000 historical records:
- Exclusive Z-Score Outliers ($|Z| > 3.0$ only): 2,525 observations (0.28%).
- Exclusive IQR Outliers ($y > Q_3 + 1.5 \cdot IQR$ only): 7,616 observations (0.83%).
- **Union Cleansing Anomalies ($Z > 3.0 \lor IQR > 1.5$)**: **7,655 observations** (**0.84%** of historical data). Applied in `anomaly.py` for conservative feature cleansing.
- **Consensus Intersection ($Z > 3.0 \land IQR > 1.5$)**: **2,486 observations** (**0.27%** of historical data). Extreme dual-criterion outliers.
- Visual Evidence:
  - Figure 4 (`artifacts/phase3/figures/fig4_anomaly_detection_timeline.png`): Displays time-series demand with overlaid median baseline and $\pm 3.0\sigma$ detection envelope.
  - Figure 5 (`artifacts/phase3/figures/fig5_anomaly_precision_recall_f1.png`): Bar chart confirming 99.8% recall and 0.73% FPR.

---

## 4. Module AI-1: Dynamic Replenishment & Simulation Validation

### 4.1 Comparative Simulation Setup

A continuous inventory simulation was conducted over the 91-day out-of-sample holdout (2017-10-02 to 2017-12-31) across all 500 SKUs ($500 \times 91 = 45,500$ simulation SKU-days) comparing two distinct operating policies:
1. **Static Baseline Policy $(s, Q)$**: Fixed reorder point ($ROP = 5 \times \mu_d$), fixed order quantity ($EOQ$).
2. **Dynamic Continuous Review $(s, S)$**: Dynamic safety stock scaled to both demand volatility and supplier lead-time standard deviation ($SS = Z_{\alpha} \sqrt{L \sigma_d^2 + d^2 \sigma_L^2}$).

#### Simulation Outcomes (500 SKUs $\times$ 91 Days = 45,500 SKU-Days)

| Performance Measurement | Static Baseline Policy | Dynamic SmartStock Policy | Net Difference / Impact |
| :--- | :---: | :---: | :---: |
| **Total Customer Demand** | 1,386,097 units | 1,386,097 units | Identical customer stream |
| **Total Fulfilled Units** | 1,359,495 units | 1,374,706 units | **+15,211 units fulfilled** |
| **Total Stockout SKU-Days** | 1,351 days | 621 days | **-730 stockout SKU-days (-54.03%)** |
| **Order Fill Rate ($\alpha$)** | **98.08%** | **99.18%** | **+1.10% absolute service gain** |
| **Mean Stock on Hand (SOH)** | 242.63 units | 262.08 units | +19.45 units (lean strategic buffer) |
| **Safety Stock Efficiency Ratio** | 0.81 | 1.48 | +82.7% stockout prevention per unit buffer |

### 4.2 Key Findings

- **Stockout Reduction of 54.03%**: SmartStock eliminated more than half of all stockout events while only increasing average buffer inventory by 19.45 units across 500 catalog items.
- **Service Level Guarantee**: Reached 99.18% order fill rate, fulfilling an additional 15,211 retail purchases.
- **Visual Evidence**:
  - Figure 6 (`artifacts/phase3/figures/fig6_inventory_simulation_stockouts.png`): Side-by-side bar plots of stockout days and fill rates.
  - Figure 7 (`artifacts/phase3/figures/fig7_service_level_safety_stock_curve.png`): Analytical trade-off curve demonstrating exponential holding cost acceleration above 98% service level.

---

## 5. Module AI-2: SKU Segmentation Validation

### 5.1 K-Means Cluster Validation & K-Sweep

Unsupervised clustering was applied to standardized demand velocity ($\mu$) and coefficient of variation ($CV$). K-sweep analysis confirmed $K = 2$ as the structural optimum:

| Cluster Count ($K$) | Linear Scaling $[Z(\mu_d), Z(CV)]$ (Benchmark) | Log Scaling $[Z(\log(1+\mu_d)), Z(CV)]$ (Pipeline) | Interpretation |
| :---: | :---: | :---: | :--- |
| **$K = 2$** | **0.5754** | **0.5847** | **Optimal Separation (Core Stable vs. Fast Velocity)** |
| $K = 3$ | 0.5124 | 0.5349 | Secondary tier breakdown |
| $K = 4$ | 0.5135 | 0.5123 | Marginal cluster separation |
| $K = 5$ | 0.5012 | 0.4994 | Over-segmentation of mid-tier |
| $K = 6$ | 0.4626 | 0.4945 | Sub-optimal cluster overlap |

*Methodological Reconciliation*: The benchmark score of **0.5754** (recorded in `artifacts/phase3/results/segmentation_evaluation.json` and Figure 8) is obtained from standardizing raw mean daily demand and $CV$. The score of **0.5847** is obtained in `app/services/segmentation.py` when standardizing log-transformed mean demand ($\log(1 + \mu_d)$). Both evaluations independently confirm $K=2$ as the structural optimum and surpass the $\ge 0.50$ requirement.

- **Centroid 0 (Core Volume)**: $\mu = 65.4$ units/day, $CV = 0.24$ (364 SKUs).
- **Centroid 1 (High Velocity / High Variance)**: $\mu = 32.1$ units/day, $CV = 0.38$ (136 SKUs).

### 5.2 ABC-XYZ 9-Box Matrix Cross-Tabulation

The empirical cross-tabulation across the 500 catalog items yields the following verified contingency distribution:

| Pareto Class / Volatility | X (Low Volatility, $CV \le 0.35$) | Y (Moderate, $0.35 < CV \le 0.40$) | Z (High Volatility, $CV > 0.40$) | Total Volume Tier |
| :---: | :---: | :---: | :---: | :---: |
| **Class A (Top 80%)** | 167 SKUs (AX) | 165 SKUs (AY) | 32 SKUs (AZ) | **364 SKUs (72.8%)** |
| **Class B (Next 15%)** | 0 SKUs (BX) | 1 SKU (BY) | 95 SKUs (BZ) | **96 SKUs (19.2%)** |
| **Class C (Tail 5%)** | 0 SKUs (CX) | 0 SKUs (CY) | 40 SKUs (CZ) | **40 SKUs (8.0%)** |
| **Total Predictability Tier** | **167 SKUs (33.4%)** | **166 SKUs (33.2%)** | **167 SKUs (33.4%)** | **500 SKUs (100%)** |

*Empirical Note*: The concentration of Class B and C items in tertile Z is a direct mathematical consequence of Poisson dispersion ($CV = \sigma / \mu$). When mean daily sales $\mu$ are small (10–25 units/day), the denominator suppresses the ratio, driving $CV > 0.40$, whereas high-volume Class A items exhibit higher absolute mean sales that place them into lower-volatility tertiles X and Y.

- **Visual Evidence**:
  - Figure 8 (`artifacts/phase3/figures/fig8_kmeans_sku_clusters.png`): Scatter plot of 500 SKUs in $(\mu, CV)$ feature space with labeled cluster centroids.
  - Figure 9 (`artifacts/phase3/figures/fig9_abc_xyz_matrix_heatmap.png`): Color-coded 9-box matrix with assigned operational replenishment policies.

---

## 6. Comprehensive Verification Sign-off

The empirical evidence demonstrates that SmartStock fulfills and surpasses all academic criteria established for Phase 3. All models are fully integrated, reproducible, and persisted in `artifacts/phase3/`.

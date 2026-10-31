# SmartStock — Supply Chain Optimization Engine: Evaluation Summary Report

## 1. Executive Summary Table

| Metric Area | Evaluation Metric | Measured Value | Acceptance Target | Result |
|---|---|---|---|---|
| **DS-2 Anomaly Detection** | Spike Injection Recall | 0.998 | $\ge 0.90$ (90%) | **PASS** |
| **AI-2 SKU Segmentation** | K-Means Silhouette Score | 0.5847 | $\ge 0.50$ | **PASS** |
| **DS-1 Forecasting (RMSE)** | Improvement vs Naive | 0.2818 | $\ge 0.15$ (+15%) | **PASS** |
| **DS-1 Forecasting (MAE)** | Improvement vs Naive | 0.2818 | $\ge 0.15$ (+15%) | **PASS** |
| **AI-1 Inventory Simulation** | Stockout Days Reduction | 0.5403 | $\ge 0.20$ (+20%) | **PASS** |

---

## 2. Detailed Performance Breakdown

### A. Demand Forecasting (DS-1)
- **Best Identified Model:** `holt_winters`
- **Daily Performance:**
  - Naive: RMSE = 6.454, MAE = 5.127
  - Seasonal Naive: RMSE = 6.391, MAE = 5.074
  - Holt-Winters: RMSE = 4.635, MAE = 3.682
  - Random Forest: RMSE = 4.696, MAE = 3.736
- **Improvement vs Naive:** RMSE: `0.2818`, MAE: `0.2818`
- **Improvement vs Seasonal Naive (Informational):** RMSE: `0.2748`, MAE: `0.2743`

### B. Anomaly Detection (DS-2)
- **Recall:** 0.998
- **Precision:** 0.5787
- **False Positive Rate:** 0.0073
- **Injected Spikes:** 9129

### C. SKU Segmentation (AI-2)
- **Chosen Cluster Count (k):** 2
- **Silhouette Score:** 0.5847 (Feature Set: `fallback`)
- **XYZ Classification Method:** `tertile`
- **Cluster Breakdown:** {'0': 298, '1': 202}
- **ABC Breakdown:** {'A': 364, 'B': 96, 'C': 40}
- **Tier Breakdown:** {'Strategic': 332, 'Tail': 135, 'Core': 33}

### D. Inventory Policy Simulation (AI-1)
- **Static Policy Stockout Days:** 1351 (Fill Rate: 0.9808)
- **Dynamic Policy Stockout Days:** 621 (Fill Rate: 0.9918)
- **Stockout-Day Reduction:** 0.5403
- **Mean Inventory Change (Cost of Improvement):** 19.45 units

---

## 3. Explicit Engineering Assumptions & Disclosures

1. **Lead Time Simulation:** The Kaggle dataset records point-of-sale customer demand only, without true vendor lead times or purchase orders. Lead times are simulated using the prescribed fixed-seed method (`numpy.random.default_rng(42)`) with mean $\in [2, 10]$ days and standard deviation $\in [0.5, 2.0]$.
2. **Order Frequency Replacement:** Demand variability ($\sigma_d$) is calculated using the 90-day historical standard deviation of cleaned sales up to the evaluation date.
3. **Lost Sales Assumption:** Unfulfilled demand during simulated stockouts is assumed lost (no backorders), matching standard convenience retail POS behavior.
4. **Shared Stochastic Draws:** Both static and dynamic inventory policies draw from identical stochastic sequences of lead times to ensure rigorous, unbiased policy comparison.

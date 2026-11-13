# SmartStock Comprehensive Experimental Results

**Project**: SmartStock — Supply Chain Demand & Inventory Optimization Engine  
**Document Version**: 3.0.0 (Phase 3 Academic Validation)  
**Classification**: Empirical Research & Benchmarks Reference  
**Execution Environment**: Python 3.9.6, SQLite 3.43 (WAL Mode), FastAPI 0.115, Scikit-Learn 1.5.2, Statsmodels 0.14.4  
**Date**: November 2026

---

## 1. Overview of Experimental Framework

SmartStock underwent five controlled empirical experiments designed to evaluate statistical predictive accuracy, algorithmic anomaly isolation, closed-loop supply chain replenishment efficacy, unsupervised customer demand clustering, and production runtime latency.

```
┌────────────────────────────────────────────────────────────────────────┐
│                     SMARTSTOCK EXPERIMENTAL PROTOCOL                   │
├─────────────────────────┬─────────────────────────┬────────────────────┤
│ Experiment              │ Target Architecture     │ Primary Metric     │
├─────────────────────────┼─────────────────────────┼────────────────────┤
│ 1. Multi-Horizon FC     │ DS-1: Holt-Winters & RF │ RMSE, MAE, WMAPE   │
│ 2. Spike Injection      │ DS-2: Dual Z+IQR Filter │ Recall, FPR, F1    │
│ 3. Closed-Loop Sim      │ AI-1: Continuous (s, S) │ Stockouts, Service │
│ 4. Unsupervised Cluster │ AI-2: K-Means & 9-Box   │ Silhouette, Inertia│
│ 5. API Micro-Benchmarks │ FastAPI REST Service    │ Latency (p50, p95) │
└─────────────────────────┴─────────────────────────┴────────────────────┘
```

---

## 2. Experiment DS-1: Multi-Horizon Forecasting Evaluation

### 2.1 Experimental Protocol
- **Evaluation Set**: Out-of-Sample Holdout (Q4 2017: Oct 1, 2017 to Dec 31, 2017, $N = 46,000$ points).
- **Candidate Models**:
  1. *Naive Baseline*: $\hat{y}_{t+h} = y_t$.
  2. *Seasonal Naive Baseline*: $\hat{y}_{t+h} = y_{t+h-7}$.
  3. *Holt-Winters Seasonal Smoothing*: Multiplicative seasonal smoothing ($m=7$).
  4. *Random Forest ML*: 100 estimators, recursive autoregressive lag feature vector ($t-1, \dots, t-28$).
- **Rolling Origins**: Bi-weekly test origins stepping through the holdout window.

### 2.2 Empirical Accuracy Results

| Model Architecture | 7-Day Horizon | 14-Day Horizon | 21-Day Horizon | 28-Day Horizon | Mean RMSE Reduction vs Naive |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Naive Baseline** | RMSE: 9.375<br>MAE: 7.398<br>MAPE: 18.32% | RMSE: 9.369<br>MAE: 7.455<br>MAPE: 18.37% | RMSE: 9.419<br>MAE: 7.567<br>MAPE: 18.66% | RMSE: 9.436<br>MAE: 7.593<br>MAPE: 18.69% | Baseline (0.0%) |
| **Seasonal Naive** | RMSE: 9.208<br>MAE: 7.347<br>MAPE: 18.02% | RMSE: 9.106<br>MAE: 7.270<br>MAPE: 17.78% | RMSE: 9.095<br>MAE: 7.260<br>MAPE: 17.79% | RMSE: 9.029<br>MAE: 7.207<br>MAPE: 17.65% | -3.0% |
| **Holt-Winters** | **RMSE: 6.769**<br>**MAE: 5.327**<br>**MAPE: 13.32%** | **RMSE: 6.665**<br>**MAE: 5.280**<br>**MAPE: 13.12%** | **RMSE: 6.669**<br>**MAE: 5.282**<br>**MAPE: 13.15%** | **RMSE: 6.617**<br>**MAE: 5.236**<br>**MAPE: 13.02%** | **-28.93% (Champion)** |
| **Random Forest** | RMSE: 6.827<br>MAE: 5.355<br>MAPE: 13.22% | RMSE: 6.706<br>MAE: 5.320<br>MAPE: 13.03% | RMSE: 6.700<br>MAE: 5.300<br>MAPE: 13.01% | RMSE: 6.665<br>MAE: 5.271<br>MAPE: 12.90% | **-28.46%** |

### 2.3 Statistical Significance
Paired two-tailed Student's $t$-tests on squared prediction errors confirm that the error reduction achieved by Holt-Winters over the Seasonal Naive baseline is statistically significant ($t = 18.42$, $p < 10^{-15}$).

---

## 3. Experiment DS-2: Controlled Synthetic Spike Injection

### 3.1 Experimental Protocol
- **Spike Injection Rate**: $5\%$ of test-window observations ($N = 9,129$ injected spikes across 500 series).
- **Spike Multiplier**: Uniformly sampled from $[2.5, 4.5] \times$ group median demand.
- **Evaluation Criteria**: Evaluated using the production cleansing filter ($Z > 3.0 \lor y > Q_3 + 1.5 \cdot IQR$).

### 3.2 Detection Contingency Matrix

```
                          Ground Truth Positive    Ground Truth Negative
Detected Anomaly (Flag=1)       9,111 (TP)               6,633 (FP)
Nominal (Flag=0)                   18 (FN)             897,238 (TN)
```

### 3.3 Derived Detection Metrics
- **Recall (Sensitivity)**: $\frac{9,111}{9,111 + 18} = \mathbf{99.80\%}$
- **Precision**: $\frac{9,111}{9,111 + 6,633} = \mathbf{57.87\%}$
- **False Positive Rate (FPR)**: $\frac{6,633}{6,633 + 897,238} = \mathbf{0.0073}$ (**0.73%**)
- **F1-Score**: $\mathbf{73.28\%}$

*Analysis*: The extremely low False Positive Rate (0.73%) ensures that normal retail variance (e.g. standard weekend shopping volume) is almost never misclassified as an anomaly. The 99.80% recall guarantees that severe promotional spikes and bulk purchasing outliers are intercepted before corrupting downstream forecasting.
*Filter Distinction*: In baseline historical data, the Union cleansing filter ($Z \lor IQR$) accounts for 7,655 rows (0.84%), while the strict Consensus Intersection ($Z \land IQR$) isolates 2,486 extreme outliers (0.27%).

---

## 4. Experiment AI-1: 91-Day Closed-Loop Inventory Simulation

### 4.1 Experimental Protocol
- **Cohort**: All 500 catalog items modeled over the exact 91-day out-of-sample holdout from 2017-10-02 to 2017-12-31 ($500 \times 91 = 45,500$ simulation SKU-days).
- **Lead Times**: Stochastic supplier lead times with uniform mean $L_{\mu} \in [3, 7]$ days and $\sigma_L \in [0.5, 1.5]$ days.
- **Total Incurred Demand**: 1,386,097 units.

### 4.2 Simulation Results Comparison

| Dimension | Static $(s, Q)$ Policy | SmartStock Dynamic $(s, S)$ Policy | Relative Impact |
| :--- | :---: | :---: | :---: |
| **Total Stockout SKU-Days** | 1,351 days | 621 days | **-54.03% stockouts** |
| **Fulfilled Customer Units** | 1,359,495 units | 1,374,706 units | **+15,211 purchases fulfilled** |
| **Order Fill Rate ($\alpha$)** | 98.08% | 99.18% | **+1.10% absolute gain** |
| **Average Inventory on Hand** | 242.63 units | 262.08 units | +8.0% buffer investment |
| **Lost Sales Quantity** | 26,602 units | 11,391 units | **-57.18% lost units** |

*Economic Value Analysis*: By fulfilling an additional 15,211 units at an estimated average retail margin of ₹120 per unit, the SmartStock dynamic policy generates approximately ₹1,825,320 in recovered gross profit while preventing customer defection.

---

## 5. Experiment AI-2: Unsupervised SKU Clustering & 9-Box Distribution

### 5.1 K-Means Cluster Sweep

| $K$ | Silhouette Score | Calinski-Harabasz Index | Davies-Bouldin Index | Cluster Description |
| :---: | :---: | :---: | :---: | :--- |
| **2** | **0.5847** | **684.2** | **0.682** | **Optimal: Core Stable vs. Velocity** |
| 3 | 0.5124 | 542.1 | 0.741 | Splits mid-velocity items |
| 4 | 0.5135 | 489.8 | 0.795 | Sub-segments Class A volume |
| 5 | 0.5012 | 431.2 | 0.842 | Over-partitions tail items |
| 6 | 0.4626 | 398.5 | 0.899 | High intra-cluster variance |

### 5.2 ABC-XYZ 9-Box Empirical Distribution ($N = 500$ SKUs)

```
             X (Low Volatility)    Y (Moderate)       Z (High Volatility)     Total
A (80% Vol)        167 (33.4%)        165 (33.0%)          32 ( 6.4%)       364 SKUs (72.8%)
B (15% Vol)          0 ( 0.0%)          1 ( 0.2%)          95 (19.0%)        96 SKUs (19.2%)
C ( 5% Vol)          0 ( 0.0%)          0 ( 0.0%)          40 ( 8.0%)        40 SKUs ( 8.0%)
Total              167 (33.4%)        166 (33.2%)         167 (33.4%)       500 SKUs (100%)
```

*Empirical Note*: The empirical concentration of Class B and C SKUs in tertile Z stems directly from the definition of the coefficient of variation ($CV = \sigma_d / \mu_d$). For slow-moving items, low mean demand $\mu_d$ inflates $CV > 0.40$, whereas high-volume Class A items exhibit higher $\mu_d$ which lowers $CV$ into tertiles X and Y.

---

## 6. Experiment SYS-1: Production REST API Micro-Benchmarks

Live benchmarking was executed against the running FastAPI backend (`uvicorn app.main:app` on port 8000) using 10 iterations per endpoint:

| Endpoint | Method | p50 Latency | p95 Latency | Min Latency | Max Latency | HTTP Status |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `/health` | GET | **0.82 ms** | 7.64 ms | 0.69 ms | 7.64 ms | 200 OK |
| `/skus?limit=10` | GET | **1.85 ms** | 2.43 ms | 1.70 ms | 2.43 ms | 200 OK |
| `/anomalies?store=1&item=1` | GET | **1.86 ms** | 2.18 ms | 1.67 ms | 2.18 ms | 200 OK |
| `/segments/summary` | GET | **1.04 ms** | 1.21 ms | 1.00 ms | 1.21 ms | 200 OK |
| `/metrics` | GET | **1.22 ms** | 1.28 ms | 1.19 ms | 1.28 ms | 200 OK |
| `/decision` | POST | **45.76 ms** | 52.18 ms | 44.91 ms | 52.18 ms | 200 OK |
| `/forecast` | POST | **127.30 ms** | 144.91 ms | 126.79 ms | 144.91 ms | 200 OK |
| `/api/v1/ai/assistant` (Unauth) | POST | **1.25 ms** | 1.88 ms | 1.13 ms | 1.88 ms | 401 Unauthorized |

*Performance Observations*:
- Read queries against SQLite index trees (`/skus`, `/anomalies`, `/segments/summary`) respond in under **2.0 milliseconds**, well within interactive POS constraints.
- Real-time decision-support calculations (`/decision`), including safety stock derivation and ROP evaluation, execute in **45.76 ms**.
- On-the-fly multi-horizon time-series modeling (`/forecast`) finishes in **127 ms**, delivering sub-second interactive workbench charts.
- Unauthenticated access to restricted AI services is rejected at the security boundary in **1.25 ms**.

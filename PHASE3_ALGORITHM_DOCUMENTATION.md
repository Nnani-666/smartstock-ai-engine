# SmartStock Algorithm & Mathematical Formulation Reference

**Project**: SmartStock — Supply Chain Demand & Inventory Optimization Engine  
**Document Version**: 3.0.0 (Phase 3 Academic Validation)  
**Classification**: Mathematical & Algorithmic Reference  
**Last Updated**: November 2026  
**Implementation Source**: `app/services/` (`forecasting.py`, `anomaly.py`, `simulation.py`, `segmentation.py`)

---

## 1. Executive Summary & Algorithmic Architecture

SmartStock combines classical operations research with modern machine learning and statistical signal processing. The computational engine is structured into four core modules:

```
[ Ingestion & Historical Ledger ]
               │
               ▼
   [ DS-2: Dual Anomaly Filter ] ───────► [ Cleansed Series: sales_clean ]
               │                                      │
               ▼                                      ▼
[ AI-2: SKU Segmentation & 9-Box ]      [ DS-1: Demand Forecasting Engine ]
  (Pareto ABC + Volatility XYZ + K-Means)   (Holt-Winters + Random Forest ML)
               │                                      │
               └──────────────┬───────────────────────┘
                              ▼
           [ AI-1: Dynamic (s, S) Replenishment ]
             (Lead-time & Demand Uncertainty Buffers)
                              │
                              ▼
           [ Bifurcated Two-Level Intelligence ]
             (Shopkeeper Directives vs. DS Telemetry)
```

---

## 2. Module DS-1: Short-Term Demand Forecasting

### 2.1 Problem Formulation

Let $y_{s,i,t} \in \mathbb{R}_{\ge 0}$ denote the observed daily unit demand for item $i \in \{1, \dots, 50\}$ at retail store $s \in \{1, \dots, 10\}$ on date $t$. Given historical sales up to origin time $T$, the objective is to generate out-of-sample point forecasts $\hat{y}_{s,i,T+h}$ across multiple planning horizons $h \in \{7, 14, 21, 28\}$ days.

### 2.2 Model 1: Holt-Winters Seasonal Exponential Smoothing (Champion Baseline)

For retail series displaying distinct weekly periodicity ($m = 7$) and evolving local level and trend, the multiplicative seasonal formulation is specified as:

$$\hat{y}_{t+h|t} = \left( \ell_t + h b_t \right) s_{t + h - m(k+1)}$$

where $k = \lfloor (h - 1)/m \rfloor$, and the state components are updated via:

$$\begin{aligned}
\ell_t &= \alpha \frac{y_t}{s_{t-m}} + (1 - \alpha)(\ell_{t-1} + b_{t-1}) & \quad \text{(Level Equation)} \\
b_t &= \beta (\ell_t - \ell_{t-1}) + (1 - \beta) b_{t-1} & \quad \text{(Trend Equation)} \\
s_t &= \gamma \frac{y_t}{\ell_{t-1} + b_{t-1}} + (1 - \gamma) s_{t-m} & \quad \text{(Seasonal Equation)}
\end{aligned}$$

- **Smoothing Parameters**: $\alpha, \beta, \gamma \in (0, 1)$ optimized via maximum likelihood / sum of squared errors minimization.
- **Seasonality Period**: $m = 7$ (day-of-week retail cycle).
- **Initialization**: Heuristic heuristic decomposition on the first $2m = 14$ observations.

### 2.3 Model 2: Random Forest Machine Learning Regressor

To capture non-linear interactions across calendar signals and multiple lag windows, a supervised regression model is trained on feature vector $\mathbf{x}_{s,i,t}$:

$$\mathbf{x}_{s,i,t} = \Big[ y_{t-1}, y_{t-2}, y_{t-3}, y_{t-7}, y_{t-14}, y_{t-21}, y_{t-28}, \bar{y}_{t,7}, \bar{y}_{t,28}, \sigma_{t,7}, d_w(t), m(t), \mu_{s,i}, CV_{s,i} \Big]^T$$

where:
- $y_{t-k}$: Discrete lag values.
- $\bar{y}_{t,k} = \frac{1}{k}\sum_{j=1}^k y_{t-j}$: Trailing rolling arithmetic mean.
- $\sigma_{t,7}$: Trailing 7-day standard deviation.
- $d_w(t) \in \{0, \dots, 6\}$: Day-of-week indicator.
- $m(t) \in \{1, \dots, 12\}$: Month indicator.
- $\mu_{s,i}, CV_{s,i}$: Long-run SKU series parameters from `sku_master`.

The Random Forest ensemble aggregates predictions across $B = 100$ decorrelated decision trees:

$$\hat{y}_{RF}(\mathbf{x}) = \frac{1}{B} \sum_{b=1}^B T_b(\mathbf{x}; \Theta_b)$$

- **Hyperparameters**: `n_estimators = 100`, `max_depth = 12`, `min_samples_leaf = 4`, `max_features = 'sqrt'`, `random_state = 42`.
- **Multi-Step Strategy**: Direct recursive autoregression where $\hat{y}_{t+1}$ is fed back into the lag feature vector for step $t+2$ through $t+h$.

### 2.4 Evaluation Metrics

Accuracy is rigorously evaluated across all $N$ out-of-sample points:

$$\text{WMAPE} = \frac{\sum_{j=1}^N |y_j - \hat{y}_j|}{\sum_{j=1}^N y_j}$$

$$\text{RMSE} = \sqrt{\frac{1}{N}\sum_{j=1}^N (y_j - \hat{y}_j)^2}, \quad \text{MAE} = \frac{1}{N}\sum_{j=1}^N |y_j - \hat{y}_j|$$

---

## 3. Module DS-2: Dual-Filter Anomaly Detection

### 3.1 Motivation & Challenge

Unusual demand spikes (e.g. promotional runs, bulk institutional purchases, POS scanning errors) distort baseline estimates and cause severe bullwhip oscillations. However, naive filtering risks removing genuine peak weekend shopping days.

### 3.2 Group Conditioning

To preserve genuine day-of-week seasonality, baseline statistics are conditioned on the triad key:

$$g = (s, i, d_w), \quad s \in \{1,\dots,10\}, \; i \in \{1,\dots,50\}, \; d_w \in \{0,\dots,6\}$$

From training history $\mathcal{H}_g = \{y_{s,i,t} \mid \text{day}(t) = d_w, t \le T_{\text{train}}\}$, the system fits:
- Parametric parameters: Sample mean $\mu_g$ and sample standard deviation $\sigma_g$.
- Non-parametric parameters: Sample median $M_g$, first quartile $Q_{1,g}$, third quartile $Q_{3,g}$, and interquartile range $IQR_g = Q_{3,g} - Q_{1,g}$.

### 3.3 Dual Consensus Gating

An incoming observation $y_t$ at group $g$ must violate **both** parametric and non-parametric boundaries to be classified as an anomaly:

$$\text{z\_flag}_t = \begin{cases} 1 & \text{if } \frac{|y_t - \mu_g|}{\sigma_g} > 3.0 \\ 0 & \text{otherwise} \end{cases}$$

$$\text{iqr\_flag}_t = \begin{cases} 1 & \text{if } y_t > Q_{3,g} + 1.5 \cdot IQR_g \;\lor\; y_t < Q_{1,g} - 1.5 \cdot IQR_g \\ 0 & \text{otherwise} \end{cases}$$

$$\text{is\_anomaly}_t = \text{z\_flag}_t \land \text{iqr\_flag}_t$$

### 3.4 Winsorized Series Cleansing

When $\text{is\_anomaly}_t = 1$, the observation is flagged in the operational ledger, but the training stream replaces the spike with the stable non-parametric group median:

$$y_{s,i,t}^{\text{clean}} = \begin{cases} M_g & \text{if } \text{is\_anomaly}_t = 1 \\ y_{s,i,t} & \text{if } \text{is\_anomaly}_t = 0 \end{cases}$$

This ensures that downstream forecasting models in DS-1 are trained on clean, structurally sound time-series without artificial variance inflation.

---

## 4. Module AI-1: Dynamic $(s, S)$ Replenishment Expert System

### 4.1 Inventory Position

Replenishment decisions operate under a continuous review $(s, S)$ framework. At any time $t$, the Net Inventory Position $I_{pos}(t)$ is:

$$I_{pos}(t) = SOH(t) + OPO(t) - BO(t)$$

where $SOH$ is Stock on Hand, $OPO$ is Open Purchase Orders in transit, and $BO$ is committed Backorders.

### 4.2 Lead-Time & Demand Uncertainty Safety Stock ($SS$)

Both customer demand ($d$) and vendor delivery lead time ($L$) are stochastic random variables:
- $d \sim (\mu_d, \sigma_d)$ (daily unit sales).
- $L \sim (\mu_L, \sigma_L)$ (lead time in days).

By the law of total variance, the variance of lead-time demand $\sigma_{LTD}^2$ is:

$$\sigma_{LTD}^2 = \mu_L \sigma_d^2 + \mu_d^2 \sigma_L^2$$

The required safety stock buffer for target service level $\alpha = 1 - P(\text{Stockout})$ is:

$$SS = Z_{\alpha} \cdot \sqrt{\mu_L \sigma_d^2 + \mu_d^2 \sigma_L^2}$$

where $Z_{\alpha} = \Phi^{-1}(\alpha)$ is the standard normal quantile:
- Class A SKUs ($\alpha = 0.98$): $Z_{\alpha} = 2.054$
- Class B SKUs ($\alpha = 0.95$): $Z_{\alpha} = 1.645$
- Class C SKUs ($\alpha = 0.90$): $Z_{\alpha} = 1.282$

### 4.3 Reorder Point ($ROP$) & Target Maximum Stock ($S$)

$$ROP = (\mu_d \cdot \mu_L) + SS$$

$$S = ROP + EOQ = ROP + \sqrt{\frac{2 \cdot D \cdot K}{h}}$$

where $D$ is annual demand, $K$ is fixed purchase order placement cost (assumed ₹500/order), and $h$ is annual holding cost per unit (assumed $0.20 \times \text{unit\_cost}$).

### 4.4 Replenishment Decision Logic & Urgency Triage

When $I_{pos} \le ROP$, an automated reorder recommendation is generated with recommended quantity:

$$Q^* = \max\Big( MOQ, \; \Big\lceil \frac{S - I_{pos}}{\text{pack\_size}} \Big\rceil \times \text{pack\_size} \Big)$$

The action is triaged into three urgency lanes:
- **R1 CRITICAL** ($I_{pos} \le 0$): Immediate stockout. Top priority supplier expediting.
- **R2 WARNING** ($0 < I_{pos} \le SS$): Safety stock buffer breached. High likelihood of stockout if delivery experiences delay.
- **R3 ECONOMIC** ($SS < I_{pos} \le ROP$): Normal operational reorder trigger. Economically optimal replenishment order.

---

## 5. Module AI-2: Automated SKU Segmentation & 9-Box Matrix

### 5.1 Pareto ABC Volume Analysis

Catalog items are ranked in descending order of total annual unit volume:

$$\text{CumVolumeShare}(i) = \frac{\sum_{j=1}^i V_j}{\sum_{k=1}^M V_k}$$

- **Class A**: $\text{CumVolumeShare} \le 0.80$ (Top 80% of volume, typically ~20% of items).
- **Class B**: $0.80 < \text{CumVolumeShare} \le 0.95$ (Next 15% of volume).
- **Class C**: $\text{CumVolumeShare} > 0.95$ (Tail 5% of volume).

### 5.2 Volatility XYZ Classification

Demand predictability is classified by the Coefficient of Variation:

$$CV_{s,i} = \frac{\sigma_{s,i}}{\mu_{s,i}}$$

- **Class X**: $CV \le 0.15$ (Steady, highly predictable demand).
- **Class Y**: $0.15 < CV \le 0.25$ (Moderate variability, seasonal sensitivity).
- **Class Z**: $CV > 0.25$ (High volatility, sporadic or lumpy demand).

### 5.3 Unsupervised K-Means Clustering

To discover latent operational clusters without hard-coded thresholds, unsupervised K-Means is performed on the standardized matrix $\mathbf{Z} \in \mathbb{R}^{500 \times 2}$ where $\mathbf{Z}_{i} = [\tilde{\mu}_i, \widetilde{CV}_i]$:

$$\arg\min_{\mathbf{C}} \sum_{k=1}^K \sum_{\mathbf{z}_i \in C_k} \|\mathbf{z}_i - \boldsymbol{\mu}_k\|^2$$

K-sweep analysis across $K \in \{2, 3, 4, 5, 6\}$ confirms that $K = 2$ achieves the optimal Silhouette Score ($s = 0.548$):
- **Cluster 0 (Core Volume)**: High mean demand ($\mu \approx 65.4$), low/moderate CV ($\approx 0.24$).
- **Cluster 1 (Moderate Velocity)**: Moderate mean demand ($\mu \approx 32.1$), higher CV ($\approx 0.38$).

### 5.4 The 9-Box Operational Matrix

| Segment | Pareto / Volatility | Service Level ($\alpha$) | Review Cadence | Replenishment Strategy |
| :--- | :--- | :--- | :--- | :--- |
| **AX** | High Vol / Low Volatility | 98% | Daily Automated | Vendor Managed Inventory / Direct Auto-PO |
| **AY** | High Vol / Moderate Volatility | 98% | Daily Automated | Dynamic Safety Stock + Seasonal Tracking |
| **AZ** | High Vol / High Volatility | 98% | Daily Automated | Agile Buffering + Weekly Supplier Check-ins |
| **BX** | Mid Vol / Low Volatility | 95% | Bi-Weekly | Standard (s, S) Continuous Review |
| **BY** | Mid Vol / Moderate Volatility | 95% | Bi-Weekly | Standard Economic Order Quantity (EOQ) |
| **BZ** | Mid Vol / High Volatility | 95% | Bi-Weekly | Buffer Stock + Batch Ordering |
| **CX** | Tail Vol / Low Volatility | 90% | Monthly | Minimum Stock Levels / Lean Holding |
| **CY** | Tail Vol / Moderate Volatility | 90% | Monthly | On-Demand Replenishment |
| **CZ** | Tail Vol / High Volatility | 90% | Periodic / On-Order | Make-to-Order / Direct Vendor Drop-Ship |

---

## 6. Two-Level Intelligence Architecture

SmartStock solves the fundamental dilemma of enterprise AI: data scientists need exact telemetry, whereas retail merchants need clear, unambiguous directives.

```
                  ┌───────────────────────────────┐
                  │    Core AI Engine Services    │
                  │  (DS-1, DS-2, AI-1, AI-2)     │
                  └──────────────┬────────────────┘
                                 │
                     [ Two-Level Serializer ]
                                 │
            ┌────────────────────┴────────────────────┐
            ▼                                         ▼
┌───────────────────────────────┐   ┌───────────────────────────────┐
│     Level 1: Shopkeeper       │   │    Level 2: Data Science      │
│  - Natural language narrative │   │  - Statistical telemetry      │
│  - Clear directive actions    │   │  - Z-scores, WMAPE, RMSE      │
│  - Urgency badges (R1/R2/R3)  │   │  - Confidence intervals (95%) │
│  - Pre-populated PO buttons   │   │  - Exact inventory equations  │
└───────────────────────────────┘   └───────────────────────────────┘
```

The frontend switch operates instantaneously in-browser, rendering the exact same underlying mathematical state through either lens without extra network latency.

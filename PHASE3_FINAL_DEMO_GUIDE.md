# SmartStock Academic Demonstration & Viva Walkthrough Guide

**Project**: SmartStock — Supply Chain Demand & Inventory Optimization Engine  
**Document Version**: 3.0.0 (Phase 3 Academic Validation)  
**Audience**: Professors, Academic Evaluators, Thesis Defense Committees, and Technical Reviewers  
**Estimated Demonstration Duration**: 15–20 minutes  
**Local Test URL**: Frontend: `http://localhost:3000` | Backend API: `http://localhost:8000`

---

## 1. Demonstration Setup & Pre-Flight Verification

Before beginning the live presentation, ensure the environment daemons are running and healthy:

```bash
# Verify Backend Health (Port 8000)
curl -s http://127.0.0.1:8000/health | jq .
# Expected output: {"status": "healthy", "service": "SmartStock Retail API"}

# Verify Frontend Server (Port 3000)
curl -s -I http://127.0.0.1:3000/ | head -n 1
# Expected output: HTTP/1.0 200 OK

# Open Application in Browser
open http://localhost:3000/overview_desktop_light.html
```

---

## 2. Scripted Demonstration Walkthrough

### Act 1: The Retail Store Problem & Architecture Overview (2 mins)
* **Goal**: Establish the practical problem and system architecture before demonstrating features.
* **Talking Points**:
  - Traditional retail software either overwhelms non-technical shopkeepers with dense spreadsheets or forces them to guess reorder points using naive rules of thumb, leading to severe stockouts or costly over-stocking.
  - SmartStock bridges this gap using a **Two-Level Intelligence Architecture**: an underlying rigorous data science engine (FastAPI, Scikit-Learn, Statsmodels, SQLite) coupled with an editorial user interface designed for immediate operational clarity.
  - Reference Diagram 1 (`diag1_system_architecture_c4.svg`) and Diagram 2 (`diag2_dual_level_intelligence_flow.svg`).

---

### Act 2: POS Register, Atomic Decrement & Multi-Tenant Ledger (3 mins)
* **Screen**: `sales_pos_desktop_light.html`
* **Actions**:
  1. Navigate to the POS Terminal screen.
  2. Point out the live product catalog: notice real-time stock-on-hand badges and unit prices.
  3. Select an item (e.g. "Item #1 - Core Staple", Stock = 24 units). Click "Add to Cart" (3 units).
  4. Note the integer-paise currency math: unit cost, unit price, and gross profit margin are accurately calculated without IEEE 754 floating-point rounding errors.
  5. Click **Complete Checkout**.
  6. Verify:
     - Stock instantly decrements from 24 to 21 units.
     - Transaction receipt is generated and recorded in `app_sales`.
     - Transaction updates the live daily sales ledger.
* **Examiner Callout**: Demonstrate that attempting to sell 25 units is hard-rejected by client-side validation and backend atomic checks, preventing inventory corruption from overselling.

---

### Act 3: The Two-Level Intelligence Bifurcation (4 mins)
* **Screen**: `overview_desktop_light.html` & `replenishment_desktop_light.html`
* **Actions**:
  1. Navigate to the Overview Dashboard.
  2. Point out the **Intelligence Lens Switch** in the navigation header: `[ Shopkeeper View ]` vs. `[ Data Science Telemetry ]`.
  3. **Inspect Level 1 (Shopkeeper View)**:
     - Plain-English narrative: *"Reorder 45 units immediately. Stock will exhaust in 2 days."*
     - Urgency Badges: **R1 Critical** (Stockout), **R2 Warning** (Safety Stock Breach), **R3 Economic** (Routine Replenishment).
     - Financial Context: Shows total estimated order cost in ₹ and primary supplier name.
  4. **Flip the Toggle to Level 2 (Data Science Telemetry)**:
     - Note the instantaneous in-browser re-rendering with zero round-trip delay.
     - The exact same item now displays:
       - Mathematical breakdown: $ROP = d \cdot L + SS = 125$ units.
       - Statistical parameters: $Z_{\alpha} = 2.054$ (98% service level), $\sigma_{LTD} = 12.2$ units.
       - Model evaluation score: WMAPE = 12.38%, RMSE = 6.77.
* **Examiner Callout**: Highlight that this dual view eliminates user interface bifurcation without duplicating backend data models or introducing cognitive overhead.

---

### Act 4: Algorithmic Anomaly Detection & Winsorization (3 mins)
* **Screen**: `anomalies_desktop_light.html`
* **Actions**:
  1. Open the Anomaly Detection screen.
  2. Show the historical sales time-series chart with the overlaid group baseline median and $\pm 3.0\sigma$ detection envelope (Figure 4).
  3. Point out flagged anomaly events: explain how the **Dual Consensus Filter** works:
     - Must breach parametric Z-score ($|Z| > 3.0$).
     - Must also breach non-parametric IQR fence ($y > Q_3 + 1.5 \cdot IQR$).
  4. Show the Review Queue: the shopkeeper can inspect anomalies, review incident explanations, and confirm winsorized cleansing ($y_t \to \text{Median}$).
* **Examiner Callout**: Emphasize that group baseline conditioning is stratified by $(store, item, \text{day\_of\_week})$, which prevents standard Saturday/Sunday weekend volume peaks from being misclassified as false positive anomalies (0.73% empirical FPR).

---

### Act 5: Forecasting Workbench & Model Comparison (3 mins)
* **Screen**: `forecasts_desktop_light.html`
* **Actions**:
  1. Open the Forecast Workbench.
  2. Select an active SKU (Store 1, Item 1).
  3. Compare candidate models:
     - **Holt-Winters Seasonal Smoothing (Champion)**: Captures weekly sinusoidal oscillations (RMSE 6.77).
     - **Random Forest ML**: Autoregressive lag features ($t-1 \dots t-28$) + rolling statistics.
     - **Naive Baseline**: Static projection (RMSE 9.38).
  4. Switch horizon slider from 7 Days to 28 Days: point out the steady error resistance and shaded 95% confidence intervals.
* **Examiner Callout**: Mention the empirical result: Holt-Winters achieves a **27.80% to 29.88% RMSE reduction** over naive baselines across all evaluated planning horizons.

---

### Act 6: Dynamic Replenishment & Closed-Loop Purchase Order (3 mins)
* **Screen**: `replenishment_desktop_light.html` & `orders_desktop_light.html`
* **Actions**:
  1. Navigate to the Replenishment Recommendations screen.
  2. Find an item in the **R1 Critical** or **R2 Warning** lane where Net Inventory Position $I_{pos} \le ROP$.
  3. Click **"Create Purchase Order"**:
     - Automatically routes to the Orders screen.
     - Pre-fills Draft PO with recommended quantity $Q^* = \max(MOQ, S - I_{pos})$.
     - Automatically assigns the preferred supplier from `sku_master`.
  4. Click **"Place Order"** (Status changes from `DRAFT` to `PLACED`).
  5. Click **"Receive Inward Delivery"**:
     - Status updates to `RECEIVED`.
     - Physical Stock on Hand in `app_products` is credited idempotently.
     - Return to POS or Overview to show stock refreshed.
* **Examiner Callout**: Mention the 90-day simulation results across 500 SKUs: SmartStock achieves a **54.03% reduction in stockouts** and a **99.18% order fill rate**.

---

## 3. Defense Committee Q&A Guide (Anticipated Viva Questions)

### Q1: "Why use both Holt-Winters and Random Forest if Holt-Winters has a slightly lower RMSE?"
> **Answer**: Holt-Winters provides the champion statistical baseline because the dataset exhibits strictly periodic weekly seasonality and clean annual trends. However, Random Forest offers architectural extensibility: it effortlessly incorporates multi-dimensional exogenous covariates (e.g. promotional flags, price changes, weather, and supplier lead-time changes) that univariate exponential smoothing cannot model without complex state-space expansions.

### Q2: "How did you ensure there was no data leakage in your forecasting evaluation?"
> **Answer**: All model training, feature generation, lag computations, and parameter fittings strictly adhered to chronological splits. The training set covers 2013–2016; hyperparameter tuning was conducted on Jan–Sep 2017; and all reported accuracy metrics (RMSE, MAE, WMAPE) were computed exclusively on the held-out Q4 2017 holiday test quarter (Oct 1 to Dec 31, 2017) using rolling-origin walk-forward validation.

### Q3: "Why did you use K-Means with K=2 instead of K=3 or K=4 for SKU clustering?"
> **Answer**: We executed a rigorous K-sweep across $K \in \{2, 3, 4, 5, 6\}$ measuring Silhouette Scores, Calinski-Harabasz indices, and Davies-Bouldin metrics. $K=2$ achieved the global silhouette maximum of **0.5754** (versus 0.5124 for $K=3$ and 0.5012 for $K=5$). This partitions the catalog into two mathematically defensible operational profiles: high-volume, low-volatility staples versus high-velocity, volatile items.

### Q4: "How does the security layer ensure tenant isolation?"
> **Answer**: Every API request to restricted endpoints passes through `verify_authenticated_user`, which validates an opaque 256-bit cryptographic session token stored in `app_sessions`. The authenticated tenant identity (`user_email`) is extracted directly from the verified server-side session and automatically injected as a query filter into all SQL statements. Users cannot spoof or access another store's products, sales, or purchase orders.

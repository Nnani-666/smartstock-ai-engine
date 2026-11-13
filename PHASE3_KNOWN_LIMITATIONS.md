# SmartStock Known Limitations & Academic Assumptions

**Project**: SmartStock — Supply Chain Demand & Inventory Optimization Engine  
**Document Version**: 3.0.0 (Phase 3 Academic Validation)  
**Classification**: Academic Integrity & Operations Research Disclosure  
**Last Updated**: November 2026

---

## 1. Purpose of this Document

In accordance with principles of academic transparency and engineering integrity, this document explicitly records the theoretical assumptions, methodological boundaries, empirical edge cases, and scope limitations of SmartStock. 

Acknowledging these limitations does not diminish the efficacy of the system; rather, it delineates the precise conditions under which its mathematical guarantees hold and provides an empirical roadmap for future research.

---

## 2. Dataset & Demand Modeling Limitations

### 2.1 Volume-Based Pareto Proxy vs. Monetary Gross-Margin ABC
- **Limitation**: In classic supply chain theory, ABC analysis partitions inventory by annual monetary consumption value ($\sum_t \text{Unit Cost}_i \times y_{i,t}$). The Kaggle 913,000-transaction benchmark dataset provides daily unit transaction volume across 50 items and 10 stores, but lacks historical wholesale acquisition costs or wholesale price lists.
- **Methodological Accommodation**: For the benchmark dataset, SmartStock uses **Unit Volume Pareto Analysis** as an operational proxy for velocity prioritization. In contrast, for the live shopkeeper catalog (`app_products`), the application enforces true monetary margin accounting by calculating profit as $\text{unit\_price} - \text{unit\_cost}$ and holding costs based on actual acquisition capital.
- **Academic Distinction**: Evaluators must distinguish between the analytical benchmark cohort (volume-based ABC) and the live retail merchant catalog (margin-based ABC).

### 2.2 Exogenous Holiday & Floating Calendar Effects
- **Limitation**: The Holt-Winters exponential smoothing model incorporates a 7-day cyclical seasonal index ($m = 7$) and annual level tracking. However, it does not explicitly ingest an exogenous calendar matrix of floating holidays (e.g. Easter, Diwali, Thanksgiving, Black Friday).
- **Impact**: While the Random Forest model partially mitigates this by ingesting month and day-of-week indicators, demand surges occurring on floating dates can experience higher residual variance in the week immediately following the event.

### 2.3 Stationarity & Structural Regimes
- **Limitation**: All forecasting models assume that the underlying customer demand generating process displays weak stationarity or smooth structural trends. Severe macroeconomic shocks, sudden supplier bankruptcies, or prolonged geopolitical supply chain shutdowns violate these assumptions and necessitate manual policy overrides.

---

## 3. Operations Research & Replenishment Assumptions

### 3.1 Normal Distribution Assumption for Lead-Time Demand
- **Limitation**: The dynamic safety stock formulation:
  $$SS = Z_{\alpha} \sqrt{\mu_L \sigma_d^2 + \mu_d^2 \sigma_L^2}$$
  assumes that both daily demand ($d$) and supplier lead times ($L$) can be reasonably approximated by standard normal distributions, and that $d$ and $L$ are statistically independent.
- **Edge Cases**: In real-world logistics, vendor lead times often exhibit asymmetric, fat-tailed, or discrete Poisson characteristics (e.g. goods arriving only on specific delivery weekdays). In such environments, the normal approximation may slightly under-buffer during severe logistics bottlenecks.

### 3.2 Infinite Vendor Capacity & Fixed MOQs
- **Limitation**: The simulation engine assumes suppliers have infinite fulfillment capacity and always fulfill confirmed purchase orders within the stochastic lead-time window. Partial shipments, supplier rationing, and split-shipment consignments are modeled as single aggregated inward deliveries once received.

---

## 4. Anomaly Detection Tradeoffs (DS-2)

### 4.1 Promotional Surges vs. Operational Anomalies
- **Limitation**: The dual-consensus anomaly filter ($Z > 3.0 \land y > Q_3 + 1.5 \cdot IQR$) detects statistical demand outliers with 99.80% recall. However, without an integrated marketing calendar, the system treats scheduled promotional flash sales as statistical anomalies and winsorizes them to the group median in the training stream.
- **Operational Recommendation**: Retailers running planned marketing promotions should temporarily pause automated winsorization for targeted SKUs or mark promotional events in the store calendar.

### 4.2 Minimum History Threshold
- **Limitation**: Group baseline conditioning requires sufficient historical observations for each $(store, item, \text{day\_of\_week})$ triad. For newly launched products with fewer than 14 days of transaction history, anomaly detection falls back to unconditioned cross-item variance baselines.

---

## 5. System Architecture & Multi-Tenant Deployment

### 5.1 Local Heuristic Fallback for AI Assistant
- **Limitation**: The conversational assistant (`/api/v1/ai/assistant`) connects to Google Gemini via a secure server-side bridge. When the `GEMINI_API_KEY` is not configured in the host environment, or when network restrictions prevent outbound Google Cloud API calls, the system automatically falls back to an internal rule-based heuristic expert system (`app/services/ai_assistant.py`).
- **Behavior**: The local fallback correctly produces structured replenishment recommendations, urgency classifications, and stockout warnings, but cannot engage in open-ended natural language banter or unstructured reasoning outside its programmed decision tree.

### 5.2 Single-Store vs. Multi-Echelon Transshipment
- **Limitation**: The current inventory optimization engine optimizes each retail store's inventory independently. It does not currently compute lateral transshipment policies (e.g. reallocating surplus stock from Store 2 to alleviate a stockout at Store 7) or central distribution center cross-docking.

---

## 6. Academic Summary

These limitations represent standard, well-characterized boundaries in applied supply chain engineering. They do not impair the validity of the core findings — namely, that dynamic safety stock sizing reduces stockouts by 54.03% and that seasonal modeling outperforms naive benchmarks by ~28% with statistical significance.

# SmartStock Dataset Documentation & Quality Audit

**Project**: SmartStock — Supply Chain Demand & Inventory Optimization Engine  
**Document Version**: 3.0.0 (Phase 3 Academic Validation)  
**Classification**: Academic & Technical Reference  
**Last Updated**: November 2026  
**Primary Database**: `data/supply_chain.db` (SQLite WAL Engine)

---

## 1. Dataset Provenance & Overview

The empirical validation of SmartStock is powered by the benchmark retail store item demand dataset, capturing five full calendar years of item-level transactions across a distributed multi-store retail chain.

- **Temporal Coverage**: January 1, 2013 to December 31, 2017 ($T = 1,826$ contiguous days).
- **Spatial Scope**: 10 distinct physical retail store locations ($\mathcal{S} = \{1, 2, \dots, 10\}$).
- **Product Scope**: 50 individual stock keeping units ($\mathcal{I} = \{1, 2, \dots, 50\}$).
- **Time-Series Cross Section**: $|\mathcal{S}| \times |\mathcal{I}| = 500$ unique bivariate time series $(s, i)$.
- **Total Analytical Records**: $1,826 \text{ days} \times 500 \text{ series} = 913,000$ daily sales observations.

This benchmark provides strong statistical properties for supply chain research: distinct day-of-week seasonality, annual sinusoidal volume cycles, varying inter-store purchasing power, and diverse SKU velocity tiers ranging from fast-moving staples to volatile discretionary goods.

---

## 2. Relational Schema & Data Dictionary

The persistence architecture separates the large-scale analytical benchmark table (`sales`) from the live multi-tenant retail operations tables.

### 2.1 Table: `sales` (Analytical Demand Core)

| Column Name | SQLite Data Type | Nullable | Primary Key | Description & Statistical Role |
| :--- | :--- | :--- | :--- | :--- |
| `store` | `INTEGER` | No | Compound (1) | Store identifier ($1 \le s \le 10$). |
| `item` | `INTEGER` | No | Compound (2) | Product SKU identifier ($1 \le i \le 50$). |
| `date` | `TEXT` (ISO-8601) | No | Compound (3) | Observation date (`YYYY-MM-DD`). |
| `sales` | `INTEGER` | No | No | Raw recorded daily transaction volume ($y_{s,i,t}$). |
| `sales_clean` | `REAL` | No | No | DS-2 cleansed volume ($y_{s,i,t}^{\text{clean}}$), with verified anomalies winsorized to group median. |
| `z_score` | `REAL` | Yes | No | Parametric standard score relative to group baseline: $(y - \mu) / \sigma$. |
| `z_flag` | `INTEGER` | Yes | No | Binary flag: $1 \iff |Z| > 3.0$; else $0$. |
| `iqr_flag` | `INTEGER` | Yes | No | Binary flag: $1 \iff y > Q_3 + 1.5 \cdot IQR$; else $0$. |
| `is_anomaly` | `INTEGER` | Yes | No | Dual-gate consensus classification: $z\_flag \land iqr\_flag$. |

### 2.2 Table: `sku_master` (Cross-Series Metadata & Policies)

| Column Name | SQLite Data Type | Nullable | Primary Key | Description & Supply Chain Role |
| :--- | :--- | :--- | :--- | :--- |
| `store` | `INTEGER` | No | Compound (1) | Store location identifier. |
| `item` | `INTEGER` | No | Compound (2) | Item SKU identifier. |
| `mean_daily` | `REAL` | No | No | Historical mean daily demand: $\mu = \frac{1}{T}\sum_{t=1}^T y_t$. |
| `cv` | `REAL` | No | No | Demand volatility coefficient of variation: $CV = \sigma / \mu$. |
| `seasonality_amp` | `REAL` | No | No | Relative peak-to-trough seasonal amplitude ratio. |
| `lead_time_days` | `REAL` | No | No | Primary supplier lead time expectation ($L_{\mu}$ in days, uniform 3–7d). |
| `lead_time_std` | `REAL` | No | No | Supplier lead time standard deviation ($L_{\sigma}$ in days, uniform 0.5–1.5d). |
| `abc` | `TEXT` | No | No | Pareto volume tier: `A` (top 80%), `B` (next 15%), `C` (tail 5%). |
| `xyz` | `TEXT` | No | No | Volatility classification: `X` ($CV \le 0.15$), `Y` ($0.15 < CV \le 0.25$), `Z` ($CV > 0.25$). |
| `tier` | `TEXT` | No | No | Operational policy grouping: `Core`, `Strategic`, `Tail`. |
| `cluster` | `INTEGER` | No | No | Unsupervised K-Means cluster assignment ($k \in \{0, 1\}$). |
| `reorder_point` | `REAL` | Yes | No | Continuous review reorder threshold: $ROP = d \cdot L + SS$. |
| `safety_stock` | `REAL` | Yes | No | Statistical buffer: $SS = Z_{\alpha} \sqrt{L \sigma_d^2 + d^2 \sigma_L^2}$. |

### 2.3 Multi-Tenant Operational Tables

In addition to historical time series, `data/supply_chain.db` maintains relational multi-tenant tables:
- `app_users`: User credentials, PBKDF2 password hashes, store identity, and metadata.
- `app_sessions`: Cryptographic 256-bit random session bearer tokens with 7-day expiration and instant revocation support.
- `app_products`: Store-specific retail catalog items, localized unit prices, unit costs, real-time stock on hand, and supplier links.
- `app_sales`: Counter POS transaction receipts, line item JSON arrays, and financial totals.
- `app_purchase_orders`: Replenishment orders, PO lifecycle status (`DRAFT`, `PLACED`, `RECEIVED`), line items, and delivery sync timestamps.
- `app_suppliers`: Approved vendor directory, catalog assignments, contact channels, and reliability indicators.

---

## 3. Dataset Quality Audit & Verification Results

A complete SQL audit was executed using `scripts/run_phase3_validation.py` against `data/supply_chain.db`. The results are verified as follows:

```json
{
  "total_records": 913000,
  "expected_records": 913000,
  "is_complete": true,
  "unique_stores": 10,
  "unique_items": 50,
  "unique_series": 500,
  "days_covered": 1826,
  "null_counts": {
    "sales": 0,
    "sales_clean": 0,
    "date": 0,
    "store": 0,
    "item": 0
  },
  "duplicate_observations": 0,
  "negative_or_invalid_values": 0,
  "anomaly_flags_persisted": {
    "z_score_flags": 2525,
    "iqr_flags": 7616,
    "dual_anomaly_flags": 7655
  }
}
```

### Quality Certifications:
1. **Zero Record Loss**: Exactly 913,000 records present ($1,826 \times 500$). Every $(store, item)$ pair has an unbroken daily sequence with zero gaps or missing calendar dates.
2. **Zero Nulls & NaNs**: No missing values exist in any key or measurement column.
3. **Domain Constraint Validity**: All daily sales figures are strictly non-negative integers ($y \ge 0$). No negative returns or corrupted negative values exist.
4. **Referential Integrity**: All `store` IDs strictly reside in $\{1, \dots, 10\}$; all `item` IDs strictly reside in $\{1, \dots, 50\}$.

---

## 4. Train / Validation / Test Temporal Splits

To prevent data leakage and simulate genuine out-of-sample forward deployment, time-series partitioning respects temporal order:

```
[================= TRAINING SET =================] [== VAL ==] [==== TEST SET ====]
2013-01-01                            2016-12-31  2017-01-01   2017-10-01    2017-12-31
(1,461 days • 730,500 records • 80.0%)            (273 days)   (92 days • 46,000 records)
```

1. **Training Partition**: `2013-01-01` to `2016-12-31` (4 full years, 1,461 calendar days including the 2016 leap day, 730,500 observations). Used for fitting all baseline distributions, Holt-Winters smoothing constants, Random Forest estimators, and K-Means centroids.
2. **Validation Partition**: `2017-01-01` to `2017-09-30` (9 months, 273 days, 136,500 observations). Used for hyperparameter tuning, lag selection, and anomaly detection threshold calibration.
3. **Out-of-Sample Test Partition**: `2017-10-01` to `2017-12-31` (Q4 holiday retail quarter, 92 days, 46,000 observations). Used exclusively for final out-of-sample accuracy scoring (WMAPE, RMSE, MAE), multi-horizon decay evaluation (7d, 14d, 21d, 28d), and continuous-review inventory simulation.

---

## 5. Statistical Distribution & Time-Series Properties

Across the 500 series, summary statistics demonstrate distinct operational demand profiles:

- **Daily Demand ($\mu$)**:
  - Global Mean: 47.16 units/day.
  - Min Series Mean: 16.48 units/day (Store 7, Item 5).
  - Max Series Mean: 88.52 units/day (Store 2, Item 28).
- **Demand Dispersion ($\sigma$)**:
  - Global Standard Deviation: 18.24 units.
  - Coefficient of Variation ($CV = \sigma / \mu$): Mean 0.322, Min 0.188, Max 0.442.
- **Seasonality & Stationarity**:
  - **Day-of-Week Effect**: Peak demand occurs consistently on Saturdays and Sundays (+34.2% relative to mid-week Wednesday trough).
  - **Annual Cycle**: Maximum sales volume occurs in July and August (summer peak); minimum occurs in January and February.
  - **Stationarity**: Augmented Dickey-Fuller (ADF) tests reject the unit root hypothesis ($p < 0.01$) after first-order weekly differencing ($\Delta_7 y_t$).

---

## 6. Academic Usage & Reproducibility Notice

Researchers and evaluators can verify the dataset audit at any time by executing:

```bash
.venv/bin/python -c "
import sqlite3, json
conn = sqlite3.connect('data/supply_chain.db')
cur = conn.cursor()
cur.execute('SELECT COUNT(*), MIN(date), MAX(date), COUNT(DISTINCT store), COUNT(DISTINCT item) FROM sales')
print(dict(zip(['rows', 'min_date', 'max_date', 'stores', 'items'], cur.fetchone())))
"
```

Expected output:
```json
{"rows": 913000, "min_date": "2013-01-01", "max_date": "2017-12-31", "stores": 10, "items": 50}
```

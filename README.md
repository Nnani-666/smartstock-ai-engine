# SmartStock — Supply Chain Demand & Inventory Optimization Engine

SmartStock is a production-grade retail inventory optimization backend and analytical engine. It features demand forecasting, automated anomaly detection, SKU ABC/XYZ segmentation, explainable priority-ordered reorder recommendations, and multi-tenant cloud persistence via Supabase.

---

## 1. Project Architecture

The application comprises three primary components:
1. **Frontend (Google Stitch):** Responsive retail POS and merchant interface covering Authentication, Overview, Inventory, Demand Forecasts, Purchase Orders, and Store Settings.
2. **Backend & Analytical Engine (Python / FastAPI):**
   - **DS-1 Demand Forecasting:** Naive, Seasonal Naive, Holt-Winters Exponential Smoothing, and Recursive Random Forest multi-step forecasts.
   - **DS-2 Anomaly Detection:** Weekday-group Z-score and IQR anomaly detection with median replacement and spike injection verification.
   - **AI-2 SKU Segmentation:** K-Means clustering with Silhouette score optimization, ABC volume Pareto classification, and XYZ variability tier mapping.
   - **AI-1 Inventory Decision Engine:** Dynamic safety stock (primary and extended lead-time variance formulas), service levels, reorder point (ROP), days of cover, and explainable replenishment recommendations.
   - **Analytical SQLite Database (`data/supply_chain.db`):** Preserves reproducible historical dataset, experimental evaluation, and stockout policy simulations.
3. **Application Database (Supabase PostgreSQL):** Multi-tenant persistent store for live users, shops, products, stock movements, purchase orders, sales transactions, notifications, and row-level security (RLS) policies.

---

## 2. Quickstart & Installation

### Prerequisites
- Python 3.11 (or $\ge 3.9$)
- SQLite3
- Supabase project credentials (configured in `.env`)

### Local Setup
```bash
# 1. Clone repository and enter directory
cd SMARTSTOCK

# 2. Install virtual environment and dependencies
make install

# 3. Configure environment variables
cp .env.example .env
# Edit .env to add your SUPABASE_URL, SUPABASE_ANON_KEY, and SUPABASE_SERVICE_ROLE_KEY
```

---

## 3. Dataset & Analytical Pipeline

### Kaggle Dataset Download
The analytical engine uses the Kaggle Store Item Demand Forecasting Challenge dataset (913,000 daily sales records across 10 stores and 50 items from 2013-01-01 to 2017-12-31):

1. Download `train.csv` from Kaggle: `kaggle competitions download -c demand-forecasting-kernels-only`
2. Place `train.csv` at: `data/raw/train.csv`
3. If running in a test or evaluation environment without Kaggle credentials, pass `--synthetic` to generate deterministic benchmark data.

### Reproducible Pipeline Execution
Execute the entire pipeline from ingestion to policy simulation with a single command:
```bash
make all
```

Individual step targets:
- `make ingest`: Ingest and validate 913,000 raw sales records into `data/supply_chain.db`.
- `make anomaly`: Execute weekday-group Z-score/IQR anomaly detection and spike injection evaluation.
- `make segment`: Fit K-Means clustering, ABC Pareto, and XYZ variability segmentation.
- `make train`: Train global Random Forest model on 853,500 training rows and save `artifacts/rf_model.joblib`.
- `make evaluate`: Execute 13-origin rolling evaluation across all 4 candidate forecasters.
- `make simulate`: Run 91-day historical stockout policy simulation and write `reports/summary.md`.
- `make test`: Run pytest suite with $\ge 80\%$ coverage enforcement.
- `make lint`: Run Ruff linter.
- `make run`: Launch local FastAPI server on port 8000.

---

## 4. API Endpoints & Curl Examples

Start the backend:
```bash
make run
```
Open interactive Swagger documentation at: `http://localhost:8000/docs`

### Health Check
```bash
curl -s http://localhost:8000/health
```

### List SKUs
```bash
curl -s "http://localhost:8000/skus?abc=A&tier=Strategic&limit=5"
```

### Get Single SKU Record
```bash
curl -s http://localhost:8000/skus/1/1
```

### Demand Forecast (Daily & Weekly)
```bash
curl -s -X POST http://localhost:8000/forecast \
  -H "Content-Type: application/json" \
  -d '{
    "store": 1,
    "item": 1,
    "horizon_days": 14,
    "granularity": "daily",
    "model": "best"
  }'
```

### Historical Anomalies Log
```bash
curl -s "http://localhost:8000/anomalies?store=1&item=1&method=any"
```

### Inventory Replenishment Decision
```bash
curl -s -X POST http://localhost:8000/decision \
  -H "Content-Type: application/json" \
  -d '{
    "store": 1,
    "item": 1,
    "current_stock": 24,
    "on_order": 0,
    "service_level": 0.98,
    "lead_time_days": 5
  }'
```

### Batch Replenishment Decisions (Up to 100 SKUs)
```bash
curl -s -X POST http://localhost:8000/decision/batch \
  -H "Content-Type: application/json" \
  -d '{
    "items": [
      {"store": 1, "item": 1, "current_stock": 24, "on_order": 0},
      {"store": 1, "item": 2, "current_stock": 14, "on_order": 50}
    ]
  }'
```

### Segmentation Summary
```bash
curl -s http://localhost:8000/segments/summary
```

### Model Evaluation Metrics
```bash
curl -s http://localhost:8000/metrics
```

### Live Supabase Products & Insights
```bash
# Live products from Supabase PostgreSQL
curl -s http://localhost:8000/api/v1/products

# Live inventory insights from Supabase PostgreSQL
curl -s http://localhost:8000/api/v1/insights
```

---

## 5. Deployment Guide (Hugging Face Spaces)

The application includes a production-ready `Dockerfile` compatible with Hugging Face Spaces (Docker SDK free CPU tier):

1. Create a new Space on [Hugging Face](https://huggingface.co/spaces) and select **Docker** SDK.
2. Push repository files: `app/`, `artifacts/`, `data/supply_chain.db`, `reports/`, `requirements.txt`, and `Dockerfile`.
3. Set Space Secrets / Environment Variables:
   - `SUPABASE_URL`: `https://txpvoqdecsjpmklelxdb.supabase.co`
   - `SUPABASE_ANON_KEY`: `...`
   - `SUPABASE_SERVICE_ROLE_KEY`: `...`
4. The container exposes port `7860` and will start automatically.

---

## 6. Engineering Assumptions

1. **Lead Time Simulation:** The Kaggle competition dataset records historical customer transactions, omitting warehouse receipts and vendor lead times. Lead times are generated deterministically using the fixed seed (`numpy.random.default_rng(42)`) with mean $\in [2, 10]$ days and standard deviation $\in [0.5, 2.0]$.
2. **Demand Standard Deviation:** Demand variability ($\sigma_d$) is derived from the standard deviation (ddof=1) of cleaned daily sales over the 90 days prior to the evaluation as-of date.
3. **Lost Sales:** Unfulfilled demand during simulated stockout periods is treated as lost sales (no backorders), consistent with convenience retail store patterns.
4. **Data Separation:** SQLite (`data/supply_chain.db`) strictly maintains the academic evaluation dataset and offline experiments, while Supabase PostgreSQL manages live merchant data, stock movements, and user sessions.

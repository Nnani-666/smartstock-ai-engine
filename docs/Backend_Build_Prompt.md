## 1. Role and Goal
You are a senior Python backend and data science engineer. Build the complete backend for the "Supply Chain Demand & Inventory Optimization Engine". It must forecast demand, detect anomalies, segment SKUs, and return rule-based reorder decisions through a REST API. Follow every specification below exactly. Where a value is given, use that value. Do not add features beyond this specification.

## 2. Hard Constraints
- Use only free and open-source tools and free tiers. No paid APIs, paid cloud services, paid databases or GPUs.
- Python 3.11. Training must fit in 4 GB RAM and finish within 60 minutes on a free Google Colab CPU runtime. The API process must run in under 1 GB RAM.
- Allowed model families: Holt-Winters Exponential Smoothing, Random Forest Regression, K-Means. Do not use LSTM, Prophet, SARIMAX, XGBoost or any deep learning library.
- Use the random seed 42 everywhere (numpy, scikit-learn, Python random).
- No placeholders, TODO comments or pseudo-code. Every file must be complete and runnable.
- Type hints and docstrings on every public function. Use the standard logging module, not print, inside the app package.
- Read configuration from `app/config.py`. Never hard-code paths or thresholds inside other modules.

## 3. Technology Stack
| Purpose | Package | Minimum version |
|---|---|---|
| Data handling | pandas, numpy | pandas 2.1, numpy 1.26 |
| Statistics | scipy | 1.11 |
| Machine learning | scikit-learn | 1.4 |
| Holt-Winters | statsmodels | 0.14 |
| Model persistence | joblib | 1.3 |
| API | fastapi, uvicorn[standard], pydantic | fastapi 0.110, pydantic 2 |
| Database | sqlite3 (standard library) | n/a |
| Testing and linting | pytest, pytest-cov, httpx, ruff | latest |
| Dataset download (optional) | kaggle | latest |

After the first successful install, write exact pinned versions to `requirements.txt` (use `pip freeze` output for the packages above only).

## 4. Dataset and Ingestion
- Source: Kaggle competition "Store Item Demand Forecasting Challenge" (slug `demand-forecasting-kernels-only`), file `train.csv`, placed at `data/raw/train.csv`. Columns: date, store (1 to 10), item (1 to 50), sales. Expected 913,000 rows, dates 2013-01-01 to 2017-12-31.
- `scripts/01_ingest.py` must: validate the row count, the date range, the absence of nulls and that sales are non-negative integers; fail with a clear message otherwise.
- Define `sku_id` as `S{store:02d}-I{item:02d}` (example: S01-I01).
- Simulate lead times with `numpy.random.default_rng(42)`. Iterate SKUs sorted by (store, item). For each SKU draw `lead_time_mean` as an integer uniform on 2 to 10 inclusive and `lead_time_std` as a float uniform on 0.5 to 2.0 rounded to 2 decimals. Store them in `sku_master`.
- Write everything to SQLite at `data/supply_chain.db`.
- Key dates (put in config): `TRAIN_END = 2017-10-01`, `TEST_START = 2017-10-02`, `TEST_END = 2017-12-31`, `LAST_DATA_DATE = 2017-12-31`.

## 5. Repository Structure
Create exactly this layout:
```
supply-chain-engine/
  app/
    __init__.py
    config.py
    db.py
    schemas.py
    main.py
    services/
      __init__.py
      anomaly.py
      features.py
      forecasting.py
      segmentation.py
      safety_stock.py
      rules.py
      decision.py
      simulation.py
  scripts/
    01_ingest.py
    02_anomaly.py
    03_segment.py
    04_train_forecast.py
    05_evaluate.py
    06_simulate_stockouts.py
  tests/
    conftest.py
    test_anomaly.py
    test_safety_stock.py
    test_rules.py
    test_segmentation.py
    test_forecasting.py
    test_api.py
  data/raw/            (git-ignored)
  data/supply_chain.db
  artifacts/           (rf_model.joblib, metrics.json, segments.json)
  reports/summary.md
  .github/workflows/ci.yml
  Dockerfile
  Makefile
  requirements.txt
  README.md
  .gitignore
```

## 6. Database Schema
Tables in `data/supply_chain.db`. Create indexes as stated.

| Table | Columns | Index |
|---|---|---|
| sales | store INTEGER, item INTEGER, date TEXT (YYYY-MM-DD), sales INTEGER, sales_clean REAL, z_score REAL, z_flag INTEGER, iqr_flag INTEGER, is_anomaly INTEGER | PRIMARY KEY (store, item, date) |
| sku_master | sku_id TEXT PRIMARY KEY, store INTEGER, item INTEGER, lead_time_mean INTEGER, lead_time_std REAL, mean_daily REAL, cv REAL, seasonality_amp REAL, cluster INTEGER, abc TEXT, xyz TEXT, tier TEXT | UNIQUE (store, item) |

`scripts/01_ingest.py` creates and fills `sales` (with `sales_clean = sales` and flags 0 initially) and the lead time columns of `sku_master`. Later scripts update the remaining columns.

## 7. Module Specifications

### 7.1 Anomaly detection (`services/anomaly.py`, `scripts/02_anomaly.py`) for DS-2
- Group key: (store, item, weekday) where weekday is 0 to 6.
- Fit per group on rows with date up to TRAIN_END only: mean, standard deviation (ddof=1), Q1, Q3, median.
- Z-score: `z = (sales - mean) / std`. If std is 0, set z to 0. `z_flag = abs(z) > 3.0`.
- IQR: `iqr = Q3 - Q1`; `iqr_flag = sales < Q1 - 1.5*iqr or sales > Q3 + 1.5*iqr`.
- `is_anomaly = z_flag OR iqr_flag`.
- Apply the fitted statistics to all rows (train and test).
- `sales_clean = group median` where `is_anomaly = 1`, otherwise `sales`. The raw `sales` column is never modified.
- Persist flags, z_score and sales_clean to the `sales` table.
- Spike injection test (function `evaluate_injection`): copy the data; choose 1% of rows with `sales >= 5` using `default_rng(42)`; replace each chosen value with `round(sales * m)` where m is uniform on 2.5 to 5.0; refit the group statistics on the injected copy's training window (this is the worst case); detect; compute recall, precision, and the false-positive rate on the original un-injected data. Write results to `artifacts/metrics.json` under the key `anomaly`.

### 7.2 Features (`services/features.py`)
Build the Random Forest feature frame from `sales_clean`, per series sorted by date. All lag and rolling features use `shift(1)` so the current day is never included.

| Feature | Definition |
|---|---|
| store, item | integers |
| dow, month, day_of_month, week_of_year | calendar fields |
| is_weekend | 1 if dow in (5, 6) |
| lag_1, lag_2, lag_3, lag_7, lag_14, lag_21, lag_28 | sales_clean lagged |
| roll_mean_7, roll_mean_14, roll_mean_28 | rolling mean of the shifted series |
| roll_std_7, roll_std_28 | rolling standard deviation (ddof=1) of the shifted series |

Drop rows with any NaN feature (the first 28 days of each series). Use float32.

### 7.3 Forecasting (`services/forecasting.py`, `scripts/04_train_forecast.py`) for DS-1
**Baselines**
- Naive: forecast for every horizon day = last observed `sales_clean` value.
- Seasonal naive: forecast for horizon day h = `sales_clean` at (origin - 7 + ((h - 1) mod 7) + 1 days back), i.e. the same weekday in the previous week.

**Holt-Winters**
- `statsmodels.tsa.holtwinters.ExponentialSmoothing(y + 1, trend="add", damped_trend=True, seasonal="mul", seasonal_periods=7)`, fitted on the last 730 days before the origin with `use_boxcox=False`, `.fit(optimized=True)`. The +1 offset avoids zeros for the multiplicative term; subtract 1 from the forecast and clip at 0.
- If the fit raises, or any forecast is not finite, fall back to seasonal naive for that series and log a warning.
- Suppress statsmodels convergence warnings with `warnings.catch_warnings`.
- Use `joblib.Parallel(n_jobs=2)` for the batch evaluation. API requests fit one series and cache the result with `functools.lru_cache(maxsize=512)` keyed by (store, item, origin_date).

**Random Forest**
- One global model: `RandomForestRegressor(n_estimators=100, max_depth=12, min_samples_leaf=20, max_features=0.5, n_jobs=-1, random_state=42)`.
- Train on rows dated 2013-01-29 to TRAIN_END, target `sales_clean`.
- Save with `joblib.dump(model, "artifacts/rf_model.joblib", compress=3)`. The file must be at most 60 MB; if larger, reduce `n_estimators` to 60 and record the change.
- Multi-step forecasting is recursive: predict day 1, append the prediction as that day's `sales_clean`, rebuild lag and rolling features, predict day 2, and so on. Clip predictions at 0.
- Provide a batched recursive function that forecasts all 500 series at once (one `predict` call per horizon day) for evaluation, and a single-series version for the API.

**Evaluation** (`scripts/05_evaluate.py`)
- Rolling origin: 13 origins, first origin 2017-10-02, then every 7 days (last origin 2017-12-25). At each origin use only data before the origin date, forecast 7 days, and score against raw `sales`.
- Models scored: naive, seasonal_naive, holt_winters, random_forest.
- Metrics, pooled over all series, origins and days: RMSE, MAE. Also weekly totals: sum each 7-day forecast and actual per series per origin, then RMSE and MAE.
- Improvement = `(baseline - model) / baseline`. Report improvement versus naive (acceptance baseline) and versus seasonal naive (informational).
- `best_model` is the model among holt_winters and random_forest with the lowest daily RMSE.
- Acceptance: best model improves both RMSE and MAE by at least 0.15 versus naive. Record `passed: true/false`.
- Write results to `artifacts/metrics.json` under `forecasting`. Provide a `--series-limit N` flag that restricts to the first N series for quick development runs.

### 7.4 Segmentation (`services/segmentation.py`, `scripts/03_segment.py`) for AI-2
- Per SKU, using `sales_clean` up to TRAIN_END: `mean_daily`; `cv = std(ddof=1) / mean`; `seasonality_amp = (max weekday mean - min weekday mean) / mean_daily`.
- Features: `log1p(mean_daily)`, `cv`, `seasonality_amp`. Standardise with `StandardScaler`.
- For k in 2..6 fit `KMeans(n_clusters=k, n_init=20, random_state=42)`; compute `silhouette_score` (euclidean) on the scaled features; choose the k with the highest score. Report all scores.
- If the best silhouette is below 0.50, also repeat the search with only `log1p(mean_daily)` and `cv`, report both results, and use whichever scores higher. Do not change anything else to chase the target. Record `passed: true/false`.
- ABC: sort SKUs by total training volume descending; cumulative share up to 80% = A, up to 95% = B, remainder = C.
- XYZ: `cv` up to 0.5 = X, up to 1.0 = Y, above 1.0 = Z. If more than 90% of SKUs land in one XYZ class, switch to tertiles of `cv` (lowest third X, middle Y, highest Z), and record `xyz_method` as `"tertile"` instead of `"fixed"`.
- Tier mapping on the ABC+XYZ code: Strategic = AX, AY, BX; Core = AZ, BY, CX; Tail = BZ, CY, CZ.
- Write cluster, abc, xyz, tier, mean_daily, cv and seasonality_amp to `sku_master`. Write the silhouette scores, chosen k, cluster sizes and `xyz_method` to `artifacts/segments.json` and `artifacts/metrics.json` under `segmentation`.

### 7.5 Safety stock (`services/safety_stock.py`)
- `z_value(service_level) = scipy.stats.norm.ppf(service_level)`.
- Primary formula: `SS = Z * sigma_d * sqrt(L)`.
- Extended formula (reported only): `SS_ext = Z * sqrt(L * sigma_d^2 + d_bar^2 * sigma_L^2)`, where `d_bar` is mean daily forecast and `sigma_L` is `lead_time_std`.
- `sigma_d` is the standard deviation (ddof=1) of `sales_clean` over the 90 days up to and including the as-of date.
- Service levels by ABC class: A 0.98, B 0.95, C 0.90. A request-supplied service level (0.50 to 0.999) overrides.
- Round `SS` up with `math.ceil`.
- Unit-test anchor: service_level 0.95, sigma_d 10, L 9 gives SS = ceil(1.6449 * 10 * 3) = 50.

### 7.6 Rule engine (`services/rules.py`, `services/decision.py`) for AI-1
Implement rules as data: a `Rule` dataclass with `rule_id`, `priority_order`, `condition` (callable on a context object), `action`, and `explanation_template`. The engine evaluates rules in ascending `priority_order` and returns the first match.

Context values, computed in `decision.py`:
- `L` = request `lead_time_days` if given, else `max(1, round(lead_time_mean))`.
- Forecast the next L days with the best model from the day after `as_of_date`. `lead_time_demand` = sum of those L forecasts. `mean_daily_forecast = lead_time_demand / L`.
- `SS` from 7.5. `ROP = ceil(lead_time_demand) + SS`.
- `inventory_position = current_stock + on_order`.
- `days_of_cover = current_stock / mean_daily_forecast` (if the forecast is 0, use 9999).

| Order | Rule id | Condition | Action |
|---|---|---|---|
| 1 | R1_EXPEDITE | inventory_position <= ROP AND on_order > 0 AND days_of_cover < L | EXPEDITE_SHIPMENT |
| 2 | R2_REORDER | inventory_position <= ROP | REORDER_NOW |
| 3 | R3_HOLD | otherwise | HOLD_STOCK |

Priority label:
- HOLD_STOCK: LOW.
- EXPEDITE_SHIPMENT: CRITICAL.
- REORDER_NOW: CRITICAL if days_of_cover < L; else HIGH if abc is A; else NORMAL.

Recommended order quantity:
- REORDER_NOW only: `order_up_to = ROP + ceil(mean_daily_forecast * 7)`; `qty = max(0, ceil(order_up_to - inventory_position))`.
- Otherwise 0.

Also return `overstock_flag = inventory_position > 2 * ROP`.

The `explanation` string must quote the numbers used, for example: "Inventory position 140 is at or below the reorder point 152 (lead-time demand 119 + safety stock 33); 2.4 days of cover is below the 6-day lead time, so reorder now."

### 7.7 Stockout simulation (`services/simulation.py`, `scripts/06_simulate_stockouts.py`) for AI-1 evaluation
- Window: 2017-10-02 to 2017-12-31 (91 days), all 500 SKUs, actual raw `sales` as demand.
- Order quantity for both policies: `Q = ceil(d90 * 14)`, where `d90` is mean `sales_clean` over the 90 days before 2017-10-02.
- Initial on-hand for both policies: `ceil(d90 * (L + 14))`, with `L = max(1, round(lead_time_mean))`.
- Static policy: `ROP_static = ceil(d90 * L)` (no safety stock), fixed for the whole window.
- Dynamic policy: ROP recomputed on each weekly origin (13 origins) using 7.5 and 7.6 with the best model and with the ABC service level; held constant during that week.
- Daily loop per SKU: receive arriving orders; if demand exceeds on-hand, record a stockout day and fulfil only on-hand (lost sales, no backorders); subtract demand; if inventory position is at or below ROP and nothing is on order, place an order of Q; its realised lead time is `max(1, round(N(lead_time_mean, lead_time_std)))`, drawn from `default_rng(42)` in a fixed SKU and order sequence, using the same draws for both policies.
- Metrics per policy: total stockout days, fill rate (fulfilled / total demand), mean on-hand inventory.
- Reduction = `(static_stockout_days - dynamic_stockout_days) / static_stockout_days`. Acceptance: at least 0.20. Report the increase in mean on-hand inventory as the cost of the improvement. Write to `artifacts/metrics.json` under `inventory_simulation` with `passed: true/false`.

## 8. API Specification (`app/main.py`, `app/schemas.py`)
- FastAPI app titled "Supply Chain Demand & Inventory Optimization Engine", version "1.0.0". Swagger UI at `/docs`.
- Use a lifespan handler to load the Random Forest model, `sku_master`, and `metrics.json` once at startup. Open SQLite read-only (`file:...?mode=ro`, `uri=True`) with one connection per request.
- Validate all input with Pydantic v2 models. Validation failures return 422. Unknown SKU returns 404. Body of errors: `{"detail": "..."}`.
- Optional API key: if the environment variable `API_KEY` is set, require header `X-API-Key` on every route except `/health`, otherwise 401. If unset, no authentication.
- Bounds: store 1 to 10, item 1 to 50.

| Method and path | Purpose | Details |
|---|---|---|
| GET /health | Liveness | `{"status": "ok", "last_data_date": "2017-12-31", "models_loaded": true}` |
| GET /skus | List SKUs | Query: store, item, abc, xyz, tier, cluster, limit (default 50, max 500), offset (default 0) |
| GET /skus/{store}/{item} | One SKU | All `sku_master` fields |
| POST /forecast | Demand forecast | See below |
| GET /anomalies | Anomaly log | Query: store (required), item (required), start, end (YYYY-MM-DD), method = z, iqr or any (default any). Returns rows with date, sales, z_score, z_flag, iqr_flag |
| POST /decision | Reorder decision for one SKU | See below |
| POST /decision/batch | Up to 100 decisions | Body `{"items": [decision requests]}`; returns a list in the same order; over 100 returns 422 |
| GET /segments/summary | Segmentation summary | Contents of `segments.json` plus counts by abc, xyz, tier |
| GET /metrics | Evaluation results | Contents of `artifacts/metrics.json` |

**POST /forecast request**
```
{
  "store": 1,
  "item": 1,
  "horizon_days": 14,
  "granularity": "daily",
  "model": "best"
}
```
- horizon_days: integer 1 to 28. granularity: `daily` or `weekly`. model: `holt_winters`, `random_forest` or `best`.
- Weekly granularity requires horizon_days to be a multiple of 7 (otherwise 422); each weekly value is the sum of 7 consecutive daily forecasts.
- Forecast starts the day after `LAST_DATA_DATE`.

**POST /forecast response**
```
{
  "sku_id": "S01-I01",
  "model": "random_forest",
  "granularity": "daily",
  "history_end": "2017-12-31",
  "forecasts": [ {"date": "2018-01-01", "yhat": 19.3} ]
}
```
Round `yhat` to 2 decimals.

**POST /decision request**
```
{
  "store": 1,
  "item": 1,
  "current_stock": 120,
  "on_order": 0,
  "service_level": null,
  "lead_time_days": null,
  "as_of_date": null
}
```
- current_stock and on_order: integers at or above 0 (on_order defaults to 0). lead_time_days: integer 1 to 60 or null. as_of_date: null (uses `LAST_DATA_DATE`) or a date between 2013-03-01 and 2017-12-31.

**POST /decision response**
```
{
  "sku_id": "S01-I01",
  "as_of_date": "2017-12-31",
  "abc": "A",
  "xyz": "X",
  "tier": "Strategic",
  "lead_time_days": 6,
  "service_level": 0.98,
  "z_value": 2.054,
  "mean_daily_forecast": 19.8,
  "lead_time_demand": 119,
  "sigma_d": 5.6,
  "safety_stock": 29,
  "safety_stock_extended": 33,
  "reorder_point": 148,
  "inventory_position": 120,
  "days_of_cover": 6.1,
  "action": "REORDER_NOW",
  "priority": "HIGH",
  "recommended_order_qty": 168,
  "overstock_flag": false,
  "triggered_rule": "R2_REORDER",
  "explanation": "..."
}
```
The numbers above are illustrative; compute real values. Round floats to 2 decimals except `z_value` (3 decimals).

## 9. Performance, Logging and Reproducibility
- p95 latency on a local run: under 500 ms for POST /decision (single), under 1 s for POST /forecast with the Random Forest, under 2 s with Holt-Winters on a cold cache.
- `Makefile` targets: `install`, `ingest`, `anomaly`, `segment`, `train`, `evaluate`, `simulate`, `all` (runs ingest through simulate in order), `test`, `lint`, `run` (`uvicorn app.main:app --host 0.0.0.0 --port 8000`).
- Scripts must be idempotent: rerunning replaces previous results and gives identical numbers.
- `scripts/06_simulate_stockouts.py` also writes `reports/summary.md`: a table of every success metric with value, target and pass or fail, plus the assumptions list (simulated lead times, replaced order frequency feature, any fallback triggered).

## 10. Testing
- pytest with `--cov=app --cov-fail-under=80`.
- Tests use a small synthetic fixture built in `conftest.py` (5 series, 120 days, seed 42, a temporary SQLite file). They must not need the Kaggle dataset or the trained model file; train a tiny Random Forest (n_estimators=5) inside the fixture.
- Required tests:
  - Anomaly: an injected value of 10 times the mean is flagged; group statistics ignore rows after TRAIN_END; `sales` is never mutated.
  - Safety stock: the unit-test anchor in 7.5; the service-level override; the extended formula.
  - Rules: one case each for R1, R2 and R3; the priority labels; the order quantity; the overstock flag.
  - Segmentation: ABC thresholds at 80% and 95%; XYZ boundaries; tier mapping; the tertile fallback.
  - Forecasting: naive and seasonal naive on a hand-computed example; Random Forest features never use the current day; forecasts are non-negative; the Holt-Winters fallback triggers on a constant zero series.
  - API: 200 on valid calls to every route; 422 on invalid bounds and on weekly horizon not a multiple of 7; 404 on an unknown SKU; 401 when `API_KEY` is set and the header is missing.

## 11. Deployment and CI (free tier)
- `Dockerfile`: base `python:3.11-slim`; copy `requirements.txt` and install with `--no-cache-dir`; copy `app/`, `artifacts/` and `data/supply_chain.db`; create a non-root user; expose port 7860; command `uvicorn app.main:app --host 0.0.0.0 --port 7860`. This matches Hugging Face Spaces (Docker SDK, free CPU tier).
- Commit `data/supply_chain.db` and `artifacts/rf_model.joblib` with Git LFS if either exceeds 50 MB. Never commit `data/raw/`.
- `.github/workflows/ci.yml` (GitHub Actions): on push and pull request, set up Python 3.11, cache pip, install requirements, run `ruff check .` and `pytest`.
- README must contain: project overview, setup, how to download the Kaggle file, `make all`, how to run the API, a curl example for each endpoint, deployment steps for Hugging Face Spaces, and the assumptions list.

## 12. Build Order and Output Format
Build in these phases. After each phase, show every file in full under a heading with its path, then list the exact commands to run and the expected output.
1. Config, database layer, ingestion, and tests for ingestion.
2. Anomaly detection (DS-2) with the injection evaluation.
3. Segmentation (AI-2).
4. Features and forecasting (DS-1), training and evaluation.
5. Safety stock, rule engine, decision service (AI-1).
6. Stockout simulation and the summary report.
7. API, remaining tests, Dockerfile, CI, README.

## 13. Definition of Done
- `make all` runs end to end and writes `artifacts/metrics.json` and `reports/summary.md`.
- `make test` passes with at least 80% coverage; `ruff check .` is clean.
- Forecast improvement is at least 15% versus naive, anomaly recall is at least 90%, simulated stockout-day reduction is at least 20%, silhouette is at least 0.50. If any target is missed, report the actual number and the reason in `reports/summary.md`; never alter thresholds, data or seeds to make a target pass.
- The API runs locally with `make run` and every route in section 8 responds as specified.
- State every assumption you made that this prompt did not cover.

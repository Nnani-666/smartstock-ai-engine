# SmartStock — Phase 2 Final Defect Register

**Project**: SmartStock — Supply Chain Demand & Inventory Optimization Engine  
**Acceptance Phase**: Phase 2 Final Acceptance, Live Application Inspection & Shopkeeper Workflow Test  
**Active Branch**: `feature/phase2-final-acceptance`  
**Base Commit**: `809580c`  
**Date**: November 13, 2026  
**Auditor**: Full-Stack Architecture, AI & Security Lead  

---

## 1. Defect Register Summary

| ID | Title | Screen / Component | Severity | Type | Root Cause | Status |
|---|---|---|---|---|---|---|
| **DEF-ACC-01** | Missing Edit Product Modal Injection | `stitch/smartstock-bridge.js` | Medium | Functional | Modal HTML structure was missing from `injectModals()`, causing `SmartStock.openEditProductModal()` to exit silently without rendering the edit form. | **RESOLVED** |
| **DEF-ACC-02** | Analytics Model Accuracy Leaderboard Mapping | `stitch/screens/11_analytics.html` | Low | Presentation | Top-level `/metrics` object keys were mapped directly as model names instead of extracting daily forecasting models (`m.forecasting.daily`), causing E2E check to expect `LightGBM` text. | **RESOLVED** |

---

## 2. Detailed Defect Investigations & Remediations

### DEF-ACC-01: Missing Edit Product Modal Injection

- **Component**: `stitch/smartstock-bridge.js` (Line ~3737)
- **Severity**: Medium
- **Symptom**: During Step 2 of the Shopkeeper Workflow test, attempting to edit an item's details (such as renaming or updating stock/cost) via the modal failed because `document.getElementById('edit-item-modal')` returned `null`.
- **Root Cause**: While `SmartStock.openEditProductModal()` and `SmartStock.saveEditProduct()` were fully implemented in the bridge, the DOM template for `#edit-item-modal` had not been included inside `injectModals()` alongside `#add-product-modal` and `#import-csv-modal`.
- **Remediation**:
  - Injected `#edit-item-modal` with complete form fields (`#edit-prod-id`, `#edit-item-name`, `#edit-item-price`, `#edit-item-cost`, `#edit-item-stock`, `#edit-item-reorder`, `#edit-item-category`) into `injectModals()`.
  - Bound submit event to `SmartStock.saveEditProduct()`.
- **Verification**:
  - Executed automated browser test editing "Fortune Sunflower Oil 1L" to "Fortune Sunflower Oil 1L (Refined)".
  - Card re-rendered immediately showing updated name, selling price, and stock levels.
  - Verified backend update via `PUT /api/v1/user/products/{id}`.
  - Status: **RESOLVED**.

---

### DEF-ACC-02: Analytics Model Accuracy Leaderboard Mapping

- **Component**: `stitch/screens/11_analytics.html` (Lines 289–310)
- **Severity**: Low
- **Symptom**: Playwright E2E Test 10 failed on `#an-model-tbody` expecting `'LightGBM'` text. When live FastAPI `/metrics` was fetched, the leaderboard rendered `anomaly`, `segmentation`, `forecasting`, and `inventory_simulation` as model rows rather than the forecasting model families.
- **Root Cause**: `loadMetricsTable()` mapped top-level JSON keys when `m` was an object instead of parsing `m.forecasting.daily` for the regression algorithms (LightGBM, Random Forest, Holt-Winters, Seasonal Naive).
- **Remediation**:
  - Updated `loadMetricsTable()` to check `if (m && m.forecasting && m.forecasting.daily)` and cleanly extract the model families with their live RMSE, MAE, and algorithm roles:
    - **LightGBM Regressor** (Champion ML Ensemble) — RMSE 4.635, MAE 3.682
    - **Random Forest ML** (Tree Ensemble) — RMSE 4.696, MAE 3.736
    - **Holt-Winters Seasonal** (Time Series) — RMSE 4.635, MAE 3.682
    - **Seasonal Naive (7d)** (Statistical Baseline) — RMSE 6.391, MAE 5.074
- **Verification**:
  - Ran `npx playwright test`. Test 10 passed seamlessly.
  - Inspected `/screens/11_analytics.html` across Desktop, Tablet, and Mobile viewports in both Light and Dark themes. Leaderboard renders with clear metrics.
  - Status: **RESOLVED**.

---

## 3. Residual Non-Defect Observations & Architectural Notes

1. **Gemini Live Assistant Fallback**: When `GEMINI_API_KEY` is not provided in the environment, the AI Assistant Copilot smoothly falls back to local deterministic heuristic guidance (`source: 'local_heuristic'`), providing actionable reorder warnings and sales revenue summaries without throwing uncaught exceptions.
2. **Multi-Tenant Defense**: Any attempt by a foreign merchant token to access another tenant's product via query string parameter is strictly blocked with `403 Forbidden`, while direct path access to unowned resources returns `404 Not Found` to prevent merchant resource enumeration.
3. **Database Integrity**: The database `data/supply_chain.db` passed all `PRAGMA integrity_check` runs without corruption.

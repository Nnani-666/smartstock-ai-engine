# SmartStock — Phase 2 Implementation Report
**Branch:** `feature/phase2-premium-editorial-ui`  
**Phase Status:** Implemented & Verified (Pending User Approval for Merge / Phase 3)  
**Design System:** Option 2 — Premium Editorial (`Newsreader` + `Hanken Grotesk` + `JetBrains Mono`)  
**Themes:** Warm Parchment & Pine Ink (Light) • Deep Forest Obsidian & Ivory Sage (Dark)

---

## 1. Executive Summary
Phase 2 transformed SmartStock from an incomplete 6-screen static UI into a cohesive, commercially styled, 12-screen (+ Hub) retail inventory and supply chain intelligence platform (`stitch/`), synchronized across desktop web, mobile responsive viewports (`390px`), iOS (`SmartStock/stitch/`), and Android (`SmartStockAndroid/app/src/main/assets/stitch/`).

Key accomplishments:
- **Bespoke Individual Screen Architectures:** Replaced cloned card boilerplate with workflow-specific layouts for all 12 core views (Split Manifesto Auth, Morning Briefing Overview, Two-Pane Inventory Workbench + Inspector, Quick-Tap POS & Billing Ledger, Chart-Led Time-Series Forecasting, Procurement & PO Progress Desk, Urgency-Triaged Replenishment Lanes, Statistical Anomaly Surveillance, Interactive 3×3 ABC–XYZ + K-Means Studio, Grounded Store Advisor, Analytics & Simulation Lab, and Suppliers Directory).
- **Two-Level Intelligence:** Implemented an instant global header toggle (`Business` vs. `Academic`) persisted in `localStorage` (`smartstock_intelligence_mode`) that switches contextual guidance, telemetry attribution, statistical diagnostics (`Z-Score`, `IQR`, `RMSE`, `MAE`, `(s, S)` equations), and plain-English shopkeeper takeaways using the same underlying backend/store data.
- **Stage E Backend Parity & Hardening:** Added full tenant-isolated product CRUD (`PUT`, `DELETE`, `POST /bulk-stock`), atomic `category_name` migration (`init_db`), and PO status progression (`PATCH /api/v1/user/purchase-orders/{po_id}/status`), plus SQLite WAL mode and `BEGIN IMMEDIATE` transaction hardening.

---

## 2. Files Added & Modified

### Design Foundation & Navigation Shell
- `stitch/editorial-theme.css` — Light/Dark CSS custom properties, typography utilities, `.ed-sheet`/`.ed-well`/`.ed-btn-*`/`.ed-badge-*`, Two-Level Intelligence visibility rules (`.biz-only` / `.tech-only`), dark-mode Tailwind compatibility rules, and zero-lag theme swap styling.
- `stitch/editorial-shell.js` — Unified responsive sidebar drawer (`#side-drawer`), masthead with `Business`/`Academic` and `Light`/`Dark` toggles, store switcher pill, notification counter, and mobile bottom quick bar.
- `stitch/index.html` — Preview Hub updated with all 13 screen launchers and Mobile (`390×844`) vs Desktop (`1280×860`) viewport switcher.

### 12 Application Screens (`stitch/screens/`)
1. `01_signin.html` — Split editorial manifesto + clean Register / Sign In sheet with demo credential helper and Light/Dark toggle.
2. `02_overview.html` — Morning Register Briefing asymmetric hero (`7:5`), Urgent Attention Digest, Health Split (`Healthy` / `Low` / `Out`), Next Steps cards, Store Advisor Digest, and Live Floor Activity.
3. `03_inventory.html` — Two-pane Catalog Workbench (`#inventory-list` + bulk action bar + 6 operational filter pills) paired with sticky SKU Detail Inspector (`#sku-inspector`).
4. `04_forecasts.html` — Chart-led Time-Series Workbench connected to `POST /forecast` and `GET /metrics` (models: `best`, `random_forest`, `holt_winters`; horizons: 7/14/21/28d; Daily/Weekly grouping) with deterministic offline projection fallback, P10–P90 confidence ribbon, and interactive Order Calculator.
5. `05_purchase_orders.html` — Procurement & Receiving Desk with status filters, auto-draft banner, 3-step visual progress tracker (`Ordered -> In Transit -> Stocked In`), transit/cancel transitions, and inward receiving.
6. `05_replenishment.html` — Urgency-Triage Reorder Workspace (`R1_EXPEDITE`, `R2_REORDER`, `R3_HOLD`) with sticky batch dispatch bar.
7. `06_settings.html` — Merchant profile, Light/Dark & Intelligence Mode controls, Low-Stock Threshold stepper, CSV export/import, sample Kirana loader, store switcher, and sign out.
8. `07_sales.html` *(New)* — Dual-zone Speed POS Terminal with category shelf, stock-locked product tiles, paise-exact cart checkout (`cash`/`UPI`/`card`), instant receipt card, and unclipped Sales History Ledger + sanitized CSV export.
9. `08_anomalies.html` *(New)* — Anomaly Surveillance connected to `GET /anomalies` (`any`, `z`, `iqr`) with SVG spike strip, peak `|Z|`, dual-confirmed counts, and Business vs Academic diagnostic table.
10. `09_segmentation.html` *(New)* — Portfolio Studio combining interactive 3×3 ABC–XYZ matrix cards, K-Means scatter SVG highlighting matching segments, Silhouette `0.5847` KPI, and filterable `/skus` registry table.
11. `10_assistant.html` *(New)* — Dedicated Conversational Store Advisor backed by `POST /api/v1/ai/assistant` with store snapshot context, quick prompt presets, provenance badges, and XSS-safe rendering.
12. `11_analytics.html` *(New)* — Live Measured Tenant Financials (revenue, gross profit, cost valuation, category bars, top sellers) strictly separated from the 500-SKU Benchmark Simulation (`54.03%` stockout reduction & model leaderboard).
13. `12_suppliers.html` *(New)* — Suppliers Directory tracking wholesale partners, average lead times, committed PO spend, Add Supplier modal, and one-tap PO issuance.

### Backend & Bridge Parity
- `app/db.py` — Enabled `PRAGMA journal_mode=WAL;` in `init_db()` and additive `category_name` column migration on `app_products`.
- `app/main.py` — Implemented Stage E routes (`PUT /api/v1/user/products/{product_id}`, `DELETE /api/v1/user/products/{product_id}`, `POST /api/v1/user/products/bulk-stock`, `PATCH /api/v1/user/purchase-orders/{po_id}/status`) plus concurrency hardening (`BEGIN IMMEDIATE` inside `update_user_product`, `update_user_po_status`, and `record_user_sale` idempotency/product checks, duplicate ID deduplication in `bulk_update_stock`, strict `POCreateRequest.status` literals, and UTC normalization on `req.timestamp`).
- `stitch/smartstock-bridge.js` — Wired new endpoints (`updatePOStatus`, `deleteProduct`, `saveEditProduct`, `bulkDelete`, `bulkAddStock`, analytical/assistant wrappers), preserved full >30 / `0` reorder points, normalized `"Today"`/`"Today (Live)"` filtering, synced PO IDs (`id: newPO.id`), avoided legacy DOM overwrites on upgraded pages, and escaped dynamic DOM sinks (`escapeHtml`).
- Mobile Bundles — Synced all `stitch/` assets identically to `SmartStock/stitch/` and `SmartStockAndroid/app/src/main/assets/stitch/`.

---

## 3. CodeRabbit Phase 2 Security & Quality Audit Disposition
The `CodeRabbit Phase 2 Reviewer` subagent (`ab611287-21f2-4c49-b156-0cc805557c57`) inspected the Phase 2 branch diff:
- **Fixed in Phase 2 Before Closure:**
  - All Phase 2 DOM XSS sinks (`filter`, `activeFilter`, `critical_risks`, `recommendations`, `/metrics` table, SVG labels) escaped with `escapeHtml()`.
  - `/forecast` request/response schema contract (`best`/`random_forest`/`holt_winters`, `res.forecasts || res.forecast`, `yhat ?? predicted_sales`).
  - SQLite WAL mode + `BEGIN IMMEDIATE` atomicity across `update_user_product`, `update_user_po_status` (blocks cancelled/completed transitions), and `record_user_sale` idempotency checks.
  - `bulk_update_stock` deduplication, `POCreateRequest.status` validation, `bulkDelete` backend `DELETE` calls, and PO ID synchronization across replenishment drafts.
  - UI parity bugs across Overview Gross Profit/PO spend, POS `"Today"` filter, Segmentation `mean_daily`, Assistant `gemini-2.5-flash` source badge, Suppliers `hub` lookup, Settings CSV export, and Sign-In `--status-danger-soft` CSS token.
- **Architectural / Production Scope Notes (Carry-Forward to Phase 3 / Deployment):**
  - Offline `localStorage` fallback session behavior (retained intentionally for standalone UI/Playwright static testing without a live FastAPI server; production deployments should enforce backend-issued JWT/session verification and disable offline password fallback).
  - Analytical routes (`/skus`, `/forecast`, `/anomalies`, `/segments/summary`, `/metrics`) enforce `X-API-Key` when `API_KEY` or `ENVIRONMENT=production` is configured; Phase 3 should propagate authenticated session/API keys cleanly when tightening analytical routes in production.
  - Supabase helper endpoints (`/api/v1/products`, `/insights`, `/purchase-orders`, `/shop`) require tenant scoping inside `SupabaseAppService` when live Supabase sync is enabled in production.
  - Third-party CDN scripts (`cdn.tailwindcss.com`, `supabase-js`) should be self-hosted or pinned with SRI/CSP in Phase 5 production hardening.

# SmartStock — Multi-Phase Development Roadmap (.planning/ROADMAP.md)

## Milestone Overview

| Phase | Title | Focus Area | Status | Target Timeline |
|---|---|---|---|---|
| **Phase 0** | **Baseline Protection, Recovery & System Audit** | Git baselines, hot backups, 360-degree audit, test verification | **COMPLETED** | Day 0 |
| **Phase 1** | **Security Hardening & Multi-Tenant Data Isolation** | API auth, JWT/session tokens, PBKDF2 hashing, RLS | **COMPLETED** | Phase 1 |
| **Phase 2** | **Commercial UI/UX Redesign & Two-Level Intelligence** | 12-screen Editorial system, Light/Dark, Business vs Academic, CRUD parity | **COMPLETED** | Phase 2 |
| **Phase 3** | **AI/DS Pipeline Verification & Real Data Connectors** | Model inference APIs, feature store, dynamic simulation | Planned | Phase 3 |
| **Phase 4** | **Business Intelligence, Seasonal Demand & Lead-Time Analytics** | Stockout risk, dead stock insights, vendor performance | Planned | Phase 4 |
| **Phase 5** | **Production QA, Full E2E Suite & Academic Demonstration** | Complete Playwright coverage, performance audits, demo guide | Planned | Phase 5 |

---

## Detailed Phase Breakdown

### Phase 0: Baseline Protection, Recovery & System Audit (COMPLETED)
- [x] Create dedicated recovery branch (`recovery-phase0-baseline`) and tag (`recovery-baseline-v0`).
- [x] Push recovery baseline to remote repository `https://github.com/Nnanirepo/smartstock.git`.
- [x] Create hot backup of SQLite analytical database (`data/supply_chain_backup_baseline.db`).
- [x] Document step-by-step restoration procedures in `RECOVERY.md`.
- [x] Run full automated test suite (55 Python tests, 17 Node unit tests, 8 Playwright E2E tests).
- [x] Complete comprehensive audit across Frontend, Backend, Database, AI/ML, Data Quality, Security, and UI/UX.
- [x] Establish Ralph Loop memory tracking in `progress.txt` and `PRD.md`.

---

### Phase 1: Security Hardening & Multi-Tenant Data Isolation
- **Goal:** Resolve all Critical and High security vulnerabilities identified during the Phase 0 audit before introducing new features.
- **Key Deliverables:**
  1. **Strict Multi-Tenant Authorization:** Enforce authenticated session checks on `/api/v1/user/*` endpoints; eliminate user email tampering via query parameters.
  2. **Cryptographic Password Hashing:** Replace fast static-salted SHA-256 with `bcrypt` or `argon2id` with per-user cryptographic salts.
  3. **Secure Cryptographic Tokens:** Implement standard signed JWTs or high-entropy cryptographically random session tokens with explicit TTLs and expiration checks.
  4. **Backend AI Proxying:** Route all Gemini API requests through a secure server-side endpoint (`/api/v1/ai/assistant`), removing the client-side API key exposure in `localStorage`.
  5. **CORS & Environment Hardening:** Configure explicit allowed origins for production and staging environments.

---

### Phase 2: Commercial UI/UX Redesign & Two-Level Intelligence
- **Goal:** Transform the interface into a world-class, commercial-grade retail platform while preserving full academic inspectability.
- **Key Deliverables:**
  1. **Dual-Mode Intelligence Switcher:**
     - *Shopkeeper Business Intelligence View:* Actionable, low-cognitive-load insights ("Order 12 units of Atta", "Sugar is running low", "Margin: 18%").
     - *Academic Technical Intelligence View:* Detailed charts for Holt-Winters vs Random Forest, RMSE/MAE evaluation tables, Z-score/IQR distributions, K-Means silhouette scores, and ROP formula breakdown.
  2. **Enhanced Mobile & Tablet Ergonomics:** Refined navigation drawer, bottom action bar, tactile number pads for quick POS checkout, and barcode scanning support.
  3. **Visual Cleanliness:** Eliminate unnecessary gradients, glowing effects, and visual noise in favor of high-contrast, trustworthy typography and clean layout spacing.

---

### Phase 3: AI/DS Pipeline Enhancement & Real Data Connectors
- **Goal:** Connect the live merchant inventory catalog directly to the analytical machine learning engine.
- **Key Deliverables:**
  1. **Dynamic Model Inference Bridge:** Enable the frontend to trigger on-demand forecasts for any custom merchant SKU using real transaction history.
  2. **Live Anomaly Alerting:** Hook POS transactions into the real-time Z-score/IQR anomaly detector to flag sudden demand surges or data entry typos.
  3. **Automated Live ABC-XYZ Re-segmentation:** Periodically re-cluster active merchant products as sales accumulate.
  4. **Safety Stock Parameter Tuning:** Allow merchants to select service level targets (90%, 95%, 98%) with instant safety stock and ROP recalculation.

---

### Phase 4: Business Intelligence, Seasonal Demand & Lead-Time Analytics
- **Goal:** Provide predictive analytics that empower merchants to make proactive purchasing decisions.
- **Key Deliverables:**
  1. **Seasonal Demand Surges:** Historical weekly and monthly seasonal indices highlighting upcoming festival or holiday surges.
  2. **Supplier Lead-Time Variance Tracker:** Monitor promised vs actual delivery times from vendors to dynamically adjust lead-time safety buffers.
  3. **Dead Stock & Overstock Detection:** Identify SKUs with low inventory turnover and calculate holding cost penalties.
  4. **What-If Inventory Simulator:** Interactive slider tool for merchants to simulate changing supplier lead times or demand spikes.

---

### Phase 5: Production Quality Assurance, Full E2E & Academic Demonstration
- **Goal:** Achieve production-ready reliability and prepare the college review presentation.
- **Key Deliverables:**
  1. **Comprehensive E2E Automation:** Expand Playwright test suite to cover all user flows (auth, product creation, sales, PO inwarding, forecast generation, AI replenishment).
  2. **Regression & Performance Validation:** Load test FastAPI endpoints and verify Lighthouse performance scores (>90).
  3. **Academic Presentation Material:** Align system output with the official Review Template slides (`docs/SMARTSTOCK_REVIEW_DOCUMENTATION.md`).

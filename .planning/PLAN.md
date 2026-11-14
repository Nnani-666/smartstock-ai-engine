# Plan: Critical Cross-Account AI Data Isolation Audit & Repair

## 1. Goal
Identify and completely eliminate cross-account data contamination in the SmartStock AI Assistant across authentication, frontend session lifecycles, backend proxies, multi-model Gemini routing, and local heuristic fallbacks.

## 2. Work Breakdown Waves

- [x] **Wave 1: Exact Reproduction & Pipeline Tracing**
  - Seed disposable test accounts:
    - Account A: `tenant_alpha@smartstock.in` with `TEST_PRODUCT_ALPHA` (units: 50, price: 100, sales: 15 units = ₹1,500).
    - Account B: `tenant_beta@smartstock.in` with `TEST_PRODUCT_BETA` (units: 30, price: 50, sales: 16 units = ₹800).
  - Execute reproduction script and browser flow (Account A -> query -> logout -> Account B -> query).
  - Trace request/response flow through frontend bridge, token management, backend `get_current_user`, and context construction.
  - Identify exact source(s) of cross-account data leakage.

- [x] **Wave 2: Full-Stack Tenant Isolation Hardening**
  - Backend isolation:
    - Enforce strict tenant derivation from session token.
    - Audit all SQL queries in `ai_assistant_endpoint` and `build_grounded_store_context`.
    - Ensure demo account defaults never pollute authenticated sessions.
    - Fix any shared in-memory caches or state.
  - Frontend session lifecycle hardening:
    - In `smartstock-bridge.js`: Invalidate backend session on logout (`POST /api/v1/auth/logout`).
    - Purge all local user storage (`smartstock_token`, `smartstock_user`, cached products, sales, carts).
    - In `10_assistant.html`: Reset and isolate chat `thread` per tenant session.
    - Abort in-flight requests on logout using `AbortController`.

- [x] **Wave 3: Multi-Model & Fallback Tenant Isolation Verification**
  - Verify Account A and Account B data across:
    - `gemini-3.5-flash-lite`
    - `gemini-3.1-flash-lite` (quota failover)
    - `local_heuristic` (offline fallback)
  - Verify prompt payload and system instructions never carry stale tenant data.

- [x] **Wave 4: Comprehensive Security Test Suite (All 16 Scenarios)**
  - Implement pytest security test suite in `tests/test_tenant_isolation_ai.py` covering all 16 specified requirements.
  - Implement Playwright E2E test in `tests/e2e/tenant_isolation_browser.spec.cjs` verifying actual browser account switching.

- [x] **Wave 5: Independent Code Review via CodeRabbit Subagent**
  - Invoke `code-reviewer` subagent to audit code changes for unscoped queries, session leakages, or security vulnerabilities.
  - Address all feedback.

- [x] **Wave 6: Audit Documentation & Verification Sign-Off**
  - Author `SMARTSTOCK_AI_TENANT_ISOLATION_AUDIT.md`.
  - Verify full test regression suite passes (100%).
  - Ensure clean Git commit on `feature/ai-tenant-isolation-fix`.

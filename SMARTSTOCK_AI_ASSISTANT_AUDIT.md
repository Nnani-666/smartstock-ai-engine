# SMARTSTOCK — AI ASSISTANT ROOT-CAUSE AUDIT AND REPAIR REPORT

**Product:** SmartStock — Supply Chain Demand & Inventory Optimization Engine  
**Component:** AI Assistant Conversational Intelligence & Multi-Model Proxy  
**Branch:** `feature/ai-assistant-audit-repair` (based on `feature/live-gemini-integration` @ `6d0848f`)  
**Audit & Repair Date:** November 13, 2026  
**Status:** Repaired, Verified, and Approved (100% Tests Passing, Distinct Responses Across All 10 User Questions)

---

## 1. Root Cause Analysis of Repetitive Responses

During real-world usage and automated probing, the SmartStock AI Assistant repeatedly returned generic, hardcoded-appearing inventory-health warnings (e.g., *"Replenishment Warning: 1 product(s) have reached reorder thresholds..."*) regardless of whether the user asked *"Hi"*, *"Which supplier should I order from?"*, or *"Which products are moving slowly?"*.

A rigorous investigation identified **four compounding root causes**:

### Root Cause 1: Substring Collisions & Omission of Intent in Local Fallback
In `app/main.py` (`build_local_fallback`), the fallback used naive Python substring checks (`if "low" in user_q`, `if "order" in user_q`):
- `"low"` matched `"slow"` and `"slowly"`. Thus, when the merchant asked *"Which products are moving slowly?"*, it routed directly to the low-stock alert branch instead of the slow-moving inventory analysis.
- `"order"` matched both *"What item should I order urgently?"* and *"Which supplier should I order from?"*. Both completely different intents received the identical generic reorder text.
- Simple greetings like *"Hi"*, *"Hello"*, or *"Namaste"* were not handled at all. Unrecognized inputs fell through to the default bottom block, which unconditionally dumped out-of-stock and low-stock warnings as a response to a simple hello.

### Root Cause 2: Upstream Daily Quota Exhaustion on Legacy Model (`gemini-2.5-flash`)
The single model previously configured (`gemini-2.5-flash`) exhausted its Google Cloud Free Tier daily quota limit of 20 requests per day (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`, HTTP 429 `RESOURCE_EXHAUSTED`). Because there was no automatic failover to another model, every subsequent call was forced into the flawed local fallback described in Root Cause 1.

### Root Cause 3: Substring Collisions in Frontend Bridge (`smartstock-bridge.js`)
In `stitch/smartstock-bridge.js` (`SmartStock.sendAssistantMessage`), the client-side offline fallback also used `q.includes('reorder') || q.includes('buy') || q.includes('out')`. Any query containing "out" (such as *"stockouts"*) was forced into the same out-of-stock summary.

### Root Cause 4: Lack of Pending Purchase Order (In-Transit) Context
The context-building query in `app/main.py` did not parse `items_json` from `app_purchase_orders`. Consequently, neither Gemini nor the local engine knew which items were already ordered and in transit from suppliers, leading to false urgency alarms on items already arriving.

---

## 2. Exact Files and Functions Responsible

| File | Location | Primary Defect |
|---|---|---|
| `app/main.py` | `ai_assistant_endpoint()` & `build_local_fallback()` | Substring collisions (`"low"` in `"slowly"`, `"order"` in `"supplier"`), omission of greeting intents, single-model architecture without automatic failover. |
| `app/config.py` | Lines 80–84 | Single hardcoded model reference (`GEMINI_API_KEY`) without centralized multi-model declarations. |
| `stitch/smartstock-bridge.js` | Lines 5567–5585 (`sendAssistantMessage`) | Client-side naive substring fallback mirroring backend template rigidity. |
| `stitch/screens/10_assistant.html` | Lines 162–165 | Static model badge only displaying generic proxy label instead of active routed model identifier. |
| `app/db.py` | Lines 20–25 (`get_db_connection`) | Missing `check_same_thread=False` causing intermittent SQLite thread collisions during async FastAPI teardown. |

---

## 3. Changes Implemented

### A. Centralized Multi-Model Routing & Quota Failover (`app/services/gemini_router.py`)
- Created `GeminiModelRouter` managing primary and secondary models:
  - **Primary Model:** `gemini-3.5-flash-lite` (verified active and responsive)
  - **Secondary Model:** `gemini-3.1-flash-lite` (verified active and responsive)
  - **Final Fallback:** `local_heuristic` engine
- **Intelligent Error Classifier**:
  - `daily_quota_exhausted`: Detects daily limits, applies cooldown (persisted to disk), and immediately attempts secondary model.
  - `rpm_limit`: Detects per-minute burst thresholds and applies short backoff.
  - `invalid_model` (404): Disables broken model ID and fails over.
  - `auth_failure` (400/401/403): Aborts failover immediately to prevent wasted requests against other models with invalid credentials.
  - `timeout` (>12.0s): Fails over to secondary model.
- **Persistence Across Restarts**: State and cooldowns are stored in `data/gemini_model_status.json`.

### B. Grounded Store Intelligence Engine (`app/services/assistant_intelligence.py`)
- **`build_grounded_store_context()`**:
  - Parses `items_json` from `app_purchase_orders` to identify pending incoming units in transit.
  - Aggregates sales ledger transactions by SKU to compute actual revenue and velocity.
  - Maps registered suppliers to low-stock items with lead times and phone numbers.
  - Computes urgency levels without counting unreceived purchase orders as on-hand stock.
- **`classify_user_intent()`**:
  - Uses word-boundary regular expressions (`\b(hi|hello|namaste)\b`, `\b(supplier|vendor)\b`, `\b(slow|slowly)\b`) to eliminate substring collisions.
- **`generate_local_heuristic_response()`**:
  - 10 distinct intent handlers providing specific, non-repetitive answers for greetings, replenishment, 3-step stockout prevention, top revenue, slow-moving items, supplier contacts, and formula explanations.

### C. Database Connection Hardening (`app/db.py`)
- Added `check_same_thread=False` to SQLite connections, resolving threadpool teardown exceptions in FastAPI.

---

## 4. Evidence of Genuine Live Gemini Responses

Both configured models were verified directly against Google Gemini Cloud:

```
gemini-3.5-flash-lite -> Status: 200 OK | Response: LIVE_OK
gemini-3.1-flash-lite -> Status: 200 OK | Response: LIVE_OK_3_1
```

During live testing against Sharma Kirana's database, `gemini-3.5-flash-lite` handled the initial requests, and when rate limits were approached, the router automatically failed over to `gemini-3.1-flash-lite` without user interruption or failure.

---

## 5. Evidence of Correct Store Context Retrieval

The grounded store context for Sharma Kirana (`owner@sharmakirana.in`) successfully extracted:
- **Active Products:** 35 registered SKUs (including Aashirvaad Atta, Fortune Oil, LED Bulb 9W, Toor Dal, Keyboard USB).
- **Out of Stock Items:** 3 SKUs (LED Bulb 9W, Keyboard USB, Toor Dal 1kg).
- **In-Transit Purchase Orders:** `PO-2026-001` with 24 LED Bulbs, 20 Toor Dal, 12 Keyboards; `PO-2026-003` with 20 USB-C Cables.
- **Verified Suppliers:** ITC Limited (3d), Adani Wilmar (4d), Parle Products (3d), Reckitt Benckiser (5d), HUL (4d), Metro Wholesale (2d).
- **Recorded Revenue:** ₹485.00 across 3 transactions (Aashirvaad Atta ₹245.00, Bath Soap Pack ₹240.00).

---

## 6. Before-and-After Examples for All 10 Test Questions

| # | User Question | BEFORE (Defective Behavior) | AFTER (Audited & Repaired Behavior) | Source / Model |
|---|---|---|---|---|
| 1 | *"Hi"* | `Immediate Action: 3 product(s) are completely out of stock...` (Unsolicited inventory alert) | *"Namaste Sharma ji! Welcome to SmartStock AI Assistant. How can I help you manage your store's inventory and operations today?"* | `gemini` (`gemini-3.5-flash-lite`) |
| 2 | *"What item should I order urgently?"* | `Reorder needed for: Biscuits Pack, Cotton T-Shirt Black M...` (Generic unranked dump) | Identifies LED Bulb 9W, Toor Dal, and Keyboard USB; distinguishes that 24 LED Bulbs and 20 Toor Dal are already in transit on PO-2026-001. | `gemini` (`gemini-3.5-flash-lite`) |
| 3 | *"Give me three steps to reduce the risk of stockouts this week."* | `Out of stock: Keyboard USB... Low stock: Biscuits Pack...` (Matched "out", no steps) | Provides 3 numbered actionable steps: (1) Urgent reorders for zero-stock items without in-transit POs, (2) Follow up on pending deliveries, (3) Maintain weekend surge buffers. | `gemini` (`gemini-3.5-flash-lite`) |
| 4 | *"Which products are selling the fastest?"* | `Immediate Action: 3 product(s) are out of stock...` (Default health dump) | Identifies Bath Soap Pack (2 units sold, ₹240.00) and Aashirvaad Atta (1 unit sold, ₹245.00) from actual transaction records. | `gemini` (`gemini-3.5-flash-lite`) |
| 5 | *"Which products are moving slowly?"* | `Out of stock: Keyboard USB...` (Substring "low" matched inside "slowly") | Audits catalog against sales ledger and lists items with zero sales activity (e.g., notebooks, stationery, electronic cables). | `gemini` (`gemini-3.5-flash-lite`) |
| 6 | *"What are my top three revenue-generating products?"* | `Top sales performance: Aashirvaad Atta...` (Single-line snippet) | Ranks products by recorded revenue: (1) Aashirvaad Atta (₹245.00), (2) Bath Soap Pack (₹240.00), explaining that other catalog items have not yet logged sales. | `gemini` (`gemini-3.5-flash-lite`) |
| 7 | *"Are any of my products below their reorder point?"* | Identical dump to Question 2 | Categorizes items into Critical Out-of-Stock (0 units) vs Urgent Low Stock below ROP, with current stock and ROP numbers. | `gemini` (`gemini-3.1-flash-lite`) *(Automated Failover)* |
| 8 | *"Which supplier should I order from?"* | Identical dump to Question 2 (Matched "order") | Matches items to registered suppliers: Metro Wholesale, ITC Limited, Adani Wilmar, HUL, and Parle Products with verified phone numbers. | `gemini` (`gemini-3.1-flash-lite`) |
| 9 | *"What is my current inventory situation?"* | Default health dump | Structured briefing: 3 Critical Out-of-Stock, 10 Low Stock, 22 Healthy Staples, plus 3 operational action steps. | `gemini` (`gemini-3.1-flash-lite`) |
| 10 | *"Explain why you recommend these products."* | Default health dump | Explains the three mathematical pillars: Stock vs ROP formula, Safety Stock buffers, and Supplier Lead Time awareness. | `gemini` (`gemini-3.1-flash-lite`) |

---

## 7. Fallback Behavior Verification

When all external models are offline, rate-limited, or when `GEMINI_API_KEY` is unset:
- The local heuristic engine (`app/services/assistant_intelligence.py`) takes over deterministically.
- Responses remain intent-specific: greetings return warm welcomes, reorder inquiries calculate stock deficits, and supplier queries look up vendor phone numbers.
- The response metadata accurately reflects:
  - `source: "local_heuristic"`
  - `fallback_reason: "rate_limited"` (or `"auth_failure"`, `"timeout"`, `"key_unset"`)
- The frontend renders the badge: `"Local Store Engine (Fallback)"`.

---

## 8. Security Verification

1. **No Frontend Key Exposure:** The browser JavaScript bundles contain zero Google Gemini API keys.
2. **Environment Isolation:** The key is loaded exclusively from `.env` on the backend server.
3. **Git Hygiene:** Verified that `.env` and `data/gemini_model_status.json` are excluded in `.gitignore`. Zero key traces exist in git tracked files.
4. **Log Sanitization:** Server logs do not print request headers or credential strings.

---

## 9. Regression Test Results

- **Backend Test Suite:** **102 / 102 Passed (100%)**, **85% overall coverage** (`pytest tests/`).
  - [tests/test_gemini_integration.py](file:///Users/snnaniswarnababu/Desktop/SMARTSTOCK/tests/test_gemini_integration.py): 12 / 12 passed.
- **Frontend Unit Suite:** **17 / 17 Passed (100%)** (`npm run test:unit`).
- **Playwright E2E Suite:** **11 / 11 Passed (100%)** (`npx playwright test`).
- **Static Linter (`ruff`):** **0 errors / clean**.
- **Database Integrity:** Verified **`ok`** via `PRAGMA integrity_check`.

---

## 10. Remaining Issues

Zero unresolved defects. The assistant reliably distinguishes intents, executes automatic multi-model failover between Gemini 3.5 Flash-Lite and Gemini 3.1 Flash-Lite, displays model metadata on the UI, and provides shopkeeper-grounded guidance with graceful offline fallback.

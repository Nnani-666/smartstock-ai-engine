# SmartStock — Phase 1 Proposed Plan (.planning/PLAN.md)
**Focus:** Security Hardening, Multi-Tenant Data Isolation & API Authorization  
**Prerequisites:** Phase 0 Audit & Baseline Completed  
**Status:** Pending User Approval Before Starting Implementation

---

## 1. Objectives
Eliminate all Critical and High security vulnerabilities discovered in the Phase 0 audit without breaking any existing frontend POS, inventory, or order management workflows.

---

## 2. Work Breakdown Structure (Tasks)

### Task 1.1: Cryptographic Authentication & Token Upgrade
- **Files Affected:** `app/main.py`, `app/db.py`, `app/schemas.py`
- **Actions:**
  - Replace static-salted SHA-256 password hashing with `passlib[bcrypt]` or `hashlib.pbkdf2_hmac` with unique per-user 16-byte cryptographic salt.
  - Implement cryptographically secure token generation (`secrets.token_hex(32)`) or signed JWTs (`python-jose` / `pyjwt`).
  - Store tokens with explicit creation timestamp and TTL (7 days) in an `app_sessions` table or signed claims.
  - Remove brute-force token matching loop in `get_auth_me`.

### Task 1.2: Strict User Authorization Middleware
- **Files Affected:** `app/main.py`, `app/db.py`
- **Actions:**
  - Create a FastAPI dependency `get_current_user` that extracts and validates the `Authorization: Bearer <token>` header.
  - Refactor all `/api/v1/user/*` endpoints (`/products`, `/purchase-orders`, `/sales`) to derive the tenant user namespace directly from the authenticated session, completely eliminating spoofable `email: str = Query(...)` and `req.user_email`.
  - Return HTTP 401 Unauthorized for missing or invalid tokens.

### Task 1.3: Server-Side AI Assistant Proxy
- **Files Affected:** `app/main.py`, `stitch/smartstock-bridge.js`
- **Actions:**
  - Add backend route `POST /api/v1/ai/assistant` in FastAPI that uses the server's `GEMINI_API_KEY` (configured in `.env`).
  - Update `smartstock-bridge.js` to dispatch analysis prompts to `POST /api/v1/ai/assistant` instead of calling `generativelanguage.googleapis.com` directly from the client.
  - Remove the requirement for shopkeepers to manually enter API keys into browser `localStorage`.

### Task 1.4: Environment & CORS Configuration
- **Files Affected:** `app/config.py`, `app/main.py`
- **Actions:**
  - Restrict CORS origins to localhost, local network IPs, and configured production origins.
  - Enforce `API_KEY` validation on analytical machine learning endpoints when running in production mode.

---

## 3. Verification & Acceptance Criteria
1. Running `pytest tests/test_retail_server.py` passes with updated authenticated headers.
2. Attempting to access another user's products via `GET /api/v1/user/products` with a mismatched token returns 401/403.
3. Password hashes stored in `app_users` follow standard PBKDF2/bcrypt format (`$algo$iterations$salt$hash`).
4. Running `npm run test:unit` and `npx playwright test` continues to pass 100%.

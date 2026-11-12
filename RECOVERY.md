# SmartStock — Project Recovery & Restoration Runbook
**Baseline Version:** `v0.9.0-phase0`  
**Baseline Git Commit:** `c81a1fe`  
**Dedicated Recovery Branch:** `recovery-phase0-baseline`  
**Dedicated Recovery Tag:** `recovery-baseline-v0`  
**Remote URL:** `https://github.com/Nnanirepo/smartstock.git`  
**Authoritative Date:** 2026-11-12

---

## 1. Quick-Start Emergency Rollback (Git)

If any future operation destabilizes or damages the workspace, follow these non-destructive steps to return to this verified baseline:

### Option A: Clean Reset to Baseline Commit
```bash
# 1. Stash any uncommitted work safely
git stash push -u -m "pre-rollback-uncommitted-changes"

# 2. Checkout the verified baseline recovery branch
git checkout recovery-phase0-baseline

# 3. Verify clean state
git status
```

### Option B: Restore Current Branch (e.g. `main`) to Baseline
```bash
# If on main and need to reset main to match the baseline exactly:
git stash push -u -m "backup-before-main-reset"
git checkout main
git reset --hard recovery-baseline-v0
```

### Option C: Re-fetch from Remote GitHub
```bash
git fetch origin
git checkout -B main origin/recovery-phase0-baseline
```

---

## 2. Database Protection & Recovery Procedures

SmartStock utilizes a **dual-database architecture**:
1. **Local SQLite Analytical & Merchant DB:** `data/supply_chain.db` (92 MB)
2. **Cloud Supabase PostgreSQL Database:** Project `txpvoqdecsjpmklelxdb`

### 2.1 SQLite Database (`data/supply_chain.db`)

#### A. Creating a Hot Backup:
```bash
# Method 1: Using sqlite3 online backup API (locks table safely)
sqlite3 data/supply_chain.db ".backup 'data/supply_chain_backup_baseline.db'"

# Method 2: Safe atomic copy
cp data/supply_chain.db data/supply_chain_backup_baseline.db
```

#### B. Restoring SQLite Database:
```bash
cp data/supply_chain_backup_baseline.db data/supply_chain.db
```

#### C. Re-running Pipeline from Scratch (if database is corrupted):
```bash
# Regenerate raw tables, anomaly flags, segmentation, and models:
make all
```

---

### 2.2 Supabase PostgreSQL Cloud Database (`txpvoqdecsjpmklelxdb`)

> **CRITICAL WARNING:** Git commits do **not** backup Supabase cloud tables. Never execute destructive DDL (`DROP TABLE`, `TRUNCATE`) without an explicit cloud backup.

#### A. Backing Up Supabase Schema & Data:
```bash
# If Supabase CLI is installed:
supabase db dump --project-ref txpvoqdecsjpmklelxdb --schema public > supabase/backup_public_$(date +%Y%m%d).sql

# Or using pg_dump with direct database connection string:
pg_dump "postgresql://postgres:[YOUR-PASSWORD]@db.txpvoqdecsjpmklelxdb.supabase.co:5432/postgres" \
  --schema=public --clean --if-exists -f supabase/supabase_full_backup.sql
```

#### B. Restoring Supabase Schema:
1. Navigate to Supabase Dashboard: `https://supabase.com/dashboard/project/txpvoqdecsjpmklelxdb/sql/new`
2. Open and run [supabase/complete_setup.sql](file:///Users/snnaniswarnababu/Desktop/SMARTSTOCK/supabase/complete_setup.sql).
3. Optionally re-seed with [supabase/seed.sql](file:///Users/snnaniswarnababu/Desktop/SMARTSTOCK/supabase/seed.sql).

---

## 3. Application Execution & Build Verification

### 3.1 Backend Server (FastAPI)
```bash
# Start backend server on port 8000
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
- Health Check: `http://localhost:8000/health`
- Swagger Documentation: `http://localhost:8000/docs`

### 3.2 Frontend (Stitch Web UI)
```bash
# Serve static stitch assets on port 3000
python3 -m http.server 3000 --directory stitch
```
- Access in browser: `http://localhost:3000`

### 3.3 Automated Test Suites
```bash
# 1. Run Python Unit & Retail Server Tests (55 tests)
PYTHONPATH=. .venv/bin/pytest tests/test_api.py tests/test_anomaly.py tests/test_forecasting.py tests/test_rules.py tests/test_safety_stock.py tests/test_segmentation.py tests/test_simulation.py tests/test_retail_server.py

# 2. Run Node.js Retail Business Logic Tests (17 tests)
npm run test:unit

# 3. Run Playwright End-to-End Tests (8 tests)
npx playwright test
```

---

## 4. Emergency Contacts & Verification Checklist
- **Baseline Git Hash:** `c81a1fe88bce955e6cbf4d8e5792aeebfec1f88c`
- **Clean Tree Check:** `git status` should return `nothing to commit, working tree clean`.
- **Remote Push Confirmed:** Both branch `recovery-phase0-baseline` and tag `recovery-baseline-v0` are verified present on GitHub `origin`.

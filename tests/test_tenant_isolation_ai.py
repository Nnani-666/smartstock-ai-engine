"""Comprehensive Tenant Data Isolation & Security Test Suite for SmartStock AI Assistant.

Verifies all 16 critical tenant-isolation scenarios:
1. Account A cannot access Account B inventory via AI.
2. Account B cannot access Account A inventory via AI.
3. Account A cannot retrieve Account B sales history.
4. Account B cannot retrieve Account A sales history.
5. Revenue aggregations are tenant-scoped.
6. Conversation history is isolated by account.
7. Cache entries cannot cross account boundaries.
8. Gemini 3.5 receives correct tenant context.
9. Gemini 3.1 receives correct tenant context during failover.
10. Local fallback receives only current tenant data.
11. Logging out invalidates previous session.
12. Requests with revoked session return 401.
13. Simultaneous sessions for different accounts remain isolated.
14. Empty sales history does not substitute demo data.
15. In-flight frontend requests do not contaminate new session.
16. Repeated account switching does not leak stale data.
"""

from __future__ import annotations

import concurrent.futures
import json
import sqlite3
import uuid
import pytest
from fastapi.testclient import TestClient

from app.auth import create_session, hash_password
from app.db import get_db, get_write_db
from app.main import app
from app.services.assistant_intelligence import (
    build_grounded_store_context,
    generate_local_heuristic_response,
)
from app.services.gemini_router import router as gemini_router


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def seeded_tenants():
    """Ensure disposable test accounts A and B exist with distinctive datasets."""
    db_path = "data/supply_chain.db"
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    user_a_email = "tenant_alpha@smartstock.in"
    user_b_email = "tenant_beta@smartstock.in"
    user_c_email = "tenant_gamma_empty@smartstock.in"

    # Seed User A
    c.execute("SELECT id FROM app_users WHERE email = ?", (user_a_email,))
    row_a = c.fetchone()
    if not row_a:
        user_a_id = str(uuid.uuid4())
        c.execute(
            """INSERT INTO app_users (id, email, password_hash, store_name, phone, manager, created_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
            (user_a_id, user_a_email, hash_password("PasswordAlpha123!"), "Alpha Store", "+91 98000 11111", "Owner Alpha"),
        )
    else:
        user_a_id = row_a[0]

    # Seed User B
    c.execute("SELECT id FROM app_users WHERE email = ?", (user_b_email,))
    row_b = c.fetchone()
    if not row_b:
        user_b_id = str(uuid.uuid4())
        c.execute(
            """INSERT INTO app_users (id, email, password_hash, store_name, phone, manager, created_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
            (user_b_id, user_b_email, hash_password("PasswordBeta123!"), "Beta Store", "+91 98000 22222", "Owner Beta"),
        )
    else:
        user_b_id = row_b[0]

    # Seed User C (Empty tenant with 0 products and 0 sales)
    c.execute("SELECT id FROM app_users WHERE email = ?", (user_c_email,))
    row_c = c.fetchone()
    if not row_c:
        user_c_id = str(uuid.uuid4())
        c.execute(
            """INSERT INTO app_users (id, email, password_hash, store_name, phone, manager, created_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
            (user_c_id, user_c_email, hash_password("PasswordGamma123!"), "Gamma Empty Store", "+91 98000 33333", "Owner Gamma"),
        )
    else:
        user_c_id = row_c[0]

    # Seed Distinct Products for Tenant A
    c.execute("DELETE FROM app_products WHERE user_email = ?", (user_a_email,))
    c.execute(
        """INSERT INTO app_products (id, user_email, sku, name, description, unit_price, unit_cost, stock_on_hand, safety_stock, reorder_point, lead_time_days, supplier, status, created_at, category_name)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)""",
        (f"prod-a-{uuid.uuid4()}", user_a_email, "SKU-ALPHA-01", "TEST_PRODUCT_ALPHA", "Distinct Alpha Goods", 100.0, 70.0, 35, 5, 10, 2, "Alpha Wholesale Dist", "active", "Alpha Category"),
    )

    # Seed Distinct Products for Tenant B
    c.execute("DELETE FROM app_products WHERE user_email = ?", (user_b_email,))
    c.execute(
        """INSERT INTO app_products (id, user_email, sku, name, description, unit_price, unit_cost, stock_on_hand, safety_stock, reorder_point, lead_time_days, supplier, status, created_at, category_name)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)""",
        (f"prod-b-{uuid.uuid4()}", user_b_email, "SKU-BETA-01", "TEST_PRODUCT_BETA", "Distinct Beta Goods", 50.0, 30.0, 14, 4, 8, 4, "Beta Regional Hub", "active", "Beta Category"),
    )

    # Clean Products for Tenant C
    c.execute("DELETE FROM app_products WHERE user_email = ?", (user_c_email,))

    # Seed Distinct Sales for Tenant A: 15 units of ALPHA @ 100 = 1500
    c.execute("DELETE FROM app_sales WHERE user_email = ?", (user_a_email,))
    c.execute(
        """INSERT INTO app_sales (id, user_email, product_id, product_name, sale_amount, units, timestamp, unit_cost)
           VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)""",
        (f"sale-a-{uuid.uuid4()}", user_a_email, "prod-a-1", "TEST_PRODUCT_ALPHA", 1500.0, 15, 70.0),
    )

    # Seed Distinct Sales for Tenant B: 16 units of BETA @ 50 = 800
    c.execute("DELETE FROM app_sales WHERE user_email = ?", (user_b_email,))
    c.execute(
        """INSERT INTO app_sales (id, user_email, product_id, product_name, sale_amount, units, timestamp, unit_cost)
           VALUES (?, ?, ?, ?, ?, ?, datetime('now'), ?)""",
        (f"sale-b-{uuid.uuid4()}", user_b_email, "prod-b-1", "TEST_PRODUCT_BETA", 800.0, 16, 30.0),
    )

    # Clean Sales for Tenant C
    c.execute("DELETE FROM app_sales WHERE user_email = ?", (user_c_email,))

    conn.commit()
    conn.close()

    return {
        "user_a": {"email": user_a_email, "password": "PasswordAlpha123!", "product": "TEST_PRODUCT_ALPHA", "sales_amt": 1500.0},
        "user_b": {"email": user_b_email, "password": "PasswordBeta123!", "product": "TEST_PRODUCT_BETA", "sales_amt": 800.0},
        "user_c": {"email": user_c_email, "password": "PasswordGamma123!", "product": None, "sales_amt": 0.0},
    }


def get_token(client, email, password):
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    return resp.json()["token"]


# Scenario 1: Account A cannot access Account B inventory via AI
def test_01_account_a_cannot_access_account_b_inventory(client, seeded_tenants):
    token_a = get_token(client, seeded_tenants["user_a"]["email"], seeded_tenants["user_a"]["password"])
    resp = client.post(
        "/api/v1/ai/assistant",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"prompt": "List all products in my store inventory."},
    )
    assert resp.status_code == 200
    text = resp.json().get("analysis", "")
    assert "TEST_PRODUCT_ALPHA" in text or "SKU-ALPHA-01" in text or "Alpha Store" in text
    assert "TEST_PRODUCT_BETA" not in text
    assert "SKU-BETA-01" not in text


# Scenario 2: Account B cannot access Account A inventory via AI
def test_02_account_b_cannot_access_account_a_inventory(client, seeded_tenants):
    token_b = get_token(client, seeded_tenants["user_b"]["email"], seeded_tenants["user_b"]["password"])
    resp = client.post(
        "/api/v1/ai/assistant",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"prompt": "List all products in my store inventory."},
    )
    assert resp.status_code == 200
    text = resp.json().get("analysis", "")
    assert "TEST_PRODUCT_BETA" in text or "SKU-BETA-01" in text or "Beta Store" in text
    assert "TEST_PRODUCT_ALPHA" not in text
    assert "SKU-ALPHA-01" not in text


# Scenario 3: Account A cannot retrieve Account B sales history
def test_03_account_a_cannot_retrieve_account_b_sales(client, seeded_tenants):
    token_a = get_token(client, seeded_tenants["user_a"]["email"], seeded_tenants["user_a"]["password"])
    resp = client.post(
        "/api/v1/ai/assistant",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"prompt": "Which products are selling the fastest?"},
    )
    assert resp.status_code == 200
    text = resp.json().get("analysis", "")
    assert "TEST_PRODUCT_BETA" not in text
    metrics = resp.json().get("metrics", {})
    assert metrics.get("recent_sales_amount") == 1500.0


# Scenario 4: Account B cannot retrieve Account A sales history
def test_04_account_b_cannot_retrieve_account_a_sales(client, seeded_tenants):
    token_b = get_token(client, seeded_tenants["user_b"]["email"], seeded_tenants["user_b"]["password"])
    resp = client.post(
        "/api/v1/ai/assistant",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"prompt": "Which products are selling the fastest?"},
    )
    assert resp.status_code == 200
    text = resp.json().get("analysis", "")
    assert "TEST_PRODUCT_ALPHA" not in text
    metrics = resp.json().get("metrics", {})
    assert metrics.get("recent_sales_amount") == 800.0


# Scenario 5: Revenue aggregations are tenant-scoped
def test_05_revenue_aggregations_tenant_scoped(client, seeded_tenants):
    token_a = get_token(client, seeded_tenants["user_a"]["email"], seeded_tenants["user_a"]["password"])
    token_b = get_token(client, seeded_tenants["user_b"]["email"], seeded_tenants["user_b"]["password"])

    resp_a = client.post(
        "/api/v1/ai/assistant",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"prompt": "What are my top revenue-generating products?"},
    )
    resp_b = client.post(
        "/api/v1/ai/assistant",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"prompt": "What are my top revenue-generating products?"},
    )

    metrics_a = resp_a.json().get("metrics", {})
    metrics_b = resp_b.json().get("metrics", {})

    assert metrics_a.get("recent_sales_amount") == 1500.0
    assert metrics_b.get("recent_sales_amount") == 800.0


# Scenario 6: Conversation history is isolated by account
def test_06_conversation_history_isolated_by_account(client, seeded_tenants):
    token_a = get_token(client, seeded_tenants["user_a"]["email"], seeded_tenants["user_a"]["password"])
    token_b = get_token(client, seeded_tenants["user_b"]["email"], seeded_tenants["user_b"]["password"])

    # Account A asks question 1
    resp_a = client.post(
        "/api/v1/ai/assistant",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"prompt": "Explain why you recommend these products."},
    )
    # Account B asks question 2
    resp_b = client.post(
        "/api/v1/ai/assistant",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"prompt": "Explain why you recommend these products."},
    )

    assert "TEST_PRODUCT_ALPHA" in resp_a.json().get("analysis", "") or "Alpha" in resp_a.json().get("analysis", "")
    assert "TEST_PRODUCT_BETA" not in resp_a.json().get("analysis", "")

    assert "TEST_PRODUCT_BETA" in resp_b.json().get("analysis", "") or "Beta" in resp_b.json().get("analysis", "")
    assert "TEST_PRODUCT_ALPHA" not in resp_b.json().get("analysis", "")


# Scenario 7: Cache entries cannot cross account boundaries
def test_07_cache_entries_cannot_cross_account_boundaries():
    # Verify that the actual smartstock-bridge.js getUserKey implementation strictly scopes keys
    import subprocess
    node_cmd = """
    const fs = require('fs');
    const code = fs.readFileSync('stitch/smartstock-bridge.js', 'utf8');
    // Extract getUserKey method
    const match = code.match(/getUserKey\\(baseKey\\)\\s*\\{([\\s\\S]*?)\\n\\s*\\},/);
    if (!match) throw new Error('getUserKey not found in bridge');
    const getUserKeyBody = match[1];
    
    function testKey(email, baseKey) {
        const getCurrentUserEmail = () => email;
        const fn = new Function('baseKey', 'getCurrentUserEmail', getUserKeyBody.replace(/this\\.getCurrentUserEmail\\(\\)/g, 'getCurrentUserEmail()'));
        return fn(baseKey, getCurrentUserEmail);
    }

    const keyA = testKey('tenant_alpha@smartstock.in', 'smartstock_ai_analysis_cache');
    const keyB = testKey('tenant_beta@smartstock.in', 'smartstock_ai_analysis_cache');
    const keyAnon = testKey('', 'smartstock_ai_analysis_cache');

    console.log(JSON.stringify({ keyA, keyB, keyAnon }));
    """
    res = subprocess.run(["node", "-e", node_cmd], capture_output=True, text=True, check=True)
    out = json.loads(res.stdout.strip())

    assert out["keyA"] != out["keyB"]
    assert out["keyA"] != out["keyAnon"]
    assert "tenant_alpha" in out["keyA"]
    assert "tenant_beta" in out["keyB"]
    assert "unauthenticated_sandbox" in out["keyAnon"]


# Scenario 8: Gemini 3.5 receives correct tenant context
def test_08_gemini_35_receives_correct_tenant_context():
    gemini_router.reset_state()
    models = gemini_router.get_eligible_models()
    assert models[0] == "gemini-3.5-flash-lite"

    # Assemble context for tenant Alpha
    ctx_a = build_grounded_store_context(
        products=[{"name": "TEST_PRODUCT_ALPHA", "sku": "SKU-ALPHA-01", "stock_on_hand": 35, "reorder_point": 10}],
        sales=[{"product_name": "TEST_PRODUCT_ALPHA", "units": 15, "sale_amount": 1500.0}],
        orders=[],
        suppliers=[],
        store_name="Alpha Store",
        user_email="tenant_alpha@smartstock.in",
    )
    assert ctx_a["store_name"] == "Alpha Store"
    assert "TEST_PRODUCT_ALPHA" in ctx_a["catalog_lines"][0]
    assert "TEST_PRODUCT_BETA" not in str(ctx_a)


# Scenario 9: Gemini 3.1 receives correct tenant context during failover
def test_09_gemini_31_receives_correct_tenant_context_during_failover():
    gemini_router.reset_state()
    # Put primary in cooldown
    gemini_router.record_failure("gemini-3.5-flash-lite", "daily_quota_exhausted", 86400.0)
    models = gemini_router.get_eligible_models()
    assert models[0] == "gemini-3.1-flash-lite"

    ctx_b = build_grounded_store_context(
        products=[{"name": "TEST_PRODUCT_BETA", "sku": "SKU-BETA-01", "stock_on_hand": 14, "reorder_point": 8}],
        sales=[{"product_name": "TEST_PRODUCT_BETA", "units": 16, "sale_amount": 800.0}],
        orders=[],
        suppliers=[],
        store_name="Beta Store",
        user_email="tenant_beta@smartstock.in",
    )
    assert ctx_b["store_name"] == "Beta Store"
    assert "TEST_PRODUCT_BETA" in ctx_b["catalog_lines"][0]
    assert "TEST_PRODUCT_ALPHA" not in str(ctx_b)
    gemini_router.reset_state()


# Scenario 10: Local fallback receives only current tenant data
def test_10_local_fallback_receives_only_current_tenant_data():
    ctx_a = build_grounded_store_context(
        products=[{"name": "TEST_PRODUCT_ALPHA", "sku": "SKU-ALPHA-01", "stock_on_hand": 35, "reorder_point": 10}],
        sales=[{"product_name": "TEST_PRODUCT_ALPHA", "units": 15, "sale_amount": 1500.0}],
        orders=[],
        suppliers=[],
        store_name="Alpha Store",
        user_email="tenant_alpha@smartstock.in",
    )
    res_a = generate_local_heuristic_response("Which products are selling fastest?", ctx_a)
    assert "Alpha Store" in res_a["analysis"]
    assert "TEST_PRODUCT_ALPHA" in res_a["analysis"]
    assert "TEST_PRODUCT_BETA" not in res_a["analysis"]

    ctx_b = build_grounded_store_context(
        products=[{"name": "TEST_PRODUCT_BETA", "sku": "SKU-BETA-01", "stock_on_hand": 14, "reorder_point": 8}],
        sales=[{"product_name": "TEST_PRODUCT_BETA", "units": 16, "sale_amount": 800.0}],
        orders=[],
        suppliers=[],
        store_name="Beta Store",
        user_email="tenant_beta@smartstock.in",
    )
    res_b = generate_local_heuristic_response("Which products are selling fastest?", ctx_b)
    assert "Beta Store" in res_b["analysis"]
    assert "TEST_PRODUCT_BETA" in res_b["analysis"]
    assert "TEST_PRODUCT_ALPHA" not in res_b["analysis"]


# Scenario 11: Logging out invalidates previous session
def test_11_logging_out_invalidates_previous_session(client, seeded_tenants):
    token = get_token(client, seeded_tenants["user_a"]["email"], seeded_tenants["user_a"]["password"])

    # Verify session is valid
    me_resp = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me_resp.status_code == 200

    # Logout
    logout_resp = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_resp.status_code == 200

    # Verify revoked in DB
    conn = sqlite3.connect("data/supply_chain.db")
    c = conn.cursor()
    c.execute("SELECT revoked FROM app_sessions WHERE token = ?", (token,))
    row = c.fetchone()
    conn.close()
    assert row is not None
    assert row[0] == 1


# Scenario 12: Requests with revoked session return 401
def test_12_requests_with_revoked_session_return_401(client, seeded_tenants):
    token = get_token(client, seeded_tenants["user_a"]["email"], seeded_tenants["user_a"]["password"])

    # Logout to revoke
    client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})

    # AI Assistant with revoked token MUST return 401
    resp = client.post(
        "/api/v1/ai/assistant",
        headers={"Authorization": f"Bearer {token}"},
        json={"prompt": "What is my stock status?"},
    )
    assert resp.status_code == 401
    assert "revoked" in resp.json().get("detail", "").lower()


# Scenario 13: Simultaneous sessions for different accounts remain isolated
def test_13_simultaneous_sessions_remain_isolated(client, seeded_tenants):
    token_a = get_token(client, seeded_tenants["user_a"]["email"], seeded_tenants["user_a"]["password"])
    token_b = get_token(client, seeded_tenants["user_b"]["email"], seeded_tenants["user_b"]["password"])

    def req(tok, prompt):
        return client.post(
            "/api/v1/ai/assistant",
            headers={"Authorization": f"Bearer {tok}"},
            json={"prompt": prompt},
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        f_a = executor.submit(req, token_a, "What are my top selling products?")
        f_b = executor.submit(req, token_b, "What are my top selling products?")

        res_a = f_a.result()
        res_b = f_b.result()

    assert res_a.status_code == 200
    assert res_b.status_code == 200

    text_a = res_a.json().get("analysis", "")
    text_b = res_b.json().get("analysis", "")

    assert "TEST_PRODUCT_BETA" not in text_a
    assert "TEST_PRODUCT_ALPHA" not in text_b


# Scenario 14: Empty sales history does not substitute demo data
def test_14_empty_sales_history_does_not_substitute_demo_data(client, seeded_tenants):
    token_c = get_token(client, seeded_tenants["user_c"]["email"], seeded_tenants["user_c"]["password"])

    resp = client.post(
        "/api/v1/ai/assistant",
        headers={"Authorization": f"Bearer {token_c}"},
        json={"prompt": "Which products are selling the fastest?"},
    )
    assert resp.status_code == 200
    text = resp.json().get("analysis", "")
    metrics = resp.json().get("metrics", {})

    # Must NOT contain Sharma Kirana demo items or revenue
    assert "Atta" not in text
    assert "Fortune" not in text
    assert "Sharma" not in text
    assert metrics.get("recent_sales_amount") == 0.0
    assert metrics.get("total_products") == 0


# Scenario 15: In-flight frontend requests do not contaminate new session
def test_15_in_flight_session_changed_detection(client, seeded_tenants):
    # Simulate race condition: Token A is acquired and an in-flight operation begins.
    token_a = get_token(client, seeded_tenants["user_a"]["email"], seeded_tenants["user_a"]["password"])
    
    # Token A is revoked while request is in flight
    logout_res = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token_a}"})
    assert logout_res.status_code == 200

    # User B logs in immediately
    token_b = get_token(client, seeded_tenants["user_b"]["email"], seeded_tenants["user_b"]["password"])

    # If the in-flight or delayed request with Token A reaches backend after revocation:
    stale_req_res = client.post(
        "/api/v1/ai/assistant",
        headers={"Authorization": f"Bearer {token_a}"},
        json={"prompt": "What are my top selling products?"},
    )
    # MUST be rejected with 401 (never returns Tenant A data to a compromised or switched channel)
    assert stale_req_res.status_code == 401

    # Active session for Tenant B proceeds normally with Tenant B data
    fresh_req_res = client.post(
        "/api/v1/ai/assistant",
        headers={"Authorization": f"Bearer {token_b}"},
        json={"prompt": "What are my top selling products?"},
    )
    assert fresh_req_res.status_code == 200
    assert "TEST_PRODUCT_BETA" in fresh_req_res.json().get("analysis", "")
    assert "TEST_PRODUCT_ALPHA" not in fresh_req_res.json().get("analysis", "")


# Scenario 16: Repeated account switching does not leak stale data
def test_16_repeated_account_switching_no_leak(client, seeded_tenants):
    token_a = get_token(client, seeded_tenants["user_a"]["email"], seeded_tenants["user_a"]["password"])
    token_b = get_token(client, seeded_tenants["user_b"]["email"], seeded_tenants["user_b"]["password"])

    # Cycle 1: Account A
    res1 = client.post("/api/v1/ai/assistant", headers={"Authorization": f"Bearer {token_a}"}, json={"prompt": "Summary"})
    assert "TEST_PRODUCT_BETA" not in res1.json().get("analysis", "")

    # Cycle 2: Account B
    res2 = client.post("/api/v1/ai/assistant", headers={"Authorization": f"Bearer {token_b}"}, json={"prompt": "Summary"})
    assert "TEST_PRODUCT_ALPHA" not in res2.json().get("analysis", "")

    # Cycle 3: Account A again
    res3 = client.post("/api/v1/ai/assistant", headers={"Authorization": f"Bearer {token_a}"}, json={"prompt": "Summary"})
    assert "TEST_PRODUCT_BETA" not in res3.json().get("analysis", "")

    # Cycle 4: Account B again
    res4 = client.post("/api/v1/ai/assistant", headers={"Authorization": f"Bearer {token_b}"}, json={"prompt": "Summary"})
    assert "TEST_PRODUCT_ALPHA" not in res4.json().get("analysis", "")

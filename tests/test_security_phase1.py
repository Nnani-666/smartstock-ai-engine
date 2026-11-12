from __future__ import annotations

"""Phase 1 Security & Multi-Tenant Isolation Test Suite.

Verifies remediation of:
- SEC-01: Multi-tenant authorization bypass and cross-user data leakage.
- SEC-02: Cryptographic password hashing (PBKDF2) and legacy login migration.
- SEC-03: Cryptographically secure random session tokens and revocation.
- SEC-04: Server-side Gemini AI assistant proxy and tenant context isolation.
- SEC-05: CORS trusted origins configuration.
"""

import hashlib
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.auth import LEGACY_SALT
from app.config import ALLOWED_ORIGINS
from app.db import get_db, get_write_db
from app.main import app


@pytest.fixture
def client(temp_db):
    """TestClient overriding database dependencies to use the isolated test database."""
    def _override_get_db():
        conn = sqlite3.connect(temp_db)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_write_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def two_merchants(client):
    """Register two distinct merchants with unique emails and return their auth credentials."""
    uid = uuid.uuid4().hex[:6]
    email_a = f"merchant_a_{uid}@store.in"
    email_b = f"merchant_b_{uid}@store.in"

    # Merchant A
    res_a = client.post(
        "/api/v1/auth/register",
        json={
            "email": email_a,
            "password": "PasswordA123!",
            "store_name": "Store Alpha",
        },
    )
    assert res_a.status_code == 200, res_a.text
    data_a = res_a.json()

    # Merchant B
    res_b = client.post(
        "/api/v1/auth/register",
        json={
            "email": email_b,
            "password": "PasswordB123!",
            "store_name": "Store Beta",
        },
    )
    assert res_b.status_code == 200, res_b.text
    data_b = res_b.json()

    # Add a product to Merchant A
    headers_a = {"Authorization": f"Bearer {data_a['token']}"}
    client.post(
        "/api/v1/user/products",
        headers=headers_a,
        json={
            "name": "Alpha Premium Tea",
            "unit_price": 150.0,
            "unit_cost": 110.0,
            "stock_on_hand": 50,
            "reorder_point": 10,
        },
    )

    # Add a product to Merchant B
    headers_b = {"Authorization": f"Bearer {data_b['token']}"}
    client.post(
        "/api/v1/user/products",
        headers=headers_b,
        json={
            "name": "Beta Organic Rice",
            "unit_price": 80.0,
            "unit_cost": 60.0,
            "stock_on_hand": 30,
            "reorder_point": 5,
        },
    )

    return {
        "a": {"email": email_a, "token": data_a["token"], "headers": headers_a},
        "b": {"email": email_b, "token": data_b["token"], "headers": headers_b},
    }


# ==============================================================================
# SEC-01: MULTI-TENANT AUTHORIZATION TESTS
# ==============================================================================

def test_unauthenticated_requests_rejected(client):
    """Protected user endpoints must reject requests without Bearer authorization."""
    assert client.get("/api/v1/user/products").status_code == 401
    assert client.post("/api/v1/user/products", json={"name": "Test"}).status_code == 401
    assert client.get("/api/v1/user/purchase-orders").status_code == 401
    assert client.get("/api/v1/user/sales").status_code == 401
    assert client.get("/api/v1/user/sales/summary").status_code == 401
    assert client.post("/api/v1/ai/assistant", json={}).status_code == 401


def test_merchant_cannot_read_another_merchants_products(client, two_merchants):
    """Merchant A querying with Merchant B's email parameter must receive 403 Forbidden."""
    headers_a = two_merchants["a"]["headers"]
    email_b = two_merchants["b"]["email"]

    # Attempt to spoof email query param to access B's catalog
    res = client.get(f"/api/v1/user/products?email={email_b}", headers=headers_a)
    assert res.status_code == 403
    assert "cannot access another merchant" in res.json()["detail"].lower()

    # Querying without email parameter returns only A's own products
    res_own = client.get("/api/v1/user/products", headers=headers_a)
    assert res_own.status_code == 200
    products = res_own.json()
    assert len(products) == 1
    assert products[0]["name"] == "Alpha Premium Tea"


def test_merchant_cannot_create_product_for_another_merchant(client, two_merchants):
    """Merchant A supplying Merchant B's email in request body must receive 403 Forbidden."""
    headers_a = two_merchants["a"]["headers"]
    email_b = two_merchants["b"]["email"]

    res = client.post(
        "/api/v1/user/products",
        headers=headers_a,
        json={
            "user_email": email_b,
            "name": "Spoofed Product",
            "unit_price": 10.0,
            "stock_on_hand": 100,
        },
    )
    assert res.status_code == 403
    assert "cannot create products in another merchant" in res.json()["detail"].lower()


def test_merchant_cannot_access_or_inward_another_merchants_orders(client, two_merchants):
    """Merchant A cannot read or inward Merchant B's purchase orders."""
    headers_a = two_merchants["a"]["headers"]
    headers_b = two_merchants["b"]["headers"]
    email_b = two_merchants["b"]["email"]

    # Create PO for Merchant B
    po_res = client.post(
        "/api/v1/user/purchase-orders",
        headers=headers_b,
        json={
            "po_number": "PO-B-001",
            "supplier": "Beta Supplier",
            "total_amount": 500.0,
            "items": [{"name": "Beta Organic Rice", "quantity": 10, "unit_cost": 50.0}],
        },
    )
    assert po_res.status_code == 200
    po_id = po_res.json()["id"]

    # Merchant A attempts to list B's POs
    res_list = client.get(f"/api/v1/user/purchase-orders?email={email_b}", headers=headers_a)
    assert res_list.status_code == 403

    # Merchant A attempts to inward B's PO
    res_inward = client.post(f"/api/v1/user/purchase-orders/{po_id}/receive", headers=headers_a)
    assert res_inward.status_code == 404  # Not found in A's namespace


def test_merchant_cannot_read_or_record_sales_for_another_merchant(client, two_merchants):
    """Merchant A cannot view or record sales in Merchant B's register."""
    headers_a = two_merchants["a"]["headers"]
    headers_b = two_merchants["b"]["headers"]
    email_b = two_merchants["b"]["email"]

    # Record sale for Merchant B
    client.post(
        "/api/v1/user/sales",
        headers=headers_b,
        json={"product_name": "Beta Organic Rice", "units": 2},
    )

    # Merchant A attempts to view B's sales
    res_sales = client.get(f"/api/v1/user/sales?email={email_b}", headers=headers_a)
    assert res_sales.status_code == 403

    # Merchant A attempts to view B's sales summary
    res_summary = client.get(f"/api/v1/user/sales/summary?email={email_b}", headers=headers_a)
    assert res_summary.status_code == 403

    # Merchant A attempts to record a sale with user_email = B
    res_record = client.post(
        "/api/v1/user/sales",
        headers=headers_a,
        json={
            "user_email": email_b,
            "product_name": "Beta Organic Rice",
            "units": 1,
        },
    )
    assert res_record.status_code == 403


# ==============================================================================
# SEC-02: PASSWORD HASHING & LEGACY MIGRATION TESTS
# ==============================================================================

def test_new_user_gets_pbkdf2_hash(client, temp_db):
    """New registrations must store PBKDF2-HMAC-SHA256 hashes with unique salts."""
    email = f"pbkdf2_user_{uuid.uuid4().hex[:6]}@store.in"
    res = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "SecurePassword123!", "store_name": "PBKDF2 Shop"},
    )
    assert res.status_code == 200

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM app_users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()

    stored_hash = row[0]
    assert stored_hash.startswith("pbkdf2_sha256$600000$")
    parts = stored_hash.split("$")
    assert len(parts) == 4
    assert len(parts[2]) == 32  # 16 bytes in hex


def test_legacy_account_login_and_auto_rehash(client, temp_db):
    """Legacy account with SHA-256 hash must authenticate AND be upgraded to PBKDF2 600k."""
    legacy_email = f"legacy_{uuid.uuid4().hex[:6]}@sharmakirana.in"
    raw_pass = "kirana2026"
    legacy_hash = hashlib.sha256(f"{LEGACY_SALT}_{raw_pass}".encode()).hexdigest()

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO app_users (id, email, password_hash, store_name, phone, manager, created_at)
           VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
        (str(uuid.uuid4()), legacy_email, legacy_hash, "Legacy Kirana", "+91 99999", "Owner"),
    )
    conn.commit()
    conn.close()

    # Login with legacy account
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": legacy_email, "password": raw_pass},
    )
    assert login_res.status_code == 200
    token = login_res.json()["token"]
    assert len(token) == 64  # Cryptographically random token

    # Check database: password_hash must now be upgraded to PBKDF2 600k!
    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT password_hash FROM app_users WHERE email = ?", (legacy_email,))
    upgraded_hash = cursor.fetchone()[0]
    conn.close()

    assert upgraded_hash.startswith("pbkdf2_sha256$600000$")
    assert upgraded_hash != legacy_hash

    # Subsequent login succeeds with the upgraded PBKDF2 hash
    login_res2 = client.post(
        "/api/v1/auth/login",
        json={"email": legacy_email, "password": raw_pass},
    )
    assert login_res2.status_code == 200


def test_invalid_password_rejected(client):
    """Invalid credentials must return 401 Unauthorized."""
    res = client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@store.in", "password": "wrong"},
    )
    assert res.status_code == 401


# ==============================================================================
# SEC-03: SECURE SESSION TOKENS & LOGOUT TESTS
# ==============================================================================

def test_session_token_format_and_persistence(client, temp_db):
    """Session tokens must be 256-bit cryptographically secure strings stored in app_sessions."""
    reg_res = client.post(
        "/api/v1/auth/register",
        json={"email": "session_test@store.in", "password": "ValidPassword123!", "store_name": "Sesh"},
    )
    token = reg_res.json()["token"]
    assert len(token) == 64

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute("SELECT user_email, revoked, expires_at FROM app_sessions WHERE token = ?", (token,))
    row = cursor.fetchone()
    conn.close()

    assert row is not None
    assert row[0] == "session_test@store.in"
    assert row[1] == 0


def test_logout_revokes_token(client):
    """Calling /api/v1/auth/logout must revoke the active token so subsequent requests fail."""
    login_res = client.post(
        "/api/v1/auth/register",
        json={"email": "logout_test@store.in", "password": "Password123!", "store_name": "Logout Shop"},
    )
    token = login_res.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Verify active
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200

    # Logout
    logout_res = client.post("/api/v1/auth/logout", headers=headers)
    assert logout_res.status_code == 200
    assert logout_res.json()["status"] == "ok"

    # Attempting to use revoked token must return 401
    me_res = client.get("/api/v1/auth/me", headers=headers)
    assert me_res.status_code == 401
    assert "revoked" in me_res.json()["detail"].lower()


def test_expired_token_rejected(client, temp_db):
    """Expired session tokens must be rejected with 401."""
    uid = uuid.uuid4().hex[:6]
    token = f"expired_token_{uid}_1234567890abcdef1234567890abcdef1234567890"
    user_id = str(uuid.uuid4())
    email = f"expired_{uid}@store.in"
    yesterday = (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)).isoformat()

    conn = sqlite3.connect(temp_db)
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO app_users (id, email, password_hash, store_name, created_at)
           VALUES (?, ?, 'hash', 'Expired Store', datetime('now'))""",
        (user_id, email),
    )
    cursor.execute(
        """INSERT INTO app_sessions (token, user_id, user_email, created_at, expires_at, revoked)
           VALUES (?, ?, ?, ?, ?, 0)""",
        (token, user_id, email, yesterday, yesterday),
    )
    conn.commit()
    conn.close()

    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()


def test_forged_legacy_deterministic_token_rejected(client):
    """Deterministic SHA256(id_email_date) tokens must be rejected (no legacy token forgery)."""
    today_str = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%d")
    forged = hashlib.sha256(f"usr_demo_sharma_owner@sharmakirana.in_{today_str}".encode()).hexdigest()
    res = client.get("/api/v1/user/products", headers={"Authorization": f"Bearer {forged}"})
    assert res.status_code == 401


def test_unauthenticated_supabase_routes_rejected(client):
    """Live Supabase application routes must require authentication."""
    assert client.get("/api/v1/products").status_code == 401
    assert client.get("/api/v1/insights").status_code == 401
    assert client.get("/api/v1/purchase-orders").status_code == 401
    assert client.get("/api/v1/shop").status_code == 401


def test_cross_tenant_idempotency_key_no_collision(client, two_merchants):
    """Two distinct merchants using the identical idempotency_key must not cause 500 error."""
    headers_a = two_merchants["a"]["headers"]
    headers_b = two_merchants["b"]["headers"]
    shared_idem_key = f"pos-txn-{uuid.uuid4().hex[:6]}"

    res_a = client.post(
        "/api/v1/user/sales",
        headers=headers_a,
        json={"product_name": "Alpha Premium Tea", "units": 1, "idempotency_key": shared_idem_key},
    )
    assert res_a.status_code == 200

    res_b = client.post(
        "/api/v1/user/sales",
        headers=headers_b,
        json={"product_name": "Beta Organic Rice", "units": 1, "idempotency_key": shared_idem_key},
    )
    assert res_b.status_code == 200


def test_negative_financial_fields_rejected(client, two_merchants):
    """Negative prices, costs, or stock quantities must be rejected by schema validation."""
    headers_a = two_merchants["a"]["headers"]
    res = client.post(
        "/api/v1/user/products",
        headers=headers_a,
        json={"name": "Bad Price", "unit_price": -50.0, "stock_on_hand": -5},
    )
    assert res.status_code == 422


# ==============================================================================
# SEC-04: GEMINI AI ASSISTANT PROXY TESTS
# ==============================================================================

def test_ai_assistant_proxy_isolated_context(client, two_merchants):
    """AI Assistant endpoint must be authenticated and only analyze the caller's store data."""
    headers_a = two_merchants["a"]["headers"]
    headers_b = two_merchants["b"]["headers"]

    # Merchant A query
    res_a = client.post("/api/v1/ai/assistant", headers=headers_a, json={})
    assert res_a.status_code == 200
    data_a = res_a.json()
    assert data_a["status"] == "ok"
    assert data_a["store_name"] == "Store Alpha"
    assert data_a["metrics"]["total_products"] == 1

    # Merchant B query
    res_b = client.post("/api/v1/ai/assistant", headers=headers_b, json={})
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["status"] == "ok"
    assert data_b["store_name"] == "Store Beta"


# ==============================================================================
# SEC-05: CORS CONFIGURATION TESTS
# ==============================================================================

def test_cors_origins_do_not_contain_wildcard_by_default():
    """ALLOWED_ORIGINS must not contain wildcard '*' by default."""
    assert "*" not in ALLOWED_ORIGINS
    assert "http://localhost:3000" in ALLOWED_ORIGINS

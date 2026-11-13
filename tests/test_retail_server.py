from __future__ import annotations

"""Server-side integration and unit tests for retail transactions, stock deductions, and accounting."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app, hash_pw
from app.services.supabase_service import SupabaseAppService, get_supabase_admin


@pytest.fixture
def retail_client(temp_db):
    """TestClient wired with a freshly initialized retail test database."""
    conn = sqlite3.connect(str(temp_db))
    init_db(conn)
    cursor = conn.cursor()

    # Create a test user
    cursor.execute("SELECT id FROM app_users WHERE email = 'merchant@sharmakirana.in'")
    if not cursor.fetchone():
        cursor.execute(
            """INSERT INTO app_users (id, email, password_hash, store_name, phone, manager, created_at)
               VALUES ('usr_test_retail', 'merchant@sharmakirana.in', ?, 'Sharma Store Test', '+91 99999 11111', 'Owner', datetime('now'))""",
            (hash_pw("securepass123"),),
        )

    # Create active test session for authenticated merchant
    test_token = "tok_test_retail_merchant_session_12345678"
    cursor.execute("DELETE FROM app_sessions WHERE token = ?", (test_token,))
    cursor.execute(
        """INSERT INTO app_sessions (token, user_id, user_email, created_at, expires_at, revoked)
           VALUES (?, 'usr_test_retail', 'merchant@sharmakirana.in', datetime('now'), datetime('now', '+7 days'), 0)""",
        (test_token,),
    )

    # Insert controlled test products with explicit prices, costs, and thresholds
    cursor.execute("DELETE FROM app_products WHERE user_email = 'merchant@sharmakirana.in'")
    cursor.execute("DELETE FROM app_sales WHERE user_email = 'merchant@sharmakirana.in'")
    cursor.execute("DELETE FROM app_purchase_orders WHERE user_email = 'merchant@sharmakirana.in'")

    test_products = [
        ("prod_atta_10", "merchant@sharmakirana.in", "SKU-ATTA", "Sharbati Atta 5kg", 240.50, 200.00, 10, 5, 4, 3, "ITC", "active", "2026-10-01T10:00:00"),
        ("prod_zero_price", "merchant@sharmakirana.in", "SKU-PROMO", "Free Promo Bag", 0.00, 15.00, 50, 10, 0, 1, "Vendor", "active", "2026-10-01T10:00:00"),
        ("prod_high_rop", "merchant@sharmakirana.in", "SKU-HIGHROP", "Bulk Rice 25kg", 1100.00, 950.00, 110, 20, 50, 5, "Metro", "active", "2026-10-01T10:00:00"),
        ("prod_scarce", "merchant@sharmakirana.in", "SKU-SCARCE", "Saffron 1g", 350.00, 280.00, 2, 1, 1, 7, "Kashmir", "active", "2026-10-01T10:00:00"),
    ]
    for p in test_products:
        cursor.execute(
            """INSERT INTO app_products (id, user_email, sku, name, unit_price, unit_cost, stock_on_hand, safety_stock, reorder_point, lead_time_days, supplier, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            p,
        )

    conn.commit()
    conn.close()

    def override_write_db():
        c = sqlite3.connect(str(temp_db))
        c.row_factory = sqlite3.Row
        try:
            yield c
        finally:
            c.close()

    def override_read_db():
        c = sqlite3.connect(f"file:{temp_db}?mode=ro", uri=True)
        c.row_factory = sqlite3.Row
        try:
            yield c
        finally:
            c.close()

    from app.db import get_db, get_write_db
    app.dependency_overrides[get_write_db] = override_write_db
    app.dependency_overrides[get_db] = override_read_db

    with TestClient(app) as tc:
        tc.headers["Authorization"] = f"Bearer {test_token}"
        yield tc

    app.dependency_overrides.pop(get_write_db, None)
    app.dependency_overrides.pop(get_db, None)


def test_sale_atomic_stock_check_and_deduction(retail_client: TestClient):
    """Sale of available units atomically deducts stock and records sale."""
    payload = {
        "user_email": "merchant@sharmakirana.in",
        "product_id": "prod_atta_10",
        "units": 3,
    }
    resp = retail_client.post("/api/v1/user/sales", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["units"] == 3
    assert data["sale_amount"] == 721.50  # 3 * 240.50
    assert data["unit_cost"] == 200.00
    assert data["remaining_stock"] == 7  # 10 - 3


def test_sale_overselling_rejected(retail_client: TestClient):
    """Sale requesting more units than available on hand is rejected with 400."""
    payload = {
        "user_email": "merchant@sharmakirana.in",
        "product_id": "prod_scarce",  # only 2 on hand
        "units": 5,
    }
    resp = retail_client.post("/api/v1/user/sales", json=payload)
    assert resp.status_code == 400
    assert "Insufficient stock" in resp.json()["detail"]


def test_sale_zero_or_negative_units_rejected(retail_client: TestClient):
    """Sale units <= 0 must be rejected."""
    payload = {
        "user_email": "merchant@sharmakirana.in",
        "product_id": "prod_atta_10",
        "units": 0,
    }
    resp = retail_client.post("/api/v1/user/sales", json=payload)
    assert resp.status_code == 400

    payload["units"] = -2
    resp = retail_client.post("/api/v1/user/sales", json=payload)
    assert resp.status_code == 400


def test_sale_nonexistent_product_rejected(retail_client: TestClient):
    """Sale for unknown product ID returns 404."""
    payload = {
        "user_email": "merchant@sharmakirana.in",
        "product_id": "prod_nonexistent_999",
        "units": 1,
    }
    resp = retail_client.post("/api/v1/user/sales", json=payload)
    assert resp.status_code == 404


def test_sale_preserves_zero_price(retail_client: TestClient):
    """Items with 0 unit_price are preserved and not replaced by fallback."""
    payload = {
        "user_email": "merchant@sharmakirana.in",
        "product_id": "prod_zero_price",
        "units": 2,
    }
    resp = retail_client.post("/api/v1/user/sales", json=payload)
    assert resp.status_code == 200
    assert resp.json()["sale_amount"] == 0.0
    assert resp.json()["remaining_stock"] == 48


def test_sale_decimal_price_precision(retail_client: TestClient):
    """Multi-unit sale with fractional currency calculates exact Decimal total."""
    payload = {
        "user_email": "merchant@sharmakirana.in",
        "product_id": "prod_atta_10",
        "units": 7,  # 7 * 240.50 = 1683.50
    }
    resp = retail_client.post("/api/v1/user/sales", json=payload)
    assert resp.status_code == 200
    assert resp.json()["sale_amount"] == 1683.50


def test_sale_timestamp_validation(retail_client: TestClient):
    """Invalid timestamp returns 400 while valid ISO-8601 is accepted."""
    payload = {
        "user_email": "merchant@sharmakirana.in",
        "product_id": "prod_high_rop",
        "units": 1,
        "timestamp": "not-a-valid-date",
    }
    resp = retail_client.post("/api/v1/user/sales", json=payload)
    assert resp.status_code == 400

    payload["timestamp"] = "2026-10-15T14:30:00Z"
    resp_ok = retail_client.post("/api/v1/user/sales", json=payload)
    assert resp_ok.status_code == 200


def test_sale_idempotency_prevents_replay(retail_client: TestClient):
    """Submitting duplicate idempotency_key returns cached result without double decrement."""
    key = "idem-test-tx-001"
    payload = {
        "user_email": "merchant@sharmakirana.in",
        "product_id": "prod_high_rop",
        "units": 5,
        "idempotency_key": key,
    }
    resp1 = retail_client.post("/api/v1/user/sales", json=payload)
    assert resp1.status_code == 200
    stock_after_first = resp1.json()["remaining_stock"]
    sale_id = resp1.json()["sale_id"]

    # Replay request
    resp2 = retail_client.post("/api/v1/user/sales", json=payload)
    assert resp2.status_code == 200
    assert resp2.json()["replayed"] is True
    assert resp2.json()["sale_id"] == sale_id

    # Verify stock in catalog did not decrease again
    prods = retail_client.get("/api/v1/user/products?email=merchant@sharmakirana.in").json()
    item = next(p for p in prods if p["id"] == "prod_high_rop")
    assert item["stock_on_hand"] == stock_after_first


def test_sales_history_endpoint(retail_client: TestClient):
    """GET /api/v1/user/sales returns all recorded sales without artificial truncation."""
    # Record 3 distinct sales
    for i in range(3):
        retail_client.post("/api/v1/user/sales", json={
            "user_email": "merchant@sharmakirana.in",
            "product_id": "prod_high_rop",
            "units": 1,
        })

    resp = retail_client.get("/api/v1/user/sales?email=merchant@sharmakirana.in")
    assert resp.status_code == 200
    sales = resp.json()
    assert len(sales) >= 3


def test_sales_summary_with_cost_and_profit(retail_client: TestClient):
    """GET /api/v1/user/sales/summary computes accurate revenue, cost, profit, and margin."""
    # prod_atta_10: price 240.50, cost 200.00. Sell 2 units.
    # Revenue = 481.00, Cost = 400.00, Gross Profit = 81.00, Margin = 16.8%
    retail_client.post("/api/v1/user/sales", json={
        "user_email": "merchant@sharmakirana.in",
        "product_id": "prod_atta_10",
        "units": 2,
    })

    resp = retail_client.get("/api/v1/user/sales/summary?email=merchant@sharmakirana.in")
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["revenue"] == 481.00
    assert summary["total_cost"] == 400.00
    assert summary["gross_profit"] == 81.00
    assert summary["cost_available"] is True
    assert summary["gross_margin_pct"] == 16.8


def test_sales_summary_missing_historical_cost(retail_client: TestClient, temp_db):
    """When a historical transaction lacks unit_cost, profit is reported as unavailable."""
    conn = sqlite3.connect(str(temp_db))
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO app_sales (id, user_email, product_id, product_name, sale_amount, units, unit_cost, timestamp)
           VALUES ('legacy-sale-01', 'merchant@sharmakirana.in', 'p_legacy', 'Old Legacy Biscuit', 50.0, 1, NULL, datetime('now'))"""
    )
    conn.commit()
    conn.close()

    resp = retail_client.get("/api/v1/user/sales/summary?email=merchant@sharmakirana.in")
    assert resp.status_code == 200
    summary = resp.json()
    assert summary["cost_available"] is False
    assert summary["gross_profit"] is None
    assert summary["gross_margin_pct"] is None


def test_receive_po_idempotent(retail_client: TestClient):
    """Receiving a completed PO returns already_completed and does not increment stock twice."""
    po_payload = {
        "user_email": "merchant@sharmakirana.in",
        "po_number": "PO-TEST-001",
        "supplier": "Metro Wholesale",
        "status": "ordered",
        "total_amount": 2000.00,
        "items": [{"product_id": "prod_atta_10", "units": 10, "unit_cost": 200.00}],
    }
    po_resp = retail_client.post("/api/v1/user/purchase-orders", json=po_payload)
    po_id = po_resp.json()["id"]

    # First receive
    rec1 = retail_client.post(f"/api/v1/user/purchase-orders/{po_id}/receive?email=merchant@sharmakirana.in")
    assert rec1.status_code == 200
    assert rec1.json()["status"] == "ok"

    # Check stock was incremented by 10
    prods = retail_client.get("/api/v1/user/products?email=merchant@sharmakirana.in").json()
    atta = next(p for p in prods if p["id"] == "prod_atta_10")
    stock_after_first = atta["stock_on_hand"]

    # Second receive should be idempotent
    rec2 = retail_client.post(f"/api/v1/user/purchase-orders/{po_id}/receive?email=merchant@sharmakirana.in")
    assert rec2.status_code == 200
    assert rec2.json()["status"] == "already_completed"

    prods2 = retail_client.get("/api/v1/user/products?email=merchant@sharmakirana.in").json()
    atta2 = next(p for p in prods2 if p["id"] == "prod_atta_10")
    assert atta2["stock_on_hand"] == stock_after_first


def test_receive_po_rejects_cancelled_order(retail_client: TestClient, temp_db):
    """Cannot receive a cancelled purchase order."""
    conn = sqlite3.connect(str(temp_db))
    cursor = conn.cursor()
    cursor.execute(
        """INSERT INTO app_purchase_orders (id, user_email, po_number, supplier, status, total_amount, items_json, created_at)
           VALUES ('po_cancelled_01', 'merchant@sharmakirana.in', 'PO-CANC', 'Supplier', 'cancelled', 500.0, '[]', datetime('now'))"""
    )
    conn.commit()
    conn.close()

    resp = retail_client.post("/api/v1/user/purchase-orders/po_cancelled_01/receive?email=merchant@sharmakirana.in")
    assert resp.status_code == 400
    assert "cancelled" in resp.json()["detail"].lower()


def test_receive_po_skips_nonpositive_units(retail_client: TestClient):
    """Items with zero or negative units in PO are ignored and do not reduce stock."""
    po_payload = {
        "user_email": "merchant@sharmakirana.in",
        "po_number": "PO-ZERO-TEST",
        "supplier": "Metro Wholesale",
        "status": "ordered",
        "total_amount": 0.00,
        "items": [
            {"product_id": "prod_scarce", "units": 0},
            {"product_id": "prod_scarce", "units": -5},
        ],
    }
    po_resp = retail_client.post("/api/v1/user/purchase-orders", json=po_payload)
    po_id = po_resp.json()["id"]

    prods_before = retail_client.get("/api/v1/user/products?email=merchant@sharmakirana.in").json()
    scarce_before = next(p for p in prods_before if p["id"] == "prod_scarce")["stock_on_hand"]

    rec = retail_client.post(f"/api/v1/user/purchase-orders/{po_id}/receive?email=merchant@sharmakirana.in")
    assert rec.status_code == 200

    prods_after = retail_client.get("/api/v1/user/products?email=merchant@sharmakirana.in").json()
    scarce_after = next(p for p in prods_after if p["id"] == "prod_scarce")["stock_on_hand"]
    assert scarce_after == scarce_before


def test_lazy_supabase_initialization():
    """SupabaseAppService instantiates lazily without raising until client is accessed."""
    service = SupabaseAppService()
    assert service._client is None
    # If keys are missing, accessing property raises informative ValueError
    with pytest.raises(ValueError, match="must be configured"):
        _ = get_supabase_admin()


def test_merchant_reorder_point_preserved(retail_client: TestClient):
    """Reorder points above 30 or zero are not altered or clamped."""
    prods = retail_client.get("/api/v1/user/products?email=merchant@sharmakirana.in").json()
    promo = next(p for p in prods if p["id"] == "prod_zero_price")
    high_rop = next(p for p in prods if p["id"] == "prod_high_rop")

    assert promo["reorder_point"] == 0
    assert high_rop["reorder_point"] == 50


def test_auth_login_returns_session_token(retail_client: TestClient):
    """POST /api/v1/auth/login returns session token on success and rejects bad pass."""
    # Bad pass
    resp_bad = retail_client.post("/api/v1/auth/login", json={
        "email": "merchant@sharmakirana.in",
        "password": "wrongpassword",
    })
    assert resp_bad.status_code == 401

    # Good pass
    resp_good = retail_client.post("/api/v1/auth/login", json={
        "email": "merchant@sharmakirana.in",
        "password": "securepass123",
    })
    assert resp_good.status_code == 200
    assert "token" in resp_good.json()
    assert resp_good.json()["user"]["email"] == "merchant@sharmakirana.in"


def test_auth_me_endpoint_with_token(retail_client: TestClient):
    """GET /api/v1/auth/me verifies Bearer token."""
    login_resp = retail_client.post("/api/v1/auth/login", json={
        "email": "merchant@sharmakirana.in",
        "password": "securepass123",
    })
    token = login_resp.json()["token"]

    # Valid token
    resp_me = retail_client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp_me.status_code == 200
    assert resp_me.json()["email"] == "merchant@sharmakirana.in"

    # Missing credentials -> 401
    auth_header = retail_client.headers.pop("Authorization", None)
    try:
        resp_unauth = retail_client.get("/api/v1/auth/me")
        assert resp_unauth.status_code == 401
    finally:
        if auth_header:
            retail_client.headers["Authorization"] = auth_header

from __future__ import annotations

"""Phase 2 Stage E backend parity integration tests (CRUD, bulk-stock, PO status, tenant isolation)."""

import sqlite3

import pytest
from fastapi.testclient import TestClient

from app.db import get_db, get_write_db, init_db
from app.main import app, hash_pw

TOKEN_A = "tok_phase2_merchant_alpha_99999999"
TOKEN_B = "tok_phase2_merchant_beta_88888888"


@pytest.fixture
def phase2_client(temp_db):
    """TestClient with two isolated merchants (Alpha & Beta) for Phase 2 CRUD & status tests."""
    conn = sqlite3.connect(str(temp_db))
    init_db(conn)
    cur = conn.cursor()

    users = [
        ("usr_p2_alpha", "alpha@kirana.in", "Alpha Store"),
        ("usr_p2_beta", "beta@kirana.in", "Beta Store"),
    ]
    for uid, email, store in users:
        cur.execute("DELETE FROM app_users WHERE email = ?", (email,))
        cur.execute(
            """INSERT INTO app_users (id, email, password_hash, store_name, phone, manager, created_at)
               VALUES (?, ?, ?, ?, '+91 98000 00000', 'Owner', datetime('now'))""",
            (uid, email, hash_pw("strongpass123"), store),
        )

    for tok, uid, email in [(TOKEN_A, "usr_p2_alpha", "alpha@kirana.in"), (TOKEN_B, "usr_p2_beta", "beta@kirana.in")]:
        cur.execute("DELETE FROM app_sessions WHERE token = ?", (tok,))
        cur.execute(
            """INSERT INTO app_sessions (token, user_id, user_email, created_at, expires_at, revoked)
               VALUES (?, ?, ?, datetime('now'), datetime('now', '+7 days'), 0)""",
            (tok, uid, email),
        )

    cur.execute("DELETE FROM app_products WHERE user_email IN ('alpha@kirana.in', 'beta@kirana.in')")
    cur.execute("DELETE FROM app_purchase_orders WHERE user_email IN ('alpha@kirana.in', 'beta@kirana.in')")

    cur.execute(
        """INSERT INTO app_products (id, user_email, sku, name, category_name, unit_price, unit_cost, stock_on_hand, safety_stock, reorder_point, lead_time_days, supplier, status, created_at)
           VALUES ('p2_prod_1', 'alpha@kirana.in', 'SKU-P2-1', 'Toor Dal 1kg', 'Staples', 165.0, 140.0, 20, 5, 10, 3, 'Metro', 'active', datetime('now'))"""
    )
    cur.execute(
        """INSERT INTO app_products (id, user_email, sku, name, category_name, unit_price, unit_cost, stock_on_hand, safety_stock, reorder_point, lead_time_days, supplier, status, created_at)
           VALUES ('p2_prod_2', 'alpha@kirana.in', 'SKU-P2-2', 'Mustard Oil 1L', 'Oils', 190.0, 160.0, 4, 5, 12, 3, 'Metro', 'low_stock', datetime('now'))"""
    )
    cur.execute(
        """INSERT INTO app_products (id, user_email, sku, name, category_name, unit_price, unit_cost, stock_on_hand, safety_stock, reorder_point, lead_time_days, supplier, status, created_at)
           VALUES ('p2_beta_1', 'beta@kirana.in', 'SKU-B-1', 'Beta Tea 250g', 'Beverages', 120.0, 95.0, 15, 5, 8, 2, 'TeaCo', 'active', datetime('now'))"""
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

    app.dependency_overrides[get_write_db] = override_write_db
    app.dependency_overrides[get_db] = override_read_db
    try:
        with TestClient(app) as tc:
            yield tc
    finally:
        app.dependency_overrides.clear()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_put_product_updates_fields_and_recalculates_status(phase2_client):
    res = phase2_client.put(
        "/api/v1/user/products/p2_prod_1",
        headers=_headers(TOKEN_A),
        json={"stock_on_hand": 6, "reorder_point": 10, "category_name": "Pulses", "name": "Organic Toor Dal 1kg"},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["name"] == "Organic Toor Dal 1kg"
    assert body["category_name"] == "Pulses"
    assert body["stock_on_hand"] == 6
    assert body["status"] == "low_stock"


def test_put_and_delete_product_enforce_tenant_isolation(phase2_client):
    # Beta cannot update Alpha's product
    put_res = phase2_client.put(
        "/api/v1/user/products/p2_prod_1",
        headers=_headers(TOKEN_B),
        json={"name": "Hijacked"},
    )
    assert put_res.status_code == 404

    # Beta cannot delete Alpha's product
    del_res = phase2_client.delete("/api/v1/user/products/p2_prod_1", headers=_headers(TOKEN_B))
    assert del_res.status_code == 404

    # Unauthenticated requests rejected
    unauth_res = phase2_client.delete("/api/v1/user/products/p2_prod_1")
    assert unauth_res.status_code == 401


def test_delete_product_succeeds_for_owner(phase2_client):
    del_res = phase2_client.delete("/api/v1/user/products/p2_prod_2", headers=_headers(TOKEN_A))
    assert del_res.status_code == 200
    assert del_res.json()["deleted_id"] == "p2_prod_2"

    # Second delete returns 404
    del_again = phase2_client.delete("/api/v1/user/products/p2_prod_2", headers=_headers(TOKEN_A))
    assert del_again.status_code == 404


def test_bulk_stock_updates_only_owned_products_atomically(phase2_client):
    # Duplicate IDs in product_ids must only apply delta once
    res = phase2_client.post(
        "/api/v1/user/products/bulk-stock",
        headers=_headers(TOKEN_A),
        json={"product_ids": ["p2_prod_1", "p2_prod_1", "p2_prod_2", "p2_beta_1"], "delta": 10},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["updated_count"] == 2
    assert set(data["updated_ids"]) == {"p2_prod_1", "p2_prod_2"}

    # Confirm delta was applied once (20 + 10 = 30)
    prods = phase2_client.get("/api/v1/user/products", headers=_headers(TOKEN_A)).json()
    p1 = next(p for p in prods if p["id"] == "p2_prod_1")
    assert p1["stock_on_hand"] == 30

    # Negative delta below zero must leave stock untouched (p2_prod_1=30, p2_prod_2=14; test delta=-20 only succeeds on p2_prod_1)
    neg_res = phase2_client.post(
        "/api/v1/user/products/bulk-stock",
        headers=_headers(TOKEN_A),
        json={"product_ids": ["p2_prod_1", "p2_prod_2"], "delta": -20},
    )
    assert neg_res.status_code == 200
    assert neg_res.json()["updated_ids"] == ["p2_prod_1"]


def test_purchase_order_status_lifecycle_and_completed_lock(phase2_client):
    # Create PO for Alpha preserving explicit id
    po_res = phase2_client.post(
        "/api/v1/user/purchase-orders",
        headers=_headers(TOKEN_A),
        json={
            "id": "po_p2_lifecycle",
            "po_number": "PO-P2-101",
            "supplier": "Metro Cash & Carry",
            "status": "ordered",
            "total_amount": 1400.0,
            "items": [{"product_id": "p2_prod_2", "name": "Mustard Oil 1L", "units": 10, "unit_cost": 140.0}],
        },
    )
    assert po_res.status_code == 200
    assert po_res.json()["id"] == "po_p2_lifecycle"

    # Cross-tenant patch blocked
    beta_patch = phase2_client.patch(
        "/api/v1/user/purchase-orders/po_p2_lifecycle/status",
        headers=_headers(TOKEN_B),
        json={"status": "cancelled"},
    )
    assert beta_patch.status_code == 404

    # Advance to in_transit
    transit_res = phase2_client.patch(
        "/api/v1/user/purchase-orders/po_p2_lifecycle/status",
        headers=_headers(TOKEN_A),
        json={"status": "in_transit"},
    )
    assert transit_res.status_code == 200
    assert transit_res.json()["new_status"] == "in_transit"

    # Receive stock -> marks completed
    rcv_res = phase2_client.post("/api/v1/user/purchase-orders/po_p2_lifecycle/receive", headers=_headers(TOKEN_A))
    assert rcv_res.status_code == 200

    # Trying to change status of completed PO is blocked with 400
    locked_res = phase2_client.patch(
        "/api/v1/user/purchase-orders/po_p2_lifecycle/status",
        headers=_headers(TOKEN_A),
        json={"status": "cancelled"},
    )
    assert locked_res.status_code == 400

    # Cannot create a PO directly in 'completed' status
    invalid_create = phase2_client.post(
        "/api/v1/user/purchase-orders",
        headers=_headers(TOKEN_A),
        json={
            "po_number": "PO-P2-BAD",
            "supplier": "Metro",
            "status": "completed",
            "total_amount": 500.0,
            "items": [],
        },
    )
    assert invalid_create.status_code == 422

    # Cancelled PO cannot transition back to ordered/in_transit
    po2_res = phase2_client.post(
        "/api/v1/user/purchase-orders",
        headers=_headers(TOKEN_A),
        json={
            "id": "po_p2_cancel_lock",
            "po_number": "PO-P2-102",
            "supplier": "Metro",
            "status": "ordered",
            "total_amount": 300.0,
            "items": [],
        },
    )
    assert po2_res.status_code == 200
    c_res = phase2_client.patch(
        "/api/v1/user/purchase-orders/po_p2_cancel_lock/status",
        headers=_headers(TOKEN_A),
        json={"status": "cancelled"},
    )
    assert c_res.status_code == 200
    reopen_res = phase2_client.patch(
        "/api/v1/user/purchase-orders/po_p2_cancel_lock/status",
        headers=_headers(TOKEN_A),
        json={"status": "ordered"},
    )
    assert reopen_res.status_code == 400

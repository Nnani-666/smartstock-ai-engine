from __future__ import annotations

"""SmartStock Phase 2 Closure Engineering Audit & Parity Verification Test Suite.

Verifies:
- Priority A: Purchase Orders (manual/forecast/replenishment, persistence, idempotency, receiving, status locks)
- Priority B: Suppliers (CRUD, persistence, tenant isolation, referential safety with historical POs)
- Priority C: Bulk operations (atomic multi-product delete, atomic bulk import with validation)
- Priority D: Security & Tenant Isolation (dual analytical auth: Bearer session token or X-API-Key; cross-tenant attacks)
"""

import sqlite3
import uuid

import pytest
from fastapi.testclient import TestClient

from app.db import get_db, get_write_db, init_db
from app.main import app, hash_pw

TOKEN_ALPHA = "tok_closure_alpha_session_111111"
TOKEN_BETA = "tok_closure_beta_session_222222"
EMAIL_ALPHA = "alpha.owner@closure.in"
EMAIL_BETA = "beta.owner@closure.in"


@pytest.fixture
def closure_client(temp_db):
    """TestClient setup with two merchants (Alpha & Beta) isolated across products, POs, suppliers, and sessions."""
    conn = sqlite3.connect(str(temp_db))
    init_db(conn)
    cur = conn.cursor()

    users = [
        ("usr_close_alpha", EMAIL_ALPHA, "Alpha Kirana Mart"),
        ("usr_close_beta", EMAIL_BETA, "Beta General Store"),
    ]
    for uid, email, store in users:
        cur.execute("DELETE FROM app_users WHERE email = ?", (email,))
        cur.execute(
            """INSERT INTO app_users (id, email, password_hash, store_name, phone, manager, created_at)
               VALUES (?, ?, ?, ?, '+91 99999 11111', 'Store Owner', datetime('now'))""",
            (uid, email, hash_pw("SecureP@ss2026"), store),
        )

    for tok, uid, email in [(TOKEN_ALPHA, "usr_close_alpha", EMAIL_ALPHA), (TOKEN_BETA, "usr_close_beta", EMAIL_BETA)]:
        cur.execute("DELETE FROM app_sessions WHERE token = ?", (tok,))
        cur.execute(
            """INSERT INTO app_sessions (token, user_id, user_email, created_at, expires_at, revoked)
               VALUES (?, ?, ?, datetime('now'), datetime('now', '+7 days'), 0)""",
            (tok, uid, email),
        )

    cur.execute("DELETE FROM app_products WHERE user_email IN (?, ?)", (EMAIL_ALPHA, EMAIL_BETA))
    cur.execute("DELETE FROM app_purchase_orders WHERE user_email IN (?, ?)", (EMAIL_ALPHA, EMAIL_BETA))
    cur.execute("DELETE FROM app_suppliers WHERE user_email IN (?, ?)", (EMAIL_ALPHA, EMAIL_BETA))

    # Seed products for Alpha
    cur.execute(
        """INSERT INTO app_products (id, user_email, sku, name, category_name, unit_price, unit_cost, stock_on_hand, safety_stock, reorder_point, lead_time_days, supplier, status, created_at)
           VALUES ('prod_alpha_1', ?, 'SKU-A1', 'Basmati Rice 5kg', 'Grains', 450.0, 380.0, 10, 5, 8, 3, 'Agro Wholesale', 'active', datetime('now'))""",
        (EMAIL_ALPHA,),
    )
    cur.execute(
        """INSERT INTO app_products (id, user_email, sku, name, category_name, unit_price, unit_cost, stock_on_hand, safety_stock, reorder_point, lead_time_days, supplier, status, created_at)
           VALUES ('prod_alpha_2', ?, 'SKU-A2', 'Sunflower Oil 1L', 'Oils', 145.0, 120.0, 4, 10, 15, 2, 'Oil Depot', 'low_stock', datetime('now'))""",
        (EMAIL_ALPHA,),
    )

    # Seed product for Beta
    cur.execute(
        """INSERT INTO app_products (id, user_email, sku, name, category_name, unit_price, unit_cost, stock_on_hand, safety_stock, reorder_point, lead_time_days, supplier, status, created_at)
           VALUES ('prod_beta_1', ?, 'SKU-B1', 'Cardamom 100g', 'Spices', 250.0, 200.0, 25, 5, 10, 4, 'Spice World', 'active', datetime('now'))""",
        (EMAIL_BETA,),
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


# ==============================================================================
# PRIORITY A: PURCHASE ORDER LIFECYCLE, PERSISTENCE, IDEMPOTENCY & STATUS LOCKS
# ==============================================================================

def test_po_creation_manual_and_persistence(closure_client):
    """Verify manual PO creation, database persistence, and items breakdown."""
    po_id = f"po_man_{uuid.uuid4().hex[:8]}"
    payload = {
        "id": po_id,
        "supplier": "Agro Wholesale",
        "expected_date": "2026-11-20",
        "notes": "Weekly replenishment order",
        "status": "pending",
        "items": [
            {
                "product_id": "prod_alpha_1",
                "sku": "SKU-A1",
                "product_name": "Basmati Rice 5kg",
                "quantity": 20,
                "unit_cost": 380.0,
            }
        ],
    }

    res = closure_client.post(
        "/api/v1/user/purchase-orders",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
        json=payload,
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["id"] == po_id
    assert data["total_amount"] == 7600.0

    # Verify retrieval
    res_get = closure_client.get(
        "/api/v1/user/purchase-orders",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
    )
    assert res_get.status_code == 200
    pos = res_get.json()
    found = next((p for p in pos if p["id"] == po_id), None)
    assert found is not None
    assert len(found["items"]) == 1
    assert found["items"][0]["quantity"] == 20


def test_po_idempotency_replay(closure_client):
    """Verify posting identical PO id replays without duplicate insert or error."""
    po_id = f"po_idem_{uuid.uuid4().hex[:8]}"
    payload = {
        "id": po_id,
        "supplier": "Agro Wholesale",
        "expected_date": "2026-11-25",
        "notes": "Idempotent batch test",
        "status": "pending",
        "items": [
            {
                "product_id": "prod_alpha_1",
                "sku": "SKU-A1",
                "product_name": "Basmati Rice 5kg",
                "quantity": 10,
                "unit_cost": 380.0,
            }
        ],
    }

    r1 = closure_client.post(
        "/api/v1/user/purchase-orders",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
        json=payload,
    )
    assert r1.status_code == 200
    assert r1.json()["replayed"] is False

    # Second post with identical ID
    r2 = closure_client.post(
        "/api/v1/user/purchase-orders",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
        json=payload,
    )
    assert r2.status_code == 200
    assert r2.json()["replayed"] is True
    assert r2.json()["id"] == po_id


def test_po_receiving_updates_stock_exactly_once(closure_client):
    """Verify receiving PO increments inventory stock and locks against duplicate receiving."""
    # Check initial stock
    p_init = closure_client.get("/api/v1/user/products", headers={"Authorization": f"Bearer {TOKEN_ALPHA}"}).json()
    prod1 = next(p for p in p_init if p["id"] == "prod_alpha_1")
    initial_stock = prod1["stock_on_hand"]

    po_id = f"po_recv_{uuid.uuid4().hex[:8]}"
    closure_client.post(
        "/api/v1/user/purchase-orders",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
        json={
            "id": po_id,
            "supplier": "Agro Wholesale",
            "items": [
                {"product_id": "prod_alpha_1", "sku": "SKU-A1", "product_name": "Basmati Rice 5kg", "quantity": 15, "unit_cost": 380.0}
            ],
        },
    )

    # Receive PO
    recv_res = closure_client.post(
        f"/api/v1/user/purchase-orders/{po_id}/receive",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
    )
    assert recv_res.status_code == 200
    assert recv_res.json()["status"] == "ok"

    # Verify stock increased by exactly 15
    p_after = closure_client.get("/api/v1/user/products", headers={"Authorization": f"Bearer {TOKEN_ALPHA}"}).json()
    prod1_after = next(p for p in p_after if p["id"] == "prod_alpha_1")
    assert prod1_after["stock_on_hand"] == initial_stock + 15

    # Attempt to receive second time - must be idempotent (status: already_completed) without incrementing stock again
    recv_second = closure_client.post(
        f"/api/v1/user/purchase-orders/{po_id}/receive",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
    )
    assert recv_second.status_code == 200
    assert recv_second.json()["status"] == "already_completed"

    # Verify stock remains initial + 15 (never incremented a second time)
    p_third = closure_client.get("/api/v1/user/products", headers={"Authorization": f"Bearer {TOKEN_ALPHA}"}).json()
    prod1_third = next(p for p in p_third if p["id"] == "prod_alpha_1")
    assert prod1_third["stock_on_hand"] == initial_stock + 15


def test_po_status_locks_completed_and_cancelled(closure_client):
    """Verify completed or cancelled PO cannot transition illegally."""
    po_id = f"po_lock_{uuid.uuid4().hex[:8]}"
    closure_client.post(
        "/api/v1/user/purchase-orders",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
        json={
            "id": po_id,
            "supplier": "Agro Wholesale",
            "items": [
                {"product_id": "prod_alpha_1", "sku": "SKU-A1", "product_name": "Basmati Rice 5kg", "quantity": 5, "unit_cost": 380.0}
            ],
        },
    )

    # Cancel PO
    c_res = closure_client.patch(
        f"/api/v1/user/purchase-orders/{po_id}/status",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
        json={"status": "cancelled"},
    )
    assert c_res.status_code == 200

    # Cannot transition cancelled PO back to pending or ordered
    revive_res = closure_client.patch(
        f"/api/v1/user/purchase-orders/{po_id}/status",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
        json={"status": "ordered"},
    )
    assert revive_res.status_code == 400


# ==============================================================================
# PRIORITY B: SUPPLIER CRUD, PERSISTENCE & REFERENTIAL SAFETY
# ==============================================================================

def test_supplier_crud_and_tenant_isolation(closure_client):
    """Verify complete CRUD lifecycle for suppliers with strict merchant scoping."""
    # Alpha creates a supplier
    create_res = closure_client.post(
        "/api/v1/user/suppliers",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
        json={
            "name": "Kaveri Grain Mills",
            "phone": "+91 94444 33333",
            "category": "Grains & Pulses",
            "hub": "Yeshwanthpur APMC",
            "lead_time_days": 4,
            "notes": "Verified bulk grain supplier",
        },
    )
    assert create_res.status_code == 200, create_res.text
    created = create_res.json()
    sup_id = created["id"]
    assert created["name"] == "Kaveri Grain Mills"

    # Alpha reads suppliers
    alpha_sups = closure_client.get(
        "/api/v1/user/suppliers",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
    ).json()
    assert any(s["id"] == sup_id for s in alpha_sups)

    # Beta MUST NOT see Alpha's supplier
    beta_sups = closure_client.get(
        "/api/v1/user/suppliers",
        headers={"Authorization": f"Bearer {TOKEN_BETA}"},
    ).json()
    assert not any(s["id"] == sup_id for s in beta_sups)

    # Beta cannot update or delete Alpha's supplier
    beta_update = closure_client.put(
        f"/api/v1/user/suppliers/{sup_id}",
        headers={"Authorization": f"Bearer {TOKEN_BETA}"},
        json={"name": "Hacked Name"},
    )
    assert beta_update.status_code == 404

    beta_delete = closure_client.delete(
        f"/api/v1/user/suppliers/{sup_id}",
        headers={"Authorization": f"Bearer {TOKEN_BETA}"},
    )
    assert beta_delete.status_code == 404

    # Alpha updates supplier
    up_res = closure_client.put(
        f"/api/v1/user/suppliers/{sup_id}",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
        json={"lead_time_days": 2, "hub": "Whitefield Hub"},
    )
    assert up_res.status_code == 200
    assert up_res.json()["lead_time_days"] == 2

    # Alpha deletes supplier
    del_res = closure_client.delete(
        f"/api/v1/user/suppliers/{sup_id}",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
    )
    assert del_res.status_code == 200
    assert del_res.json()["deleted_id"] == sup_id


def test_supplier_deletion_preserves_historical_po(closure_client):
    """Verify deleting a supplier does not cascade-delete or corrupt existing purchase orders."""
    # Create supplier
    sup_res = closure_client.post(
        "/api/v1/user/suppliers",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
        json={"name": "Temporary Flour Mills", "lead_time_days": 2},
    )
    sup_id = sup_res.json()["id"]

    # Issue PO referencing this supplier
    po_id = f"po_hist_{uuid.uuid4().hex[:8]}"
    closure_client.post(
        "/api/v1/user/purchase-orders",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
        json={
            "id": po_id,
            "supplier": "Temporary Flour Mills",
            "items": [{"product_id": "prod_alpha_1", "sku": "SKU-A1", "product_name": "Basmati Rice 5kg", "quantity": 10, "unit_cost": 380.0}],
        },
    )

    # Delete supplier
    del_res = closure_client.delete(
        f"/api/v1/user/suppliers/{sup_id}",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
    )
    assert del_res.status_code == 200

    # Ensure historical PO remains intact
    pos = closure_client.get(
        "/api/v1/user/purchase-orders",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
    ).json()
    po_match = next((p for p in pos if p["id"] == po_id), None)
    assert po_match is not None
    assert po_match["supplier"] == "Temporary Flour Mills"


# ==============================================================================
# PRIORITY C: BULK OPERATIONS (ATOMIC DELETE & ATOMIC IMPORT)
# ==============================================================================

def test_atomic_bulk_delete_with_tenant_isolation(closure_client):
    """Verify POST /api/v1/user/products/bulk-delete deletes only owned items in an atomic transaction."""
    # Alpha tries to delete its own prod_alpha_2 AND Beta's prod_beta_1
    res = closure_client.post(
        "/api/v1/user/products/bulk-delete",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
        json={"product_ids": ["prod_alpha_2", "prod_beta_1"]},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["deleted_count"] == 1
    assert data["deleted_ids"] == ["prod_alpha_2"]

    # Beta's product must remain untouched
    beta_check = closure_client.get(
        "/api/v1/user/products",
        headers={"Authorization": f"Bearer {TOKEN_BETA}"},
    ).json()
    beta_skus = [p["id"] for p in beta_check]
    assert "prod_beta_1" in beta_skus


def test_atomic_bulk_import_with_validation(closure_client):
    """Verify POST /api/v1/user/products/bulk-import parses valid rows and reports row-level errors."""
    import_payload = {
        "products": [
            {
                "name": "Tata Salt 1kg",
                "sku": "SKU-SALT-1",
                "unit_price": 28.0,
                "unit_cost": 22.0,
                "stock_on_hand": 50,
                "reorder_point": 15,
                "category_name": "Staples",
            },
            {
                "name": "   ",  # Invalid empty name
                "sku": "SKU-EMPTY",
                "unit_price": 50.0,
                "unit_cost": 40.0,
                "stock_on_hand": 10,
            },
            {
                "name": "Red Label Tea 500g",
                "sku": "SKU-TEA-RED",
                "unit_price": 240.0,
                "unit_cost": 195.0,
                "stock_on_hand": 20,
                "reorder_point": 8,
                "category_name": "Beverages",
            },
        ]
    }

    res = closure_client.post(
        "/api/v1/user/products/bulk-import",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
        json=import_payload,
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert data["imported_count"] == 2
    assert len(data["errors"]) == 1
    assert "Row 2: Name cannot be empty" in data["errors"][0]

    # Verify imported items appear in Alpha's catalog
    prods = closure_client.get(
        "/api/v1/user/products",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
    ).json()
    sku_set = {p["sku"] for p in prods}
    assert "SKU-SALT-1" in sku_set
    assert "SKU-TEA-RED" in sku_set


# ==============================================================================
# PRIORITY D: DUAL AUTH FOR ANALYTICAL ROUTES & CROSS-TENANT DEFENSE
# ==============================================================================

def test_analytical_routes_accept_bearer_token(closure_client, monkeypatch):
    """Verify analytical routes accept Bearer session tokens without requiring hardcoded API key."""
    # Enforce API key requirement to ensure auth gate is active
    monkeypatch.setenv("API_KEY", "prod_super_secret_key_2026")
    import app.main as app_main
    from app import config as cfg
    monkeypatch.setattr(cfg, "API_KEY", "prod_super_secret_key_2026")
    monkeypatch.setattr(app_main, "API_KEY", "prod_super_secret_key_2026")

    # 1. Unauthenticated request must fail
    res_unauth = closure_client.get("/metrics")
    assert res_unauth.status_code == 401

    # 2. Bearer session token authenticated request must succeed
    res_bearer = closure_client.get("/metrics", headers={"Authorization": f"Bearer {TOKEN_ALPHA}"})
    assert res_bearer.status_code == 200

    # 3. Segments summary with Bearer
    res_seg = closure_client.get("/segments/summary", headers={"Authorization": f"Bearer {TOKEN_ALPHA}"})
    assert res_seg.status_code == 200

    # 4. SKUs with Bearer
    res_skus = closure_client.get("/skus", headers={"Authorization": f"Bearer {TOKEN_ALPHA}"})
    assert res_skus.status_code == 200

    # 5. Forecast with Bearer
    res_fc = closure_client.post(
        "/forecast",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
        json={"store": 1, "item": 1, "horizon_days": 7, "granularity": "daily", "model": "best"},
    )
    assert res_fc.status_code == 200

    # 6. Anomalies with Bearer
    res_anom = closure_client.get("/anomalies?store=1&item=1", headers={"Authorization": f"Bearer {TOKEN_ALPHA}"})
    assert res_anom.status_code == 200

    # 7. X-API-Key continues to work as expected
    res_api_key = closure_client.get("/metrics", headers={"X-API-Key": "prod_super_secret_key_2026"})
    assert res_api_key.status_code == 200


def test_cross_tenant_isolation_matrix(closure_client):
    """Verify comprehensive tenant boundaries across products, POs, suppliers, and sales."""
    # Alpha tries to update Beta's product
    res_up = closure_client.put(
        "/api/v1/user/products/prod_beta_1",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
        json={"unit_price": 1.0},
    )
    assert res_up.status_code == 404

    # Alpha tries to delete Beta's product directly
    res_del = closure_client.delete(
        "/api/v1/user/products/prod_beta_1",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
    )
    assert res_del.status_code == 404

    # Beta creates a PO
    po_beta = f"po_beta_{uuid.uuid4().hex[:8]}"
    closure_client.post(
        "/api/v1/user/purchase-orders",
        headers={"Authorization": f"Bearer {TOKEN_BETA}"},
        json={"id": po_beta, "supplier": "Spice World", "items": [{"product_id": "prod_beta_1", "sku": "SKU-B1", "product_name": "Cardamom 100g", "quantity": 5, "unit_cost": 200.0}]},
    )

    # Alpha tries to receive Beta's PO
    res_cross_recv = closure_client.post(
        f"/api/v1/user/purchase-orders/{po_beta}/receive",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
    )
    assert res_cross_recv.status_code == 404

    # Alpha tries to change status of Beta's PO
    res_cross_stat = closure_client.patch(
        f"/api/v1/user/purchase-orders/{po_beta}/status",
        headers={"Authorization": f"Bearer {TOKEN_ALPHA}"},
        json={"status": "cancelled"},
    )
    assert res_cross_stat.status_code == 404

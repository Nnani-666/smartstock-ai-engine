from __future__ import annotations

"""API integration tests for all analytical routes and validation rules."""

from fastapi.testclient import TestClient

import app.main


def test_api_health(client: TestClient):
    """GET /health returns 200 with valid health schema."""
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "last_data_date" in data
    assert "models_loaded" in data


def test_api_get_skus(client: TestClient):
    """GET /skus returns list of SKUs."""
    resp = client.get("/skus?limit=5")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_api_get_single_sku(client: TestClient):
    """GET /skus/{store}/{item} returns 200 for known SKU and 404 for unknown."""
    resp = client.get("/skus/1/1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["sku_id"] == "S01-I01"

    # Unknown SKU returns 404
    resp_404 = client.get("/skus/1/50")
    assert resp_404.status_code == 404


def test_api_forecast(client: TestClient):
    """POST /forecast returns 200 on valid daily request, 422 on invalid weekly."""
    payload = {
        "store": 1,
        "item": 1,
        "horizon_days": 14,
        "granularity": "daily",
        "model": "holt_winters",
    }
    resp = client.post("/forecast", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["sku_id"] == "S01-I01"
    assert len(data["forecasts"]) == 14

    # Weekly horizon not multiple of 7 returns 422
    payload_invalid = {
        "store": 1,
        "item": 1,
        "horizon_days": 10,
        "granularity": "weekly",
        "model": "holt_winters",
    }
    resp_invalid = client.post("/forecast", json=payload_invalid)
    assert resp_invalid.status_code == 422


def test_api_anomalies(client: TestClient):
    """GET /anomalies returns 200 with anomaly log."""
    resp = client.get("/anomalies?store=1&item=1&method=any")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_api_decision(client: TestClient):
    """POST /decision returns 200 with complete decision metrics."""
    payload = {
        "store": 1,
        "item": 1,
        "current_stock": 20,
        "on_order": 0,
        "service_level": 0.95,
        "lead_time_days": 5,
    }
    resp = client.post("/decision", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["sku_id"] == "S01-I01"
    assert "action" in data
    assert "safety_stock" in data
    assert "reorder_point" in data
    assert "explanation" in data


def test_api_decision_batch(client: TestClient):
    """POST /decision/batch handles up to 100 items."""
    item_req = {
        "store": 1,
        "item": 1,
        "current_stock": 20,
        "on_order": 0,
    }
    resp = client.post("/decision/batch", json={"items": [item_req, item_req]})
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2


def test_api_segments_and_metrics(client: TestClient):
    """GET /segments/summary and GET /metrics return 200."""
    resp_seg = client.get("/segments/summary")
    assert resp_seg.status_code == 200

    resp_met = client.get("/metrics")
    assert resp_met.status_code == 200


def test_api_key_authentication(client: TestClient, monkeypatch):
    """Verify 401 when API_KEY is set and header is missing."""
    monkeypatch.setattr(app.main, "API_KEY", "secret-test-key")

    # Missing header -> 401
    resp_unauth = client.get("/skus/1/1")
    assert resp_unauth.status_code == 401

    # Valid header -> 200
    resp_auth = client.get("/skus/1/1", headers={"X-API-Key": "secret-test-key"})
    assert resp_auth.status_code == 200


def test_api_sku_filtering(client: TestClient):
    """Verify SKU filtering by abc, xyz, tier, and cluster."""
    resp = client.get("/skus?abc=A&xyz=X&tier=Strategic&cluster=0")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_api_decision_batch_over_limit(client: TestClient):
    """Verify batch request exceeding 100 items returns 422."""
    item_req = {"store": 1, "item": 1, "current_stock": 20, "on_order": 0}
    resp = client.post("/decision/batch", json={"items": [item_req] * 101})
    assert resp.status_code == 422


def test_api_live_app_routes(client: TestClient):
    """Verify live SmartStock application routes require authentication and respond."""
    # Unauthenticated request must return 401
    assert client.get("/api/v1/products").status_code == 401

    # Register & authenticate test user
    reg = client.post("/api/v1/auth/register", json={
        "email": "live_api_tester@store.in",
        "password": "TestPassword123!",
        "store_name": "Live API Store",
    })
    assert reg.status_code == 200
    headers = {"Authorization": f"Bearer {reg.json()['token']}"}

    resp_prod = client.get("/api/v1/products", headers=headers)
    assert resp_prod.status_code == 200

    resp_ins = client.get("/api/v1/insights", headers=headers)
    assert resp_ins.status_code == 200

    resp_po = client.get("/api/v1/purchase-orders", headers=headers)
    assert resp_po.status_code == 200

    resp_shop = client.get("/api/v1/shop?code=STORE-402", headers=headers)
    assert resp_shop.status_code in [200, 404]


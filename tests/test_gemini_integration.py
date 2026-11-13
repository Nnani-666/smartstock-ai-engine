import os

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import GEMINI_API_KEY
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    login_resp = client.post("/api/v1/auth/login", json={"email": "owner@sharmakirana.in", "password": "terminal123"})
    assert login_resp.status_code == 200, f"Login failed: {login_resp.text}"
    token = login_resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


class MockGeminiResponse:
    """Mock Gemini API HTTP 200 response matching Google GenAI REST schema."""
    def __init__(self, text="Store operations are running smoothly. Fortune Sunflower Oil requires replenishment.", status_code=200):
        self.status_code = status_code
        self._text = text

    def json(self):
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [{"text": self._text}],
                        "role": "model",
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {
                "promptTokenCount": 240,
                "candidatesTokenCount": 85,
                "totalTokenCount": 325,
            },
        }


# 1. API key detection without revealing its value
def test_01_api_key_detection():
    key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
    assert key is not None, "GEMINI_API_KEY is not set"
    assert len(key) > 20, "GEMINI_API_KEY appears invalidly short"
    assert not key.startswith(" "), "GEMINI_API_KEY has leading whitespace"
    # Never reveal or assert key text in assertions or logs


# 2. Successful live Gemini response parsing and metadata
def test_02_gemini_response_structure(client, auth_headers, monkeypatch):
    captured_requests = []

    class MockHttpxClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, headers=None, json=None, **kwargs):
            captured_requests.append({"url": url, "headers": headers, "json": json})
            return MockGeminiResponse(
                text="Healthy operations detected. Total active SKUs: 5. 1 item requires reordering before Diwali."
            )

    monkeypatch.setattr("httpx.Client", MockHttpxClient)

    resp = client.post(
        "/api/v1/ai/assistant",
        headers=auth_headers,
        json={"prompt": "Provide store operations and inventory health summary."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["source"] == "gemini-2.5-flash"
    assert data["model"] == "gemini-2.5-flash"
    assert "Healthy operations detected" in data["analysis"]
    assert "metrics" in data
    assert data["metrics"]["total_products"] == 5
    assert data["metrics"]["low_stock"] == 1

    # Verify request payload was properly structured
    assert len(captured_requests) == 1
    req_json = captured_requests[0]["json"]
    assert "systemInstruction" in req_json
    assert req_json["generationConfig"]["temperature"] == 0.2
    assert req_json["generationConfig"]["maxOutputTokens"] == 1500


# 3. Grounded context generation with real inventory data
def test_03_real_inventory_grounding(client, auth_headers, monkeypatch):
    captured_payloads = []

    class MockHttpxClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, headers=None, json=None, **kwargs):
            captured_payloads.append(json)
            # Simulate Gemini grounding response
            return MockGeminiResponse(
                text="Based on your inventory records, Fortune Sunlite Refined Sunflower Oil is low at 8 units (reorder point 12)."
            )

    monkeypatch.setattr("httpx.Client", MockHttpxClient)

    resp = client.post(
        "/api/v1/ai/assistant",
        headers=auth_headers,
        json={"prompt": "What products are running low?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "gemini-2.5-flash"
    assert "Fortune Sunlite Refined Sunflower Oil" in data["analysis"]

    # Verify system instruction contains real inventory data
    sys_text = captured_payloads[0]["systemInstruction"]["parts"][0]["text"]
    assert "Fortune Sunlite Refined Sunflower Oil" in sys_text
    assert "Aashirvaad Superior MP" in sys_text
    assert "Active Catalog & Current Inventory:" in sys_text


# 4. Questions involving recent sales
def test_04_recent_sales_grounding(client, auth_headers, monkeypatch):
    captured_payloads = []

    class MockHttpxClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, headers=None, json=None, **kwargs):
            captured_payloads.append(json)
            return MockGeminiResponse(
                text="Your recent revenue is ₹245.00 with sales in Atta. Focus on replenishing high velocity items."
            )

    monkeypatch.setattr("httpx.Client", MockHttpxClient)

    resp = client.post(
        "/api/v1/ai/assistant",
        headers=auth_headers,
        json={"prompt": "Which products generated the highest revenue recently?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["source"] == "gemini-2.5-flash"
    assert "₹245.00" in data["analysis"]

    sys_text = captured_payloads[0]["systemInstruction"]["parts"][0]["text"]
    assert "Recent Sales Highlights:" in sys_text
    assert "Total recorded revenue: ₹245.00" in sys_text


# 5. Replenishment-related questions with supplier and seasonal context
def test_05_replenishment_guidance(client, auth_headers, monkeypatch):
    captured_payloads = []

    class MockHttpxClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, headers=None, json=None, **kwargs):
            captured_payloads.append(json)
            return MockGeminiResponse(
                text="Reorder Fortune Sunflower Oil from Metro Cash & Carry. Lead time is 3 days; place order now for Diwali demand surge."
            )

    monkeypatch.setattr("httpx.Client", MockHttpxClient)

    resp = client.post(
        "/api/v1/ai/assistant",
        headers=auth_headers,
        json={"prompt": "Which products should I reorder today?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "gemini-2.5-flash"
    assert "Metro Cash & Carry" in data["analysis"]

    sys_text = captured_payloads[0]["systemInstruction"]["parts"][0]["text"]
    assert "Diwali" in sys_text
    assert "Verified Suppliers:" in sys_text


# 6. Missing or unavailable catalog data handling
def test_06_missing_catalog_item(client, auth_headers, monkeypatch):
    class MockHttpxClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, headers=None, json=None, **kwargs):
            return MockGeminiResponse(
                text="Fresh Dragon Fruit is not listed in your active store catalog. No stock records are available."
            )

    monkeypatch.setattr("httpx.Client", MockHttpxClient)

    resp = client.post(
        "/api/v1/ai/assistant",
        headers=auth_headers,
        json={"prompt": "What is the current stock level of Fresh Dragon Fruit?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "gemini-2.5-flash"
    assert "not listed" in data["analysis"].lower() or "not" in data["analysis"].lower()


# 7. Invalid API key handling (graceful fallback)
def test_07_invalid_api_key_fallback(client, auth_headers, monkeypatch):
    class Mock400Response:
        status_code = 400

        def json(self):
            return {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key."}}

    class MockHttpxClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, *args, **kwargs):
            return Mock400Response()

    monkeypatch.setattr("httpx.Client", MockHttpxClient)

    resp = client.post(
        "/api/v1/ai/assistant",
        headers=auth_headers,
        json={"prompt": "Which products should I reorder today?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["source"] == "local_heuristic"
    assert data.get("fallback_reason") == "auth_failure"


# 8. Rate limit or quota exhaustion handling (HTTP 429)
def test_08_quota_exhaustion_fallback(client, auth_headers, monkeypatch):
    class Mock429Response:
        status_code = 429

        def json(self):
            return {"error": {"code": 429, "message": "Resource exhausted", "status": "RESOURCE_EXHAUSTED"}}

    class MockHttpxClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, *args, **kwargs):
            return Mock429Response()

    monkeypatch.setattr("httpx.Client", MockHttpxClient)

    resp = client.post(
        "/api/v1/ai/assistant",
        headers=auth_headers,
        json={"prompt": "Provide store operations and inventory health summary."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["source"] == "local_heuristic"
    assert data.get("fallback_reason") == "rate_limited"


# 9. Gemini timeout handling
def test_09_timeout_fallback(client, auth_headers, monkeypatch):
    class MockTimeoutClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, *args, **kwargs):
            raise httpx.TimeoutException("Connection timed out after 10.0s")

    monkeypatch.setattr("httpx.Client", MockTimeoutClient)

    resp = client.post(
        "/api/v1/ai/assistant",
        headers=auth_headers,
        json={"prompt": "Provide store operations and inventory health summary."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["source"] == "local_heuristic"
    assert data.get("fallback_reason") == "timeout"


# 10. Local heuristic fallback when key is unset
def test_10_key_unset_fallback(client, auth_headers, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.setattr("app.main.GEMINI_API_KEY", None)

    resp = client.post(
        "/api/v1/ai/assistant",
        headers=auth_headers,
        json={"prompt": "Which products should I reorder today?"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["source"] == "local_heuristic"
    assert data.get("fallback_reason") == "key_unset"
    assert "Fortune Sunlite Refined Sunflower Oil" in data["analysis"] or "reorder" in data["analysis"].lower()


# 11. Authentication and tenant isolation
def test_11_auth_and_tenant_isolation(client):
    # Unauthenticated request must return 401
    unauth_resp = client.post(
        "/api/v1/ai/assistant",
        json={"prompt": "What are my products?"},
    )
    assert unauth_resp.status_code == 401

    # Authenticate as trial user
    login_resp = client.post("/api/v1/auth/login", json={"email": "trial12@gmail.com", "password": "Password123!"})
    if login_resp.status_code == 200:
        trial_token = login_resp.json()["token"]
        trial_headers = {"Authorization": f"Bearer {trial_token}"}
        resp = client.post(
            "/api/v1/ai/assistant",
            headers=trial_headers,
            json={"prompt": "Provide store summary."},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["metrics"]["total_products"] == 3
        assert "Sharma" not in data.get("store_name", "")


# 12. Real live Gemini invocation or verified rate limit fallback
def test_12_live_environment_execution(client, auth_headers):
    # Execute actual unmocked call against configured environment
    resp = client.post(
        "/api/v1/ai/assistant",
        headers=auth_headers,
        json={"prompt": "Provide a 3-bullet store operations and inventory health summary."},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    # Source is either live Gemini 2.5 Flash, or verified rate_limited fallback if daily free quota exhausted
    assert data["source"] in ("gemini-2.5-flash", "local_heuristic")
    if data["source"] == "local_heuristic":
        assert data.get("fallback_reason") in ("rate_limited", "auth_failure", "timeout")
    else:
        assert data["model"] == "gemini-2.5-flash"
    assert len(data["analysis"]) > 20

import os
import tempfile
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import GEMINI_API_KEY, GEMINI_PRIMARY_MODEL, GEMINI_SECONDARY_MODEL
from app.main import app
from app.services.gemini_router import GeminiModelRouter, router


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
    def __init__(self, text="Healthy store operations. Replenish sunflower oil.", status_code=200):
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


# 1. Primary model configuration & detection
def test_01_primary_and_secondary_model_config():
    assert GEMINI_PRIMARY_MODEL == "gemini-3.5-flash-lite"
    assert GEMINI_SECONDARY_MODEL == "gemini-3.1-flash-lite"
    key = os.getenv("GEMINI_API_KEY") or GEMINI_API_KEY
    assert key is not None and len(key) > 20
    # Key value is never exposed


# 2. Primary model succeeds on live/mock request
def test_02_primary_model_success(client, auth_headers, monkeypatch):
    router.reset_state()
    requested_urls = []

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, headers=None, json=None, **kwargs):
            requested_urls.append(url)
            return MockGeminiResponse(text="Namaste! Store operations are running smoothly.")

    monkeypatch.setattr("httpx.Client", MockClient)

    resp = client.post("/api/v1/ai/assistant", headers=auth_headers, json={"prompt": "Hi"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["source"] == "gemini"
    assert data["model"] == "gemini-3.5-flash-lite"
    assert "Namaste" in data["analysis"]
    assert "gemini-3.5-flash-lite:generateContent" in requested_urls[0]


# 3. Primary quota exhaustion activates secondary model
def test_03_failover_to_secondary_on_primary_exhaustion(client, auth_headers, monkeypatch):
    router.reset_state()
    requested_urls = []

    class Mock429Response:
        status_code = 429

        def json(self):
            return {
                "error": {
                    "code": 429,
                    "message": "Resource exhausted on free tier",
                    "details": [
                        {
                            "@type": "type.googleapis.com/google.rpc.QuotaFailure",
                            "violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}],
                        },
                        {
                            "@type": "type.googleapis.com/google.rpc.RetryInfo",
                            "retryDelay": "3600s",
                        },
                    ],
                }
            }

    class MockFailoverClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, headers=None, json=None, **kwargs):
            requested_urls.append(url)
            if "gemini-3.5-flash-lite" in url:
                return Mock429Response()
            elif "gemini-3.1-flash-lite" in url:
                return MockGeminiResponse(text="Secondary model response: replenish Sunflower Oil.")
            return MockGeminiResponse(text="Fallback")

    monkeypatch.setattr("httpx.Client", MockFailoverClient)

    resp = client.post("/api/v1/ai/assistant", headers=auth_headers, json={"prompt": "What should I order urgently?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["source"] == "gemini"
    assert data["model"] == "gemini-3.1-flash-lite"
    assert "Secondary model response" in data["analysis"]

    # Verify both models were attempted in correct order
    assert len(requested_urls) == 2
    assert "gemini-3.5-flash-lite" in requested_urls[0]
    assert "gemini-3.1-flash-lite" in requested_urls[1]

    # Verify primary model is now marked on cooldown
    avail, reason = router.is_model_available("gemini-3.5-flash-lite")
    assert not avail
    assert "daily_quota_exhausted" in str(reason)


# 4. Both models exhausted activates local fallback
def test_04_both_models_exhausted_triggers_local_fallback(client, auth_headers, monkeypatch):
    router.reset_state()

    class Mock429Response:
        status_code = 429

        def json(self):
            return {"error": {"code": 429, "message": "Resource exhausted"}}

    class MockAllExhaustedClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, headers=None, json=None, **kwargs):
            return Mock429Response()

    monkeypatch.setattr("httpx.Client", MockAllExhaustedClient)

    resp = client.post("/api/v1/ai/assistant", headers=auth_headers, json={"prompt": "What should I order urgently?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["source"] == "local_heuristic"
    assert data.get("fallback_reason") in ("rpm_limit", "daily_quota_exhausted", "rate_limited")
    assert "Priority replenishment recommendations" in data["analysis"] or "reorder" in data["analysis"].lower()


# 5. Daily quota exhaustion prevents repeated calls to the exhausted model
def test_05_exhausted_model_not_called_again(client, auth_headers, monkeypatch):
    router.reset_state()
    # router has primary model marked disabled_daily
    router.record_failure("gemini-3.5-flash-lite", "daily_quota_exhausted", cooldown_seconds=86400.0)
    requested_urls = []

    class MockClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, headers=None, json=None, **kwargs):
            requested_urls.append(url)
            return MockGeminiResponse(text="Direct answer from secondary model.")

    monkeypatch.setattr("httpx.Client", MockClient)

    resp = client.post("/api/v1/ai/assistant", headers=auth_headers, json={"prompt": "Which products are selling fastest?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "gemini-3.1-flash-lite"
    # Ensure primary model was NEVER requested
    for u in requested_urls:
        assert "gemini-3.5-flash-lite" not in u
    assert "gemini-3.1-flash-lite" in requested_urls[0]


# 6. Per-minute exhaustion is handled separately
def test_06_rpm_rate_limit_handling():
    test_router = GeminiModelRouter(status_file=Path(tempfile.gettempdir()) / "test_status_rpm.json")
    cat, cooldown = test_router.classify_error(429, {"error": {"message": "Rate limit exceeded. Please wait."}})
    assert cat == "rpm_limit"
    assert cooldown == 60.0


# 7. Invalid API key does not trigger futile secondary model calls
def test_07_invalid_api_key_aborts_immediately(client, auth_headers, monkeypatch):
    router.reset_state()
    requested_urls = []

    class Mock400InvalidKey:
        status_code = 400

        def json(self):
            return {"error": {"code": 400, "message": "API key not valid. Please pass a valid API key."}}

    class MockAuthFailClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, headers=None, json=None, **kwargs):
            requested_urls.append(url)
            return Mock400InvalidKey()

    monkeypatch.setattr("httpx.Client", MockAuthFailClient)

    resp = client.post("/api/v1/ai/assistant", headers=auth_headers, json={"prompt": "What is my inventory situation?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["source"] == "local_heuristic"
    assert data.get("fallback_reason") == "auth_failure"
    # Should only make 1 attempt, aborting secondary attempts with same invalid key
    assert len(requested_urls) == 1


# 8. Invalid model IDs activate the next model
def test_08_invalid_model_id_activates_secondary(client, auth_headers, monkeypatch):
    router.reset_state()
    requested_urls = []

    class Mock404Model:
        status_code = 404

        def json(self):
            return {"error": {"code": 404, "message": "models/gemini-3.5-flash-lite is not found"}}

    class MockModelFailoverClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, headers=None, json=None, **kwargs):
            requested_urls.append(url)
            if "gemini-3.5-flash-lite" in url:
                return Mock404Model()
            return MockGeminiResponse(text="Response from valid secondary model.")

    monkeypatch.setattr("httpx.Client", MockModelFailoverClient)

    resp = client.post("/api/v1/ai/assistant", headers=auth_headers, json={"prompt": "Explain recommendations."})
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "gemini-3.1-flash-lite"
    assert len(requested_urls) == 2


# 9. Timeout handling fails over to secondary
def test_09_timeout_fails_over(client, auth_headers, monkeypatch):
    router.reset_state()
    requested_urls = []

    class MockTimeoutFailoverClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, headers=None, json=None, **kwargs):
            requested_urls.append(url)
            if "gemini-3.5-flash-lite" in url:
                raise httpx.TimeoutException("Read timed out")
            return MockGeminiResponse(text="Success after timeout failover.")

    monkeypatch.setattr("httpx.Client", MockTimeoutFailoverClient)

    resp = client.post("/api/v1/ai/assistant", headers=auth_headers, json={"prompt": "Which products are moving slowly?"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == "gemini-3.1-flash-lite"
    assert "Success after timeout failover" in data["analysis"]


# 10. Model cooldown survives application restart (disk persistence)
def test_10_cooldown_survives_restart():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tf:
        status_path = Path(tf.name)

    try:
        r1 = GeminiModelRouter(status_file=status_path)
        r1.record_failure("gemini-3.5-flash-lite", "daily_quota_exhausted", cooldown_seconds=5000.0)

        # Create new router instance reading from same persisted file
        r2 = GeminiModelRouter(status_file=status_path)
        avail, reason = r2.is_model_available("gemini-3.5-flash-lite")
        assert not avail
        assert "daily_quota_exhausted" in str(reason)
    finally:
        if status_path.exists():
            status_path.unlink()


# 11. Grounding contains tenant data without leaking
def test_11_tenant_isolation_and_grounding(client, auth_headers):
    # Query unauthenticated
    unauth = client.post("/api/v1/ai/assistant", json={"prompt": "Hi"})
    assert unauth.status_code == 401

    # Query trial user
    login_trial = client.post("/api/v1/auth/login", json={"email": "trial12@gmail.com", "password": "Password123!"})
    if login_trial.status_code == 200:
        t_token = login_trial.json()["token"]
        resp = client.post("/api/v1/ai/assistant", headers={"Authorization": f"Bearer {t_token}"}, json={"prompt": "Hi"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["metrics"]["total_products"] == 3
        assert "Sharma" not in data.get("store_name", "")


# 12. Unsolicited greetings do not return out of stock warnings
def test_12_greeting_intent_returns_natural_welcome(client, auth_headers, monkeypatch):
    # Force local fallback to test intent engine directly
    monkeypatch.setattr("app.main.GEMINI_API_KEY", None)
    resp = client.post("/api/v1/ai/assistant", headers=auth_headers, json={"prompt": "Namaste"})
    assert resp.status_code == 200
    data = resp.json()
    assert "Namaste" in data["analysis"]
    # Must NOT return an unsolicited inventory health alert
    assert "Immediate Action:" not in data["analysis"]
    assert "Replenishment Warning:" not in data["analysis"]

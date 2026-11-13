"""Centralized multi-model router and quota failover manager for Google Gemini.

Supports automatic switching across configured models:
  Primary: gemini-3.5-flash-lite
  Secondary: gemini-3.1-flash-lite
  Final Fallback: local_heuristic engine
"""

from __future__ import annotations

import json
import logging
import re
import time
from pathlib import Path
from typing import Any

from app.config import (
    GEMINI_PRIMARY_MODEL,
    GEMINI_SECONDARY_MODEL,
    MODEL_STATUS_FILE,
)

logger = logging.getLogger(__name__)


class GeminiModelRouter:
    """Manages model availability, quota-aware failover, and cooldown persistence."""

    def __init__(
        self,
        primary_model: str = GEMINI_PRIMARY_MODEL,
        secondary_model: str = GEMINI_SECONDARY_MODEL,
        status_file: Path = MODEL_STATUS_FILE,
    ):
        self.primary_model = primary_model
        self.secondary_model = secondary_model
        self.status_file = status_file
        self._state: dict[str, dict[str, Any]] = self._load_state()

    def _default_model_state(self, model_id: str) -> dict[str, Any]:
        return {
            "model_id": model_id,
            "is_available": True,
            "disabled_daily": False,
            "cooldown_until": 0.0,
            "last_success_at": None,
            "last_failure_at": None,
            "last_failure_category": None,
            "failure_count": 0,
            "retry_delay_seconds": 0.0,
        }

    def _load_state(self) -> dict[str, dict[str, Any]]:
        state: dict[str, dict[str, Any]] = {}
        for m in [self.primary_model, self.secondary_model]:
            state[m] = self._default_model_state(m)

        if self.status_file.exists():
            try:
                with open(self.status_file, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        for m, data in saved.items():
                            if isinstance(data, dict):
                                cur = state.setdefault(m, self._default_model_state(m))
                                cur.update(data)
            except Exception as exc:
                logger.warning("Could not read Gemini model status file: %s", exc)

        return state

    def _save_state(self) -> None:
        try:
            self.status_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.status_file, "w", encoding="utf-8") as f:
                json.dump(self._state, f, indent=2)
        except Exception as exc:
            logger.warning("Could not save Gemini model status file: %s", exc)

    def get_model_status(self, model_id: str) -> dict[str, Any]:
        if model_id not in self._state:
            self._state[model_id] = self._default_model_state(model_id)
        return dict(self._state[model_id])

    def is_model_available(self, model_id: str) -> tuple[bool, str | None]:
        """Check if model is currently eligible for request dispatch."""
        st = self._state.get(model_id)
        if not st:
            return True, None

        now = time.time()
        if st.get("disabled_daily"):
            cooldown = st.get("cooldown_until", 0.0)
            if now < cooldown:
                remaining = int(cooldown - now)
                return False, f"daily_quota_exhausted (cooldown active for {remaining}s)"
            # Cooldown expired, re-enable for testing
            st["disabled_daily"] = False
            st["is_available"] = True
            st["cooldown_until"] = 0.0
            self._save_state()

        if st.get("cooldown_until", 0.0) > now:
            remaining = int(st["cooldown_until"] - now)
            cat = st.get("last_failure_category", "rate_limited")
            return False, f"{cat} (cooldown active for {remaining}s)"

        if not st.get("is_available", True):
            return False, st.get("last_failure_category", "unavailable")

        return True, None

    def get_eligible_models(self) -> list[str]:
        """Returns ordered list of models that can currently accept traffic."""
        eligible = []
        for m in [self.primary_model, self.secondary_model]:
            avail, _ = self.is_model_available(m)
            if avail:
                eligible.append(m)
        return eligible

    def record_success(self, model_id: str) -> None:
        if model_id not in self._state:
            self._state[model_id] = self._default_model_state(model_id)
        st = self._state[model_id]
        st["is_available"] = True
        st["disabled_daily"] = False
        st["cooldown_until"] = 0.0
        st["last_success_at"] = time.time()
        st["failure_count"] = 0
        self._save_state()

    def classify_error(
        self,
        status_code: int,
        response_body: dict[str, Any] | None = None,
        exc: Exception | None = None,
    ) -> tuple[str, float]:
        """Classify Gemini API errors into actionable categories and cooldowns."""
        if exc is not None:
            exc_name = type(exc).__name__
            if "Timeout" in exc_name:
                return "timeout", 15.0
            return "network_error", 15.0

        if status_code in (401, 403):
            return "auth_failure", 0.0

        body = response_body or {}
        err = body.get("error", {})
        msg = str(err.get("message", "")).lower()
        details = err.get("details", [])

        # Check for invalid API key
        if status_code == 400 and ("api key" in msg or "not valid" in msg or "invalid" in msg):
            return "auth_failure", 0.0

        # Check for invalid model ID
        if status_code == 404:
            return "invalid_model", 86400.0

        # Parse retry delay if provided
        retry_delay = 0.0
        for d in details:
            if isinstance(d, dict) and "@type" in d.get("@type", "") and "RetryInfo" in d.get("@type", "") and "retryDelay" in d:
                rd_str = str(d["retryDelay"])
                m = re.search(r"(\d+(\.\d+)?)", rd_str)
                if m:
                    try:
                        retry_delay = float(m.group(1))
                    except ValueError:
                        pass

        if status_code == 429:
            # Check if this is daily quota exhaustion vs RPM rate limit
            is_daily = (
                "generaterequestsperday" in msg
                or "requests per day" in msg
                or "daily limit" in msg
                or "free_tier_requests" in msg
            )
            for d in details:
                if isinstance(d, dict) and "violations" in d:
                    for v in d["violations"]:
                        qid = str(v.get("quotaId", "")).lower()
                        qdesc = str(v.get("description", "")).lower()
                        if "day" in qid or "day" in qdesc:
                            is_daily = True

            if is_daily:
                cooldown = retry_delay if retry_delay > 0 else 86400.0
                return "daily_quota_exhausted", cooldown
            # Per-minute rate limit
            cooldown = retry_delay if retry_delay > 0 else 60.0
            return "rpm_limit", cooldown

        if status_code in (500, 502, 503, 504):
            return "service_unavailable", 30.0

        return f"upstream_http_{status_code}", 15.0

    def record_failure(
        self,
        model_id: str,
        category: str,
        cooldown_seconds: float = 0.0,
    ) -> None:
        if model_id not in self._state:
            self._state[model_id] = self._default_model_state(model_id)

        st = self._state[model_id]
        now = time.time()
        st["last_failure_at"] = now
        st["last_failure_category"] = category
        st["failure_count"] = st.get("failure_count", 0) + 1
        st["retry_delay_seconds"] = cooldown_seconds

        if category == "daily_quota_exhausted":
            st["disabled_daily"] = True
            st["is_available"] = False
            st["cooldown_until"] = now + max(cooldown_seconds, 3600.0)
        elif category == "invalid_model":
            st["is_available"] = False
            st["cooldown_until"] = now + 86400.0
        elif category in ("rpm_limit", "timeout", "service_unavailable"):
            st["cooldown_until"] = now + max(cooldown_seconds, 15.0)

        self._save_state()

    def reset_state(self) -> None:
        """Reset state for tests or administrative clearing."""
        for m in [self.primary_model, self.secondary_model]:
            self._state[m] = self._default_model_state(m)
        self._save_state()


# Global router singleton
router = GeminiModelRouter()

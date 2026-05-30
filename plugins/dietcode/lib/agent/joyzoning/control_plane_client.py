"""Optional JoyZoning control plane client — observe/report only, never execute."""
from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any, Optional

from urllib.parse import urlparse

from agent.joyzoning.config import get_joyzoning_config

logger = logging.getLogger(__name__)

_ALLOWED_CP_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def _validate_control_plane_url(url: str) -> None:
    if not url:
        return
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"control plane URL must be http(s): {url!r}")
    host = (parsed.hostname or "").lower()
    if host not in _ALLOWED_CP_HOSTS:
        raise ValueError(
            f"control plane URL host {host!r} not in allowlist "
            f"{sorted(_ALLOWED_CP_HOSTS)} (SSRF guard)."
        )


def _parse_json_response(raw: str, status: int) -> dict[str, Any]:
    if not raw.strip():
        if 200 <= status < 300:
            return {"success": True, "http_status": status}
        return {"success": False, "http_status": status, "error": "empty_response"}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {"success": False, "http_status": status, "error": "invalid_json", "raw": raw[:500]}
    if isinstance(data, dict):
        if "success" not in data and 200 <= status < 300:
            data = {**data, "success": True}
        data.setdefault("http_status", status)
        return data
    return {"success": 200 <= status < 300, "http_status": status, "data": data}


class ControlPlaneClient:
    """Read-only / observe-only bridge to JoyZoning habitat (:9470).

    Hermes remains execution authority. This client never dispatches leases,
    accept-merges, or JSDP chain advances — those are habitat operator actions.
    """

    def __init__(self, base_url: Optional[str] = None, timeout: float = 5.0):
        cfg = get_joyzoning_config()
        self.base_url = (base_url or cfg.control_plane_url).rstrip("/")
        _validate_control_plane_url(self.base_url)
        self.timeout = timeout
        self.observe_only = cfg.control_plane_observe_only
        import os
        self._ingest_token = (
            cfg.ingest_token or os.environ.get("JOYZONING_INGEST_TOKEN", "").strip()
        )

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    def health(self) -> dict[str, Any]:
        if not self.configured:
            return {"success": False, "skipped": True, "reason": "control plane URL not configured"}
        try:
            return self._get("/api/hermes/health")
        except Exception as exc:
            return {"success": False, "error": str(exc), "reachable": False}

    def agent_context(self) -> dict[str, Any]:
        """Runtime operator state from JoyZoning habitat (sessions, leases, approvals)."""
        if not self.configured:
            return {"success": False, "skipped": True, "reason": "control plane URL not configured"}
        try:
            return self._get("/api/agent/context")
        except Exception as exc:
            return {"success": False, "error": str(exc), "reachable": False}

    def agent_manifest(self) -> dict[str, Any]:
        """Static JoyZoning agent manifest (commands, endpoints, verification rules)."""
        if not self.configured:
            return {"success": False, "skipped": True, "reason": "control plane URL not configured"}
        try:
            return self._get("/api/agent/manifest")
        except Exception as exc:
            return {"success": False, "error": str(exc), "reachable": False}

    def fetch_events(self, *, since: float = 0.0, session_id: str = "") -> dict[str, Any]:
        if not self.configured:
            return {"success": False, "skipped": True}
        params = f"since={since}"
        if session_id:
            params += f"&sessionId={session_id}"
        return self._get(f"/api/events?{params}")

    def emit_observation(
        self,
        *,
        event_type: str,
        layer: str,
        scope_id: str,
        session_id: str,
        run_id: str,
        payload: dict[str, Any],
        timestamp: float,
    ) -> dict[str, Any]:
        """Mirror Hermes operational events for habitat supervision (non-authoritative)."""
        if not self.configured or not self.observe_only:
            return {"success": False, "skipped": True}
        body = {
            "type": event_type,
            "layer": layer,
            "scopeId": scope_id,
            "sessionId": session_id,
            "runId": run_id,
            "payload": payload,
            "timestamp": timestamp,
            "source": "hermes-runtime",
            "authoritative": False,
        }
        try:
            return self._post_json("/api/internal/hermes-observation", body)
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 405, 501):
                return {"success": False, "skipped": True, "http_status": exc.code}
            body_raw = exc.read().decode("utf-8", errors="replace")
            logger.warning(
                "control plane observation rejected (%s): %s",
                exc.code,
                body_raw[:300],
            )
            return _parse_json_response(body_raw, exc.code)
        except Exception as exc:
            logger.debug("control plane observation mirror unavailable", exc_info=True)
            return {"success": False, "error": str(exc)}

    def _get(self, path: str) -> dict[str, Any]:
        req = urllib.request.Request(f"{self.base_url}{path}", method="GET")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return _parse_json_response(resp.read().decode("utf-8"), resp.status)
        except urllib.error.HTTPError as exc:
            return _parse_json_response(exc.read().decode("utf-8", errors="replace"), exc.code)

    def _post_json(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self._ingest_token:
            headers["X-JoyZoning-Internal-Token"] = self._ingest_token
        req = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            method="POST",
            headers=headers,
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            raw = resp.read().decode("utf-8")
            result = _parse_json_response(raw, resp.status)
            if 200 <= resp.status < 300 and result.get("ok") is True:
                result["success"] = True
            return result

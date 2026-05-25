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
        self._ingest_token = os.environ.get("JOYZONING_INGEST_TOKEN", "").strip()

    @property
    def configured(self) -> bool:
        return bool(self.base_url)

    def health(self) -> dict[str, Any]:
        if not self.configured:
            return {"success": False, "skipped": True, "reason": "control plane URL not configured"}
        return self._get("/api/hermes/health")

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
    ) -> None:
        """Mirror Hermes operational events for habitat supervision (non-authoritative)."""
        if not self.configured or not self.observe_only:
            return
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
            self._post_json("/api/internal/hermes-observation", body)
        except Exception:
            # Habitat may not expose ingest yet — journal is still canonical for Hermes.
            logger.debug("control plane observation mirror unavailable", exc_info=True)

    def _get(self, path: str) -> dict[str, Any]:
        req = urllib.request.Request(f"{self.base_url}{path}", method="GET")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))

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
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw.strip() else {"success": True}
        except urllib.error.HTTPError as exc:
            if exc.code in (404, 405, 501):
                raise
            raise

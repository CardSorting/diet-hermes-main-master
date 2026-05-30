"""Tests for DietCode dashboard ↔ BroccoliDB API bridge."""

from unittest.mock import patch

import pytest

_RUNNER = "plugins.dietcode.lib.tools.broccolidb_tools.runner"


class TestDietcodeBroccolidbHealth:
    def test_health_when_tree_missing(self, _isolate_hermes_home):
        from hermes_cli.dietcode_broccolidb import get_health

        with patch(f"{_RUNNER}.check_requirements", return_value=False), patch(
            f"{_RUNNER}.resolve_broccolidb_root", return_value=None
        ), patch(f"{_RUNNER}.resolve_broccolidb_db_path", return_value=None):
            health = get_health()

        assert health["enabled"] is True
        assert health["available"] is False
        assert health["live"] is False
        assert "not found" in health["message"].lower()

    def test_health_live_when_db_exists(self, _isolate_hermes_home, tmp_path):
        from hermes_cli.dietcode_broccolidb import get_health

        db = tmp_path / "broccolidb.db"
        db.write_bytes(b"sqlite")

        with patch(f"{_RUNNER}.check_requirements", return_value=True), patch(
            f"{_RUNNER}.resolve_broccolidb_root", return_value=str(tmp_path / "broccolidb")
        ), patch(f"{_RUNNER}.resolve_broccolidb_db_path", return_value=str(db)), patch(
            "shutil.which", return_value="/usr/bin/npx"
        ):
            health = get_health()

        assert health["available"] is True
        assert health["db_exists"] is True
        assert health["live"] is True
        assert health["node_ok"] is True

    def test_health_respects_config_disable(self, _isolate_hermes_home, monkeypatch):
        from hermes_cli.dietcode_broccolidb import get_health

        monkeypatch.setattr(
            "hermes_cli.dietcode_broccolidb._dietcode_dashboard_cfg",
            lambda: {"broccolidb_enabled": False},
        )
        health = get_health()
        assert health["enabled"] is False
        assert health["live"] is False


class TestDietcodeBroccolidbSnapshot:
    def test_snapshot_skips_subprocess_when_not_live(self, _isolate_hermes_home):
        from hermes_cli.dietcode_broccolidb import get_snapshot

        with patch("hermes_cli.dietcode_broccolidb.get_health", return_value={"live": False, "message": "nope"}):
            snap = get_snapshot()

        assert snap["success"] is False
        assert snap["live"] is False
        assert snap["error"] == "nope"


class TestDietcodeWebServerRoutes:
    @pytest.fixture(autouse=True)
    def _client(self, monkeypatch, _isolate_hermes_home):
        try:
            from starlette.testclient import TestClient
        except ImportError:
            pytest.skip("fastapi/starlette not installed")

        import hermes_state
        from hermes_constants import get_hermes_home
        from hermes_cli.web_server import app, _SESSION_HEADER_NAME, _SESSION_TOKEN

        monkeypatch.setattr(hermes_state, "DEFAULT_DB_PATH", get_hermes_home() / "state.db")
        self.client = TestClient(app)
        self.client.headers[_SESSION_HEADER_NAME] = _SESSION_TOKEN

    def test_dietcode_health_route(self):
        with patch(
            "hermes_cli.dietcode_broccolidb.get_health",
            return_value={"enabled": True, "live": False, "message": "stub"},
        ):
            resp = self.client.get("/api/dietcode/health")
        assert resp.status_code == 200
        assert resp.json()["message"] == "stub"

    def test_dietcode_snapshot_route(self):
        with patch(
            "hermes_cli.dietcode_broccolidb.get_snapshot",
            return_value={"success": False, "live": False, "error": "offline"},
        ):
            resp = self.client.get("/api/dietcode/snapshot")
        assert resp.status_code == 200
        assert resp.json()["error"] == "offline"

    def test_dietcode_proposal_action_route(self):
        with patch(
            "hermes_cli.dietcode_broccolidb.set_proposal_action",
            return_value={"success": True, "id": "p1", "status": "approved"},
        ):
            resp = self.client.post(
                "/api/dietcode/proposals/p1/action",
                json={"action": "approve"},
            )
        assert resp.status_code == 200
        assert resp.json()["status"] == "approved"

    def test_dietcode_proposal_action_rejects_failure(self):
        with patch(
            "hermes_cli.dietcode_broccolidb.set_proposal_action",
            return_value={"success": False, "error": "not found"},
        ):
            resp = self.client.post(
                "/api/dietcode/proposals/missing/action",
                json={"action": "deny"},
            )
        assert resp.status_code == 400


class TestWebSearchTimeoutHelper:
    def test_get_web_search_timeout_seconds_default(self, _isolate_hermes_home):
        from tools.web_tools import get_web_search_timeout_seconds

        assert get_web_search_timeout_seconds() == 45

    def test_get_web_search_timeout_seconds_clamps(self, _isolate_hermes_home):
        from tools.web_tools import get_web_search_timeout_seconds

        with patch("tools.web_tools._load_web_config", return_value={"search_timeout_seconds": 999}):
            assert get_web_search_timeout_seconds() == 300

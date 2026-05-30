"""Tests for BroccoliDB native RPC gateway (db_gateway.py)."""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest


def _seed_broccolidb_with_rpc(tmp_path):
    root = tmp_path / "broccolidb"
    (root / "core").mkdir(parents=True)
    (root / "infrastructure" / "hermes").mkdir(parents=True)
    (root / "infrastructure" / "dashboard").mkdir(parents=True)
    (root / "package.json").write_text('{"name":"broccolidb"}')
    for name in ("hermes_rpc.ts", "rpc_handlers.ts", "hermes_oneshot.ts", "queue_metrics.ts"):
        (root / "infrastructure" / "hermes" / name).write_text(f"// {name} stub\n")
    (root / "infrastructure" / "dashboard" / "snapshot.ts").write_text("// snapshot\n")
    return root


class TestBroccolidbDbGateway:
    def test_rpc_available_when_script_present(self, tmp_path, monkeypatch):
        root = _seed_broccolidb_with_rpc(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("HERMES_BROCCOLIDB_RPC", raising=False)

        from plugins.dietcode.lib.tools.broccolidb_tools.db_gateway import rpc_available

        with patch("plugins.dietcode.lib.tools.broccolidb_tools.db_gateway.resolve_broccolidb_root", return_value=str(root)):
            assert rpc_available() is True

    def test_rpc_disabled_by_env(self, tmp_path, monkeypatch):
        root = _seed_broccolidb_with_rpc(tmp_path)
        monkeypatch.setenv("HERMES_BROCCOLIDB_RPC", "0")

        from plugins.dietcode.lib.tools.broccolidb_tools.db_gateway import rpc_available

        with patch("plugins.dietcode.lib.tools.broccolidb_tools.db_gateway.resolve_broccolidb_root", return_value=str(root)):
            assert rpc_available() is False

    def test_invoke_returns_parsed_result(self, tmp_path, monkeypatch):
        _seed_broccolidb_with_rpc(tmp_path)
        monkeypatch.setenv("HERMES_BROCCOLIDB_RPC", "1")

        from plugins.dietcode.lib.tools.broccolidb_tools.db_gateway import BroccoliDbGateway

        gw = BroccoliDbGateway()
        gw._ready = True
        fake_proc = MagicMock()
        fake_proc.poll.return_value = None
        fake_proc.stdin = MagicMock()
        fake_proc.stdout = MagicMock()
        fake_proc.stdout.readline.return_value = json.dumps(
            {"id": 1, "ok": True, "result": {"success": True, "total": 3}}
        )

        with patch.object(gw, "_ensure_process"), patch.object(
            gw, "_process", fake_proc
        ), patch("plugins.dietcode.lib.tools.broccolidb_tools.db_gateway.rpc_available", return_value=True):
            gw._process = fake_proc
            raw = gw.invoke("queue_status")

        data = json.loads(raw)
        assert data["success"] is True
        assert data["total"] == 3
        assert data.get("rpc") is True

    def test_invoke_batch_delegates_to_batch_method(self):
        from plugins.dietcode.lib.tools.broccolidb_tools.db_gateway import BroccoliDbGateway

        gw = BroccoliDbGateway()
        with patch.object(gw, "invoke", return_value='{"success":true,"results":[]}') as mock_invoke:
            raw = gw.invoke_batch([("ping", {}), ("queue_status", {})])
        mock_invoke.assert_called_once()
        assert mock_invoke.call_args[0][0] == "batch"
        assert json.loads(raw)["success"] is True

    def test_oneshot_dispatch_when_rpc_disabled(self, tmp_path, monkeypatch):
        root = _seed_broccolidb_with_rpc(tmp_path)
        monkeypatch.setenv("HERMES_BROCCOLIDB_RPC", "0")
        with patch("plugins.dietcode.lib.tools.broccolidb_tools.db_gateway.resolve_broccolidb_root", return_value=str(root)), patch(
            "plugins.dietcode.lib.tools.broccolidb_tools.db_gateway.subprocess.run"
        ) as mock_run:
            mock_run.return_value = type(
                "R",
                (),
                {"returncode": 0, "stdout": '{"success":true,"pong":true}', "stderr": ""},
            )()
            from plugins.dietcode.lib.tools.broccolidb_tools.db_gateway import run_oneshot_rpc

            raw = run_oneshot_rpc("ping")
        data = json.loads(raw)
        assert data.get("success") is True
        assert mock_run.called

    def test_run_agent_rpc_uses_db_rpc_when_available(self):
        import plugins.dietcode.lib.tools.broccolidb_tools.agent_rpc as agent_rpc_mod

        with patch.object(agent_rpc_mod, "run_db_rpc", return_value='{"success":true,"warmed":true}') as mock_rpc:
            with patch(
                "plugins.dietcode.lib.tools.broccolidb_tools.db_gateway.rpc_available",
                return_value=True,
            ):
                out = agent_rpc_mod.run_agent_rpc("warm", {})
        mock_rpc.assert_called_once()
        assert json.loads(out).get("success") is True

    def test_run_hive_sync_uses_rpc_when_available(self, monkeypatch):
        from plugins.dietcode.lib.tools.broccolidb_tools import runner

        with patch("plugins.dietcode.lib.tools.broccolidb_tools.db_gateway.rpc_available", return_value=True), patch(
            "plugins.dietcode.lib.tools.broccolidb_tools.db_gateway.run_db_rpc",
            return_value='{"success":true,"task_id":"t_abc123"}',
        ) as mock_rpc:
            out = runner.run_hive_sync({"task_id": "t_abc123", "title": "x", "status": "ready", "event": "sync"})
        mock_rpc.assert_called_once()
        assert json.loads(out)["success"] is True

    def test_unknown_method_rejected(self):
        from plugins.dietcode.lib.tools.broccolidb_tools.db_gateway import BroccoliDbGateway

        gw = BroccoliDbGateway()
        raw = gw.invoke("not_a_method")
        data = json.loads(raw)
        assert data["success"] is False
        assert data["error_code"] == "UNKNOWN_METHOD"

    def test_run_db_rpc_delegates(self):
        with patch(
            "plugins.dietcode.lib.tools.broccolidb_tools.db_gateway.get_gateway"
        ) as mock_get:
            mock_gw = MagicMock()
            mock_gw.invoke.return_value = '{"success":true}'
            mock_get.return_value = mock_gw

            from plugins.dietcode.lib.tools.broccolidb_tools.db_gateway import run_db_rpc

            out = run_db_rpc("ping")
            mock_gw.invoke.assert_called_once_with("ping", {}, timeout=60)
            assert out == '{"success":true}'

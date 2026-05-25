"""Tests for JoyZoning habitat → Hermes CONVERGED HTTP bridge."""
from __future__ import annotations

import json

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from gateway.config import PlatformConfig
from gateway.platforms.api_server import (
    APIServerAdapter,
    cors_middleware,
    security_headers_middleware,
)


def _make_app(adapter: APIServerAdapter) -> web.Application:
    mws = [mw for mw in (cors_middleware, security_headers_middleware) if mw is not None]
    app = web.Application(middlewares=mws)
    app["api_server_adapter"] = adapter
    app.router.add_post(
        "/api/internal/joyzoning/habitat-ack",
        adapter._handle_joyzoning_habitat_ack,
    )
    return app


@pytest.fixture
def jz_env(tmp_path, monkeypatch):
    home = tmp_path / ".hermes"
    home.mkdir()
    (home / "config.yaml").write_text("joyzoning:\n  enabled: true\n")
    monkeypatch.setenv("HERMES_HOME", str(home))
    import agent.joyzoning.config as cfg_mod
    cfg_mod._config_cache = None
    return home


@pytest.mark.asyncio
async def test_habitat_ack_marks_converged(jz_env, monkeypatch):
    monkeypatch.setenv("JOYZONING_HABITAT_BRIDGE_TOKEN", "bridge-secret")
    from agent.joyzoning.convergence import ConvergenceState, transition_convergence

    transition_convergence(
        ConvergenceState.READY_FOR_REVIEW,
        scope_id="t_httpbridge",
        summary="review",
        force=True,
    )

    adapter = APIServerAdapter(PlatformConfig(enabled=True, extra={}))
    app = _make_app(adapter)
    async with TestClient(TestServer(app)) as client:
        resp = await client.post(
            "/api/internal/joyzoning/habitat-ack",
            json={
                "scope_id": "t_httpbridge",
                "token": "bridge-secret",
                "summary": "accept-merge via HTTP",
            },
        )
        assert resp.status == 200
        data = await resp.json()
        assert data["success"] is True
        assert data["state"] == "converged"

    from agent.joyzoning.convergence import get_convergence_state
    assert get_convergence_state("t_httpbridge") == ConvergenceState.CONVERGED


@pytest.mark.asyncio
async def test_habitat_ack_rejects_bad_token(jz_env, monkeypatch):
    monkeypatch.setenv("JOYZONING_HABITAT_BRIDGE_TOKEN", "bridge-secret")
    adapter = APIServerAdapter(PlatformConfig(enabled=True, extra={}))
    app = _make_app(adapter)
    async with TestClient(TestServer(app)) as client:
        resp = await client.post(
            "/api/internal/joyzoning/habitat-ack",
            json={"scope_id": "t_badtoken", "token": "wrong"},
        )
        assert resp.status == 409
        data = await resp.json()
        assert data["success"] is False

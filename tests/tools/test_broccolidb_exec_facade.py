"""Contract tests for BroccoliDB execution facade (no live Node required)."""


def test_rpc_methods_include_core_paths():
    from tools.broccolidb_tools.db_native import RPC_METHODS

    for method in (
        "dashboard_snapshot",
        "hive_sync",
        "agent_invoke",
        "pool_flush",
        "batch",
    ):
        assert method in RPC_METHODS


def test_exec_facade_reexports():
    from tools.broccolidb_tools import exec as bdb_exec

    assert bdb_exec.RPC_VERSION >= 4
    assert callable(bdb_exec.run_db_rpc)
    assert callable(bdb_exec.run_agent_rpc)
    assert callable(bdb_exec.warm_db_rpc)

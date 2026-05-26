/**
 * Hermes ↔ BroccoliDB/BroccoliQ native RPC — persistent stdin/stdout worker.
 *
 * Handlers live in rpc_handlers.ts (shared with hive_*.ts CLI wrappers).
 */
import * as readline from "node:readline";
import { getActiveShards, getDb, setDbPath } from "../db/Config.js";
import { RPC_VERSION, dispatchRpc } from "./rpc_handlers.js";

const dbEnv = process.env.HERMES_BROCCOLIDB_DB;
if (dbEnv) setDbPath(dbEnv);

type RpcRequest = { id?: number; method?: string; params?: Record<string, unknown> };
type RpcResponse = {
	id: number;
	ok: boolean;
	result?: Record<string, unknown>;
	error?: string;
	error_code?: string;
};

async function dispatch(req: RpcRequest): Promise<RpcResponse> {
	const id = typeof req.id === "number" ? req.id : 0;
	const method = String(req.method ?? "").trim();
	const params =
		req.params && typeof req.params === "object" ? req.params : {};

	if (!method) {
		return { id, ok: false, error: "method required", error_code: "INVALID_REQUEST" };
	}

	try {
		const result = await dispatchRpc(method, params);
		if (result.success === false && result.error) {
			return {
				id,
				ok: false,
				error: String(result.error),
				error_code: String(result.error_code ?? "RPC_ERROR"),
			};
		}
		return { id, ok: true, result };
	} catch (e) {
		const message = e instanceof Error ? e.message : String(e);
		return { id, ok: false, error: message, error_code: "RPC_ERROR" };
	}
}

async function main() {
	const shards = getActiveShards().length ? getActiveShards() : ["main"];
	const warmShard = shards.includes("kanban") ? "kanban" : shards[0]!;
	await getDb(warmShard);

	if (process.env.HERMES_BROCCOLIDB_PRELOAD_AGENT === "1") {
		const { getAgentContext } = await import("./agent_session.js");
		await getAgentContext();
	}

	process.stdout.write(
		`${JSON.stringify({ ready: true, rpc_version: RPC_VERSION })}\n`,
	);

	const rl = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
	for await (const line of rl) {
		const trimmed = line.trim();
		if (!trimmed) continue;
		let req: RpcRequest;
		try {
			req = JSON.parse(trimmed) as RpcRequest;
		} catch {
			const bad: RpcResponse = {
				id: 0,
				ok: false,
				error: "invalid JSON request",
				error_code: "PARSE_ERROR",
			};
			process.stdout.write(`${JSON.stringify(bad)}\n`);
			continue;
		}
		const resp = await dispatch(req);
		process.stdout.write(`${JSON.stringify(resp)}\n`);
	}
}

main().catch((e: unknown) => {
	const message = e instanceof Error ? e.message : String(e);
	process.stdout.write(
		`${JSON.stringify({ id: 0, ok: false, error: message, error_code: "FATAL" })}\n`,
	);
	process.exit(1);
});

/**
 * Hermes one-shot RPC dispatch — cold path without persistent worker.
 *
 * Usage: tsx infrastructure/hermes/hermes_oneshot.ts <method> '<params-json>'
 */
import { setDbPath } from "../db/Config.js";
import { dispatchRpc } from "./rpc_handlers.js";

const dbEnv = process.env.HERMES_BROCCOLIDB_DB;
if (dbEnv) setDbPath(dbEnv);

const method = (process.argv[2] || "ping").trim();
let params: Record<string, unknown> = {};
if (process.argv[3]) {
	try {
		params = JSON.parse(process.argv[3]) as Record<string, unknown>;
	} catch {
		console.log(
			JSON.stringify({
				success: false,
				error: "invalid params JSON",
				error_code: "PARSE_ERROR",
			}),
		);
		process.exit(1);
	}
}

try {
	const result = await dispatchRpc(method, params);
	console.log(JSON.stringify(result));
} catch (e) {
	const message = e instanceof Error ? e.message : String(e);
	console.log(JSON.stringify({ success: false, error: message, error_code: "ONESHOT_ERROR" }));
	process.exit(1);
}

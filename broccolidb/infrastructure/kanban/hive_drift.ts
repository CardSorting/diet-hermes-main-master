/**
 * Kanban ↔ hive drift probe — fetch hive_tasks status for a set of kanban ids.
 *
 * Invoked by tools/kanban_broccolidb_bridge.compute_drift() via KANBAN_HIVE_DRIFT_PAYLOAD.
 */
import { getDb, setDbPath } from "../db/Config.js";

interface DriftPayload {
	shard_id?: string;
	task_ids: string[];
}

const TASK_ID_RE = /^t_[a-z0-9]{6,32}$/i;

function readPayload(): DriftPayload {
	const raw = process.env.KANBAN_HIVE_DRIFT_PAYLOAD;
	if (!raw) {
		throw new Error("KANBAN_HIVE_DRIFT_PAYLOAD missing");
	}
	const parsed = JSON.parse(raw) as DriftPayload;
	if (!Array.isArray(parsed.task_ids)) {
		throw new Error("task_ids must be an array");
	}
	return parsed;
}

async function main() {
	const dbPath = process.env.HERMES_BROCCOLIDB_DB;
	if (dbPath) {
		setDbPath(dbPath);
	}

	const payload = readPayload();
	const shardId = payload.shard_id || "kanban";
	const taskIds = [
		...new Set(
			payload.task_ids
				.filter((id): id is string => typeof id === "string")
				.map((id) => id.trim().toLowerCase())
				.filter((id) => TASK_ID_RE.test(id)),
		),
	];

	if (taskIds.length === 0) {
		console.log(JSON.stringify({ success: true, rows: [], shard_id: shardId }));
		return;
	}

	const db = await getDb(shardId);
	const rows = await db
		.selectFrom("hive_tasks")
		.select(["task_id", "status"])
		.where("task_id", "in", taskIds)
		.execute();

	console.log(JSON.stringify({ success: true, rows, shard_id: shardId }));
}

main().catch((err) => {
	console.log(
		JSON.stringify({
			success: false,
			error: err instanceof Error ? err.message : String(err),
		}),
	);
	process.exitCode = 1;
});

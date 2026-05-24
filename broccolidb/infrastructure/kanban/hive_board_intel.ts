/**
 * BroccoliQ board metrics for kanban orchestrators.
 *
 * Invoked via KANBAN_HIVE_BOARD_INTEL_PAYLOAD — scoped to the configured shard
 * with bounded queue/hive scans (no unbounded multi-shard full-table walks).
 */
import { getDb, setDbPath } from "../db/Config.js";

interface BoardIntelPayload {
	shard_id?: string;
	queue_limit?: number;
	hive_limit?: number;
}

function readPayload(): BoardIntelPayload {
	const raw = process.env.KANBAN_HIVE_BOARD_INTEL_PAYLOAD;
	if (!raw) {
		throw new Error("KANBAN_HIVE_BOARD_INTEL_PAYLOAD missing");
	}
	return JSON.parse(raw) as BoardIntelPayload;
}

function clampLimit(value: unknown, fallback: number, max: number): number {
	const n = typeof value === "number" ? value : fallback;
	return Math.max(1, Math.min(Math.floor(n), max));
}

async function main() {
	const dbPath = process.env.HERMES_BROCCOLIDB_DB;
	if (dbPath) {
		setDbPath(dbPath);
	}

	const payload = readPayload();
	const shardId = payload.shard_id || "kanban";
	const queueLimit = clampLimit(payload.queue_limit, 500, 2000);
	const hiveLimit = clampLimit(payload.hive_limit, 500, 2000);

	const db = await getDb(shardId);

	const jobs = await db
		.selectFrom("queue_jobs")
		.select(["status"])
		.limit(queueLimit)
		.execute();

	const hive = await db
		.selectFrom("hive_tasks")
		.select(["status"])
		.limit(hiveLimit)
		.execute();

	const queueByStatus: Record<string, number> = {};
	for (const row of jobs) {
		queueByStatus[row.status] = (queueByStatus[row.status] ?? 0) + 1;
	}

	const hiveByStatus: Record<string, number> = {};
	for (const row of hive) {
		hiveByStatus[row.status] = (hiveByStatus[row.status] ?? 0) + 1;
	}

	console.log(
		JSON.stringify({
			success: true,
			shard_id: shardId,
			queue: {
				total: jobs.length,
				byStatus: queueByStatus,
				limit: queueLimit,
				truncated: jobs.length >= queueLimit,
			},
			hive: {
				total: hive.length,
				byStatus: hiveByStatus,
				limit: hiveLimit,
				truncated: hive.length >= hiveLimit,
			},
		}),
	);
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

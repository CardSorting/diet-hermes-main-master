/**
 * Kanban → BroccoliQ hive sync (production path).
 *
 * Invoked by tools/kanban_broccolidb_bridge.py with KANBAN_HIVE_SYNC_PAYLOAD set.
 * Writes directly to the configured shard DB (dbPool.flush() only targets main).
 */
import * as crypto from "node:crypto";
import { getDb, setDbPath } from "../db/Config.js";

export interface KanbanHiveSyncPayload {
	task_id: string;
	title: string;
	body?: string;
	assignee?: string;
	status: string;
	priority?: number;
	result?: string | null;
	created_at?: number;
	started_at?: number | null;
	completed_at?: number | null;
	board?: string;
	event: string;
	shard_id?: string;
	signal_events?: string[];
	run_id?: string | null;
	tenant?: string | null;
	/** JoyZoning habitat scope (forensic, non-authoritative). */
	habitat_task?: string;
	joyzoning_scope?: string;
	convergence_state?: string;
}

const TASK_ID_RE = /^t_[a-z0-9]{6,32}$/i;

function readPayload(): KanbanHiveSyncPayload {
	const raw = process.env.KANBAN_HIVE_SYNC_PAYLOAD;
	if (!raw) {
		throw new Error("KANBAN_HIVE_SYNC_PAYLOAD missing");
	}
	return JSON.parse(raw) as KanbanHiveSyncPayload;
}

function normalizeTaskId(taskId: string): string {
	const tid = taskId.trim().toLowerCase();
	if (!TASK_ID_RE.test(tid)) {
		throw new Error(`invalid task_id format: ${taskId}`);
	}
	return tid;
}

async function main() {
	const dbPath = process.env.HERMES_BROCCOLIDB_DB;
	if (dbPath) {
		setDbPath(dbPath);
	}

	const payload = readPayload();
	const taskId = normalizeTaskId(payload.task_id);

	const now = Date.now();
	const hiveId = `hive_${taskId.replace(/[^a-z0-9_\-]/g, "_")}`;
	const shardId = payload.shard_id || "kanban";

	const db = await getDb(shardId);
	const existing = await db
		.selectFrom("hive_tasks")
		.selectAll()
		.where("task_id", "=", taskId)
		.executeTakeFirst();

	const merged = {
		id: existing?.id ?? hiveId,
		task_id: taskId,
		title: payload.title || existing?.title || taskId,
		objective: payload.title || existing?.objective || taskId,
		description: payload.body ?? existing?.description ?? "",
		status: payload.status || existing?.status || "unknown",
		priority: payload.priority ?? existing?.priority ?? 0,
		user_agent: payload.assignee || existing?.user_agent || "hermes",
		agent_id: payload.assignee || existing?.agent_id || null,
		result:
			payload.result !== undefined && payload.result !== null
				? payload.result
				: (existing?.result ?? null),
		created_at: payload.created_at ?? existing?.created_at ?? now,
		updated_at: now,
		started_at:
			payload.event === "start"
				? (payload.started_at ?? existing?.started_at ?? now)
				: (payload.started_at ?? existing?.started_at ?? null),
		completed_at:
			payload.event === "complete"
				? (payload.completed_at ?? existing?.completed_at ?? now)
				: (payload.completed_at ?? existing?.completed_at ?? null),
		vitals_heartbeat:
			payload.event === "heartbeat"
				? String(now)
				: (existing?.vitals_heartbeat ?? null),
	};

	await db
		.insertInto("hive_tasks")
		.values(merged)
		.onConflict((oc) =>
			oc.column("task_id").doUpdateSet({
				title: merged.title,
				objective: merged.objective,
				description: merged.description,
				status: merged.status,
				priority: merged.priority,
				user_agent: merged.user_agent,
				agent_id: merged.agent_id,
				result: merged.result,
				updated_at: merged.updated_at,
				started_at: merged.started_at,
				completed_at: merged.completed_at,
				vitals_heartbeat: merged.vitals_heartbeat,
			}),
		)
		.execute();

	const signalEvents = new Set(payload.signal_events ?? ["create", "complete", "block", "start"]);
	if (signalEvents.has(payload.event)) {
		await db
			.insertInto("queue_jobs")
			.values({
				id: `kanban-${taskId}-${payload.event}-${now}-${crypto.randomUUID().slice(0, 8)}`,
				payload: JSON.stringify({
					type: "kanban_orchestration",
					task_id: taskId,
					event: payload.event,
					status: payload.status,
					board: payload.board ?? "default",
					assignee: payload.assignee,
					run_id: payload.run_id ?? null,
					tenant: payload.tenant ?? null,
					habitat_task: payload.habitat_task ?? null,
					joyzoning_scope: payload.joyzoning_scope ?? null,
					convergence_state: payload.convergence_state ?? null,
				}),
				status: "pending",
				priority: payload.event === "complete" ? 2 : 1,
				attempts: 0,
				maxAttempts: 5,
				runAt: now,
				error: null,
				createdAt: now,
				updatedAt: now,
			})
			.execute();
	}

	await db
		.insertInto("hive_audit")
		.values({
			id: crypto.randomUUID(),
			session_id: payload.run_id ?? null,
			type: `kanban_${payload.event}`,
			message: `Kanban hive sync: ${taskId} → ${merged.status}`,
			data: JSON.stringify({
				board: payload.board,
				event: payload.event,
				assignee: payload.assignee,
				tenant: payload.tenant,
				habitat_task: payload.habitat_task ?? null,
				joyzoning_scope: payload.joyzoning_scope ?? null,
				convergence_state: payload.convergence_state ?? null,
			}),
			timestamp: now,
		})
		.execute();

	console.log(
		JSON.stringify({
			success: true,
			hiveId: merged.id,
			task_id: taskId,
			event: payload.event,
			shard_id: shardId,
			merged_status: merged.status,
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

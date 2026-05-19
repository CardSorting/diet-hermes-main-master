import * as admin from 'firebase-admin'

export type ToolRequestStatus =
  | 'pending_approval'
  | 'approved'
  | 'claimed'
  | 'running'
  | 'completed'
  | 'failed'
  | 'cancelled'
  | 'expired'

export interface WorkspaceSnapshot {
  workspaceId: string
  repoRoot: string
  gitCommitSha: string
  branchName: string
  dirtyState: boolean
  createdAt: number
  workerId: string
}

export interface ResultProvenance {
  workerId: string
  workspaceId: string
  startedAt: number
  completedAt: number
  exitCode?: number
  stdoutHash?: string
  stderrHash?: string
  artifactHash?: string
  diffHash?: string
}

export interface ToolRequest {
  requestId: string
  sessionId: string
  workspaceId: string
  tool: string
  args: any
  argsHash: string
  status: ToolRequestStatus
  idempotencyKey: string
  createdAt: any
  approvedAt?: any
  claimedAt?: any
  claimedBy?: string
  leaseExpiresAt?: any
  attemptCount: number
  maxAttempts: number
  result?: any
  error?: string
  
  // Provenance fields
  baseCommitSha?: string
  expectedDirtyState?: boolean
  createdByRuntimeStep?: number
  resultProvenance?: ResultProvenance
}

export interface EnvironmentSnapshot {
  os: string
  nodeVersion: string
  packageLockHash?: string
  envHash?: string
}

export interface ToolInvocation {
  tool: string
  args: any
  stdoutHash?: string
  diffHash?: string
  exitCode?: number
}

export interface ExecutionJournal {
  journalId: string
  sessionId: string
  workspaceId: string
  requestId: string
  runtimeVersion: string
  modelId: string
  promptHash: string
  baseCommitSha: string
  finalCommitSha?: string
  toolSequence: ToolInvocation[]
  environmentSnapshot: EnvironmentSnapshot
  timing: {
    startedAt: number
    completedAt?: number
    durationMs?: number
  }
  replayable: boolean
}

// Evolve: Execution Universe & Virtual Snapshot Schema
export interface ExecutionUniverse {
  universeId: string
  workspaceSnapshotId: string
  filesystemHash: string
  dependencyLockHash?: string
  containerImageHash?: string
  environmentSnapshot: EnvironmentSnapshot
  mountedSecrets: string[]
  runtimeVersion: string
}

export type DivergenceType =
  | 'filesystem_divergence'
  | 'dependency_divergence'
  | 'runtime_divergence'
  | 'nondeterministic_output_divergence'
  | 'timing_divergence'

export interface ReplayDivergence {
  diverged: boolean
  type?: DivergenceType
  details?: string
}

export interface SessionBranch {
  branchId: string
  parentSessionId: string
  forkedFromJournalId: string
  targetUniverseId: string
  createdAt: number
}

export interface ToolPlanItem {
  step: number
  tool: string
  args: any
  requireApproval: boolean
}

export interface RuntimeIntent {
  intentId: string
  intentType: 'refactor' | 'test' | 'lint' | 'patch' | 'custom'
  intentSummary: string
  status: 'pending' | 'planned' | 'executing' | 'completed' | 'failed'
  generatedToolPlan: ToolPlanItem[]
  createdAt: any
}

export interface WorkerIdentity {
  workerId: string
  workspaceId: string
  capabilities: string[]
  heartbeat: number
  lastSeenAt: any
}

export type SessionEventType =
  | 'session.created'
  | 'user.message'
  | 'runtime.thinking'
  | 'runtime.message'
  | 'session.complete'
  | 'session.failed'
  | 'session.cancelled'
  | 'session.max_steps_exceeded'
  // Audit & recovery events
  | 'tool.claimed'
  | 'tool.lease_expired'
  | 'tool.retry_scheduled'
  | 'tool.result_rejected'
  | 'approval.expired'
  | 'tool.completed'
  | 'tool.failed'
  | 'approval.granted'
  | 'approval.denied'
  // Workspace Provenance Events
  | 'workspace.snapshot_created'
  | 'workspace.drift_detected'
  | 'tool.provenance_attached'
  | 'artifact.hash_recorded'
  | 'diff.hash_recorded'
  // Intent & Journal Replay Events
  | 'intent.created'
  | 'intent.planned'
  | 'journal.emitted'
  | 'replay.divergence_detected'
  | 'replay.success'
  // Evolve: Virtual Universe & Branching Timeline Events
  | 'universe.created'
  | 'session.branched'
  | 'replay.divergence_classified'

export interface SessionEvent {
  eventId: string
  sessionId: string
  type: SessionEventType
  createdAt: any
  payload: any
  source: 'local-client' | 'remote-runtime'
}

export const SAFETY_LIMITS = {
  maxRuntimeSteps: 10,
  maxToolRequests: 8,
  maxFilesRead: 25,
  maxFilesWritten: 10,
  maxCommandSeconds: 60,
  maxOutputBytes: 100_000,
  maxAttempts: 3,
  approvalTimeoutMs: 300000, // 5 minutes approval timeout
}

export function computeArgsHash(tool: string, args: any): string {
  const serialized = JSON.stringify({ tool, args: args || {} })
  let hash = 0
  for (let i = 0; i < serialized.length; i++) {
    const char = serialized.charCodeAt(i)
    hash = (hash << 5) - hash + char
    hash |= 0 // Convert to 32bit integer
  }
  return `hash-${hash}`
}

export class SessionEventRepository {
  constructor(private db: admin.firestore.Firestore) {}

  async appendEvent(sessionId: string, type: SessionEventType, source: SessionEvent['source'], payload: any = {}): Promise<SessionEvent> {
    const eventId = `ev-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`
    const event: SessionEvent = {
      eventId,
      sessionId,
      type,
      source,
      createdAt: admin.firestore.FieldValue.serverTimestamp(),
      payload,
    }

    console.log(`[EventSpine] Appending event: ${type} (source: ${source})`)
    await this.db
      .collection('sessions')
      .doc(sessionId)
      .collection('events')
      .doc(eventId)
      .set(event)
    return event
  }

  async getEvents(sessionId: string): Promise<SessionEvent[]> {
    const snap = await this.db
      .collection('sessions')
      .doc(sessionId)
      .collection('events')
      .orderBy('createdAt', 'asc')
      .get()

    return snap.docs.map(doc => {
      const data = doc.data()
      return {
        eventId: doc.id,
        sessionId,
        type: data.type,
        source: data.source,
        createdAt: data.createdAt,
        payload: data.payload || {},
      }
    })
  }

  async createToolRequest(
    sessionId: string, 
    tool: string, 
    args: any, 
    options: { 
      requireApproval: boolean, 
      workspaceId?: string,
      baseCommitSha?: string,
      expectedDirtyState?: boolean,
      createdByRuntimeStep?: number
    }
  ): Promise<ToolRequest> {
    const requestId = `req-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`
    const status: ToolRequestStatus = options.requireApproval ? 'pending_approval' : 'approved'
    const argsHash = computeArgsHash(tool, args)
    const idempotencyKey = `idem-${requestId}`

    const request: ToolRequest = {
      requestId,
      sessionId,
      workspaceId: options.workspaceId || 'ws-default',
      tool,
      args,
      argsHash,
      status,
      idempotencyKey,
      attemptCount: 0,
      maxAttempts: SAFETY_LIMITS.maxAttempts,
      createdAt: admin.firestore.FieldValue.serverTimestamp(),
      ...(status === 'approved' ? { approvedAt: admin.firestore.FieldValue.serverTimestamp() } : {}),
      
      // Provenance fields
      baseCommitSha: options.baseCommitSha,
      expectedDirtyState: options.expectedDirtyState,
      createdByRuntimeStep: options.createdByRuntimeStep
    }

    console.log(`[EventSpine] Creating ToolRequest: ${tool} (status: ${status}, hash: ${argsHash})`)
    await this.db
      .collection('sessions')
      .doc(sessionId)
      .collection('toolRequests')
      .doc(requestId)
      .set(request)

    return request
  }

  async getToolRequests(sessionId: string): Promise<ToolRequest[]> {
    const snap = await this.db
      .collection('sessions')
      .doc(sessionId)
      .collection('toolRequests')
      .get()

    return snap.docs.map(doc => {
      const data = doc.data()
      return {
        requestId: doc.id,
        sessionId,
        workspaceId: data.workspaceId,
        tool: data.tool,
        args: data.args,
        argsHash: data.argsHash,
        status: data.status,
        idempotencyKey: data.idempotencyKey,
        createdAt: data.createdAt,
        approvedAt: data.approvedAt,
        claimedAt: data.claimedAt,
        claimedBy: data.claimedBy,
        lastError: data.lastError,
        leaseExpiresAt: data.leaseExpiresAt,
        attemptCount: data.attemptCount || 0,
        maxAttempts: data.maxAttempts || SAFETY_LIMITS.maxAttempts,
        result: data.result,
        error: data.error,
        baseCommitSha: data.baseCommitSha,
        expectedDirtyState: data.expectedDirtyState,
        createdByRuntimeStep: data.createdByRuntimeStep,
        resultProvenance: data.resultProvenance
      }
    })
  }

  async createRuntimeIntent(sessionId: string, intentType: RuntimeIntent['intentType'], intentSummary: string, plan: ToolPlanItem[]): Promise<RuntimeIntent> {
    const intentId = `intent-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`
    const intent: RuntimeIntent = {
      intentId,
      intentType,
      intentSummary,
      status: 'planned',
      generatedToolPlan: plan,
      createdAt: admin.firestore.FieldValue.serverTimestamp()
    }

    console.log(`[EventSpine] Creating RuntimeIntent: ${intentType} (${intentSummary})`)
    await this.db
      .collection('sessions')
      .doc(sessionId)
      .collection('intents')
      .doc(intentId)
      .set(intent)

    return intent
  }

  async createExecutionJournal(sessionId: string, journal: ExecutionJournal): Promise<void> {
    console.log(`[EventSpine] Emitting ExecutionJournal: ${journal.journalId}`)
    await this.db
      .collection('sessions')
      .doc(sessionId)
      .collection('journals')
      .doc(journal.journalId)
      .set(journal)
  }

  async createExecutionUniverse(sessionId: string, universe: ExecutionUniverse): Promise<void> {
    console.log(`[EventSpine] Registering ExecutionUniverse: ${universe.universeId}`)
    await this.db
      .collection('sessions')
      .doc(sessionId)
      .collection('universes')
      .doc(universe.universeId)
      .set(universe)
  }

  async createSessionBranch(sessionId: string, branch: SessionBranch): Promise<void> {
    console.log(`[EventSpine] Spawning SessionBranch: ${branch.branchId} from Parent: ${branch.parentSessionId}`)
    await this.db
      .collection('sessions')
      .doc(sessionId)
      .collection('branches')
      .doc(branch.branchId)
      .set(branch)
  }
}

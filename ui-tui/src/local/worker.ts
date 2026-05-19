import { readdirSync, statSync, readFileSync, writeFileSync, existsSync } from 'node:fs'
import { join, resolve, relative } from 'node:path'
import { execSync } from 'node:child_process'
import { collection, onSnapshot, doc, setDoc, serverTimestamp, runTransaction, getDocs } from 'firebase/firestore'
import { executePatchLocally } from './patchExecutor.js'
import { applyCommandPolicy } from './policy.js'

export const SAFETY_LIMITS = {
  maxRuntimeSteps: 10,
  maxToolRequests: 8,
  maxFilesRead: 25,
  maxFilesWritten: 10,
  maxCommandSeconds: 60,
  maxOutputBytes: 100_000,
  maxAttempts: 3,
}

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

export interface EnvironmentSnapshot {
  os: string
  nodeVersion: string
  packageLockHash?: string
  envHash?: string
  filesystemHash?: string // Evolve: Merkle snapshot hash
}

export interface ToolInvocation {
  tool: string
  args: any
  stdoutHash?: string
  diffHash?: string
  exitCode?: number
  durationMs?: number // timing
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
  universeId?: string // Evolve: Bind to ExecutionUniverse
}

// Evolve: Snapshot Virtualization & Execution Universe
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

export interface PolicyRule {
  ruleId: string
  effect: 'deny' | 'allow'
  actionPattern: string
  condition?: string
}

export interface PolicyGraph {
  policyId: string
  rules: PolicyRule[]
  scopes: any
  constraints: {
    requiresApproval: boolean
    forbiddenPaths: string[]
    allowedPaths: string[]
  }
}


export class ExecutionWorker {
  private unsubscribe: (() => void) | null = null
  private heartbeatTimer: any = null
  private workerId: string
  private workspaceId: string
  private capabilities: string[]
  private activeUniverseId?: string

  constructor(
    private db: any,
    private sessionId: string,
    private workspaceRoot: string
  ) {
    this.workerId = `worker-${process.platform}-${Math.random().toString(36).substring(2, 7)}`
    this.workspaceId = this.getWorkspaceId(resolve(this.workspaceRoot))
    this.capabilities = ['list_files', 'read_file', 'git_diff', 'run_tests', 'write_file', 'apply_patch', 'run_command']
  }

  async start() {
    console.log(`[Worker] Starting Hardened Execution Worker ${this.workerId} for session ${this.sessionId}`)
    
    // Register worker and start heartbeat
    await this.updateHeartbeat()
    this.heartbeatTimer = setInterval(() => this.updateHeartbeat(), 5000)

    // Evolve: Virtual Snapshot & Universe Compilation
    const snapshot = await this.getWorkspaceSnapshot()
    const filesystemHash = this.calculateFilesystemHash(resolve(this.workspaceRoot))
    const dependencyLockHash = this.calculateDependencyLockHash(resolve(this.workspaceRoot))
    
    const universeId = `univ-${this.workspaceId}-${Date.now()}`
    this.activeUniverseId = universeId

    const envSnapshot: EnvironmentSnapshot = {
      os: process.platform,
      nodeVersion: process.version,
      packageLockHash: dependencyLockHash,
      envHash: this.hashString(JSON.stringify(process.env.PATH || '')),
      filesystemHash
    }

    const universe: ExecutionUniverse = {
      universeId,
      workspaceSnapshotId: this.workspaceId,
      filesystemHash,
      dependencyLockHash,
      environmentSnapshot: envSnapshot,
      mountedSecrets: [],
      runtimeVersion: 'v0.9.0-sovereign-kernel'
    }

    // Register active session context and snapshots
    const sessionDocRef = doc(this.db, 'sessions', this.sessionId)
    await setDoc(sessionDocRef, { workspaceSnapshot: snapshot, activeUniverseId: universeId }, { merge: true })
    
    // Write Universe registry doc
    const universeRef = doc(this.db, 'sessions', this.sessionId, 'universes', universeId)
    await setDoc(universeRef, universe)

    await this.writeEvent('workspace.snapshot_created', { workspaceId: this.workspaceId, snapshot })
    await this.writeEvent('universe.created', { universeId, universe })

    const requestsRef = collection(this.db, 'sessions', this.sessionId, 'toolRequests')
    this.unsubscribe = onSnapshot(requestsRef, (snapshot) => {
      snapshot.docChanges().forEach(async (change) => {
        if (change.type === 'added' || change.type === 'modified') {
          const data = change.doc.data()
          if (data.status === 'approved') {
            await this.tryClaimAndExecute(change.doc.id, data)
          }
        }
      })
    })
  }

  stop() {
    if (this.unsubscribe) {
      this.unsubscribe()
      this.unsubscribe = null
    }
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
    console.log(`[Worker] Stopped Execution Worker ${this.workerId}.`)
  }

  private getWorkspaceId(root: string): string {
    let hash = 0
    for (let i = 0; i < root.length; i++) {
      hash = (hash << 5) - hash + root.charCodeAt(i)
      hash |= 0
    }
    return `ws-${Math.abs(hash)}`
  }

  calculateFilesystemHash(root: string): string {
    const files: { path: string; hash: string }[] = []
    const traverse = (dir: string) => {
      if (!existsSync(dir)) return
      const items = readdirSync(dir)
      for (const item of items) {
        if (item === 'node_modules' || item === '.git' || item === '.hermes' || item === '.test_workspace' || item === '.test_worker_sandbox') {
          continue
        }
        const fullPath = join(dir, item)
        const stat = statSync(fullPath)
        if (stat.isDirectory()) {
          traverse(fullPath)
        } else {
          try {
            const content = readFileSync(fullPath, 'utf8')
            files.push({
              path: relative(root, fullPath),
              hash: this.hashString(content)
            })
          } catch {
            // Unreadable or binary files
          }
        }
      }
    }
    traverse(root)
    files.sort((a, b) => a.path.localeCompare(b.path))
    return this.hashString(JSON.stringify(files))
  }

  calculateDependencyLockHash(root: string): string {
    const locks = ['package-lock.json', 'package.json', 'yarn.lock', 'pnpm-lock.yaml', 'requirements.txt', 'poetry.lock']
    let combined = ''
    for (const lock of locks) {
      const fullPath = join(root, lock)
      if (existsSync(fullPath)) {
        try {
          combined += `${lock}:${readFileSync(fullPath, 'utf8')};`
        } catch {
          // ignore unreadable
        }
      }
    }
    return this.hashString(combined || 'no-dependencies')
  }

  async getWorkspaceSnapshot(): Promise<WorkspaceSnapshot> {
    const root = resolve(this.workspaceRoot)
    let gitCommitSha = ''
    let branchName = ''
    let dirtyState = false

    try {
      gitCommitSha = execSync('git rev-parse HEAD', { cwd: root, stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
      branchName = execSync('git rev-parse --abbrev-ref HEAD', { cwd: root, stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
      const porcelain = execSync('git status --porcelain', { cwd: root, stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
      dirtyState = porcelain.length > 0
    } catch {
      // Fallback in case directory is not a git repository
      gitCommitSha = 'no-git-sha'
      branchName = 'no-git-branch'
    }

    return {
      workspaceId: this.workspaceId,
      repoRoot: root,
      gitCommitSha,
      branchName,
      dirtyState,
      createdAt: Date.now(),
      workerId: this.workerId
    }
  }

  private hashString(str: string): string {
    let hash = 0
    for (let i = 0; i < str.length; i++) {
      hash = (hash << 5) - hash + str.charCodeAt(i)
      hash |= 0
    }
    return `hash-${hash}`
  }

  private async updateHeartbeat() {
    const workerRef = doc(this.db, 'sessions', this.sessionId, 'workers', this.workerId)
    await setDoc(workerRef, {
      workerId: this.workerId,
      workspaceId: this.workspaceId,
      capabilities: this.capabilities,
      heartbeat: Date.now(),
      lastSeenAt: serverTimestamp()
    }, { merge: true })
  }

  private async isSessionCancelled(): Promise<boolean> {
    const eventsRef = collection(this.db, 'sessions', this.sessionId, 'events')
    const snap = await getDocs(eventsRef)
    return snap.docs.some(doc => {
      const type = doc.data().type
      return type === 'session.cancelled' || type === 'session.complete' || type === 'session.failed'
    })
  }

  // Evolve: Speculative Universe Replay & Divergence Taxonomy
  async replayJournal(journal: ExecutionJournal): Promise<{ matches: boolean; divergence?: string; classification?: ReplayDivergence }> {
    console.log(`[Worker] 🔄 Replaying Execution Journal: ${journal.journalId}`)
    
    // 1. Validate environment snapshots / runtime compatibility
    if (process.platform !== journal.environmentSnapshot.os || process.version !== journal.environmentSnapshot.nodeVersion) {
      const details = `Runtime Mismatch: expected ${journal.environmentSnapshot.os}/${journal.environmentSnapshot.nodeVersion}, currently running ${process.platform}/${process.version}`
      const classification: ReplayDivergence = { diverged: true, type: 'runtime_divergence', details }
      await this.writeEvent('replay.divergence_classified', { journalId: journal.journalId, classification })
      await this.writeEvent('replay.divergence_detected', { journalId: journal.journalId, reason: details })
      return { matches: false, divergence: details, classification }
    }

    // 2. Validate dependency lockfile consistency
    const currentLockHash = this.calculateDependencyLockHash(resolve(this.workspaceRoot))
    if (journal.environmentSnapshot.packageLockHash && currentLockHash !== journal.environmentSnapshot.packageLockHash) {
      const details = `Dependency lockfile drifted: Expected lockfile hash ${journal.environmentSnapshot.packageLockHash}, but computed ${currentLockHash}`
      const classification: ReplayDivergence = { diverged: true, type: 'dependency_divergence', details }
      await this.writeEvent('replay.divergence_classified', { journalId: journal.journalId, classification })
      await this.writeEvent('replay.divergence_detected', { journalId: journal.journalId, reason: details })
      return { matches: false, divergence: details, classification }
    }

    // 3. Validate filesystem consistency (Merkle Root verification)
    const currentFSHash = this.calculateFilesystemHash(resolve(this.workspaceRoot))
    if (journal.environmentSnapshot.filesystemHash && currentFSHash !== journal.environmentSnapshot.filesystemHash) {
      const details = `Filesystem Merkle hash drifted: Expected filesystem hash ${journal.environmentSnapshot.filesystemHash}, got ${currentFSHash}`
      const classification: ReplayDivergence = { diverged: true, type: 'filesystem_divergence', details }
      await this.writeEvent('replay.divergence_classified', { journalId: journal.journalId, classification })
      await this.writeEvent('replay.divergence_detected', { journalId: journal.journalId, reason: details })
      return { matches: false, divergence: details, classification }
    }

    // 4. Git base commit compatibility checks
    const currentSnapshot = await this.getWorkspaceSnapshot()
    if (currentSnapshot.gitCommitSha !== journal.baseCommitSha) {
      const details = `Base Commit Mismatch: expected ${journal.baseCommitSha}, currently at ${currentSnapshot.gitCommitSha}`
      const classification: ReplayDivergence = { diverged: true, type: 'filesystem_divergence', details }
      await this.writeEvent('replay.divergence_classified', { journalId: journal.journalId, classification })
      await this.writeEvent('replay.divergence_detected', { journalId: journal.journalId, reason: details })
      return { 
        matches: false, 
        divergence: details,
        classification
      }
    }

    // 5. Re-run tool sequence and assert deterministic outputs
    for (const invocation of journal.toolSequence) {
      try {
        const start = Date.now()
        const result = await this.executeTool(invocation.tool, invocation.args, `replay-${journal.journalId}`)
        const duration = Date.now() - start

        const currentStdoutHash = this.hashString(typeof result === 'string' ? result : JSON.stringify(result))
        
        if (currentStdoutHash !== invocation.stdoutHash) {
          const details = `Nondeterministic Divergence: stdout hash mismatch. Expected ${invocation.stdoutHash}, got ${currentStdoutHash}`
          const classification: ReplayDivergence = { diverged: true, type: 'nondeterministic_output_divergence', details }
          await this.writeEvent('replay.divergence_classified', { journalId: journal.journalId, classification })
          await this.writeEvent('replay.divergence_detected', { journalId: journal.journalId, reason: details })
          return { 
            matches: false, 
            divergence: details,
            classification
          }
        }

        // Timing divergence verification: alert if execution duration drifted by over 10x
        if (invocation.durationMs !== undefined && duration > invocation.durationMs * 10) {
          const details = `Timing Divergence: tool ${invocation.tool} duration drifted. Expected ~${invocation.durationMs}ms, took ${duration}ms`
          const classification: ReplayDivergence = { diverged: true, type: 'timing_divergence', details }
          await this.writeEvent('replay.divergence_classified', { journalId: journal.journalId, classification })
          await this.writeEvent('replay.divergence_detected', { journalId: journal.journalId, reason: details })
          return { matches: false, divergence: details, classification }
        }
      } catch (e: any) {
        const details = `Replay execution failed: ${e.message || String(e)}`
        const classification: ReplayDivergence = { diverged: true, type: 'nondeterministic_output_divergence', details }
        await this.writeEvent('replay.divergence_classified', { journalId: journal.journalId, classification })
        await this.writeEvent('replay.divergence_detected', { journalId: journal.journalId, reason: details })
        return { 
          matches: false, 
          divergence: details,
          classification
        }
      }
    }

    await this.writeEvent('replay.success', { journalId: journal.journalId })
    return { matches: true }
  }

  private async tryClaimAndExecute(requestId: string, reqData: any) {
    if (await this.isSessionCancelled()) {
      console.log(`[Worker] Session ${this.sessionId} is terminated or cancelled. Ignoring claims.`)
      return
    }

    if (!this.capabilities.includes(reqData.tool)) {
      console.warn(`[Worker] Capability mismatch: Worker does not support tool '${reqData.tool}'. Bypass claim.`)
      return
    }

    const docRef = doc(this.db, 'sessions', this.sessionId, 'toolRequests', requestId)
    
    try {
      console.log(`[Worker] Attempting to lease tool request: ${reqData.tool} (request: ${requestId})`)
      
      // 1. Concurrency lock lease claim transaction
      await runTransaction(this.db, async (transaction) => {
        const docSnap = await transaction.get(docRef)
        if (!docSnap.exists()) {
          throw new Error('ToolRequest document does not exist')
        }
        const currentData = docSnap.data()
        if (currentData?.status !== 'approved') {
          throw new Error(`ToolRequest is already claimed or finished. Status: ${currentData?.status}`)
        }
        
        transaction.update(docRef, {
          status: 'claimed',
          claimedBy: this.workerId,
          claimedAt: serverTimestamp(),
          leaseExpiresAt: new Date(Date.now() + 15000) // 15 second lease for high-velocity turns
        })
      })

      console.log(`[Worker] ⚡ Lease claimed successfully for request ${requestId}.`)
      await this.writeEvent('tool.claimed', { requestId, workerId: this.workerId })
      
      // Update status to running
      await setDoc(docRef, { status: 'running' }, { merge: true })

      // 2. Workspace Drift Prevention Guards!
      const freshSnapshot = await this.getWorkspaceSnapshot()
      const isWriteCapable = ['write_file', 'apply_patch', 'run_command'].includes(reqData.tool)
      let drifted = false
      let driftError = ''

      if (reqData.workspaceId && reqData.workspaceId !== this.workspaceId) {
        drifted = true
        driftError = `Workspace ID mismatch: Expected '${reqData.workspaceId}', found '${this.workspaceId}'`
      } else if (isWriteCapable && reqData.baseCommitSha && reqData.baseCommitSha !== freshSnapshot.gitCommitSha) {
        drifted = true
        driftError = `Workspace Git Commit SHA drifted: Expected base commit '${reqData.baseCommitSha}', currently at '${freshSnapshot.gitCommitSha}'`
      } else if (isWriteCapable && reqData.expectedDirtyState !== undefined && reqData.expectedDirtyState !== freshSnapshot.dirtyState) {
        drifted = true
        driftError = `Workspace Dirty State drifted: Expected dirtyState ${reqData.expectedDirtyState}, currently is ${freshSnapshot.dirtyState}`
      }

      if (drifted) {
        console.error(`[Worker] ⚠️ Workspace Drift Detected! ${driftError}`)
        
        await runTransaction(this.db, async (transaction) => {
          transaction.update(docRef, {
            status: 'failed',
            error: `Workspace Drift Detected: ${driftError}`
          })
        })

        await this.writeEvent('workspace.drift_detected', { requestId, driftError, expectedCommit: reqData.baseCommitSha, currentCommit: freshSnapshot.gitCommitSha })
        await this.writeEvent('tool.failed', { requestId })
        return
      }

      // 3. Perform the execution inside local sandbox with result provenance
      const startedAt = Date.now()
      try {
        const result = await this.executeTool(reqData.tool, reqData.args || {}, requestId)
        const completedAt = Date.now()

        // Gather stdout hash, artifact diff and post-execution diff hash
        const stdoutHash = this.hashString(typeof result === 'string' ? result : JSON.stringify(result))
        let diffHash = ''
        let artifactHash = ''

        try {
          const root = resolve(this.workspaceRoot)
          const diff = execSync('git diff', { cwd: root, stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
          if (diff) {
            diffHash = this.hashString(diff)
          }
          
          if (isWriteCapable && reqData.args.path) {
            const filePath = resolve(root, reqData.args.path)
            if (existsSync(filePath)) {
              artifactHash = this.hashString(readFileSync(filePath, 'utf8'))
            }
          }
        } catch {
          // git command failed or not inside a repo
        }

        const provenance: ResultProvenance = {
          workerId: this.workerId,
          workspaceId: this.workspaceId,
          startedAt,
          completedAt,
          exitCode: 0,
          stdoutHash,
          ...(diffHash ? { diffHash } : {}),
          ...(artifactHash ? { artifactHash } : {})
        }

        // Evolve: Execution Journal Assembly
        const journalId = `journ-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`
        const filesystemHash = this.calculateFilesystemHash(resolve(this.workspaceRoot))
        const dependencyLockHash = this.calculateDependencyLockHash(resolve(this.workspaceRoot))

        const journal: ExecutionJournal = {
          journalId,
          sessionId: this.sessionId,
          workspaceId: this.workspaceId,
          requestId,
          runtimeVersion: 'v0.9.0-sovereign-kernel',
          modelId: 'hermes-3-70b-hosted',
          promptHash: this.hashString(reqData.argsHash || ''),
          baseCommitSha: reqData.baseCommitSha || freshSnapshot.gitCommitSha,
          finalCommitSha: freshSnapshot.gitCommitSha,
          toolSequence: [{
            tool: reqData.tool,
            args: reqData.args,
            stdoutHash,
            ...(diffHash ? { diffHash } : {}),
            exitCode: 0,
            durationMs: completedAt - startedAt
          }],
          environmentSnapshot: {
            os: process.platform,
            nodeVersion: process.version,
            packageLockHash: dependencyLockHash,
            envHash: this.hashString(JSON.stringify(process.env.PATH || '')),
            filesystemHash
          },
          timing: {
            startedAt,
            completedAt,
            durationMs: completedAt - startedAt
          },
          replayable: true,
          universeId: this.activeUniverseId
        }

        // 4. Result Idempotency Transaction verification: verify lease still belongs to this workerId!
        let resultRejected = false
        await runTransaction(this.db, async (transaction) => {
          const freshSnap = await transaction.get(docRef)
          if (!freshSnap.exists()) throw new Error('ToolRequest not found')
          const freshData = freshSnap.data()
          if ((freshData.status !== 'claimed' && freshData.status !== 'running') || freshData.claimedBy !== this.workerId) {
            resultRejected = true
            throw new Error('Lease expired or claimed by another worker')
          }
          transaction.update(docRef, {
            status: 'completed',
            result,
            resultProvenance: provenance
          })
        })

        if (resultRejected) {
          console.warn(`[Worker] Result rejected for request ${requestId}: lease expired.`)
          await this.writeEvent('tool.result_rejected', { requestId, workerId: this.workerId })
          return
        }

        // Persist journal doc
        const journalRef = doc(this.db, 'sessions', this.sessionId, 'journals', journalId)
        await setDoc(journalRef, journal)

        // Notify runtime loop via events log trigger
        if (artifactHash) {
          await this.writeEvent('artifact.hash_recorded', { requestId, artifactHash })
        }
        if (diffHash) {
          await this.writeEvent('diff.hash_recorded', { requestId, diffHash })
        }
        await this.writeEvent('journal.emitted', { journalId, requestId })
        await this.writeEvent('tool.completed', { requestId })
      } catch (execErr: any) {
        console.error(`[Worker] Tool execution error for ${requestId}:`, execErr)
        
        let resultRejected = false
        await runTransaction(this.db, async (transaction) => {
          const freshSnap = await transaction.get(docRef)
          if (!freshSnap.exists()) throw new Error('ToolRequest not found')
          const freshData = freshSnap.data()
          if ((freshData.status !== 'claimed' && freshData.status !== 'running') || freshData.claimedBy !== this.workerId) {
            resultRejected = true
            throw new Error('Lease expired or claimed by another worker')
          }
          transaction.update(docRef, {
            status: 'failed',
            error: execErr.message || String(execErr)
          })
        })

        if (resultRejected) {
          console.warn(`[Worker] Result rejected for request ${requestId}: lease expired.`)
          await this.writeEvent('tool.result_rejected', { requestId, workerId: this.workerId })
          return
        }

        await this.writeEvent('tool.failed', { requestId })
      }

    } catch (err: any) {
      console.log(`[Worker] Lease bypass or claim failed for request ${requestId}: ${err.message}`)
    }
  }

  private async executeTool(tool: string, args: any, requestId: string): Promise<any> {
    const resolvedRoot = resolve(this.workspaceRoot)

    switch (tool) {
      case 'list_files': {
        const files: string[] = []
        const traverse = (dir: string) => {
          if (!existsSync(dir)) return
          const items = readdirSync(dir)
          for (const item of items) {
            if (item === 'node_modules' || item === '.git' || item === '.hermes' || item === '.test_workspace' || item === '.test_worker_sandbox') {
              continue
            }
            const fullPath = join(dir, item)
            const stat = statSync(fullPath)
            if (stat.isDirectory()) {
              traverse(fullPath)
            } else {
              files.push(relative(resolvedRoot, fullPath))
            }
          }
        }
        traverse(resolvedRoot)
        return files.slice(0, SAFETY_LIMITS.maxFilesRead)
      }

      case 'read_file': {
        const filePath = resolve(resolvedRoot, args.path)
        if (!filePath.startsWith(resolvedRoot)) {
          throw new Error(`Security Violation: Path ${args.path} escapes workspace root.`)
        }
        if (!existsSync(filePath)) {
          throw new Error(`File not found: ${args.path}`)
        }
        const content = readFileSync(filePath, 'utf8')
        return content.length > SAFETY_LIMITS.maxOutputBytes 
          ? content.slice(0, SAFETY_LIMITS.maxOutputBytes) + '\n... [truncated]'
          : content
      }

      case 'git_diff': {
        try {
          const diff = execSync('git diff', { cwd: resolvedRoot, stdio: ['ignore', 'pipe', 'ignore'], timeout: 10000 }).toString()
          return diff || 'No active changes in repository.'
        } catch {
          return 'Workspace is not a git repository or git command failed.'
        }
      }

      case 'run_tests': {
        try {
          const out = execSync('npx vitest run --passWithNoTests', { 
            cwd: resolvedRoot, 
            stdio: ['ignore', 'pipe', 'pipe'], 
            timeout: SAFETY_LIMITS.maxCommandSeconds * 1000 
          }).toString()
          return out.length > SAFETY_LIMITS.maxOutputBytes 
            ? out.slice(0, SAFETY_LIMITS.maxOutputBytes) + '\n... [truncated]'
            : out
        } catch (e: any) {
          throw new Error(`Tests failed: ${e.stdout?.toString() || e.message || String(e)}`)
        }
      }

      case 'write_file': {
        const filePath = resolve(resolvedRoot, args.path)
        if (!filePath.startsWith(resolvedRoot)) {
          throw new Error(`Security Violation: Path ${args.path} escapes workspace root.`)
        }
        writeFileSync(filePath, args.content || '', 'utf8')
        return `Successfully wrote content to ${args.path}`
      }

      case 'apply_patch': {
        const patchResult = executePatchLocally(resolvedRoot, [{ path: args.path || 'patch.diff', diff: args.patch }], requestId, `app-${requestId}`)
        if (!patchResult.success) {
          throw new Error(patchResult.error || 'Failed to apply patch.')
        }
        return `Successfully applied patch. Files changed: ${patchResult.filesChanged.join(', ')}`
      }

      case 'run_command': {
        const command = args.command || ''
        if (!applyCommandPolicy(command, resolvedRoot)) {
          throw new Error(`Security Violation: Command violates local safety policy.`)
        }
        try {
          const out = execSync(command, { 
            cwd: resolvedRoot, 
            stdio: ['ignore', 'pipe', 'pipe'], 
            timeout: SAFETY_LIMITS.maxCommandSeconds * 1000 
          }).toString()
          return out.length > SAFETY_LIMITS.maxOutputBytes 
            ? out.slice(0, SAFETY_LIMITS.maxOutputBytes) + '\n... [truncated]'
            : out
        } catch (e: any) {
          throw new Error(`Command failed: ${e.stderr?.toString() || e.stdout?.toString() || e.message || String(e)}`)
        }
      }

      default:
        throw new Error(`Unknown or unsupported tool '${tool}' in worker.`)
    }
  }

  private async writeEvent(type: string, payload: any) {
    const eventId = `ev-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`
    const eventRef = doc(this.db, 'sessions', this.sessionId, 'events', eventId)
    await setDoc(eventRef, {
      eventId,
      sessionId: this.sessionId,
      type,
      source: 'local-client',
      createdAt: serverTimestamp(),
      payload
    })
  }
}

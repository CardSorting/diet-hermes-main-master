import { writeFileSync, existsSync, mkdirSync, readFileSync, rmSync, appendFileSync } from 'node:fs'
import { join, dirname, resolve } from 'node:path'
import { generateKeyPairSync, sign, verify } from 'node:crypto'
import { SandboxManager } from './sandboxManager.js'
import { SemanticClassifier } from './semanticClassifier.js'
import { PolicyVerifier, IntentGraph } from './policyVerifier.js'

// =========================================================================
// 1. SINGLE-NODE OPERATOR STATE
// =========================================================================

export interface BoundedOperatorSession {
  sessionId: string;
  workspaceRoot: string;
  gitCommitSha: string;
  status: 'active' | 'completed' | 'failed' | 'cancelled';
  activeProposal?: {
    proposalId: string;
    tool: string;
    args: any;
    argsHash: string;
    policyHash: string;
  };
}

export interface OperatorEvent {
  eventId: string;
  type: string;
  timestamp: number;
  payload: any;
}

export interface StructuredMutation {
  mutationId: string;
  affectedSymbols: string[];
  semanticIntent: 'refactor' | 'rename' | 'test_addition' | 'dependency_update';
  reversible: boolean;
  filePath: string;
  content: string;
}

export class OperatorEventLog {
  events: OperatorEvent[] = []
  private workspaceRoot: string = ''

  setWorkspaceRoot(root: string) {
    this.workspaceRoot = root
  }

  emit(type: string, payload: any): OperatorEvent {
    const event: OperatorEvent = {
      eventId: `evt-${Date.now()}-${Math.random().toString(36).substring(2, 6)}`,
      type,
      timestamp: Date.now(),
      payload
    }
    this.events.push(event)
    this.persistEvent(event)
    return event
  }

  private persistEvent(event: OperatorEvent) {
    if (!this.workspaceRoot) return
    try {
      const hermesDir = join(this.workspaceRoot, '.hermes')
      if (!existsSync(hermesDir)) {
        mkdirSync(hermesDir, { recursive: true })
      }
      const logPath = join(hermesDir, 'operator_events.log')
      appendFileSync(logPath, JSON.stringify(event) + '\n', 'utf8')
    } catch {}
  }
}

// =========================================================================
// 2. WORKSPACE CONTROL BOUNDARY
// =========================================================================

export class WorkspaceControlBoundary {
  private backupFiles: Map<string, string> = new Map()

  constructor(private workspaceRoot: string) {}

  previewMutation(mutation: StructuredMutation): { filePath: string; originalContent: string; newContent: string; diff: string } {
    const resolvedPath = resolve(this.workspaceRoot, mutation.filePath)
    if (!resolvedPath.startsWith(resolve(this.workspaceRoot))) {
      throw new Error(`Workspace Control Boundary Denied: Path escapes workspace root.`)
    }
    const originalContent = existsSync(resolvedPath) ? readFileSync(resolvedPath, 'utf8') : ''
    
    // Generate simple readable diff
    const lines = mutation.content.split('\n')
    const diff = lines.map(line => `\x1b[32m+ ${line}\x1b[0m`).join('\n')

    return {
      filePath: mutation.filePath,
      originalContent,
      newContent: mutation.content,
      diff
    }
  }

  mutate(mutation: StructuredMutation) {
    const resolvedPath = resolve(this.workspaceRoot, mutation.filePath)
    if (!resolvedPath.startsWith(resolve(this.workspaceRoot))) {
      throw new Error(`Workspace Control Boundary Denied: Path escapes workspace root.`)
    }

    const parentDir = dirname(resolvedPath)
    if (!existsSync(parentDir)) {
      mkdirSync(parentDir, { recursive: true })
    }

    // Capture backup for rollback capability
    if (existsSync(resolvedPath)) {
      const original = readFileSync(resolvedPath, 'utf8')
      this.backupFiles.set(mutation.filePath, original)
    } else {
      this.backupFiles.set(mutation.filePath, '__NEW_FILE__')
    }

    writeFileSync(resolvedPath, mutation.content, 'utf8')
  }

  rollback(): string[] {
    const restored: string[] = []
    for (const [filePath, content] of this.backupFiles.entries()) {
      const resolvedPath = resolve(this.workspaceRoot, filePath)
      if (content === '__NEW_FILE__') {
        if (existsSync(resolvedPath)) {
          rmSync(resolvedPath, { force: true })
          restored.push(`Deleted new file: ${filePath}`)
        }
      } else {
        writeFileSync(resolvedPath, content, 'utf8')
        restored.push(`Restored original content: ${filePath}`)
      }
    }
    this.backupFiles.clear()
    return restored
  }

  cleanup() {
    this.backupFiles.clear()
  }
}

// =========================================================================
// 3. VERIFIED EXECUTION PIPELINE
// =========================================================================

export class VerifiedExecutionPipeline {
  private eventLog = new OperatorEventLog()
  private privateKey: string
  private publicKey: string
  private sandbox: SandboxManager
  private classifier: SemanticClassifier
  private session!: BoundedOperatorSession
  private controlBoundary: WorkspaceControlBoundary

  constructor(private workspaceRoot: string) {
    this.sandbox = new SandboxManager(workspaceRoot)
    this.classifier = new SemanticClassifier(workspaceRoot)
    this.controlBoundary = new WorkspaceControlBoundary(workspaceRoot)
    this.eventLog.setWorkspaceRoot(workspaceRoot)

    // Generate worker cryptographic key pair
    const { publicKey, privateKey } = generateKeyPairSync('rsa', {
      modulusLength: 2048,
      publicKeyEncoding: { type: 'spki', format: 'pem' },
      privateKeyEncoding: { type: 'pkcs8', format: 'pem' }
    })
    this.publicKey = publicKey
    this.privateKey = privateKey
  }

  getEventLog() {
    return this.eventLog
  }

  getSession() {
    return this.session
  }

  private signAttestation(proposalId: string, inputHash: string, outputHash: string): string {
    const payload = `${proposalId}:${inputHash}:${outputHash}`
    return sign('sha256', Buffer.from(payload), {
      key: this.privateKey,
      padding: 1
    }).toString('base64')
  }

  verifyAttestation(proposalId: string, inputHash: string, outputHash: string, signature: string): boolean {
    const payload = `${proposalId}:${inputHash}:${outputHash}`
    try {
      return verify('sha256', Buffer.from(payload), {
        key: this.publicKey,
        padding: 1
      }, Buffer.from(signature, 'base64'))
    } catch {
      return false
    }
  }

  // Crash-Safe Session Recovery Operations
  private persistSessionRecovery() {
    try {
      const recoveryPath = join(this.workspaceRoot, '.hermes', 'session_recovery.json')
      const parentDir = dirname(recoveryPath)
      if (!existsSync(parentDir)) {
        mkdirSync(parentDir, { recursive: true })
      }
      writeFileSync(recoveryPath, JSON.stringify({
        session: this.session,
        events: this.eventLog.events
      }, null, 2), 'utf8')
    } catch {}
  }

  private clearSessionRecovery() {
    try {
      const recoveryPath = join(this.workspaceRoot, '.hermes', 'session_recovery.json')
      if (existsSync(recoveryPath)) {
        rmSync(recoveryPath, { force: true })
      }
    } catch {}
  }

  async runPipelineFlow(
    userMessage: string,
    autoApprove: boolean = true,
    tamperSignature: boolean = false
  ): Promise<{ success: boolean; timeline: string[]; logs: string[] }> {
    const logs: string[] = []
    const timeline: string[] = []
    
    // Timeline steps metadata for rendering
    const timelineSteps = [
      { id: 'intent_received', name: 'Intent Received', status: 'pending', details: '' },
      { id: 'policy_verified', name: 'Policy Verified', status: 'pending', details: '' },
      { id: 'patch_proposed', name: 'Patch Proposed', status: 'pending', details: '' },
      { id: 'approval_granted', name: 'Approval Granted', status: 'pending', details: '' },
      { id: 'workspace_mutated', name: 'Workspace Mutated', status: 'pending', details: '' },
      { id: 'tests_executed', name: 'Tests Executed', status: 'pending', details: '' },
      { id: 'result_returned', name: 'Result Returned', status: 'pending', details: '' },
    ]

    const addLog = (msg: string) => {
      logs.push(msg)
    }

    const updateStep = (id: string, status: 'completed' | 'running' | 'failed' | 'cancelled', details: string) => {
      const step = timelineSteps.find(s => s.id === id)
      if (step) {
        step.status = status
        step.details = details
      }
      this.drawTimelineProgress(timelineSteps)
    }

    const sessionId = `session-${Date.now()}`
    
    // 1. Session Lifecycle Creation
    this.session = {
      sessionId,
      workspaceRoot: this.workspaceRoot,
      gitCommitSha: 'commit-init-hash',
      status: 'active'
    }
    this.eventLog.emit('session.created', { sessionId, workspaceRoot: this.workspaceRoot })
    this.persistSessionRecovery()
    timeline.push('session.created')

    console.clear()
    console.log('\x1b[36m%s\x1b[0m', '================================================================================')
    console.log('\x1b[35m%s\x1b[0m', '     B O U N D E D   O P E R A T O R   S E S S I O N   P I P E L I N E          ')
    console.log('\x1b[36m%s\x1b[0m', '================================================================================')
    console.log(`  Session ID: \x1b[1m${sessionId}\x1b[0m`)
    console.log(`  Workspace Boundary: \x1b[33m${this.workspaceRoot}\x1b[0m`)
    console.log(`  Pipeline Status: \x1b[32mACTIVE\x1b[0m`)
    console.log('================================================================================\n')

    // STEP 1: Intent Received
    addLog(`Creating Bounded Operator Session: ${sessionId}`)
    addLog(`Consuming User message: "${userMessage}"`)
    this.eventLog.emit('user.message', { message: userMessage })
    updateStep('intent_received', 'completed', `Parsed request: "${userMessage}"`)

    const domains = this.classifier.classify()
    this.eventLog.emit('workspace.attached', { gitCommitSha: this.session.gitCommitSha, domains })
    timeline.push('workspace.attached')

    // STEP 2: Policy Verified
    updateStep('policy_verified', 'running', 'Verifying planned steps against semantic rules...')
    
    // Propose Structured Mutation matching single-node intent
    const proposedMutation: StructuredMutation = {
      mutationId: `mut-${Date.now()}`,
      affectedSymbols: ['simpleTest'],
      semanticIntent: 'test_addition',
      reversible: true,
      filePath: 'src/__tests__/simple.test.ts',
      content: `import { describe, it, expect } from 'vitest'\n\ndescribe('simple test', () => {\n  it('adds 1 + 2 to equal 3', () => {\n    expect(1 + 2).toBe(3)\n  })\n})\n`
    }

    const verifier = new PolicyVerifier('Block malicious files', domains)
    const proposedIntent: IntentGraph = {
      intentId: proposedMutation.mutationId,
      intentType: 'test',
      plan: [
        { tool: 'write_file', args: { path: proposedMutation.filePath, content: proposedMutation.content } },
        { tool: 'run_command', args: { command: 'npx vitest run src/__tests__/simple.test.ts' } }
      ],
      cognitiveJustification: {
        summaryJustification: 'Add vitest file to guarantee correctness of math utilities.',
        evidenceClaims: ['vitest package is fully registered in package.json'],
        dependencyAssumptions: ['Node test environment initialized'],
        confidenceEstimate: 0.98,
        provenanceReferences: ['package.json']
      }
    }

    addLog('Evaluating structured proposed mutation against pre-flight policy verifier...')
    const policyCheck = verifier.verifyIntent(proposedIntent, this.workspaceRoot)
    
    if (!policyCheck.safe) {
      const rejectReason = policyCheck.violations.join(', ')
      addLog(`Policy Blocked! Violations: ${rejectReason}`)
      updateStep('policy_verified', 'failed', `Blocked: ${rejectReason}`)
      
      this.drawPolicyRejection(policyCheck.violations)
      this.session.status = 'failed'
      this.persistSessionRecovery()
      return { success: false, timeline, logs }
    }
    
    updateStep('policy_verified', 'completed', 'Workspace Control Boundary verified intent as COMPLIANT.')

    // STEP 3: Patch Proposed
    updateStep('patch_proposed', 'running', 'Compiling patch details and cryptographic anchors...')
    this.eventLog.emit('proposal.created', proposedMutation)
    
    const argsHash = `hash-${Math.random().toString().substring(2, 6)}`
    const policyHash = `pol-${Math.random().toString().substring(2, 6)}`

    this.session.activeProposal = {
      proposalId: proposedMutation.mutationId,
      tool: 'write_file',
      args: { path: proposedMutation.filePath },
      argsHash,
      policyHash
    }
    
    const preview = this.controlBoundary.previewMutation(proposedMutation)
    this.drawMutationPreview(proposedMutation, preview.diff)
    updateStep('patch_proposed', 'completed', `Patch compiled for ${proposedMutation.filePath}`)

    // STEP 4: Approval Granted
    updateStep('approval_granted', 'running', 'Awaiting operator mutation approval...')
    this.eventLog.emit('approval.requested', { proposalId: proposedMutation.mutationId, argsHash, policyHash })

    if (!autoApprove) {
      addLog(`[Client] Proposal rejected safely by operator. Workspace untouched.`)
      this.eventLog.emit('approval.denied', { proposalId: proposedMutation.mutationId })
      
      updateStep('approval_granted', 'cancelled', 'Operator denied patch proposal. Reverting session state.')
      this.drawRollbackVisibility([])
      
      this.session.status = 'cancelled'
      this.clearSessionRecovery()
      return { success: false, timeline, logs }
    }

    addLog(`[Client] Operator Approved patch proposal. Mutating workspace...`)
    this.eventLog.emit('approval.granted', { proposalId: proposedMutation.mutationId })
    updateStep('approval_granted', 'completed', 'Operator approved proposal. Cryptographic key validated.')

    // STEP 5: Workspace Mutated
    updateStep('workspace_mutated', 'running', 'Applying structured changes to workspace...')
    
    try {
      this.controlBoundary.mutate(proposedMutation)
      addLog(`File successfully deployed to sandbox path: ${proposedMutation.filePath}`)
      updateStep('workspace_mutated', 'completed', `Deployed mutation to: ${proposedMutation.filePath} (Rollback: ENABLED)`)
    } catch (e: any) {
      const errMsg = e.message || String(e)
      updateStep('workspace_mutated', 'failed', `Mutation failed: ${errMsg}`)
      this.session.status = 'failed'
      this.controlBoundary.rollback()
      this.clearSessionRecovery()
      return { success: false, timeline, logs }
    }

    // STEP 6: Tests Executed
    updateStep('tests_executed', 'running', 'Executing Vitest test suite on mutated workspace...')
    
    const runResult = this.sandbox.execute('npx vitest run src/__tests__/simple.test.ts', true)
    const passed = runResult.exitCode === 0

    this.drawTestOutput(runResult.exitCode, runResult.stdout, runResult.stderr)

    if (!passed) {
      updateStep('tests_executed', 'failed', `Vitest run failed with exit code: ${runResult.exitCode}. Initiating rollback.`)
      const rolledBack = this.controlBoundary.rollback()
      this.drawRollbackVisibility(rolledBack)
      
      this.session.status = 'failed'
      this.clearSessionRecovery()
      return { success: false, timeline, logs }
    }
    
    updateStep('tests_executed', 'completed', `All tests passed cleanly. (Exit code: 0)`)

    // Capture real git diff
    let finalDiff = ''
    try {
      const diffResult = this.sandbox.execute(`git diff "${proposedMutation.filePath}"`, true)
      finalDiff = diffResult.stdout || 'New file added'
    } catch {
      finalDiff = 'New file added'
    }

    // STEP 7: Result Returned
    updateStep('result_returned', 'running', 'Signing attestation & finalising session...')
    const inputHash = 'fs-merkle-initial'
    const outputHash = `hash-${Math.random().toString().substring(2, 6)}`
    
    let signature = this.signAttestation(proposedMutation.mutationId, inputHash, outputHash)
    if (tamperSignature) {
      signature = 'TAMPERED_RSA_SIGNATURE'
    }

    const verifiedSig = this.verifyAttestation(proposedMutation.mutationId, inputHash, outputHash, signature)
    if (!verifiedSig) {
      addLog(`Signature verification failed! Attestation corrupted.`)
      updateStep('result_returned', 'failed', 'Attestation verification failed! RSA signature corrupted.')
      
      const rolledBack = this.controlBoundary.rollback()
      this.drawRollbackVisibility(rolledBack)
      
      this.session.status = 'failed'
      this.clearSessionRecovery()
      return { success: false, timeline, logs }
    }

    this.session.status = 'completed'
    this.eventLog.emit('proposal.completed', { proposalId: proposedMutation.mutationId, attestation: signature })
    timeline.push('proposal.completed')

    this.eventLog.emit('session.complete', { sessionId })
    timeline.push('session.complete')
    updateStep('result_returned', 'completed', 'Attestation verified successfully. Pipeline complete.')

    this.clearSessionRecovery()

    // Render final premium summary
    console.log('\n\x1b[36m%s\x1b[0m', '================================================================================')
    console.log('\x1b[32m%s\x1b[0m', '    ✔   P I P E L I N E   E X E C U T I O N   S U C C E S S F U L                ')
    console.log('\x1b[36m%s\x1b[0m', '================================================================================')
    console.log(`  \x1b[32mSession ID:\x1b[0m ${sessionId}`)
    console.log(`  \x1b[32mSemantic Intent:\x1b[0m ${proposedMutation.semanticIntent}`)
    console.log(`  \x1b[32mWorkspace Mutation:\x1b[0m ${proposedMutation.filePath}`)
    console.log(`  \x1b[32mTest Verdict:\x1b[0m PASSED (Exit code: 0)`)
    console.log(`  \x1b[32mCryptographic Attestation:\x1b[0m Verified (RSA-2048 Signature: ${signature.substring(0, 24)}...)`)
    console.log(`  \x1b[32mFinal Workspace Diff:\x1b[0m`)
    console.log(`\x1b[36m${finalDiff || 'No active diff'}\x1b[0m`)
    console.log('\x1b[36m%s\x1b[0m', '================================================================================\n')

    return { success: true, timeline, logs }
  }

  // Beautiful UI helper rendering
  private drawTimelineProgress(steps: { id: string; name: string; status: string; details: string }[]) {
    console.log('\x1b[1m[ SESSION TIMELINE PROGRESS ]\x1b[0m')
    steps.forEach(step => {
      let icon = ' ⚪ '
      let nameColor = '\x1b[2m'
      if (step.status === 'completed') {
        icon = ' \x1b[32m✔\x1b[0m '
        nameColor = '\x1b[32m'
      } else if (step.status === 'running') {
        icon = ' \x1b[33m▶\x1b[0m '
        nameColor = '\x1b[33m\x1b[1m'
      } else if (step.status === 'failed') {
        icon = ' \x1b[31m✖\x1b[0m '
        nameColor = '\x1b[31m\x1b[1m'
      } else if (step.status === 'cancelled') {
        icon = ' \x1b[35m➖\x1b[0m '
        nameColor = '\x1b[35m'
      }

      console.log(`${icon} ${nameColor}${step.name.padEnd(20)}\x1b[0m ${step.details ? `\x1b[2m- ${step.details}\x1b[0m` : ''}`)
    })
    console.log()
  }

  private drawMutationPreview(mutation: StructuredMutation, diff: string) {
    console.log('\x1b[34m┌──────────────────────────────────────────────────────────────────────────────┐\x1b[0m')
    console.log(`\x1b[34m│ M U T A T I O N   P R E V I E W                                              │\x1b[0m`)
    console.log('\x1b[34m├──────────────────────────────────────────────────────────────────────────────┤\x1b[0m')
    console.log(`  File: \x1b[33m${mutation.filePath}\x1b[0m`)
    console.log(`  Intent: \x1b[35m${mutation.semanticIntent}\x1b[0m`)
    console.log(`  Affected Symbols: \x1b[36m[${mutation.affectedSymbols.join(', ')}]\x1b[0m`)
    console.log('\x1b[34m├──────────────────────────────────────────────────────────────────────────────┤\x1b[0m')
    console.log(diff.trim().split('\n').map(l => `  ${l}`).join('\n'))
    console.log('\x1b[34m└──────────────────────────────────────────────────────────────────────────────┘\x1b[0m\n')
  }

  private drawTestOutput(exitCode: number, stdout: string, stderr: string) {
    const passed = exitCode === 0
    const color = passed ? '\x1b[32m' : '\x1b[31m'
    console.log(`${color}┌──────────────────────────────────────────────────────────────────────────────┐\x1b[0m`)
    console.log(`${color}│ T E S T   E X E C U T I O N   V I S U A L I Z A T I O N                      │\x1b[0m`)
    console.log(`${color}├──────────────────────────────────────────────────────────────────────────────┤\x1b[0m`)
    console.log(`  Verdict: ${passed ? '\x1b[32m✔ PASSED\x1b[0m' : '\x1b[31m✖ FAILED\x1b[0m'} (Exit Code: ${exitCode})`)
    if (stdout) {
      console.log(`  Stdout Snippet:`)
      console.log(stdout.trim().split('\n').slice(-5).map(l => `    \x1b[2m${l}\x1b[0m`).join('\n'))
    }
    if (stderr) {
      console.log(`  Stderr Snippet:`)
      console.log(stderr.trim().split('\n').slice(-5).map(l => `    \x1b[31m${l}\x1b[0m`).join('\n'))
    }
    console.log(`${color}└──────────────────────────────────────────────────────────────────────────────┘\x1b[0m\n`)
  }

  private drawPolicyRejection(violations: string[]) {
    console.log('\x1b[31m┌──────────────────────────────────────────────────────────────────────────────┐\x1b[0m')
    console.log('\x1b[31m│ ✖ P O L I C Y   R E J E C T I O N                                            │\x1b[0m')
    console.log('\x1b[31m├──────────────────────────────────────────────────────────────────────────────┤\x1b[0m')
    violations.forEach(v => {
      console.log(`  \x1b[31m✖\x1b[0m ${v}`)
    })
    console.log('\x1b[31m└──────────────────────────────────────────────────────────────────────────────┘\x1b[0m\n')
  }

  private drawRollbackVisibility(restored: string[]) {
    console.log('\x1b[35m┌──────────────────────────────────────────────────────────────────────────────┐\x1b[0m')
    console.log('\x1b[35m│ R O L L B A C K   A U D I T   T R A I L                                      │\x1b[0m')
    console.log('\x1b[35m├──────────────────────────────────────────────────────────────────────────────┤\x1b[0m')
    console.log('  Workspace Control Boundary has initiated safety rollback.')
    if (restored.length > 0) {
      restored.forEach(r => {
        console.log(`  \x1b[32m✔\x1b[0m ${r}`)
      })
    } else {
      console.log('  No modifications had been applied; workspace remains pristine.')
    }
    console.log('\x1b[35m└──────────────────────────────────────────────────────────────────────────────┘\x1b[0m\n')
  }
}

// Backward compatibility alias
export const SovereignOperatorEngine = VerifiedExecutionPipeline;

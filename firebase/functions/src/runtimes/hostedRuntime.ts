import * as admin from 'firebase-admin'
import { SessionEventRepository, SessionEvent, ToolRequest, SAFETY_LIMITS, computeArgsHash, RuntimeIntent, ToolPlanItem, SessionBranch } from './hostedEvents.js'

export class HostedHermesRuntime {
  private repo: SessionEventRepository

  constructor(private db: admin.firestore.Firestore) {
    this.repo = new SessionEventRepository(db)
  }

  // Evolve: Timeline Branching & Speculative Execution
  async branchSession(parentSessionId: string, forkedFromJournalId: string): Promise<string> {
    const branchId = `session-fork-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`
    console.log(`[HostedRuntime] Branching session: ${parentSessionId} from Journal: ${forkedFromJournalId} -> ${branchId}`)
    
    // 1. Fetch parent session data & snapshots
    const parentSnap = await this.db.collection('sessions').doc(parentSessionId).get()
    const parentData = parentSnap.data() || {}

    const journalSnap = await this.db.collection('sessions').doc(parentSessionId).collection('journals').doc(forkedFromJournalId).get()
    const journal = journalSnap.data()

    const targetUniverseId = journal?.universeId || `univ-${branchId}`
    const branch: SessionBranch = {
      branchId,
      parentSessionId,
      forkedFromJournalId,
      targetUniverseId,
      createdAt: Date.now()
    }

    // 2. Initialize speculative child session
    await this.db.collection('sessions').doc(branchId).set({
      ...parentData,
      sessionId: branchId,
      parentSessionId,
      workspaceSnapshot: parentData.workspaceSnapshot,
      createdAt: admin.firestore.FieldValue.serverTimestamp()
    })

    // 3. Inject speculative branched events timeline
    const branchRepo = new SessionEventRepository(this.db)
    await branchRepo.appendEvent(branchId, 'session.created', 'remote-runtime')
    await branchRepo.appendEvent(branchId, 'session.branched', 'remote-runtime', {
      branchId,
      parentSessionId,
      forkedFromJournalId,
      targetUniverseId
    })

    await this.repo.createSessionBranch(parentSessionId, branch)
    return branchId
  }

  async runStep(sessionId: string): Promise<void> {
    console.log(`[HostedRuntime] Processing session: ${sessionId}`)
    
    // 1. Perform transactional lease and approval expiration recovery first
    await this.recoverLeasesAndApprovals(sessionId)

    const events = await this.repo.getEvents(sessionId)
    if (events.length === 0) {
      console.log(`[HostedRuntime] Session ${sessionId} has no events.`)
      return
    }

    // 2. Verify safety limits and terminal states
    const isTerminal = events.some(e => 
      e.type === 'session.complete' || 
      e.type === 'session.failed' || 
      e.type === 'session.cancelled' || 
      e.type === 'session.max_steps_exceeded'
    )
    if (isTerminal) {
      console.log(`[HostedRuntime] Session ${sessionId} is in a terminal state. Skipping.`)
      return
    }

    // Check steps and tool requests count
    const steps = events.filter(e => e.type === 'runtime.thinking').length
    const requests = await this.repo.getToolRequests(sessionId)
    const toolRequests = requests.length

    if (steps >= SAFETY_LIMITS.maxRuntimeSteps || toolRequests >= SAFETY_LIMITS.maxToolRequests) {
      console.warn(`[HostedRuntime] Safety limits exceeded for session ${sessionId}. Steps: ${steps}, Tool Requests: ${toolRequests}`)
      await this.repo.appendEvent(sessionId, 'session.max_steps_exceeded', 'remote-runtime', {
        reason: `Safety limits exceeded. Steps: ${steps}/${SAFETY_LIMITS.maxRuntimeSteps}, Tools: ${toolRequests}/${SAFETY_LIMITS.maxToolRequests}`
      })
      return
    }

    // 3. Fetch workspace snapshot if available to attach provenance
    const sessionSnap = await this.db.collection('sessions').doc(sessionId).get()
    const snapshot = sessionSnap.data()?.workspaceSnapshot

    const lastEvent = events[events.length - 1]
    console.log(`[HostedRuntime] Last event type: ${lastEvent.type}`)

    switch (lastEvent.type) {
      case 'session.created':
        console.log(`[HostedRuntime] Session created. Awaiting user.message...`)
        break

      case 'user.message': {
        const userContent = (lastEvent.payload.content || '').trim().toLowerCase()
        await this.repo.appendEvent(sessionId, 'runtime.thinking', 'remote-runtime', {
          summary: `Analyzing user request: "${lastEvent.payload.content}"`
        })

        // Evolve: Runtime Intent & Deterministic Planning Graph
        let intentType: RuntimeIntent['intentType'] = 'custom'
        let intentSummary = 'Custom interaction plan'
        const plan: ToolPlanItem[] = []

        if (userContent.startsWith('list files')) {
          intentType = 'custom'
          intentSummary = 'Query workspace directory structure'
          plan.push({ step: 1, tool: 'list_files', args: {}, requireApproval: false })
        } else if (userContent.startsWith('read file')) {
          const filePath = userContent.replace('read file', '').trim()
          intentType = 'custom'
          intentSummary = `Read file content from: ${filePath}`
          plan.push({ step: 1, tool: 'read_file', args: { path: filePath }, requireApproval: false })
        } else if (userContent.startsWith('git diff')) {
          intentType = 'custom'
          intentSummary = 'Fetch repository difference logs'
          plan.push({ step: 1, tool: 'git_diff', args: {}, requireApproval: false })
        } else if (userContent.startsWith('run tests')) {
          intentType = 'test'
          intentSummary = 'Execute testing harness suite'
          plan.push({ step: 1, tool: 'run_tests', args: {}, requireApproval: false })
        } else if (userContent.startsWith('write file')) {
          const parts = lastEvent.payload.content.replace(/write file/i, '').trim().split(' ')
          const path = parts[0]
          const content = parts.slice(1).join(' ')
          intentType = 'patch'
          intentSummary = `Deploy structured code changes to: ${path}`
          plan.push({ step: 1, tool: 'write_file', args: { path, content }, requireApproval: true })
        } else if (userContent.startsWith('apply patch')) {
          const patch = lastEvent.payload.content.replace(/apply patch/i, '').trim()
          intentType = 'patch'
          intentSummary = 'Integrate unified workspace diff patch'
          plan.push({ step: 1, tool: 'apply_patch', args: { patch }, requireApproval: true })
        } else if (userContent.startsWith('run command')) {
          const command = lastEvent.payload.content.replace(/run command/i, '').trim()
          intentType = 'custom'
          intentSummary = `Execute command tool: ${command}`
          plan.push({ step: 1, tool: 'run_command', args: { command }, requireApproval: true })
        } else if (userContent === 'cancel') {
          await this.repo.appendEvent(sessionId, 'session.cancelled', 'remote-runtime')
          return
        } else {
          // General answer
          await this.repo.appendEvent(sessionId, 'runtime.message', 'remote-runtime', {
            content: `I received your message: "${lastEvent.payload.content}". Available v0 commands are: list files, read file <path>, git diff, run tests, write file <path> <content>, run command <cmd>.`
          })
          await this.repo.appendEvent(sessionId, 'session.complete', 'remote-runtime')
          return
        }

        // Register RuntimeIntent
        const intent = await this.repo.createRuntimeIntent(sessionId, intentType, intentSummary, plan)
        await this.repo.appendEvent(sessionId, 'intent.created', 'remote-runtime', { intentId: intent.intentId, intentType })
        await this.repo.appendEvent(sessionId, 'intent.planned', 'remote-runtime', { intentId: intent.intentId, plan })

        // Create tool request from first plan step
        const firstStep = plan[0]
        const req = await this.repo.createToolRequest(sessionId, firstStep.tool, firstStep.args, { 
          requireApproval: firstStep.requireApproval,
          workspaceId: snapshot?.workspaceId,
          baseCommitSha: snapshot?.gitCommitSha,
          expectedDirtyState: snapshot?.dirtyState,
          createdByRuntimeStep: steps
        })

        // Emit tool.provenance_attached audit log
        await this.repo.appendEvent(sessionId, 'tool.provenance_attached', 'remote-runtime', {
          requestId: req.requestId,
          workspaceId: snapshot?.workspaceId,
          baseCommitSha: snapshot?.gitCommitSha,
          expectedDirtyState: snapshot?.dirtyState
        })
        
        if (firstStep.requireApproval) {
          await this.repo.appendEvent(sessionId, 'runtime.thinking', 'remote-runtime', {
            summary: `Awaiting user approval for dangerous tool: ${firstStep.tool} (args: ${JSON.stringify(firstStep.args)})`
          })
        }
        break
      }

      case 'approval.granted': {
        const { requestId, argsHash } = lastEvent.payload
        const reqSnap = await this.db.collection('sessions').doc(sessionId).collection('toolRequests').doc(requestId).get()
        
        if (!reqSnap.exists) {
          console.error(`[HostedRuntime] ToolRequest ${requestId} not found for approval.`)
          await this.repo.appendEvent(sessionId, 'session.failed', 'remote-runtime', {
            error: `ToolRequest ${requestId} not found.`
          })
          return
        }

        const reqData = reqSnap.data() as ToolRequest
        if (reqData.argsHash !== argsHash) {
          console.error(`[HostedRuntime] Approval hash mismatch! Target: ${reqData.argsHash}, Received: ${argsHash}`)
          await this.repo.appendEvent(sessionId, 'session.failed', 'remote-runtime', {
            error: `Security Violation: Approval hash mismatch for requestId ${requestId}.`
          })
          return
        }

        console.log(`[HostedRuntime] ToolRequest ${requestId} verified and approved. Waiting for worker lease...`)
        break
      }

      case 'approval.denied': {
        const { requestId } = lastEvent.payload
        await this.repo.appendEvent(sessionId, 'runtime.message', 'remote-runtime', {
          content: `Tool request ${requestId} was denied by the user. Reason: ${lastEvent.payload.reason || 'None'}`
        })
        await this.repo.appendEvent(sessionId, 'session.complete', 'remote-runtime')
        break
      }

      case 'tool.completed': {
        const { requestId } = lastEvent.payload
        const reqSnap = await this.db.collection('sessions').doc(sessionId).collection('toolRequests').doc(requestId).get()
        const reqData = reqSnap.data() as ToolRequest

        await this.repo.appendEvent(sessionId, 'runtime.thinking', 'remote-runtime', {
          summary: `Processing completed tool result for request: ${requestId}`
        })

        await this.repo.appendEvent(sessionId, 'runtime.message', 'remote-runtime', {
          content: `Tool execution completed. Result:\n${typeof reqData.result === 'string' ? reqData.result : JSON.stringify(reqData.result, null, 2)}`
        })
        await this.repo.appendEvent(sessionId, 'session.complete', 'remote-runtime')
        break
      }

      case 'tool.failed': {
        const { requestId } = lastEvent.payload
        const reqSnap = await this.db.collection('sessions').doc(sessionId).collection('toolRequests').doc(requestId).get()
        const reqData = reqSnap.data() as ToolRequest

        await this.repo.appendEvent(sessionId, 'runtime.message', 'remote-runtime', {
          content: `Tool execution failed for request ${requestId}. Error: ${reqData.error}`
        })
        await this.repo.appendEvent(sessionId, 'session.failed', 'remote-runtime', {
          error: `Tool execution failed: ${reqData.error}`
        })
        break
      }

      case 'approval.expired':
      case 'tool.lease_expired':
      case 'tool.retry_scheduled':
      case 'tool.result_rejected':
      case 'tool.claimed':
      case 'workspace.snapshot_created':
      case 'workspace.drift_detected':
      case 'tool.provenance_attached':
      case 'artifact.hash_recorded':
      case 'diff.hash_recorded':
      case 'intent.created':
      case 'intent.planned':
      case 'journal.emitted':
      case 'replay.divergence_detected':
      case 'replay.success':
      case 'universe.created':
      case 'session.branched':
      case 'replay.divergence_classified':
        console.log(`[HostedRuntime] Observability / recovery audit event received: ${lastEvent.type}`)
        break

      default:
        console.log(`[HostedRuntime] Unhandled event type in state machine: ${lastEvent.type}`)
    }
  }

  private async recoverLeasesAndApprovals(sessionId: string): Promise<void> {
    const requestsRef = this.db.collection('sessions').doc(sessionId).collection('toolRequests')
    const snap = await requestsRef.get()

    const now = Date.now()

    for (const doc of snap.docs) {
      const data = doc.data() as ToolRequest
      
      // 1. Approval expiration check
      if (data.status === 'pending_approval' && data.createdAt) {
        const createdMs = data.createdAt.toDate ? data.createdAt.toDate().getTime() : (data.createdAt.seconds * 1000)
        if (now - createdMs > SAFETY_LIMITS.approvalTimeoutMs) {
          console.warn(`[HostedRuntime] Approval request ${doc.id} expired.`)
          await this.db.runTransaction(async (transaction) => {
            transaction.update(doc.ref, { status: 'expired' })
          })
          await this.repo.appendEvent(sessionId, 'approval.expired', 'remote-runtime', { requestId: doc.id })
        }
      }

      // 2. Lease recovery check
      if (data.status === 'claimed' || data.status === 'running') {
        if (data.leaseExpiresAt) {
          const leaseMs = data.leaseExpiresAt.toDate ? data.leaseExpiresAt.toDate().getTime() : (data.leaseExpiresAt.seconds * 1000)
          if (now > leaseMs) {
            console.warn(`[HostedRuntime] Lease for ToolRequest ${doc.id} expired! Attempt count: ${data.attemptCount}/${data.maxAttempts}`)
            
            await this.db.runTransaction(async (transaction) => {
              const freshSnap = await transaction.get(doc.ref)
              const freshData = freshSnap.data() as ToolRequest
              
              if (freshData.status !== 'claimed' && freshData.status !== 'running') {
                return
              }

              const newAttempt = (freshData.attemptCount || 0) + 1
              if (newAttempt < freshData.maxAttempts) {
                // Recover back to approved state
                transaction.update(doc.ref, {
                  status: 'approved',
                  attemptCount: newAttempt,
                  claimedBy: admin.firestore.FieldValue.delete(),
                  claimedAt: admin.firestore.FieldValue.delete(),
                  leaseExpiresAt: admin.firestore.FieldValue.delete()
                })

                // We queue recovery logs to run asynchronously after transaction
                await this.repo.appendEvent(sessionId, 'tool.lease_expired', 'remote-runtime', { requestId: doc.id })
                await this.repo.appendEvent(sessionId, 'tool.retry_scheduled', 'remote-runtime', { 
                  requestId: doc.id, 
                  attemptCount: newAttempt 
                })
              } else {
                // Transition to failed
                transaction.update(doc.ref, {
                  status: 'failed',
                  error: 'Max lease recovery attempts exceeded. Worker failed to execute tool within lease periods.'
                })

                await this.repo.appendEvent(sessionId, 'tool.lease_expired', 'remote-runtime', { requestId: doc.id })
                await this.repo.appendEvent(sessionId, 'tool.failed', 'remote-runtime', { 
                  requestId: doc.id,
                  error: 'Max lease recovery attempts exceeded.'
                })
              }
            })
          }
        }
      }
    }
  }
}

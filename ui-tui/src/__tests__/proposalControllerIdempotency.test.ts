import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { join } from 'node:path'
import { existsSync, rmSync, mkdirSync } from 'node:fs'
import { EventEmitter } from 'node:events'
import { useProposalController, createProposalEventHandler } from '../app/proposalController.js'
import * as state from '../local/state.js'
import * as commandExecutor from '../local/commandExecutor.js'
import * as patchExecutor from '../local/patchExecutor.js'

class MockGateway extends EventEmitter {
  public requests: { method: string, params: any }[] = []
  public db: Record<string, any> = {}

  async request(method: string, params: any) {
    this.requests.push({ method, params })
    
    if (method === 'proposal.get') {
      return this.db[params.id] || {}
    }
    if (method === 'firebase.approval.write') {
      return { success: true, approvalId: 'mock-approval-id' }
    }
    if (method === 'firebase.proposal.updateStatus') {
      if (this.db[params.id]) {
        this.db[params.id].status = params.status
      }
      return { success: true }
    }
    if (method === 'firebase.execution.write') {
      return { success: true }
    }
    return { success: true }
  }
}

describe('Proposal Controller Idempotency', () => {
  const TEST_ROOT = join(import.meta.dirname, '.test_workspace_controller')
  let gw: MockGateway
  let originalCwd: () => string

  beforeEach(() => {
    if (existsSync(TEST_ROOT)) rmSync(TEST_ROOT, { recursive: true, force: true })
    mkdirSync(TEST_ROOT, { recursive: true })
    
    process.env.HERMES_TRANSPORT = 'firebase'
    originalCwd = process.cwd
    process.cwd = () => TEST_ROOT

    gw = new MockGateway()

    vi.spyOn(commandExecutor, 'executeCommandLocally').mockReturnValue({ success: true, stdout: 'mock' })
    vi.spyOn(patchExecutor, 'executePatchLocally').mockReturnValue({ success: true, filesChanged: [] })
  })

  afterEach(() => {
    if (existsSync(TEST_ROOT)) rmSync(TEST_ROOT, { recursive: true, force: true })
    process.cwd = originalCwd
    vi.restoreAllMocks()
    delete process.env.HERMES_TRANSPORT
  })

  it('refuses execution if completed in Firestore', async () => {
    gw.db['prop-completed'] = { proposalId: 'prop-completed', status: 'completed' }
    
    let activeProp: any = null
    const handler = createProposalEventHandler(gw as any, activeProp, (p) => { activeProp = p })

    // Simulate incoming approval request
    await handler({ type: 'firebase.approval.request', payload: { proposalId: 'prop-completed' } })
    
    // Should NOT have set the active proposal because it's completed
    expect(activeProp).toBeNull()
  })

  it('refuses execution if denied in Firestore', async () => {
    gw.db['prop-denied'] = { proposalId: 'prop-denied', status: 'denied' }
    
    let activeProp: any = null
    const handler = createProposalEventHandler(gw as any, activeProp, (p) => { activeProp = p })

    await handler({ type: 'firebase.approval.request', payload: { proposalId: 'prop-denied' } })
    expect(activeProp).toBeNull()
  })

  it('replayed approval does not execute twice during same session', async () => {
    gw.db['prop-1'] = { proposalId: 'prop-1', status: 'pending_approval', type: 'proposal.command', command: 'echo 1' }
    
    let activeProp: any = null
    let handler = createProposalEventHandler(gw as any, null, (p) => { activeProp = p })
    
    await handler({ type: 'firebase.approval.request', payload: { proposalId: 'prop-1' } })
    expect(activeProp).not.toBeNull()

    // Provide the active proposal to the next call to simulate React state
    handler = createProposalEventHandler(gw as any, activeProp, (p) => { activeProp = p })
    await handler({ type: 'firebase.approval.decision', payload: { choice: 'approve' } })

    expect(commandExecutor.executeCommandLocally).toHaveBeenCalledTimes(1)
    
    // Replay the decision event
    await handler({ type: 'firebase.approval.decision', payload: { choice: 'approve' } })
    
    // Should STILL be 1, because activeProposal was nullified or state checked
    expect(commandExecutor.executeCommandLocally).toHaveBeenCalledTimes(1)
  })

  it('restart + replay does not execute twice due to state.json', async () => {
    gw.db['prop-2'] = { proposalId: 'prop-2', status: 'pending_approval', type: 'proposal.command', command: 'echo 1' }
    
    // Mark as executed locally
    state.markProposalExecuted(TEST_ROOT, 'prop-2')

    let activeProp: any = null
    const handler = createProposalEventHandler(gw as any, activeProp, (p) => { activeProp = p })

    // If a request comes in, it should be ignored entirely
    await handler({ type: 'firebase.approval.request', payload: { proposalId: 'prop-2' } })
    expect(activeProp).toBeNull()
  })

  it('denied proposal refuses execution and marks local state', async () => {
    gw.db['prop-deny'] = { proposalId: 'prop-deny', status: 'pending_approval', type: 'proposal.command', command: 'echo 1' }
    
    let activeProp: any = null
    let handler = createProposalEventHandler(gw as any, null, (p) => { activeProp = p })
    await handler({ type: 'firebase.approval.request', payload: { proposalId: 'prop-deny' } })
    
    handler = createProposalEventHandler(gw as any, activeProp, (p) => { activeProp = p })
    await handler({ type: 'firebase.approval.decision', payload: { choice: 'deny' } })

    expect(commandExecutor.executeCommandLocally).not.toHaveBeenCalled()
    expect(state.isProposalExecuted(TEST_ROOT, 'prop-deny')).toBe(true) // local memory prevents future
    expect(gw.db['prop-deny'].status).toBe('denied')
  })
})

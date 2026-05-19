import { describe, expect, it, vi, beforeEach } from 'vitest'
import { HostedHermesRuntime } from '../runtimes/hostedRuntime.js'
import { SAFETY_LIMITS, computeArgsHash } from '../runtimes/hostedEvents.js'

const mocks = vi.hoisted(() => {
  const mockAdd = vi.fn()
  const mockSet = vi.fn()
  const mockGet = vi.fn()
  const mockDoc = vi.fn()
  const mockCollection = vi.fn()

  mockCollection.mockReturnValue({
    doc: mockDoc,
    add: mockAdd,
    get: mockGet,
    orderBy: vi.fn().mockReturnThis(),
  })

  mockDoc.mockReturnValue({
    collection: mockCollection,
    get: mockGet,
    set: mockSet,
  })

  return { mockAdd, mockSet, mockGet, mockDoc, mockCollection }
})

vi.mock('firebase-admin', () => {
  return {
    default: {
      firestore: Object.assign(() => ({
        collection: mocks.mockCollection
      }), {
        FieldValue: {
          serverTimestamp: () => 'mock-timestamp',
          delete: () => 'mock-delete'
        }
      })
    },
    firestore: Object.assign(() => ({
      collection: mocks.mockCollection
    }), {
      FieldValue: {
        serverTimestamp: () => 'mock-timestamp',
        delete: () => 'mock-delete'
      }
    })
  }
})

describe('HostedHermesRuntime', () => {
  let runtime: HostedHermesRuntime
  let db: any

  beforeEach(() => {
    vi.clearAllMocks()
    db = {
      collection: mocks.mockCollection
    } as any
    runtime = new HostedHermesRuntime(db)
  })

  const createEventsSnapshot = (events: any[]) => ({
    docs: events.map(e => ({
      id: e.eventId || 'ev-mock',
      data: () => ({
        ...e,
        createdAt: e.createdAt || { seconds: Date.now() / 1000 }
      })
    }))
  })

  it('routes "list files" user prompt directly to approved ToolRequest', async () => {
    const events = [
      { type: 'session.created', source: 'local-client' },
      { type: 'user.message', source: 'local-client', payload: { content: 'list files' } }
    ]
    mocks.mockGet
      .mockResolvedValueOnce({ docs: [] }) // 1. recoverLeasesAndApprovals
      .mockResolvedValueOnce(createEventsSnapshot(events)) // 2. getEvents
      .mockResolvedValueOnce({ docs: [] }) // 3. getToolRequests
      .mockResolvedValueOnce({ exists: true, data: () => ({}) }) // 4. sessionSnap

    await runtime.runStep('s1')

    // Should write runtime.thinking, RuntimeIntent, intent.created, intent.planned, ToolRequest, then tool.provenance_attached event
    expect(mocks.mockSet).toHaveBeenCalledTimes(6)
    
    // First set is runtime.thinking
    expect(mocks.mockSet).toHaveBeenNthCalledWith(1, expect.objectContaining({
      type: 'runtime.thinking'
    }))

    // Second set is RuntimeIntent inside intents subcollection
    expect(mocks.mockSet).toHaveBeenNthCalledWith(2, expect.objectContaining({
      intentType: 'custom',
      intentSummary: 'Query workspace directory structure'
    }))

    // Third is intent.created event
    expect(mocks.mockSet).toHaveBeenNthCalledWith(3, expect.objectContaining({
      type: 'intent.created'
    }))

    // Fourth is intent.planned event
    expect(mocks.mockSet).toHaveBeenNthCalledWith(4, expect.objectContaining({
      type: 'intent.planned'
    }))

    // Fifth set is ToolRequest inside toolRequests subcollection
    expect(mocks.mockSet).toHaveBeenNthCalledWith(5, expect.objectContaining({
      tool: 'list_files',
      status: 'approved'
    }))
  })

  it('gates "write file" command behind pending_approval ToolRequest', async () => {
    const events = [
      { type: 'session.created', source: 'local-client' },
      { type: 'user.message', source: 'local-client', payload: { content: 'write file test.txt Hello World' } }
    ]
    mocks.mockGet
      .mockResolvedValueOnce({ docs: [] }) // 1. recoverLeasesAndApprovals
      .mockResolvedValueOnce(createEventsSnapshot(events)) // 2. getEvents
      .mockResolvedValueOnce({ docs: [] }) // 3. getToolRequests
      .mockResolvedValueOnce({ exists: true, data: () => ({}) }) // 4. sessionSnap

    await runtime.runStep('s1')

    expect(mocks.mockSet).toHaveBeenCalledTimes(7)

    // First is thinking
    expect(mocks.mockSet).toHaveBeenNthCalledWith(1, expect.objectContaining({
      type: 'runtime.thinking'
    }))

    // Second set is RuntimeIntent inside intents subcollection
    expect(mocks.mockSet).toHaveBeenNthCalledWith(2, expect.objectContaining({
      intentType: 'patch',
      intentSummary: 'Deploy structured code changes to: test.txt'
    }))

    // Third is intent.created event
    expect(mocks.mockSet).toHaveBeenNthCalledWith(3, expect.objectContaining({
      type: 'intent.created'
    }))

    // Fourth is intent.planned event
    expect(mocks.mockSet).toHaveBeenNthCalledWith(4, expect.objectContaining({
      type: 'intent.planned'
    }))

    // Fifth is ToolRequest set (pending_approval)
    expect(mocks.mockSet).toHaveBeenNthCalledWith(5, expect.objectContaining({
      tool: 'write_file',
      status: 'pending_approval',
      args: { path: 'test.txt', content: 'Hello World' }
    }))

    // Sixth is tool.provenance_attached event
    expect(mocks.mockSet).toHaveBeenNthCalledWith(6, expect.objectContaining({
      type: 'tool.provenance_attached'
    }))

    // Seventh is thinking (Awaiting user approval)
    expect(mocks.mockSet).toHaveBeenNthCalledWith(7, expect.objectContaining({
      type: 'runtime.thinking',
      payload: expect.objectContaining({
        summary: expect.stringContaining('Awaiting user approval')
      })
    }))
  })

  it('verifies argsHash matches during approval.granted event', async () => {
    const args = { path: 'test.txt' }
    const hash = computeArgsHash('write_file', args)
    const events = [
      { type: 'session.created', source: 'local-client' },
      { type: 'user.message', source: 'local-client', payload: { content: 'write file test.txt' } },
      { type: 'approval.granted', source: 'local-client', payload: { requestId: 'req-1', argsHash: hash } }
    ]
    
    mocks.mockGet
      .mockResolvedValueOnce({ docs: [] }) // 1. recoverLeasesAndApprovals
      .mockResolvedValueOnce(createEventsSnapshot(events)) // 2. getEvents
      .mockResolvedValueOnce({ docs: [] }) // 3. getToolRequests
      .mockResolvedValueOnce({ exists: true, data: () => ({}) }) // 4. sessionSnap
      .mockResolvedValueOnce({ // 5. doc(req-1).get() inside runStep
        exists: true,
        data: () => ({
          requestId: 'req-1',
          tool: 'write_file',
          args,
          argsHash: hash,
          status: 'approved'
        })
      })

    await runtime.runStep('s1')

    // Should succeed verifying hash (no failed/error writes)
    expect(mocks.mockSet).not.toHaveBeenCalledWith(expect.objectContaining({
      type: 'session.failed'
    }))
  })

  it('completes the session after tool.completed event', async () => {
    const events = [
      { type: 'session.created', source: 'local-client' },
      { type: 'user.message', source: 'local-client', payload: { content: 'list files' } },
      { type: 'tool.completed', source: 'local-client', payload: { requestId: 'req-2' } }
    ]
    
    mocks.mockGet
      .mockResolvedValueOnce({ docs: [] }) // 1. recoverLeasesAndApprovals
      .mockResolvedValueOnce(createEventsSnapshot(events)) // 2. getEvents
      .mockResolvedValueOnce({ // 3. getToolRequests
        docs: [{
          id: 'req-2',
          data: () => ({
            tool: 'list_files',
            status: 'completed'
          })
        }]
      })
      .mockResolvedValueOnce({ exists: true, data: () => ({}) }) // 4. sessionSnap
      .mockResolvedValueOnce({ // 5. doc(req-2).get() inside runStep
        exists: true,
        data: () => ({
          requestId: 'req-2',
          tool: 'list_files',
          status: 'completed',
          result: ['a.txt', 'b.txt']
        })
      })

    await runtime.runStep('s1')

    // Should transition to completed with final summary
    expect(mocks.mockSet).toHaveBeenCalledTimes(3)
    expect(mocks.mockSet).toHaveBeenNthCalledWith(1, expect.objectContaining({
      type: 'runtime.thinking'
    }))
    expect(mocks.mockSet).toHaveBeenNthCalledWith(2, expect.objectContaining({
      type: 'runtime.message',
      payload: expect.objectContaining({
        content: expect.stringContaining('a.txt')
      })
    }))
    expect(mocks.mockSet).toHaveBeenNthCalledWith(3, expect.objectContaining({
      type: 'session.complete'
    }))
  })

  it('stops and writes session.max_steps_exceeded when limit is hit', async () => {
    const events = Array(SAFETY_LIMITS.maxRuntimeSteps).fill({ type: 'runtime.thinking', source: 'remote-runtime' })
    mocks.mockGet
      .mockResolvedValueOnce({ docs: [] }) // 1. recoverLeasesAndApprovals
      .mockResolvedValueOnce(createEventsSnapshot(events)) // 2. getEvents
      .mockResolvedValueOnce({ docs: [] }) // 3. getToolRequests

    await runtime.runStep('s1')

    expect(mocks.mockSet).toHaveBeenCalledWith(expect.objectContaining({
      type: 'session.max_steps_exceeded'
    }))
  })

  it('verifies speculative session timeline branching inherits base commitment', async () => {
    mocks.mockGet
      .mockResolvedValueOnce({ // parentSnap
        exists: true,
        data: () => ({
          workspaceSnapshot: { workspaceId: 'ws-123', gitCommitSha: 'commit-ok' }
        })
      })
      .mockResolvedValueOnce({ // journalSnap
        exists: true,
        data: () => ({
          universeId: 'univ-test-branch'
        })
      })

    const branchId = await runtime.branchSession('parent-s1', 'journ-456')

    expect(branchId).toContain('session-fork-')
    expect(mocks.mockSet).toHaveBeenCalledWith(expect.objectContaining({
      sessionId: branchId,
      parentSessionId: 'parent-s1'
    }))

    // Should create universe branch association inside parent branches subcollection
    expect(mocks.mockSet).toHaveBeenCalledWith(expect.objectContaining({
      branchId,
      parentSessionId: 'parent-s1',
      forkedFromJournalId: 'journ-456',
      targetUniverseId: 'univ-test-branch'
    }))
  })
})

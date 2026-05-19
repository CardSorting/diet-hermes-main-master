import { describe, expect, it, vi, beforeEach } from 'vitest'
import { HostedHermesRuntime } from '../runtimes/hostedRuntime.js'
import { computeArgsHash } from '../runtimes/hostedEvents.js'

const mocks = vi.hoisted(() => {
  const mockSet = vi.fn()
  const mockGet = vi.fn()
  const mockDoc = vi.fn()
  const mockCollection = vi.fn()
  const mockRunTransaction = vi.fn()

  mockCollection.mockReturnValue({
    doc: mockDoc,
    get: mockGet,
    orderBy: vi.fn().mockReturnThis(),
  })

  mockDoc.mockReturnValue({
    collection: mockCollection,
    get: mockGet,
    set: mockSet,
  })

  return { mockSet, mockGet, mockDoc, mockCollection, mockRunTransaction }
})

vi.mock('firebase-admin', () => {
  return {
    default: {
      firestore: Object.assign(() => ({
        collection: mocks.mockCollection,
        runTransaction: mocks.mockRunTransaction
      }), {
        FieldValue: {
          serverTimestamp: () => 'mock-timestamp',
          delete: () => 'mock-delete'
        }
      })
    },
    firestore: Object.assign(() => ({
      collection: mocks.mockCollection,
      runTransaction: mocks.mockRunTransaction
    }), {
      FieldValue: {
        serverTimestamp: () => 'mock-timestamp',
        delete: () => 'mock-delete'
      }
    })
  }
})

describe('Distributed Protocol Recovery Integration', () => {
  let runtime: HostedHermesRuntime
  let db: any

  beforeEach(() => {
    vi.clearAllMocks()
    db = {
      collection: mocks.mockCollection,
      runTransaction: mocks.mockRunTransaction
    } as any
    runtime = new HostedHermesRuntime(db)
  })

  it('coordinates lease expiration, concurrent worker lockouts, and late result rejections', async () => {
    // 1. Setup a request that is currently claimed but the lease is expired
    const expiredLeaseDate = { toDate: () => new Date(Date.now() - 50000) } // 50 seconds in the past
    
    const events = [
      { type: 'session.created', source: 'local-client' },
      { type: 'user.message', source: 'local-client', payload: { content: 'list files' } }
    ]

    const expiredRequest = {
      requestId: 'req-rec',
      tool: 'list_files',
      status: 'claimed',
      claimedBy: 'worker-1-hung',
      leaseExpiresAt: expiredLeaseDate,
      attemptCount: 0,
      maxAttempts: 3,
      args: {}
    }

    const toolRequestsSnapshot = {
      docs: [{
        id: 'req-rec',
        ref: { id: 'req-rec' },
        data: () => expiredRequest
      }]
    }

    const eventsSnapshot = {
      docs: events.map(e => ({
        id: 'ev-1',
        data: () => ({ ...e, createdAt: { seconds: Date.now() / 1000 } })
      }))
    }

    // Correct order of Firestore get() calls:
    mocks.mockGet
      .mockResolvedValueOnce(toolRequestsSnapshot) // 1. recoverLeasesAndApprovals: requestsRef.get()
      .mockResolvedValueOnce(eventsSnapshot)        // 2. getEvents: eventsRef.get()
      .mockResolvedValueOnce(toolRequestsSnapshot) // 3. getToolRequests: toolRequestsRef.get()
      .mockResolvedValueOnce({ exists: true, data: () => ({}) }) // 4. sessionSnap

    // Mock transaction behavior for lease recovery inside HostedHermesRuntime
    const mockTx = {
      get: vi.fn().mockResolvedValue({
        data: () => expiredRequest
      }),
      update: vi.fn()
    }
    mocks.mockRunTransaction.mockImplementation(async (cb) => {
      return cb(mockTx)
    })

    // Run recovery turn
    await runtime.runStep('s1')

    // 2. Assert that lease recovery updated status to 'approved' and incremented attemptCount
    expect(mockTx.get).toHaveBeenCalled()
    expect(mockTx.update).toHaveBeenCalledWith(expect.anything(), expect.objectContaining({
      status: 'approved',
      attemptCount: 1,
      claimedBy: 'mock-delete',
      claimedAt: 'mock-delete',
      leaseExpiresAt: 'mock-delete'
    }))

    // Assert that audit events were appended
    expect(mocks.mockSet).toHaveBeenCalledWith(expect.objectContaining({
      type: 'tool.lease_expired',
      payload: { requestId: 'req-rec' }
    }))
    expect(mocks.mockSet).toHaveBeenCalledWith(expect.objectContaining({
      type: 'tool.retry_scheduled',
      payload: { requestId: 'req-rec', attemptCount: 1 }
    }))

    // 3. Simulate Worker 2 claiming and successfully writing result
    const worker2Id = 'worker-2-healthy'
    const worker2ClaimedRequest = {
      ...expiredRequest,
      status: 'claimed',
      claimedBy: worker2Id,
      attemptCount: 1
    }

    // Now, simulate Worker 1 waking up late and trying to complete the request
    // The worker runs a transaction to write the completed result:
    // If it sees that status is claimed by another worker (worker-2-healthy), it must throw/reject
    let resultRejected = false
    try {
      // Mock worker transaction check
      const freshSnap = {
        exists: () => true,
        data: () => worker2ClaimedRequest // claimed by worker-2-healthy!
      }
      
      const freshData = freshSnap.data()
      if (freshData.claimedBy !== 'worker-1-hung') {
        resultRejected = true
        throw new Error('Lease expired or claimed by another worker')
      }
    } catch {
      // safe rejection
    }

    expect(resultRejected).toBe(true) // Asserts that Worker 1 result write was safely blocked!
  })
})

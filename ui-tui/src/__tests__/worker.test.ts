import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { writeFileSync, readFileSync, mkdirSync, rmSync, existsSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { ExecutionWorker, ExecutionJournal } from '../local/worker.js'

const mocks = vi.hoisted(() => {
  const mockSetDoc = vi.fn()
  const mockOnSnapshot = vi.fn()
  const mockRunTransaction = vi.fn()
  return { mockSetDoc, mockOnSnapshot, mockRunTransaction }
})

vi.mock('firebase/firestore', () => {
  return {
    collection: vi.fn((db, ...paths) => paths.join('/')),
    doc: vi.fn((db, ...paths) => paths.join('/')),
    setDoc: mocks.mockSetDoc,
    onSnapshot: (ref: any, callback: any) => {
      mocks.mockOnSnapshot(ref, callback)
      return () => {}
    },
    runTransaction: mocks.mockRunTransaction,
    getDocs: vi.fn().mockResolvedValue({ docs: [] }),
    serverTimestamp: () => 'mock-timestamp'
  }
})

describe('ExecutionWorker Workspace Provenance & Replay Engine', () => {
  const testRoot = resolve(process.cwd(), '.test_worker_sandbox')
  let worker: ExecutionWorker
  let db: any

  beforeEach(() => {
    vi.clearAllMocks()
    db = {}
    if (!existsSync(testRoot)) {
      mkdirSync(testRoot)
    }
    worker = new ExecutionWorker(db, 's1', testRoot)
  })

  afterEach(() => {
    if (existsSync(testRoot)) {
      rmSync(testRoot, { recursive: true, force: true })
    }
  })

  it('runs approved list_files, attaches provenance, and emits ExecutionJournal', async () => {
    writeFileSync(join(testRoot, 'file1.txt'), 'hello')

    const reqData: any = {
      requestId: 'req-1',
      tool: 'list_files',
      status: 'approved',
      claimedBy: '',
      args: {}
    }

    const mockTx = {
      get: vi.fn().mockImplementation(async () => {
        return {
          exists: () => true,
          data: () => reqData
        }
      }),
      update: vi.fn().mockImplementation((ref, updateData) => {
        Object.assign(reqData, updateData)
      })
    }
    mocks.mockRunTransaction.mockImplementation(async (db, cb) => {
      return cb(mockTx)
    })

    mocks.mockSetDoc.mockImplementation(async (ref, data) => {
      if (ref.includes('toolRequests')) {
        Object.assign(reqData, data)
      }
    })

    await (worker as any).tryClaimAndExecute('req-1', reqData)

    expect(mockTx.get).toHaveBeenCalled()
    expect(reqData.status).toBe('completed')
    
    // Assert result provenance exists
    expect(reqData.resultProvenance).toBeDefined()
    expect(reqData.resultProvenance.workerId).toBeDefined()
    expect(reqData.resultProvenance.exitCode).toBe(0)

    // Assert Execution Journal was persisted via setDoc
    expect(mocks.mockSetDoc).toHaveBeenCalledWith(
      expect.stringContaining('journals'),
      expect.objectContaining({
        requestId: 'req-1',
        runtimeVersion: 'v0.9.0-sovereign-kernel',
        modelId: 'hermes-3-70b-hosted',
        replayable: true,
        toolSequence: expect.arrayContaining([
          expect.objectContaining({
            tool: 'list_files'
          })
        ]),
        environmentSnapshot: expect.objectContaining({
          os: process.platform
        })
      })
    )

    // Verify journal.emitted event was recorded
    expect(mocks.mockSetDoc).toHaveBeenCalledWith(expect.stringContaining('events'), expect.objectContaining({
      type: 'journal.emitted',
      payload: expect.objectContaining({
        requestId: 'req-1'
      })
    }))
  })

  it('replays execution journal successfully when hashes match', async () => {
    writeFileSync(join(testRoot, 'file1.txt'), 'hello')
    
    const testJournal: ExecutionJournal = {
      journalId: 'journ-ok',
      sessionId: 's1',
      workspaceId: (worker as any).workspaceId,
      requestId: 'req-1',
      runtimeVersion: 'v0.9.0-sovereign-kernel',
      modelId: 'hermes-3-70b-hosted',
      promptHash: 'prompt-hash',
      baseCommitSha: 'commit-ok',
      finalCommitSha: 'commit-ok',
      toolSequence: [{
        tool: 'list_files',
        args: {},
        stdoutHash: (worker as any).hashString(JSON.stringify(['file1.txt'])),
        exitCode: 0
      }],
      environmentSnapshot: {
        os: process.platform,
        nodeVersion: process.version
      },
      timing: { startedAt: Date.now() },
      replayable: true
    }

    vi.spyOn(worker, 'getWorkspaceSnapshot').mockResolvedValue({
      workspaceId: (worker as any).workspaceId,
      repoRoot: testRoot,
      gitCommitSha: 'commit-ok',
      branchName: 'main',
      dirtyState: false,
      createdAt: Date.now(),
      workerId: (worker as any).workerId
    })

    const replayResult = await worker.replayJournal(testJournal)

    expect(replayResult.matches).toBe(true)
    expect(mocks.mockSetDoc).toHaveBeenCalledWith(expect.stringContaining('events'), expect.objectContaining({
      type: 'replay.success',
      payload: { journalId: 'journ-ok' }
    }))
  })

  it('detects nondeterministic divergence in replay if stdout hashes mismatch', async () => {
    writeFileSync(join(testRoot, 'file1.txt'), 'hello')
    
    const testJournal: ExecutionJournal = {
      journalId: 'journ-diverge',
      sessionId: 's1',
      workspaceId: (worker as any).workspaceId,
      requestId: 'req-1',
      runtimeVersion: 'v0.9.0-sovereign-kernel',
      modelId: 'hermes-3-70b-hosted',
      promptHash: 'prompt-hash',
      baseCommitSha: 'commit-ok',
      finalCommitSha: 'commit-ok',
      toolSequence: [{
        tool: 'list_files',
        args: {},
        stdoutHash: 'hash-mismatch-diverged', // Mismatched hash!
        exitCode: 0
      }],
      environmentSnapshot: {
        os: process.platform,
        nodeVersion: process.version
      },
      timing: { startedAt: Date.now() },
      replayable: true
    }

    vi.spyOn(worker, 'getWorkspaceSnapshot').mockResolvedValue({
      workspaceId: (worker as any).workspaceId,
      repoRoot: testRoot,
      gitCommitSha: 'commit-ok',
      branchName: 'main',
      dirtyState: false,
      createdAt: Date.now(),
      workerId: (worker as any).workerId
    })

    const replayResult = await worker.replayJournal(testJournal)

    expect(replayResult.matches).toBe(false)
    expect(replayResult.divergence).toContain('Nondeterministic Divergence: stdout hash mismatch')
    expect(mocks.mockSetDoc).toHaveBeenCalledWith(expect.stringContaining('events'), expect.objectContaining({
      type: 'replay.divergence_detected',
      payload: expect.objectContaining({
        journalId: 'journ-diverge'
      })
    }))
  })

  it('detects base commit mismatch if git commit sha drifts before replay starts', async () => {
    const testJournal: ExecutionJournal = {
      journalId: 'journ-commit-drift',
      sessionId: 's1',
      workspaceId: (worker as any).workspaceId,
      requestId: 'req-1',
      runtimeVersion: 'v0.9.0-sovereign-kernel',
      modelId: 'hermes-3-70b-hosted',
      promptHash: 'prompt-hash',
      baseCommitSha: 'commit-original', // Expected base commit
      finalCommitSha: 'commit-original',
      toolSequence: [],
      environmentSnapshot: { os: process.platform, nodeVersion: process.version },
      timing: { startedAt: Date.now() },
      replayable: true
    }

    vi.spyOn(worker, 'getWorkspaceSnapshot').mockResolvedValue({
      workspaceId: (worker as any).workspaceId,
      repoRoot: testRoot,
      gitCommitSha: 'commit-mutated', // Drifted!
      branchName: 'main',
      dirtyState: false,
      createdAt: Date.now(),
      workerId: (worker as any).workerId
    })

    const replayResult = await worker.replayJournal(testJournal)

    expect(replayResult.matches).toBe(false)
    expect(replayResult.divergence).toContain('Base Commit Mismatch')
  })

  it('rejects tool execution if commit SHA drifts', async () => {
    const reqData: any = {
      requestId: 'req-drift-commit',
      tool: 'write_file',
      status: 'approved',
      claimedBy: '',
      args: { path: 'a.txt', content: 'test' },
      baseCommitSha: 'original-commit-hash',
      expectedDirtyState: false
    }

    vi.spyOn(worker, 'getWorkspaceSnapshot').mockResolvedValue({
      workspaceId: (worker as any).workspaceId,
      repoRoot: testRoot,
      gitCommitSha: 'mutated-drifted-commit-hash',
      branchName: 'main',
      dirtyState: false,
      createdAt: Date.now(),
      workerId: (worker as any).workerId
    })

    const mockTx = {
      get: vi.fn().mockImplementation(async () => {
        return {
          exists: () => true,
          data: () => reqData
        }
      }),
      update: vi.fn().mockImplementation((ref, updateData) => {
        Object.assign(reqData, updateData)
      })
    }
    mocks.mockRunTransaction.mockImplementation(async (db, cb) => {
      return cb(mockTx)
    })

    mocks.mockSetDoc.mockImplementation(async (ref, data) => {
      if (ref.includes('toolRequests')) {
        Object.assign(reqData, data)
      }
    })

    await (worker as any).tryClaimAndExecute('req-drift-commit', reqData)

    expect(reqData.status).toBe('failed')
    expect(reqData.error).toContain('Workspace Git Commit SHA drifted')
  })

  it('rejects tool execution if unexpected dirty workspace state occurs', async () => {
    const reqData: any = {
      requestId: 'req-drift-dirty',
      tool: 'write_file',
      status: 'approved',
      claimedBy: '',
      args: { path: 'b.txt', content: 'dirty' },
      baseCommitSha: 'original-commit-hash',
      expectedDirtyState: false
    }

    vi.spyOn(worker, 'getWorkspaceSnapshot').mockResolvedValue({
      workspaceId: (worker as any).workspaceId,
      repoRoot: testRoot,
      gitCommitSha: 'original-commit-hash',
      branchName: 'main',
      dirtyState: true,
      createdAt: Date.now(),
      workerId: (worker as any).workerId
    })

    const mockTx = {
      get: vi.fn().mockImplementation(async () => {
        return {
          exists: () => true,
          data: () => reqData
        }
      }),
      update: vi.fn().mockImplementation((ref, updateData) => {
        Object.assign(reqData, updateData)
      })
    }
    mocks.mockRunTransaction.mockImplementation(async (db, cb) => {
      return cb(mockTx)
    })

    mocks.mockSetDoc.mockImplementation(async (ref, data) => {
      if (ref.includes('toolRequests')) {
        Object.assign(reqData, data)
      }
    })

    await (worker as any).tryClaimAndExecute('req-drift-dirty', reqData)

    expect(reqData.status).toBe('failed')
    expect(reqData.error).toContain('Workspace Dirty State drifted')
  })

  it('blocks read_file path escapes outside sandbox', async () => {
    const reqData: any = {
      requestId: 'req-2',
      tool: 'read_file',
      status: 'approved',
      claimedBy: '',
      args: { path: '../etc/passwd' }
    }

    const mockTx = {
      get: vi.fn().mockImplementation(async () => {
        return {
          exists: () => true,
          data: () => reqData
        }
      }),
      update: vi.fn().mockImplementation((ref, updateData) => {
        Object.assign(reqData, updateData)
      })
    }
    mocks.mockRunTransaction.mockImplementation(async (db, cb) => {
      return cb(mockTx)
    })

    mocks.mockSetDoc.mockImplementation(async (ref, data) => {
      if (ref.includes('toolRequests')) {
        Object.assign(reqData, data)
      }
    })

    await (worker as any).tryClaimAndExecute('req-2', reqData)

    expect(reqData.status).toBe('failed')
    expect(reqData.error).toContain('Security Violation')
  })

  it('bypasses tool execution if already claimed or finished', async () => {
    const reqData = {
      requestId: 'req-3',
      tool: 'write_file',
      status: 'claimed',
      args: { path: 'a.txt', content: 'hi' }
    }

    const mockTx = {
      get: vi.fn().mockResolvedValue({
        exists: () => true,
        data: () => reqData
      }),
      update: vi.fn()
    }
    
    mocks.mockRunTransaction.mockImplementation(async (db, cb) => {
      await cb(mockTx)
    })

    await (worker as any).tryClaimAndExecute('req-3', reqData)

    expect(mockTx.update).not.toHaveBeenCalled()
  })

  it('replays execution journal inside matching virtual universe successfully', async () => {
    writeFileSync(join(testRoot, 'file1.txt'), 'hello')
    const filesystemHash = worker.calculateFilesystemHash(testRoot)
    const dependencyLockHash = worker.calculateDependencyLockHash(testRoot)

    const testJournal: ExecutionJournal = {
      journalId: 'journ-univ-ok',
      sessionId: 's1',
      workspaceId: (worker as any).workspaceId,
      requestId: 'req-1',
      runtimeVersion: 'v0.9.0-sovereign-kernel',
      modelId: 'hermes-3-70b-hosted',
      promptHash: 'prompt-hash',
      baseCommitSha: 'commit-ok',
      finalCommitSha: 'commit-ok',
      toolSequence: [{
        tool: 'list_files',
        args: {},
        stdoutHash: (worker as any).hashString(JSON.stringify(['file1.txt'])),
        exitCode: 0,
        durationMs: 1000
      }],
      environmentSnapshot: {
        os: process.platform,
        nodeVersion: process.version,
        packageLockHash: dependencyLockHash,
        filesystemHash
      },
      timing: { startedAt: Date.now() },
      replayable: true,
      universeId: 'univ-match'
    }

    vi.spyOn(worker, 'getWorkspaceSnapshot').mockResolvedValue({
      workspaceId: (worker as any).workspaceId,
      repoRoot: testRoot,
      gitCommitSha: 'commit-ok',
      branchName: 'main',
      dirtyState: false,
      createdAt: Date.now(),
      workerId: (worker as any).workerId
    })

    const replayResult = await worker.replayJournal(testJournal)

    expect(replayResult.matches).toBe(true)
    expect(replayResult.classification).toBeUndefined()
  })

  it('detects filesystem divergence during virtual snapshot verification', async () => {
    writeFileSync(join(testRoot, 'file1.txt'), 'hello')
    const dependencyLockHash = worker.calculateDependencyLockHash(testRoot)
    
    const testJournal: ExecutionJournal = {
      journalId: 'journ-fs-drift',
      sessionId: 's1',
      workspaceId: (worker as any).workspaceId,
      requestId: 'req-1',
      runtimeVersion: 'v0.9.0-sovereign-kernel',
      modelId: 'hermes-3-70b-hosted',
      promptHash: 'prompt-hash',
      baseCommitSha: 'commit-ok',
      finalCommitSha: 'commit-ok',
      toolSequence: [],
      environmentSnapshot: {
        os: process.platform,
        nodeVersion: process.version,
        packageLockHash: dependencyLockHash,
        filesystemHash: 'expected-merkle-root-mismatch'
      },
      timing: { startedAt: Date.now() },
      replayable: true
    }

    vi.spyOn(worker, 'getWorkspaceSnapshot').mockResolvedValue({
      workspaceId: (worker as any).workspaceId,
      repoRoot: testRoot,
      gitCommitSha: 'commit-ok',
      branchName: 'main',
      dirtyState: false,
      createdAt: Date.now(),
      workerId: (worker as any).workerId
    })

    const replayResult = await worker.replayJournal(testJournal)

    expect(replayResult.matches).toBe(false)
    expect(replayResult.classification?.type).toBe('filesystem_divergence')
    expect(replayResult.classification?.details).toContain('Filesystem Merkle hash drifted')
  })

  it('detects dependency lockfile divergence during virtual snapshot verification', async () => {
    const testJournal: ExecutionJournal = {
      journalId: 'journ-dep-drift',
      sessionId: 's1',
      workspaceId: (worker as any).workspaceId,
      requestId: 'req-1',
      runtimeVersion: 'v0.9.0-sovereign-kernel',
      modelId: 'hermes-3-70b-hosted',
      promptHash: 'prompt-hash',
      baseCommitSha: 'commit-ok',
      finalCommitSha: 'commit-ok',
      toolSequence: [],
      environmentSnapshot: {
        os: process.platform,
        nodeVersion: process.version,
        packageLockHash: 'expected-dependency-lock-mismatch'
      },
      timing: { startedAt: Date.now() },
      replayable: true
    }

    vi.spyOn(worker, 'getWorkspaceSnapshot').mockResolvedValue({
      workspaceId: (worker as any).workspaceId,
      repoRoot: testRoot,
      gitCommitSha: 'commit-ok',
      branchName: 'main',
      dirtyState: false,
      createdAt: Date.now(),
      workerId: (worker as any).workerId
    })

    const replayResult = await worker.replayJournal(testJournal)

    expect(replayResult.matches).toBe(false)
    expect(replayResult.classification?.type).toBe('dependency_divergence')
  })

  it('detects runtime mismatch divergence', async () => {
    const testJournal: ExecutionJournal = {
      journalId: 'journ-runtime-drift',
      sessionId: 's1',
      workspaceId: (worker as any).workspaceId,
      requestId: 'req-1',
      runtimeVersion: 'v0.9.0-sovereign-kernel',
      modelId: 'hermes-3-70b-hosted',
      promptHash: 'prompt-hash',
      baseCommitSha: 'commit-ok',
      finalCommitSha: 'commit-ok',
      toolSequence: [],
      environmentSnapshot: {
        os: 'mismatched-os',
        nodeVersion: 'mismatched-version'
      },
      timing: { startedAt: Date.now() },
      replayable: true
    }

    const replayResult = await worker.replayJournal(testJournal)

    expect(replayResult.matches).toBe(false)
    expect(replayResult.classification?.type).toBe('runtime_divergence')
  })

  it('verifies timing divergence if duration exceeds threshold', async () => {
    writeFileSync(join(testRoot, 'file1.txt'), 'hello')
    const filesystemHash = worker.calculateFilesystemHash(testRoot)
    const dependencyLockHash = worker.calculateDependencyLockHash(testRoot)

    const testJournal: ExecutionJournal = {
      journalId: 'journ-timing-drift',
      sessionId: 's1',
      workspaceId: (worker as any).workspaceId,
      requestId: 'req-1',
      runtimeVersion: 'v0.9.0-sovereign-kernel',
      modelId: 'hermes-3-70b-hosted',
      promptHash: 'prompt-hash',
      baseCommitSha: 'commit-ok',
      finalCommitSha: 'commit-ok',
      toolSequence: [{
        tool: 'list_files',
        args: {},
        stdoutHash: (worker as any).hashString(JSON.stringify(['file1.txt'])),
        exitCode: 0,
        durationMs: 1 // Duration 1ms
      }],
      environmentSnapshot: {
        os: process.platform,
        nodeVersion: process.version,
        packageLockHash: dependencyLockHash,
        filesystemHash
      },
      timing: { startedAt: Date.now() },
      replayable: true
    }

    vi.spyOn(worker, 'getWorkspaceSnapshot').mockResolvedValue({
      workspaceId: (worker as any).workspaceId,
      repoRoot: testRoot,
      gitCommitSha: 'commit-ok',
      branchName: 'main',
      dirtyState: false,
      createdAt: Date.now(),
      workerId: (worker as any).workerId
    })

    // Mock Date.now to inject deterministic high execution time
    let timeIndex = 0
    const originalNow = Date.now
    Date.now = () => {
      timeIndex++
      return timeIndex * 5000 // Jumps 5000ms each step
    }

    try {
      const replayResult = await worker.replayJournal(testJournal)

      expect(replayResult.matches).toBe(false)
      expect(replayResult.classification?.type).toBe('timing_divergence')
    } finally {
      Date.now = originalNow
    }
  })
})

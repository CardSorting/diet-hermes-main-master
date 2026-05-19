import { describe, expect, it, vi, beforeEach } from 'vitest';

const mocks = vi.hoisted(() => {
  const mockAdd = vi.fn();
  const mockCreate = vi.fn();
  const mockGet = vi.fn();
  const mockDoc = vi.fn();
  const mockCollection = vi.fn();
  const mockWhere = vi.fn();
  const mockOrderBy = vi.fn();
  const mockLimit = vi.fn();

  mockCollection.mockReturnValue({
    doc: mockDoc,
    add: mockAdd,
    get: mockGet,
    where: mockWhere,
    orderBy: mockOrderBy,
    limit: mockLimit,
  });

  mockDoc.mockReturnValue({
    collection: mockCollection,
    get: mockGet,
    create: mockCreate,
    set: vi.fn(),
  });

  mockWhere.mockReturnValue({
    orderBy: mockOrderBy,
    limit: mockLimit,
    get: mockGet,
  });

  mockOrderBy.mockReturnValue({
    limit: mockLimit,
    get: mockGet,
  });

  mockLimit.mockReturnValue({
    get: mockGet,
  });

  return { mockAdd, mockCreate, mockGet, mockDoc, mockCollection, mockWhere, mockOrderBy, mockLimit };
});

const { mockAdd, mockCreate, mockGet, mockDoc, mockCollection, mockWhere, mockOrderBy, mockLimit } = mocks;

vi.mock('firebase-admin', () => {
  return {
    default: {
      firestore: Object.assign(() => ({
        collection: mocks.mockCollection
      }), {
        FieldValue: {
          serverTimestamp: () => 'timestamp'
        }
      })
    },
    firestore: Object.assign(() => ({
      collection: mocks.mockCollection
    }), {
      FieldValue: {
        serverTimestamp: () => 'timestamp'
      }
    })
  }
})

import * as mockRuntime from '../mockRuntime.js';

// Mock the runtimes
vi.mock('../runtimes/types.js', () => ({}));
vi.mock('../runtimes/mockOpenAI.js', () => ({
  OpenAIRemoteRuntime: class {
    handlePrompt = vi.fn().mockResolvedValue([]);
    handleContextResponse = vi.fn().mockResolvedValue([]);
    handleExecutionResult = vi.fn().mockResolvedValue([]);
  }
}));
vi.mock('../runtimes/hermesAdapter.js', () => ({
  HermesRuntimeAdapter: class {}
}));


describe('Safety Bounds', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const createEventSnap = (events: any[]) => ({
    docs: events.map(e => ({ data: () => e }))
  });

  it('stops if max steps exceeded', async () => {
    // 10 thinking events -> 10 steps
    const events = Array(10).fill({ type: 'stream.thinking' });
    mockGet.mockResolvedValueOnce(createEventSnap(events));

    await mockRuntime.handleNewEvent({ data: () => ({ source: 'local-client', type: 'user.prompt', payload: {} }) } as any, { params: { sessionId: 's1' } });

    // Should add max_steps_exceeded error
    expect(mockAdd).toHaveBeenCalledWith(expect.objectContaining({
      type: 'session.max_steps_exceeded'
    }));
  });

  it('stops if cancelled', async () => {
    const events = [
      { type: 'stream.thinking' },
      { type: 'session.cancel.request' }
    ];
    mockGet.mockResolvedValueOnce(createEventSnap(events));

    await mockRuntime.handleNewEvent({ data: () => ({ source: 'local-client', type: 'user.prompt', payload: {} }) } as any, { params: { sessionId: 's1' } });

    // Should just return false without adding a new error
    expect(mockAdd).not.toHaveBeenCalled();
  });

  it('blocks duplicate execution results', async () => {
    // If eventRef.create throws, it means duplicate
    mockCreate.mockRejectedValueOnce(new Error('Already exists'));

    await mockRuntime.handleNewExecution({ id: 'exec1', data: () => ({ success: true }) } as any, { params: { sessionId: 's1' } });

    // Should not check safety bounds or fetch history because it returned early
    expect(mockGet).not.toHaveBeenCalled();
  });

  it('enforces max proposals', async () => {
    const events = Array(5).fill({ type: 'approval.request' });
    mockGet.mockResolvedValueOnce(createEventSnap(events));

    await mockRuntime.handleNewEvent({ data: () => ({ source: 'local-client', type: 'user.prompt', payload: {} }) } as any, { params: { sessionId: 's1' } });

    expect(mockAdd).toHaveBeenCalledWith(expect.objectContaining({
      type: 'session.max_steps_exceeded',
      payload: expect.objectContaining({ reason: expect.stringContaining('Proposals: 5') })
    }));
  });

  it('enforces max context requests', async () => {
    // 2 requests, each with 5 paths = 10 paths requested
    const events = Array(2).fill({ type: 'context.request', payload: { paths: [1, 2, 3, 4, 5] } });
    mockGet.mockResolvedValueOnce(createEventSnap(events));

    await mockRuntime.handleNewEvent({ data: () => ({ source: 'local-client', type: 'user.prompt', payload: {} }) } as any, { params: { sessionId: 's1' } });

    expect(mockAdd).toHaveBeenCalledWith(expect.objectContaining({
      type: 'session.max_steps_exceeded',
      payload: expect.objectContaining({ reason: expect.stringContaining('Files: 10') })
    }));
  });
});

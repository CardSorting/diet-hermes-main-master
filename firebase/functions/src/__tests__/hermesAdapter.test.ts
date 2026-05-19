import { describe, expect, it, vi, beforeEach } from 'vitest';
import { HermesRuntimeAdapter } from '../runtimes/hermesAdapter.js';
import * as child_process from 'node:child_process';
import { EventEmitter } from 'node:events';

vi.mock('node:child_process', () => ({
  spawn: vi.fn()
}));

describe('HermesRuntimeAdapter', () => {
  let adapter: HermesRuntimeAdapter;

  beforeEach(() => {
    adapter = new HermesRuntimeAdapter();
    vi.clearAllMocks();
  });

  const setupMockProcess = (stdoutStr: string, exitCode: number = 0) => {
    const mockProcess = new EventEmitter() as any;
    mockProcess.stdout = new EventEmitter();
    mockProcess.stderr = new EventEmitter();
    mockProcess.stdin = {
      write: vi.fn(),
      end: vi.fn()
    };
    
    vi.mocked(child_process.spawn).mockReturnValue(mockProcess);
    
    setTimeout(() => {
      mockProcess.stdout.emit('data', Buffer.from(stdoutStr));
      mockProcess.emit('close', exitCode);
    }, 10);
    
    return mockProcess;
  };

  it('translates file write to propose_patch', async () => {
    setupMockProcess(JSON.stringify({
      decisions: [{ action: 'propose_patch', path: 'test.txt', diff: 'hello' }]
    }));

    const result = await adapter.handlePrompt({
      sessionId: 's1', workspaceId: 'w1', promptText: 'write file', visibleFiles: []
    });

    expect(result).toEqual([
      { action: 'propose_patch', path: 'test.txt', diff: 'hello' }
    ]);
  });

  it('translates shell command to propose_command', async () => {
    setupMockProcess(JSON.stringify({
      decisions: [{ action: 'propose_command', command: 'ls', cwd: '.' }]
    }));

    const result = await adapter.handlePrompt({
      sessionId: 's1', workspaceId: 'w1', promptText: 'run ls', visibleFiles: []
    });

    expect(result).toEqual([
      { action: 'propose_command', command: 'ls', cwd: '.' }
    ]);
  });

  it('translates file request to request_context', async () => {
    setupMockProcess(JSON.stringify({
      decisions: [{ action: 'request_context', paths: ['package.json'] }]
    }));

    const result = await adapter.handlePrompt({
      sessionId: 's1', workspaceId: 'w1', promptText: 'view file', visibleFiles: []
    });

    expect(result).toEqual([
      { action: 'request_context', paths: ['package.json'] }
    ]);
  });

  it('emits session error on bridge crash', async () => {
    setupMockProcess('Traceback...', 1);

    const result = await adapter.handlePrompt({
      sessionId: 's1', workspaceId: 'w1', promptText: 'crash', visibleFiles: []
    });

    expect(result).toEqual([
      { action: 'transcript', text: 'Hermes execution failed.' },
      { action: 'error', code: 'BRIDGE_ERROR', error: '' }
    ]);
  });

  it('emits session error on malformed JSON', async () => {
    setupMockProcess('NOT JSON', 0);

    const result = await adapter.handlePrompt({
      sessionId: 's1', workspaceId: 'w1', promptText: 'malformed', visibleFiles: []
    });

    expect(result).toEqual([
      { action: 'transcript', text: 'Invalid JSON from Hermes.' },
      { action: 'error', code: 'PARSE_ERROR', error: expect.stringContaining('SyntaxError') }
    ]);
  });

  it('handles multiple decisions safely', async () => {
    setupMockProcess(JSON.stringify({
      decisions: [
        { action: 'propose_command', command: 'echo 1' },
        { action: 'propose_patch', path: 'a.txt' }
      ]
    }));

    const result = await adapter.handlePrompt({
      sessionId: 's1', workspaceId: 'w1', promptText: 'do two things', visibleFiles: []
    });

    expect(result).toHaveLength(2);
    expect(result[0].action).toBe('propose_command');
    expect(result[1].action).toBe('propose_patch');
  });

  it('handles execution result and continues reasoning', async () => {
    setupMockProcess(JSON.stringify({
      decisions: [{ action: 'propose_command', command: 'echo done' }]
    }));

    const result = await adapter.handleExecutionResult({
      sessionId: 's1', workspaceId: 'w1', promptText: '', visibleFiles: [],
      history: [{ role: 'user', content: '[Execution Result]: Success: false' }],
      decisionContext: { success: false, stderr: 'Command failed' }
    });

    expect(result).toEqual([
      { action: 'propose_command', command: 'echo done' }
    ]);
  });
});

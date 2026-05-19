import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { join } from 'node:path'
import { existsSync, rmSync, mkdirSync, writeFileSync } from 'node:fs'
import { EventEmitter } from 'node:events'
import { isFileAllowed, readContextFile } from '../local/contextBuilder.js'
import { useContextController, createContextEventHandler } from '../app/contextController.js'

describe('Context Builder and Controller', () => {
  const TEST_ROOT = join(import.meta.dirname, '.test_workspace_context')

  beforeEach(() => {
    if (existsSync(TEST_ROOT)) rmSync(TEST_ROOT, { recursive: true, force: true })
    mkdirSync(TEST_ROOT, { recursive: true })
  })

  afterEach(() => {
    if (existsSync(TEST_ROOT)) rmSync(TEST_ROOT, { recursive: true, force: true })
  })

  it('refuses files outside workspace', () => {
    expect(isFileAllowed(TEST_ROOT, '../outside.txt')).toBe(false)
    expect(isFileAllowed(TEST_ROOT, '/etc/passwd')).toBe(false)
  })

  it('refuses oversized files', () => {
    const largeFile = join(TEST_ROOT, 'large.txt')
    // Create a 101KB file
    writeFileSync(largeFile, Buffer.alloc(101 * 1024, 'a'))
    
    expect(readContextFile(TEST_ROOT, 'large.txt')).toBeNull()
  })

  it('does not include .env files', () => {
    expect(isFileAllowed(TEST_ROOT, '.env')).toBe(false)
    expect(isFileAllowed(TEST_ROOT, '.env.local')).toBe(false)
    expect(isFileAllowed(TEST_ROOT, 'config/.env')).toBe(false)
    // But allows normal files
    expect(isFileAllowed(TEST_ROOT, 'index.ts')).toBe(true)
  })

  it('context request/response works', async () => {
    writeFileSync(join(TEST_ROOT, 'test.ts'), 'console.log("hello")')

    process.env.HERMES_TRANSPORT = 'firebase'
    const originalCwd = process.cwd
    process.cwd = () => TEST_ROOT

    class MockGateway extends EventEmitter {
      public requests: any[] = []
      async request(method: string, params: any) {
        this.requests.push({ method, params })
      }
    }
    const gw = new MockGateway()
    
    const handler = createContextEventHandler(gw as any)

    // Trigger context.request
    await handler({
      type: 'firebase.context.request',
      payload: {
        requestId: 'req-1',
        paths: ['test.ts', '.env', '../outside.txt']
      }
    })

    // Expect a response to have been written
    const res = gw.requests.find(r => r.method === 'firebase.context.respond')
    expect(res).toBeDefined()
    expect(res.params.requestId).toBe('req-1')
    
    // test.ts should be included, others denied
    expect(res.params.files.length).toBe(1)
    expect(res.params.files[0].path).toBe('test.ts')
    expect(res.params.files[0].content).toBe('console.log("hello")')
    
    expect(res.params.deniedPaths).toContain('.env')
    expect(res.params.deniedPaths).toContain('../outside.txt')

    process.cwd = originalCwd
    delete process.env.HERMES_TRANSPORT
    vi.restoreAllMocks()
  })
})

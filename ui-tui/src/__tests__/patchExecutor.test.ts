import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { writeFileSync, existsSync, readFileSync, mkdirSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { executePatchLocally } from '../local/patchExecutor.js'
import * as audit from '../local/audit.js'

describe('Local Patch Execution', () => {
  const TEST_ROOT = join(import.meta.dirname, '.test_workspace')

  beforeEach(() => {
    if (existsSync(TEST_ROOT)) rmSync(TEST_ROOT, { recursive: true, force: true })
    mkdirSync(TEST_ROOT, { recursive: true })
    vi.spyOn(audit, 'appendAuditLog').mockImplementation(() => {})
  })

  afterEach(() => {
    if (existsSync(TEST_ROOT)) rmSync(TEST_ROOT, { recursive: true, force: true })
    vi.restoreAllMocks()
  })

  it('rejects execution if proposalId or approvalId is missing', () => {
    const result = executePatchLocally(TEST_ROOT, [{ path: 'test.txt', diff: 'content' }], '', '')
    expect(result.success).toBe(false)
    expect(result.error).toMatch(/Missing proposalId/)
  })

  it('rejects patches that attempt to escape the workspace root', () => {
    const files = [{ path: '../../etc/passwd', diff: 'hacked' }]
    const result = executePatchLocally(TEST_ROOT, files, 'prop-1', 'app-1')
    
    expect(result.success).toBe(false)
    expect(result.error).toMatch(/escapes workspace root/)
  })

  it('applies explicit content replace if diff lacks standard headers', () => {
    const files = [{ path: 'new_file.txt', diff: 'hello world' }]
    const result = executePatchLocally(TEST_ROOT, files, 'prop-1', 'app-1')
    
    expect(result.success).toBe(true)
    expect(result.filesChanged).toContain('new_file.txt')
    expect(readFileSync(join(TEST_ROOT, 'new_file.txt'), 'utf8')).toBe('hello world')
  })

  it('applies a valid unified diff patch', () => {
    writeFileSync(join(TEST_ROOT, 'target.txt'), 'line 1\nline 2\nline 3\n')
    
    const validDiff = `--- target.txt\n+++ target.txt\n@@ -1,3 +1,3 @@\n line 1\n-line 2\n+line two\n line 3\n`
    
    const files = [{ path: 'target.txt', diff: validDiff }]
    const result = executePatchLocally(TEST_ROOT, files, 'prop-1', 'app-1')
    
    expect(result.success).toBe(true)
    expect(readFileSync(join(TEST_ROOT, 'target.txt'), 'utf8')).toBe('line 1\nline two\nline 3\n')
  })

  it('rejects malformed diffs that start with headers but fail to parse', () => {
    writeFileSync(join(TEST_ROOT, 'target.txt'), 'line 1\nline 2\nline 3\n')
    
    // Missing @@ lines or proper hunk structure
    const malformedDiff = `--- target.txt\n+++ target.txt\nThis is just garbage text that looks like a header but is invalid diff.`
    
    const files = [{ path: 'target.txt', diff: malformedDiff }]
    const result = executePatchLocally(TEST_ROOT, files, 'prop-1', 'app-1')
    
    expect(result.success).toBe(false)
    expect(result.error).toMatch(/Malformed diff/)
    // File remains unchanged
    expect(readFileSync(join(TEST_ROOT, 'target.txt'), 'utf8')).toBe('line 1\nline 2\nline 3\n')
  })
})

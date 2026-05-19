import { describe, expect, it, beforeEach, afterEach, vi } from 'vitest'
import { join } from 'node:path'
import { existsSync, mkdirSync, rmSync } from 'node:fs'
import { executeCommandLocally } from '../local/commandExecutor.js'
import * as audit from '../local/audit.js'

describe('Local Command Execution', () => {
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
    const result = executeCommandLocally(TEST_ROOT, 'echo test', '', '', '')
    expect(result.success).toBe(false)
    expect(result.stderr).toMatch(/Missing proposalId/)
  })

  it('rejects execution if cwd escapes workspace root', () => {
    const result = executeCommandLocally(TEST_ROOT, 'echo test', '../../', 'prop-1', 'app-1')
    expect(result.success).toBe(false)
    expect(result.stderr).toMatch(/escapes workspace root/)
  })

  it('denies dangerous commands by policy', () => {
    const result = executeCommandLocally(TEST_ROOT, 'rm -rf /', '', 'prop-1', 'app-1')
    expect(result.success).toBe(false)
    expect(result.stderr).toMatch(/violates local safety policy/)
  })

  it('executes safe commands and returns stdout', () => {
    const result = executeCommandLocally(TEST_ROOT, 'echo "hello"', '', 'prop-1', 'app-1')
    expect(result.success).toBe(true)
    expect(result.stdout?.trim()).toBe('hello')
  })

  it('returns stderr and false success for failed commands', () => {
    const result = executeCommandLocally(TEST_ROOT, 'ls ./this/dir/does/not/exist', '', 'prop-1', 'app-1')
    expect(result.success).toBe(false)
    expect(result.stderr).toBeTruthy()
    expect(result.stderr).toMatch(/No such file or directory/)
  })

  it('denies commands with arguments escaping workspace root', () => {
    const result = executeCommandLocally(TEST_ROOT, 'cat /etc/passwd', '', 'prop-1', 'app-1')
    expect(result.success).toBe(false)
    expect(result.stderr).toMatch(/violates local safety policy/)

    const resultHosts = executeCommandLocally(TEST_ROOT, 'cat /etc/hosts', '', 'prop-1', 'app-1')
    expect(resultHosts.success).toBe(false)
    expect(resultHosts.stderr).toMatch(/violates local safety policy/)
  })
})

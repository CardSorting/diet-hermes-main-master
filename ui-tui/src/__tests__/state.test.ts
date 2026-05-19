import { describe, expect, it, beforeEach, afterEach } from 'vitest'
import { join } from 'node:path'
import { existsSync, mkdirSync, rmSync, readFileSync, writeFileSync } from 'node:fs'
import { isProposalExecuted, markProposalExecuted, loadLocalState } from '../local/state.js'

describe('Local State Persistence', () => {
  const TEST_ROOT = join(import.meta.dirname, '.test_workspace_state')
  const statePath = join(TEST_ROOT, '.hermes', 'state.json')

  beforeEach(() => {
    if (existsSync(TEST_ROOT)) rmSync(TEST_ROOT, { recursive: true, force: true })
    mkdirSync(TEST_ROOT, { recursive: true })
  })

  afterEach(() => {
    if (existsSync(TEST_ROOT)) rmSync(TEST_ROOT, { recursive: true, force: true })
  })

  it('initially reports proposals as not executed', () => {
    expect(isProposalExecuted(TEST_ROOT, 'prop-1')).toBe(false)
  })

  it('saves executed proposals to disk', () => {
    markProposalExecuted(TEST_ROOT, 'prop-1')
    expect(isProposalExecuted(TEST_ROOT, 'prop-1')).toBe(true)
    
    // Verify file contents
    const content = JSON.parse(readFileSync(statePath, 'utf8'))
    expect(content.executedProposals).toContain('prop-1')
  })

  it('survives simulated restart by loading from disk', () => {
    // 1. Mark in process A (simulated)
    mkdirSync(join(TEST_ROOT, '.hermes'), { recursive: true })
    writeFileSync(statePath, JSON.stringify({ executedProposals: ['prop-x'] }))

    // 2. Read in process B
    expect(isProposalExecuted(TEST_ROOT, 'prop-x')).toBe(true)
    expect(isProposalExecuted(TEST_ROOT, 'prop-y')).toBe(false)
  })

  it('prevents marking the same proposal twice', () => {
    expect(markProposalExecuted(TEST_ROOT, 'prop-1')).toBe(true)
    expect(markProposalExecuted(TEST_ROOT, 'prop-1')).toBe(false) // already marked
    
    const state = loadLocalState(TEST_ROOT)
    expect(state.executedProposals.filter(p => p === 'prop-1').length).toBe(1)
  })
})

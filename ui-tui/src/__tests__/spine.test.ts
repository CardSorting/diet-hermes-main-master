import { describe, it, expect, beforeEach } from 'vitest'
import { VerifiedExecutionPipeline } from '../local/fabric/spine.js'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { mkdtempSync, rmSync } from 'node:fs'

describe('Bounded Operator Session Pipeline', () => {
  let testRoot: string
  let pipeline: VerifiedExecutionPipeline

  beforeEach(() => {
    testRoot = mkdtempSync(join(tmpdir(), 'hermes-spine-test-'))
    pipeline = new VerifiedExecutionPipeline(testRoot)

    return () => {
      try {
        rmSync(testRoot, { recursive: true, force: true })
      } catch {}
    }
  })

  it('runs complete happy path successfully', async () => {
    const res = await pipeline.runPipelineFlow('add a simple test for this function', true, false)
    expect(res.success).toBe(true)
    expect(pipeline.getSession().status).toBe('completed')
  })

  it('fails gracefully on denied operator approvals', async () => {
    const res = await pipeline.runPipelineFlow('add a simple test for this function', false, false)
    expect(res.success).toBe(false)
    expect(pipeline.getSession().status).toBe('cancelled')
  })

  it('rejects tampered or corrupted cryptographic attestations', async () => {
    const res = await pipeline.runPipelineFlow('add a simple test for this function', true, true)
    expect(res.success).toBe(false)
    expect(pipeline.getSession().status).toBe('failed')
  })

  it('verifies signature verification logic correctly', () => {
    const inputHash = 'input-ok'
    const outputHash = 'output-ok'
    const sig = (pipeline as any).signAttestation('mut-1', inputHash, outputHash)
    
    const isValid = pipeline.verifyAttestation('mut-1', inputHash, outputHash, sig)
    expect(isValid).toBe(true)

    // Tampered verification fails
    const isCorrupt = pipeline.verifyAttestation('mut-1', inputHash, 'mutated-output', sig)
    expect(isCorrupt).toBe(false)
  })
})

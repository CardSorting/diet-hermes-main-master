import { execSync } from 'node:child_process'
import { resolve } from 'node:path'
import { appendAuditLog } from './audit.js'
import { applyCommandPolicy } from './policy.js'

export interface CommandResult {
  success: boolean
  stdout?: string
  stderr?: string
}

export function executeCommandLocally(
  root: string, 
  command: string, 
  cwd: string, 
  proposalId: string, 
  approvalId: string
): CommandResult {
  if (!proposalId || !approvalId) {
    return {
      success: false,
      stderr: 'Execution denied: Missing proposalId or approvalId.'
    }
  }

  // 1. Enforce cwd containment
  const resolvedRoot = resolve(root)
  const targetCwd = cwd ? resolve(root, cwd) : resolvedRoot
  
  if (!targetCwd.startsWith(resolvedRoot)) {
    const errorMsg = `Execution denied: CWD ${targetCwd} escapes workspace root.`
    appendAuditLog(root, {
      action: 'command.run.error',
      proposalId,
      success: false,
      details: { error: errorMsg, command, targetCwd }
    })
    return { success: false, stderr: errorMsg }
  }

  // 2. Apply dangerous command policy
  if (!applyCommandPolicy(command, targetCwd)) {
    const errorMsg = 'Execution denied: Command violates local safety policy.'
    appendAuditLog(root, {
      action: 'command.run.error',
      proposalId,
      success: false,
      details: { error: errorMsg, command }
    })
    return { success: false, stderr: errorMsg }
  }

  appendAuditLog(root, {
    action: 'command.run.start',
    proposalId,
    success: true,
    details: { command, cwd: targetCwd }
  })

  // 3. Execute
  try {
    // maxBuffer prevents memory explosions from runaway commands
    const stdout = execSync(command, { cwd: targetCwd, encoding: 'utf8', maxBuffer: 1024 * 1024 })
    
    appendAuditLog(root, {
      action: 'command.run.complete',
      proposalId,
      success: true,
      details: { stdout }
    })
    
    return { success: true, stdout }
  } catch (e: any) {
    const stdout = e.stdout?.toString()
    const stderr = e.stderr?.toString() || e.message
    
    appendAuditLog(root, {
      action: 'command.run.error',
      proposalId,
      success: false,
      details: { stdout, stderr }
    })

    return { 
      success: false, 
      stdout,
      stderr
    }
  }
}

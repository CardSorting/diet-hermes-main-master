import { writeFileSync, readFileSync, existsSync } from 'node:fs'
import { dirname, join, resolve } from 'node:path'
import { parsePatch, applyPatch } from 'diff'
import { appendAuditLog } from './audit.js'

export interface PatchResult {
  success: boolean
  filesChanged: string[]
  error?: string
}

export function executePatchLocally(
  root: string, 
  files: { path: string, diff: string }[], 
  proposalId: string, 
  approvalId: string
): PatchResult {
  if (!proposalId || !approvalId) {
    return { success: false, filesChanged: [], error: 'Execution denied: Missing proposalId or approvalId.' }
  }

  const resolvedRoot = resolve(root)
  const filesChanged: string[] = []

  appendAuditLog(root, {
    action: 'patch.apply.start',
    proposalId,
    success: true,
    details: { files: files.map(f => f.path) }
  })

  try {
    for (const file of files) {
      const fullPath = resolve(root, file.path)

      if (!fullPath.startsWith(resolvedRoot)) {
        throw new Error(`Patch denied: Path ${fullPath} escapes workspace root.`)
      }

      if (file.diff.startsWith('---') || file.diff.startsWith('+++')) {
        const parsed = parsePatch(file.diff)
        if (!parsed || parsed.length === 0 || !parsed[0].hunks || parsed[0].hunks.length === 0) {
          throw new Error(`Malformed diff for file ${file.path}`)
        }

        const currentContent = existsSync(fullPath) ? readFileSync(fullPath, 'utf8') : ''
        const newContent = applyPatch(currentContent, parsed[0] as any)
        
        if (newContent === false) {
          throw new Error(`Failed to apply patch to ${file.path}`)
        }

        // We use string cast because diff package typing returns string | boolean
        writeFileSync(fullPath, newContent as string, 'utf8')
      } else {
        // Explicitly labeled mock or content replace
        console.warn(`[CONTENT REPLACE] Replacing entire content of ${file.path} because it lacks standard diff headers.`)
        writeFileSync(fullPath, file.diff, 'utf8')
      }

      filesChanged.push(file.path)
    }

    appendAuditLog(root, {
      action: 'patch.apply.complete',
      proposalId,
      success: true,
      details: { filesChanged }
    })

    return { success: true, filesChanged }
  } catch (error: any) {
    appendAuditLog(root, {
      action: 'patch.apply.error',
      proposalId,
      success: false,
      details: { error: error.message }
    })
    console.error('Patch execution failed:', error)
    return { success: false, filesChanged, error: error.message }
  }
}

import { readFileSync, statSync, existsSync } from 'node:fs'
import { resolve, basename } from 'node:path'
import { ContextFile } from '../firebase/contracts.js'
import { execSync } from 'node:child_process'

const MAX_FILE_SIZE = 100 * 1024 // 100KB limit for POC

export function isFileAllowed(root: string, filePath: string): boolean {
  const fullPath = resolve(root, filePath)
  const resolvedRoot = resolve(root)

  if (!fullPath.startsWith(resolvedRoot)) {
    return false // Prevent workspace escape
  }

  const name = basename(fullPath)
  if (name === '.env' || name.endsWith('.env') || name.startsWith('.env.')) {
    return false // Deny secrets
  }

  return true
}

export function readContextFile(root: string, filePath: string): ContextFile | null {
  if (!isFileAllowed(root, filePath)) {
    return null
  }

  const fullPath = resolve(root, filePath)
  if (!existsSync(fullPath)) {
    return null
  }

  try {
    const stats = statSync(fullPath)
    if (stats.size > MAX_FILE_SIZE) {
      return null // Refuse oversized
    }

    const content = readFileSync(fullPath, 'utf8')
    // A simple binary check could go here, but omitted for POC brevity
    if (content.includes('\0')) {
      return null // Ignore binary
    }

    return {
      path: filePath,
      content,
      truncated: false
    }
  } catch (e) {
    console.error(`Failed to read context file ${filePath}:`, e)
    return null
  }
}

export function getGitStatus(root: string) {
  try {
    const branch = execSync('git branch --show-current', { cwd: root, stdio: 'pipe' }).toString().trim()
    const head = execSync('git rev-parse HEAD', { cwd: root, stdio: 'pipe' }).toString().trim()
    const dirty = execSync('git status --porcelain', { cwd: root, stdio: 'pipe' }).toString().trim().length > 0
    return { branch, head, dirty }
  } catch {
    return { branch: 'main', head: 'unknown', dirty: false }
  }
}

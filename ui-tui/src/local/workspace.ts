import { randomUUID } from 'node:crypto'
import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join, basename } from 'node:path'
import { execSync } from 'node:child_process'

import { FirebaseWorkspaceMetadata } from '../firebase/contracts.js'

export interface LocalWorkspaceMetadata {
  workspaceId: string
  workspaceRoot: string
  createdAt: number
  lastSessionId?: string
}

function getHermesDir(root: string): string {
  const dir = join(root, '.hermes')
  if (!existsSync(dir)) {
    mkdirSync(dir, { recursive: true })
  }
  return dir
}

export function getOrCreateWorkspaceMetadata(root: string): LocalWorkspaceMetadata {
  const hermesDir = getHermesDir(root)
  const metaPath = join(hermesDir, 'workspace.json')

  if (existsSync(metaPath)) {
    try {
      const data = readFileSync(metaPath, 'utf8')
      return JSON.parse(data) as LocalWorkspaceMetadata
    } catch {
      // Fall through to recreate
    }
  }

  const meta: LocalWorkspaceMetadata = {
    workspaceId: randomUUID(),
    workspaceRoot: root,
    createdAt: Date.now()
  }

  writeFileSync(metaPath, JSON.stringify(meta, null, 2), 'utf8')
  return meta
}

export function updateWorkspaceMetadata(root: string, update: Partial<LocalWorkspaceMetadata>) {
  const meta = getOrCreateWorkspaceMetadata(root)
  const updated = { ...meta, ...update }
  const metaPath = join(getHermesDir(root), 'workspace.json')
  writeFileSync(metaPath, JSON.stringify(updated, null, 2), 'utf8')
}

export function collectFirebaseWorkspaceMetadata(root: string): FirebaseWorkspaceMetadata {
  const meta = getOrCreateWorkspaceMetadata(root)

  let gitBranch = ''
  let gitHead = ''
  let dirty = false

  try {
    gitBranch = execSync('git rev-parse --abbrev-ref HEAD', { cwd: root, stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
    gitHead = execSync('git rev-parse HEAD', { cwd: root, stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
    
    // Check if dirty
    const status = execSync('git status --porcelain', { cwd: root, stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim()
    dirty = status.length > 0
  } catch {
    // Not a git repo or git not installed
  }

  return {
    workspaceId: meta.workspaceId,
    rootName: basename(root),
    gitBranch: gitBranch || undefined,
    gitHead: gitHead || undefined,
    dirty
  }
}

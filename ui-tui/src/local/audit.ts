import { existsSync, mkdirSync, appendFileSync } from 'node:fs'
import { join } from 'node:path'

import { LocalAuditEntry } from '../firebase/contracts.js'

function getAuditLogPath(root: string): string {
  const logsDir = join(root, '.hermes', 'logs')
  if (!existsSync(logsDir)) {
    mkdirSync(logsDir, { recursive: true })
  }
  return join(logsDir, 'audit.log')
}

export function appendAuditLog(root: string, entry: Omit<LocalAuditEntry, 'timestamp'>) {
  const logPath = getAuditLogPath(root)
  const fullEntry: LocalAuditEntry = {
    timestamp: new Date().toISOString(),
    ...entry
  }
  
  appendFileSync(logPath, JSON.stringify(fullEntry) + '\n', 'utf8')
}

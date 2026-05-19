import { existsSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'

export interface HermesLocalState {
  executedProposals: string[]
}

function getStatePath(root: string): string {
  const stateDir = join(root, '.hermes')
  if (!existsSync(stateDir)) {
    mkdirSync(stateDir, { recursive: true })
  }
  return join(stateDir, 'state.json')
}

export function loadLocalState(root: string): HermesLocalState {
  const path = getStatePath(root)
  if (existsSync(path)) {
    try {
      const content = readFileSync(path, 'utf8')
      return JSON.parse(content)
    } catch {
      // Return default if corrupted
    }
  }
  return { executedProposals: [] }
}

export function saveLocalState(root: string, state: HermesLocalState) {
  const path = getStatePath(root)
  writeFileSync(path, JSON.stringify(state, null, 2), 'utf8')
}

export function markProposalExecuted(root: string, proposalId: string): boolean {
  const state = loadLocalState(root)
  if (state.executedProposals.includes(proposalId)) {
    return false
  }
  state.executedProposals.push(proposalId)
  saveLocalState(root, state)
  return true
}

export function isProposalExecuted(root: string, proposalId: string): boolean {
  const state = loadLocalState(root)
  return state.executedProposals.includes(proposalId)
}

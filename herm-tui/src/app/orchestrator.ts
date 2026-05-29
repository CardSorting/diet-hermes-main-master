// Session orchestrator helpers — live multi-session switcher (upstream ui-tui parity).

import type { SessionActiveItem } from "../context/wire"

export const VISIBLE = 12

export const STATUS_GLYPH: Record<string, string> = {
  idle: "✓",
  starting: "…",
  waiting: "?",
  working: "▶",
}

export const STATUS_LABEL: Record<string, string> = {
  idle: "idle",
  starting: "starting",
  waiting: "waiting",
  working: "working",
}

export const shortModel = (model = "") => model.replace(/^.*\//, "") || "model?"

export const activeSessionCountLabel = (count: number) =>
  `${count} live ${count === 1 ? "session" : "sessions"}`

export const newSessionRowIndex = (sessionCount: number) => Math.max(0, sessionCount)

export const isNewSessionRow = (index: number, sessionCount: number) =>
  index >= newSessionRowIndex(sessionCount)

export const clampOrchestratorSelection = (index: number, sessionCount: number) =>
  Math.max(0, Math.min(index, newSessionRowIndex(sessionCount)))

export const currentSessionSelectionIndex = (
  sessions: readonly SessionActiveItem[],
  currentSessionId: string | null,
) => {
  const index = sessions.findIndex(
    s => Boolean(s.current) || (!!currentSessionId && s.id === currentSessionId),
  )
  return index >= 0 ? index : 0
}

export const windowOffset = (total: number, selected: number, visible = VISIBLE) => {
  if (total <= visible) return 0
  const clamped = Math.max(0, Math.min(selected, total - 1))
  return Math.max(0, Math.min(clamped - Math.floor(visible / 2), total - visible))
}

export const orchestratorVisibleRowIndexes = (
  sessionCount: number,
  selected: number,
  visible = VISIBLE,
) => {
  const total = Math.max(0, sessionCount) + 1
  const clamped = clampOrchestratorSelection(selected, sessionCount)
  const offset = windowOffset(total, clamped, visible)
  const count = Math.min(visible, total - offset)
  return Array.from({ length: count }, (_, i) => offset + i)
}

export type CloseFallback =
  | { action: "activate"; sessionId: string }
  | { action: "new" }
  | { action: "stay" }

export const closeFallbackAfterClose = (
  closedId: string,
  currentSessionId: string | null,
  remaining: readonly SessionActiveItem[],
): CloseFallback => {
  if (!currentSessionId || closedId !== currentSessionId) return { action: "stay" }
  const next = remaining.find(s => s.id !== closedId)
  return next ? { action: "activate", sessionId: next.id } : { action: "new" }
}

export const draftTitleFromPrompt = (prompt: string, max = 64) => {
  const compact = prompt.replace(/\s+/g, " ").trim()
  if (compact.length <= max) return compact
  return `${compact.slice(0, Math.max(0, max - 1)).trimEnd()}…`
}

export const draftModelArgFromPickerValue = (value: string) => {
  const parts = value.trim().split(/\s+/).filter(Boolean)
  const kept: string[] = []
  for (const part of parts) {
    if (part === "--tui-session" || part === "--global") continue
    kept.push(part)
  }
  return kept.join(" ")
}

export const draftModelNameFromArg = (value: string) => {
  const parts = draftModelArgFromPickerValue(value).split(/\s+/).filter(Boolean)
  const modelParts: string[] = []
  for (let i = 0; i < parts.length; i++) {
    const part = parts[i]!
    if (part === "--provider") { i++; continue }
    if (part.startsWith("--")) continue
    modelParts.push(part)
  }
  return modelParts.join(" ").trim()
}

export const draftModelDisplayLabel = (value: string) => {
  const modelName = draftModelNameFromArg(value)
  return modelName ? shortModel(modelName) : "current/default"
}

// Live session orchestrator overlay — switch between in-process gateway sessions.

import { useState, useEffect, useCallback, useRef, type Dispatch, type SetStateAction } from "react"
import { useKeyboard, useTerminalDimensions } from "@opentui/react"
import { useTheme } from "../theme"
import { useGateway } from "../context/gateway"
import type { SessionActiveItem, SessionActiveListResponse, SessionCloseResponse } from "../context/wire"
import { handleListKey } from "../keys/list"
import { useKeys } from "../keys"
import {
  VISIBLE,
  STATUS_GLYPH,
  STATUS_LABEL,
  shortModel,
  activeSessionCountLabel,
  isNewSessionRow,
  clampOrchestratorSelection,
  currentSessionSelectionIndex,
  orchestratorVisibleRowIndexes,
  closeFallbackAfterClose,
  draftTitleFromPrompt,
  draftModelArgFromPickerValue,
  draftModelDisplayLabel,
  windowOffset,
} from "../app/orchestrator"

const MIN_WIDTH = 64
const MAX_WIDTH = 128

type Props = {
  currentSessionId: string
  draft: string
  setDraft: (v: string) => void
  draftModel: string
  onCancel: () => void
  onClose: (id: string) => Promise<SessionCloseResponse | null>
  onNew: () => void
  onNewPrompt: (prompt: string, modelArg?: string) => void
  onPickModel: () => void
  onSelect: (id: string) => void
}

export const ActiveSessionSwitcher = (props: Props) => {
  const gw = useGateway()
  const theme = useTheme().theme
  const keys = useKeys()
  const dims = useTerminalDimensions()
  const width = Math.max(MIN_WIDTH, Math.min(MAX_WIDTH, dims.width - 6))

  const [items, setItems] = useState<SessionActiveItem[]>([])
  const [err, setErr] = useState("")
  const [sel, setSel] = useState(0)
  const [loading, setLoading] = useState(true)
  const [closingId, setClosingId] = useState("")
  const initialSelectionAppliedRef = useRef(false)

  const load = useCallback(async (quiet = false) => {
    if (!quiet) setLoading(true)
    try {
      const r = await gw.request<SessionActiveListResponse>("session.active_list", {
        current_session_id: props.currentSessionId,
      })
      const next = r.sessions ?? []
      const init = !initialSelectionAppliedRef.current
      initialSelectionAppliedRef.current = true
      setItems(next)
      setSel(s =>
        init
          ? clampOrchestratorSelection(
              currentSessionSelectionIndex(next, props.currentSessionId),
              next.length,
            )
          : clampOrchestratorSelection(s, next.length),
      )
      setErr("")
      setLoading(false)
      return next
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e))
      setLoading(false)
      return []
    }
  }, [gw, props.currentSessionId])

  useEffect(() => {
    void load()
    const timer = setInterval(() => void load(true), 1500)
    return () => clearInterval(timer)
  }, [load])

  const submitDraft = useCallback(() => {
    const prompt = props.draft.trim()
    if (!prompt) return
    props.setDraft("")
    props.onNewPrompt(
      prompt,
      props.draftModel ? draftModelArgFromPickerValue(props.draftModel) : undefined,
    )
  }, [props])

  const closeSelected = useCallback(async () => {
    const target = items[sel]
    if (!target || isNewSessionRow(sel, items.length) || closingId) return
    setErr("")
    setClosingId(target.id)
    try {
      const result = await props.onClose(target.id)
      const closed = Boolean(result?.closed ?? result?.ok)
      if (!closed) {
        setErr("session was already closed")
        return
      }
      const remaining = await load(true)
      const fallback = closeFallbackAfterClose(
        target.id,
        props.currentSessionId,
        remaining,
      )
      if (fallback.action === "activate") props.onSelect(fallback.sessionId)
      else if (fallback.action === "new") props.onNew()
      else setSel(s => clampOrchestratorSelection(s, remaining.length))
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e))
    } finally {
      setClosingId("")
    }
  }, [closingId, items, load, props, sel])

  const newSelected = isNewSessionRow(sel, items.length)
  const draftHasText = Boolean(props.draft.trim())
  const totalRows = items.length + 1
  const count = totalRows

  useListKeysOrchestrator({
    active: !loading,
    count,
    setSel,
    items,
    sel,
    newSelected,
    draftHasText,
    submitDraft,
    onActivate: () => {
      if (newSelected) {
        if (draftHasText) submitDraft()
        else props.onNew()
        return
      }
      const row = items[sel]
      if (row) props.onSelect(row.id)
    },
    onRefresh: () => void load(),
    onCloseRow: () => void closeSelected(),
    onNew: () => props.onNew(),
    onCancel: props.onCancel,
    onModelPicker: props.onPickModel,
  })

  if (loading) {
    return (
      <box flexDirection="column" width={width} padding={1}>
        <text fg={theme.textMuted}>loading session orchestrator…</text>
      </box>
    )
  }

  const offset = windowOffset(totalRows, sel, VISIBLE)
  const visibleRows = orchestratorVisibleRowIndexes(items.length, sel, VISIBLE)

  return (
    <box flexDirection="column" width={width} padding={1}
         border borderColor={theme.primary} backgroundColor={theme.backgroundPanel}>
      <box height={1}><text fg={theme.primary}><strong>Session Orchestrator</strong></text></box>
      <box height={1}><text fg={theme.textMuted}>{activeSessionCountLabel(items.length)}</text></box>
      {err ? <box height={1}><text fg={theme.error}>error: {err}</text></box> : null}
      {!items.length ? (
        <box height={1}>
          <text fg={theme.textMuted}>
            no live sessions — closed TUIs only leave resumable transcripts
          </text>
        </box>
      ) : null}
      {offset > 0 ? (
        <box height={1}><text fg={theme.textMuted}>↑ {offset} more</text></box>
      ) : null}

      {visibleRows.map(i => {
        const selected = sel === i
        const fg = selected ? theme.text : theme.textMuted
        const bg = selected ? theme.backgroundElement : undefined

        if (isNewSessionRow(i, items.length)) {
          const title = draftTitleFromPrompt(props.draft) || "Start a new live session"
          return (
            <box key="new" height={1} flexDirection="row" backgroundColor={bg} overflow="hidden">
              <box width={2} flexShrink={0}><text fg={fg}>{selected ? "▸ " : "  "}</text></box>
              <box width={5} flexShrink={0}><text fg={theme.accent}><strong>+</strong></text></box>
              <box width={11} flexShrink={0}><text fg={theme.accent}>new</text></box>
              <box width={11} flexShrink={0}><text fg={fg}>✎ draft</text></box>
              <box width={18} flexShrink={0}><text fg={fg}>{draftModelDisplayLabel(props.draftModel)}</text></box>
              <box flexGrow={1} minWidth={0} overflow="hidden">
                <text fg={fg} wrapMode="none">{title}</text>
              </box>
            </box>
          )
        }

        const s = items[i]!
        const status = s.status ?? "idle"
        const current = s.current || s.id === props.currentSessionId
        const title = closingId === s.id ? "closing…" : (s.title || s.preview || "(untitled)")
        const statusColor =
          status === "working" ? theme.success
            : status === "waiting" ? theme.warning
              : fg

        return (
          <box key={s.id} height={1} flexDirection="row" backgroundColor={bg} overflow="hidden">
            <box width={2} flexShrink={0}><text fg={fg}>{selected ? "▸ " : "  "}</text></box>
            <box width={5} flexShrink={0}><text fg={fg}>{String(i + 1).padStart(2)}.</text></box>
            <box width={11} flexShrink={0}>
              <text fg={current ? theme.accent : fg} wrapMode="none">
                {current ? "current" : s.id.slice(0, 10)}
              </text>
            </box>
            <box width={11} flexShrink={0}>
              <text fg={statusColor} wrapMode="none">
                {STATUS_GLYPH[status] ?? "·"} {STATUS_LABEL[status] ?? status}
              </text>
            </box>
            <box width={18} flexShrink={0}><text fg={fg} wrapMode="none">{shortModel(s.model)}</text></box>
            <box flexGrow={1} minWidth={0} overflow="hidden">
              <text fg={fg} wrapMode="none">{title}</text>
            </box>
          </box>
        )
      })}

      {offset + VISIBLE < totalRows ? (
        <box height={1}><text fg={theme.textMuted}>↓ {totalRows - offset - VISIBLE} more</text></box>
      ) : null}

      {newSelected ? (
        <>
          <box height={1} />
          <box height={1} flexDirection="row" overflow="hidden">
            <box flexShrink={0}><text fg={theme.textMuted}>prompt › </text></box>
            <box flexGrow={1} minWidth={0} height={1}>
              <input
                value={props.draft}
                onInput={props.setDraft}
                onSubmit={submitDraft}
                focused
                textColor={theme.text}
                backgroundColor={theme.backgroundElement}
                focusedBackgroundColor={theme.backgroundElement}
              />
            </box>
          </box>
          <box height={1}>
            <text fg={theme.textMuted}>
              Enter start · Tab model · model: {draftModelDisplayLabel(props.draftModel)}
            </text>
          </box>
        </>
      ) : (
        <box height={1}>
          <text fg={theme.textMuted}>Enter switch · Ctrl+D close · select +new to draft</text>
        </box>
      )}
      <box height={1}>
        <text fg={theme.textMuted}>↑↓ move · Ctrl+N new · Ctrl+R refresh · Esc close</text>
      </box>
    </box>
  )
}

function useListKeysOrchestrator(o: {
  active: boolean
  count: number
  setSel: Dispatch<SetStateAction<number>>
  items: SessionActiveItem[]
  sel: number
  newSelected: boolean
  draftHasText: boolean
  submitDraft: () => void
  onActivate: () => void
  onRefresh: () => void
  onCloseRow: () => void
  onNew: () => void
  onCancel: () => void
  onModelPicker: () => void
}) {
  const keys = useKeys()

  useKeyboard((key) => {
    if (!o.active) return

    const ch = key.name.length === 1 ? key.name : ""
    const ctrl = (letter: string) =>
      key.ctrl && (ch === letter || ch === String.fromCharCode(letter.charCodeAt(0) - 96))

    if (key.name === "escape") {
      o.onCancel()
      key.stopPropagation()
      return
    }
    if (ctrl("n")) {
      o.onNew()
      key.stopPropagation()
      return
    }
    if (ctrl("r")) {
      o.onRefresh()
      key.stopPropagation()
      return
    }
    if (key.name === "tab" && o.newSelected) {
      o.onModelPicker()
      key.stopPropagation()
      return
    }
    if (ctrl("d") && !o.newSelected) {
      o.onCloseRow()
      key.stopPropagation()
      return
    }

    if (o.newSelected && o.draftHasText) return

    if (
      handleListKey(keys, key, {
        count: o.count,
        setSel: o.setSel,
        onActivate: o.onActivate,
        onRefresh: o.onRefresh,
      })
    ) {
      key.stopPropagation()
    }
  })
}

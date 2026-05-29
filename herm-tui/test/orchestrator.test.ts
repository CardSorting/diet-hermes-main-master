import { describe, expect, it } from "bun:test"
import type { SessionActiveItem } from "../src/context/wire"
import {
  activeSessionCountLabel,
  clampOrchestratorSelection,
  closeFallbackAfterClose,
  currentSessionSelectionIndex,
  draftModelArgFromPickerValue,
  draftModelDisplayLabel,
  draftTitleFromPrompt,
  isNewSessionRow,
  newSessionRowIndex,
  orchestratorVisibleRowIndexes,
} from "../src/app/orchestrator"

describe("session orchestrator helpers", () => {
  it("labels live sessions compactly", () => {
    expect(activeSessionCountLabel(0)).toBe("0 live sessions")
    expect(activeSessionCountLabel(1)).toBe("1 live session")
    expect(activeSessionCountLabel(3)).toBe("3 live sessions")
  })

  it("highlights the current live session when the picker opens", () => {
    const sessions = [
      { id: "first", status: "idle" },
      { id: "second", status: "working", current: true },
      { id: "third", status: "idle" },
    ] satisfies SessionActiveItem[]

    expect(currentSessionSelectionIndex(sessions, "second")).toBe(1)
    expect(
      currentSessionSelectionIndex(
        [{ id: "first", status: "idle" }, { id: "third", status: "idle" }],
        "third",
      ),
    ).toBe(1)
    expect(currentSessionSelectionIndex(sessions, "missing")).toBe(1)
    expect(currentSessionSelectionIndex([], "missing")).toBe(0)
  })

  it("adds a selectable New row after live sessions", () => {
    expect(newSessionRowIndex(0)).toBe(0)
    expect(newSessionRowIndex(3)).toBe(3)
    expect(clampOrchestratorSelection(-5, 2)).toBe(0)
    expect(clampOrchestratorSelection(99, 2)).toBe(2)
    expect(isNewSessionRow(0, 0)).toBe(true)
    expect(isNewSessionRow(1, 2)).toBe(false)
    expect(isNewSessionRow(2, 2)).toBe(true)
    expect(orchestratorVisibleRowIndexes(3, 3, 12)).toEqual([0, 1, 2, 3])
    expect(orchestratorVisibleRowIndexes(13, 13, 12)).toContain(13)
  })

  it("selects a safe fallback after closing the current live session", () => {
    const remaining = [
      { id: "next", status: "idle" },
      { id: "other", status: "working" },
    ] satisfies SessionActiveItem[]

    expect(closeFallbackAfterClose("other", "current", remaining)).toEqual({ action: "stay" })
    expect(closeFallbackAfterClose("current", "current", remaining)).toEqual({
      action: "activate",
      sessionId: "next",
    })
    expect(closeFallbackAfterClose("current", "current", [])).toEqual({ action: "new" })
  })

  it("turns model picker values into session-scoped draft model args", () => {
    expect(draftModelArgFromPickerValue("kimi-k2.6 --provider ollama-cloud --tui-session")).toBe(
      "kimi-k2.6 --provider ollama-cloud",
    )
    expect(draftModelArgFromPickerValue("openai/gpt-5.5 --provider openai-codex --global")).toBe(
      "openai/gpt-5.5 --provider openai-codex",
    )
  })

  it("shows clean draft model labels", () => {
    expect(draftModelDisplayLabel("kimi-k2.6 --provider ollama-cloud --tui-session")).toBe("kimi-k2.6")
    expect(draftModelDisplayLabel("openai/gpt-5.5 --provider openai-codex --global")).toBe("gpt-5.5")
    expect(draftModelDisplayLabel("")).toBe("current/default")
  })

  it("builds a compact title from the orchestrator prompt", () => {
    expect(draftTitleFromPrompt("  Build the websocket orchestrator panel.  ", 24)).toBe(
      "Build the websocket orc…",
    )
  })
})

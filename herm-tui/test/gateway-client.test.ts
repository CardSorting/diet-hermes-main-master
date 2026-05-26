import { describe, expect, test } from "bun:test"
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "fs"
import { join, resolve } from "path"
import { tmpdir } from "os"
import { GatewayClient, python } from "../src/context/gateway-client"

const withEnv = <T>(key: string, value: string | undefined, fn: () => T): T => {
  const prev = process.env[key]
  if (value === undefined) delete process.env[key]
  else process.env[key] = value
  try { return fn() }
  finally {
    if (prev === undefined) delete process.env[key]
    else process.env[key] = prev
  }
}

const tmp = () => mkdtempSync(join(tmpdir(), "herm-gateway-"))

describe("batched events", () => {
  test("dispatch unwraps params.events into individual event emissions", () => {
    const c = new GatewayClient()
    const seen: string[] = []
    c.on("event", ev => seen.push(ev.type))
    c.drain()

    const dispatch = (c as unknown as { dispatch(m: Record<string, unknown>): void }).dispatch
    dispatch.call(c, {
      method: "event",
      params: {
        events: [
          { type: "message.delta", session_id: "s1", payload: { text: "a" } },
          { type: "status.update", session_id: "s1", payload: { text: "busy" } },
        ],
      },
    })

    expect(seen).toEqual(["message.delta", "status.update"])
  })
})

describe("python", () => {
  test("uses HERMES_PYTHON when set", () => {
    withEnv("HERMES_PYTHON", resolve("custom", "python"), () => {
      expect(python(resolve("root"), "win32")).toBe(resolve("custom", "python"))
    })
  })

  test("resolves Windows virtualenv layout", () => {
    withEnv("HERMES_PYTHON", undefined, () => {
      withEnv("VIRTUAL_ENV", undefined, () => {
        const root = tmp()
        try {
          const bin = join(root, "venv", "Scripts", "python.exe")
          mkdirSync(join(root, "venv", "Scripts"), { recursive: true })
          writeFileSync(bin, "")
          expect(python(root, "win32")).toBe(bin)
        } finally {
          rmSync(root, { recursive: true, force: true })
        }
      })
    })
  })

  test("resolves POSIX virtualenv layout", () => {
    withEnv("HERMES_PYTHON", undefined, () => {
      withEnv("VIRTUAL_ENV", undefined, () => {
        const root = tmp()
        try {
          const bin = join(root, "venv", "bin", "python")
          mkdirSync(join(root, "venv", "bin"), { recursive: true })
          writeFileSync(bin, "")
          expect(python(root, "linux")).toBe(bin)
        } finally {
          rmSync(root, { recursive: true, force: true })
        }
      })
    })
  })
})

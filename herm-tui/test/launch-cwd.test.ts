import { describe, expect, test } from "bun:test"
import { mkdirSync, mkdtempSync, realpathSync, rmSync } from "fs"
import { join, resolve } from "path"
import { tmpdir } from "os"
import { isBundlerCwd, resolveLaunchCwd } from "../src/utils/launch-cwd"

const withEnv = (patch: Record<string, string | undefined>, fn: () => void) => {
  const prev: Record<string, string | undefined> = {}
  for (const [k, v] of Object.entries(patch)) {
    prev[k] = process.env[k]
    if (v === undefined) delete process.env[k]
    else process.env[k] = v
  }
  try { fn() }
  finally {
    for (const [k, v] of Object.entries(prev)) {
      if (v === undefined) delete process.env[k]
      else process.env[k] = v
    }
  }
}

describe("resolveLaunchCwd", () => {
  test("prefers PWD over HERMES_CWD when cwd is herm-tui bundle", () => {
    const base = mkdtempSync(join(tmpdir(), "herm-launch-"))
    const checkout = join(base, "agent")
    const bundle = join(checkout, "herm-tui")
    const project = join(base, "client")
    const stale = join(base, "stale")
    mkdirSync(bundle, { recursive: true })
    mkdirSync(project)
    mkdirSync(stale)
    const resolvedProject = realpathSync(project)
    const prev = process.cwd()
    try {
      process.chdir(bundle)
      withEnv(
        {
          HERMES_CWD: realpathSync(stale),
          TERMINAL_CWD: undefined,
          PWD: resolvedProject,
        },
        () => {
          expect(resolveLaunchCwd(checkout)).toBe(resolvedProject)
        },
      )
    } finally {
      process.chdir(prev)
      rmSync(base, { recursive: true, force: true })
    }
  })

  test("uses HERMES_CWD when process cwd is herm-tui bundle", () => {
    const base = mkdtempSync(join(tmpdir(), "herm-launch-"))
    const checkout = join(base, "agent")
    const bundle = join(checkout, "herm-tui")
    const project = join(base, "client")
    mkdirSync(bundle, { recursive: true })
    mkdirSync(project)
    const resolvedProject = realpathSync(project)
    const prev = process.cwd()
    try {
      process.chdir(bundle)
      withEnv(
        {
          HERMES_CWD: resolvedProject,
          TERMINAL_CWD: undefined,
          PWD: undefined,
        },
        () => {
          expect(resolveLaunchCwd(checkout)).toBe(resolvedProject)
        },
      )
    } finally {
      process.chdir(prev)
      rmSync(base, { recursive: true, force: true })
    }
  })

  test("isBundlerCwd matches checkout and bundle only", () => {
    const base = mkdtempSync(join(tmpdir(), "herm-bundler-"))
    const checkout = join(base, "agent")
    const bundle = join(checkout, "herm-tui")
    const decoy = join(base, "not-herm-tui")
    mkdirSync(bundle, { recursive: true })
    mkdirSync(decoy)
    try {
      expect(isBundlerCwd(checkout, checkout)).toBe(true)
      expect(isBundlerCwd(bundle, checkout)).toBe(true)
      expect(isBundlerCwd(decoy, checkout)).toBe(false)
    } finally {
      rmSync(base, { recursive: true, force: true })
    }
  })
})

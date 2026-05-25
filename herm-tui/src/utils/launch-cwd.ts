import { realpathSync, statSync } from "fs"
import { join, resolve } from "path"

const CWD_PLACEHOLDERS = new Set([".", "auto", "cwd"])

const tryDir = (raw: string | undefined): string | null => {
  const text = raw?.trim()
  if (!text || CWD_PLACEHOLDERS.has(text)) return null
  try {
    const p = resolve(text)
    const st = statSync(p, { throwIfNoEntry: false })
    if (!st?.isDirectory()) return null
    return realpathSync(p)
  } catch { /* invalid */ }
  return null
}

export const isBundlerCwd = (proc: string, agentRoot: string): boolean => {
  const root = agentRoot.trim()
  if (!root) {
    const p = realpath(proc)
    return p.endsWith("/herm-tui") || p.endsWith("\\herm-tui")
  }
  const norm = realpath(proc)
  const checkout = realpath(root)
  const bundle = realpath(join(root, "herm-tui"))
  return norm === checkout || norm === bundle
}

const realpath = (p: string): string => {
  try {
    return realpathSync(p)
  } catch {
    return resolve(p)
  }
}

/** Working directory for tools/context — not the herm-tui bundle dir. */
export const resolveLaunchCwd = (agentRoot: string): string => {
  const proc = process.cwd()
  const bundler = isBundlerCwd(proc, agentRoot)

  const ordered: string[] = []
  const hermes = process.env.HERMES_CWD?.trim()
  const pwd = process.env.PWD?.trim()
  const term = process.env.TERMINAL_CWD?.trim()
  if (bundler) {
    if (pwd) ordered.push(pwd)
    if (hermes) ordered.push(hermes)
    if (term) ordered.push(term)
    ordered.push(proc)
  } else {
    ordered.push(proc)
    if (pwd) ordered.push(pwd)
    if (hermes) ordered.push(hermes)
    if (term) ordered.push(term)
  }

  const seen = new Set<string>()
  const root = agentRoot.trim()
  for (const raw of ordered) {
    const p = tryDir(raw)
    if (!p || seen.has(p)) continue
    seen.add(p)
    if (bundler && root && isBundlerCwd(p, root)) continue
    return p
  }
  return proc
}

/** Cwd for UI before gateway.session.info arrives (never the bundle dir). */
export const displayWorkspaceCwd = (agentRoot?: string): string => {
  const root = agentRoot?.trim() || process.env.HERMES_AGENT_ROOT?.trim() || process.env.HERMES_PYTHON_SRC_ROOT?.trim() || ""
  const pinned = process.env.TERMINAL_CWD?.trim() || process.env.HERMES_CWD?.trim()
  if (pinned && !CWD_PLACEHOLDERS.has(pinned)) {
    const p = tryDir(pinned)
    if (p) return p
  }
  return resolveLaunchCwd(root)
}

/** Pin process env when Herm is started without the Python wrapper (bun dev). */
export const ensureLaunchCwdEnv = (agentRoot: string): string => {
  const cwd = resolveLaunchCwd(agentRoot)
  process.env.HERMES_CWD = cwd
  process.env.TERMINAL_CWD = cwd
  process.env._HERMES_TUI_GATEWAY = "1"
  return cwd
}

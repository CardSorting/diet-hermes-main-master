import { resolve } from 'node:path'

export function applyCommandPolicy(command: string, root: string): boolean {
  const deniedPatterns = [
    /^rm -rf\b/,
    /^sudo\b/,
    /^chmod -R\b/,
    /curl.*\|.*sh/,
    /wget.*\|.*sh/,
    /^git push --force\b/,
    /\b(shutdown|reboot|passwd|dd|mkfs|init|killall)\b/
  ]

  for (const pattern of deniedPatterns) {
    if (pattern.test(command)) {
      console.warn(`Command denied by policy: ${command}`)
      return false
    }
  }

  // Parse arguments to detect path escaping
  const resolvedRoot = resolve(root)
  
  // Simple argument extraction (handles basic quoting)
  const args: string[] = []
  let current = ''
  let inQuote: string | null = null
  for (let i = 0; i < command.length; i++) {
    const char = command[i]
    if ((char === '"' || char === "'") && (i === 0 || command[i - 1] !== '\\')) {
      if (inQuote === char) {
        inQuote = null
      } else if (!inQuote) {
        inQuote = char
      }
    } else if (char === ' ' && !inQuote) {
      if (current) {
        args.push(current)
        current = ''
      }
    } else {
      current += char
    }
  }
  if (current) args.push(current)

  // Analyze each argument
  for (const arg of args) {
    // Skip system binaries (like /bin/sh or /usr/bin/git)
    const isSystemBinary = arg.startsWith('/bin/') || arg.startsWith('/usr/') || arg.startsWith('/opt/homebrew/')
    
    // Look for relative or absolute paths escaping workspace root
    if (arg.includes('..') || (arg.startsWith('/') && !isSystemBinary)) {
      const resolvedPath = resolve(root, arg)
      if (!resolvedPath.startsWith(resolvedRoot)) {
        console.warn(`Command denied: Path argument '${arg}' escapes workspace root.`)
        return false
      }
    }
  }

  return true
}

import type { ThemeColors } from './theme.js'

const RICH_RE = /\[(?:bold\s+)?(?:dim\s+)?(#(?:[0-9a-fA-F]{3,8}))\]([\s\S]*?)(\[\/\])/g

export function parseRichMarkup(markup: string): Line[] {
  const lines: Line[] = []

  for (const raw of markup.split('\n')) {
    const trimmed = raw.trimEnd()

    if (!trimmed) {
      lines.push(['', ' '])

      continue
    }

    const matches = [...trimmed.matchAll(RICH_RE)]

    if (!matches.length) {
      lines.push(['', trimmed])

      continue
    }

    let cursor = 0

    for (const m of matches) {
      const before = trimmed.slice(cursor, m.index)

      if (before) {
        lines.push(['', before])
      }

      lines.push([m[1]!, m[2]!])
      cursor = m.index! + m[0].length
    }

    if (cursor < trimmed.length) {
      lines.push(['', trimmed.slice(cursor)])
    }
  }

  return lines
}

/** DietCode fork fallback when gateway skin logo is not loaded yet. */
const DIETCODE_LOGO_ART = [
  '  o   o   o   o   o   o   o   o',
  '╔══════════════════════════════════════╗',
  '║ DIETCODE — zero-calorie diffs        ║',
  '║ ██████╗ ██╗███████╗████████╗         ║',
  '║ ██╔══██╗██║██╔════╝╚══██╔══╝         ║',
  '║ ██║  ██║██║█████╗     ██║            ║',
  '║ ██████╔╝██║███████╗   ██║            ║',
  '║ ██████╗ ██████╗ ██████╗ ███████╗     ║',
  '║ ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝     ║',
  '╚══════════════════════════════════════╝',
  '  o   o   o   o   o   o   o   o'
]

const LOGO_ART = DIETCODE_LOGO_ART

const DIETCODE_CAN_ART = [
  '        o       o       o',
  '         .-------.',
  '        /  DIET   \\',
  '       |   CODE   |',
  '        \\  0 cal  /',
  "         '-------'",
  '            | |',
  '        ~  o o o  ~',
  '     ~~~~~~~~~~~~~~~~~',
  '   carbonated · ready to pour'
]

const CADUCEUS_ART = DIETCODE_CAN_ART

const LOGO_GRADIENT = [0, 1, 1, 2, 2, 1, 1, 2, 2, 0, 0] as const
const CADUC_GRADIENT = [2, 1, 0, 0, 1, 2, 1, 0, 0, 2] as const

const colorize = (art: string[], gradient: readonly number[], c: ThemeColors): Line[] => {
  const p = [c.primary, c.accent, c.border, c.muted]

  return art.map((text, i) => [p[gradient[i]!] ?? c.muted, text])
}

export const LOGO_WIDTH = 40
export const CADUCEUS_WIDTH = 28

export const logo = (c: ThemeColors, customLogo?: string): Line[] =>
  customLogo ? parseRichMarkup(customLogo) : colorize(LOGO_ART, LOGO_GRADIENT, c)

export const caduceus = (c: ThemeColors, customHero?: string): Line[] =>
  customHero ? parseRichMarkup(customHero) : colorize(CADUCEUS_ART, CADUC_GRADIENT, c)

export const artWidth = (lines: Line[]) => lines.reduce((m, [, t]) => Math.max(m, t.length), 0)

type Line = [string, string]

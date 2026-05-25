/** Soda-themed status copy for DietCode TUI (mirrors hermes_cli/soda_callbacks.py). */

export const SODA_TAGLINES = [
  'Just for the diff of it.',
  'Break builds, not hearts.',
  'The pause that refreshes your CI.',
  'Live fizzfully. Ship responsibly.',
  'Zero-calorie diffs · maximum fizz.',
  'Crack open a fresh patch.'
] as const

export const SODA_STATUS_IDLE = [
  'Ready to pour…',
  'Can sealed — awaiting your tab pull',
  'Bubbles settled — type to carbonate'
] as const

export const SODA_TOOL_DONE = [
  'poured clean',
  'all fizzy',
  'tab sealed',
  'zero spill'
] as const

/** Bubble spinner glyphs (fixed display width). */
export const FIZZ_FRAMES = ['·', '∘', '○', '◌', '◎', '◉', '●', '◉', '◎', '◌', '○', '∘'] as const

export function pickSoda<T extends readonly string[]>(items: T): T[number] {
  return items[Math.floor(Math.random() * items.length)]!
}

export function pickSodaTagline(): string {
  return pickSoda(SODA_TAGLINES)
}

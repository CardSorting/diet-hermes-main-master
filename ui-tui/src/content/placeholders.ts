import { pick } from '../lib/text.js'

export const PLACEHOLDERS = [
  'Pour in a task — just for the diff of it…',
  'Try "explain this project in plain English"',
  'Try "make a safe patch for…"',
  'Try "what should I run first?"',
  'Try "/help" for commands',
  'Try "fix the failing checks"',
  'Try "walk me through the main folders"'
]

export const PLACEHOLDER = pick(PLACEHOLDERS)

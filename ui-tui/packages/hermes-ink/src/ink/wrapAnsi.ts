import wrapAnsiNpm from 'wrap-ansi'

type WrapAnsiOptions = {
  hard?: boolean
  wordWrap?: boolean
  trim?: boolean
}

const wrapAnsiBun = typeof Bun !== 'undefined' && typeof Bun.wrapAnsi === 'function' ? Bun.wrapAnsi : null

const wrapAnsiNpmFunc = typeof wrapAnsiNpm === 'function' ? wrapAnsiNpm : (wrapAnsiNpm as any).default

const wrapAnsi: (input: string, columns: number, options?: WrapAnsiOptions) => string = wrapAnsiBun ?? wrapAnsiNpmFunc

export { wrapAnsi }

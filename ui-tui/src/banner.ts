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

// Black-and-white block art: no color slots, rendered in the terminal's
// default foreground so the wordmark stays monochrome in every theme.
const LOGO_ART = [
  '██████╗ ██████╗  ██████╗ ███╗   ███╗███████╗████████╗██╗  ██╗███████╗██╗   ██╗███████╗',
  '██╔══██╗██╔══██╗██╔═══██╗████╗ ████║██╔════╝╚══██╔══╝██║  ██║██╔════╝██║   ██║██╔════╝',
  '██████╔╝██████╔╝██║   ██║██╔████╔██║█████╗     ██║   ███████║█████╗  ██║   ██║███████╗',
  '██╔═══╝ ██╔══██╗██║   ██║██║╚██╔╝██║██╔══╝     ██║   ██╔══██║██╔══╝  ██║   ██║╚════██║',
  '██║     ██║  ██║╚██████╔╝██║ ╚═╝ ██║███████╗   ██║   ██║  ██║███████╗╚██████╔╝███████║',
  '╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚═╝     ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝ ╚═════╝ ╚══════╝'
]

// The torch of Prometheus: black-and-white hero art for the left panel.
const TORCH_ART = [
  '        ▄▄▄▄▄▄',
  '       █▀▀▀▀▀▀█',
  '      █  ▄▄▄▄  █',
  '     █  █▀▀▀▀█  █',
  '    █   █ ██ █   █',
  '   █    ▀▀██▀▀    █',
  '  █                █',
  '  █      ████      █',
  '   ▀█▄▄▄██████▄▄▄█▀',
  '     ▀▀▀▀▀▀▀▀▀▀▀▀'
]

const monochrome = (art: string[]): Line[] => art.map((text) => ['', text])

export const LOGO_WIDTH = Math.max(...LOGO_ART.map(line => line.length))
export const TORCH_WIDTH = Math.max(...TORCH_ART.map(line => line.length))

export const logo = (_c: ThemeColors, customLogo?: string): Line[] =>
  customLogo ? parseRichMarkup(customLogo) : monochrome(LOGO_ART)

export const torch = (_c: ThemeColors, customHero?: string): Line[] =>
  customHero ? parseRichMarkup(customHero) : monochrome(TORCH_ART)

export const artWidth = (lines: Line[]) => lines.reduce((m, [, t]) => Math.max(m, t.length), 0)

type Line = [string, string]

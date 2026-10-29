import { format, parseISO } from 'date-fns'

export const fmtInt = (n: number | null | undefined) => (n == null ? '–' : Math.round(n).toLocaleString('en-US'))

export const fmtNum = (n: number | null | undefined, d = 1) =>
  n == null || Number.isNaN(n) ? '–' : n.toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d })

export const fmtPct = (n: number | null | undefined, d = 1, sign = false) => {
  if (n == null || Number.isNaN(n)) return '–'
  const s = n.toLocaleString('en-US', { maximumFractionDigits: d, minimumFractionDigits: d })
  return (sign && n > 0 ? '+' : '') + s + '%'
}

export const fmtDate = (iso: string | null | undefined, f = 'd MMM') => (iso ? format(parseISO(iso), f) : '–')
export const fmtDateLong = (iso: string | null | undefined) => fmtDate(iso, 'EEE d MMM yyyy')
export const fmtMonth = (period: string) => format(parseISO(period + '-01'), 'MMM yyyy')

export const compact = (n: number | null | undefined) => {
  if (n == null) return '–'
  if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (Math.abs(n) >= 1_000) return (n / 1_000).toFixed(n >= 10_000 ? 0 : 1) + 'k'
  return String(Math.round(n))
}

export const trendWord = (pct: number | null | undefined, up = 'up', down = 'down', flat = 'flat') =>
  pct == null ? flat : pct > 2 ? up : pct < -2 ? down : flat

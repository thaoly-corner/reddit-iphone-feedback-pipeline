import clsx from 'clsx'
import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { fmtPct } from '../lib/format'

/* ---------- Page scaffolding ---------- */

export function PageHeader({ eyebrow, title, lead, aside }: { eyebrow: string; title: string; lead?: ReactNode; aside?: ReactNode }) {
  return (
    <header className="pt-8 pb-5 fade-in">
      <div className="flex items-end justify-between gap-6 flex-wrap">
        <div className="min-w-0">
          <div className="eyebrow mb-2 flex items-center gap-2">
            <i className="w-5 h-px bg-accent" />
            {eyebrow}
          </div>
          <h1 className="display text-[38px] md:text-[48px] text-ink">{title}</h1>
        </div>
        {aside && <div className="shrink-0 pb-1">{aside}</div>}
      </div>
      {lead && <p className="mt-3 max-w-3xl text-[14.5px] leading-relaxed text-ink-2">{lead}</p>}
    </header>
  )
}

export function Lead({ children }: { children: ReactNode }) {
  return (
    <div className="panel px-5 py-4 mb-6 fade-in flex gap-4 items-start border-l-[3px] border-l-accent">
      <span className="eyebrow mt-1.5 shrink-0 text-accent">Finding</span>
      <p className="display-md text-[18px] md:text-[20px] text-ink max-w-4xl">{children}</p>
    </div>
  )
}

export function Section({
  title,
  sub,
  children,
  right,
  className,
  evidence,
}: {
  title: string
  sub?: ReactNode
  children: ReactNode
  right?: ReactNode
  className?: string
  evidence?: Evidence
}) {
  return (
    <section className={clsx('panel p-5 mb-5 fade-in', className)}>
      <div className="flex items-start justify-between gap-4 mb-4 flex-wrap">
        <div>
          <h2 className="display-md text-[16px] text-ink">{title}</h2>
          {sub && <div className="text-[12.5px] text-ink-3 mt-0.5 max-w-3xl">{sub}</div>}
        </div>
        <div className="flex items-center gap-2 flex-wrap">{right}</div>
      </div>
      {children}
      {evidence && <EvidenceLine {...evidence} />}
    </section>
  )
}

export interface Evidence {
  br: string
  mart?: string
  endpoint: string
  ms?: number
  dbMs?: number
  cached?: boolean
  rows?: number
}

export function EvidenceLine({ br, mart, endpoint, ms, dbMs, cached, rows }: Evidence) {
  return (
    <div className="mt-4 pt-3 border-t border-dashed border-line flex flex-wrap items-center gap-x-3 gap-y-1 text-[10.5px] text-ink-3 num">
      <span className="text-accent font-semibold">{br}</span>
      {mart && <span>{mart}</span>}
      <span>{endpoint}</span>
      {rows != null && <span>{rows} rows</span>}
      {ms != null && (
        <span>
          {ms} ms{dbMs != null ? ` · db ${dbMs}` : ''}
        </span>
      )}
      {cached && <span className="text-signal">cached</span>}
    </div>
  )
}

/* ---------- Numbers ---------- */

export function Kpi({
  label,
  value,
  delta,
  deltaLabel = 'vs prior period',
  hint,
  invert = false,
  size = 'lg',
  bare = false,
}: {
  label: string
  value: ReactNode
  delta?: number | null
  deltaLabel?: string
  hint?: ReactNode
  invert?: boolean
  size?: 'lg' | 'md'
  bare?: boolean
}) {
  const good = delta == null ? null : (delta >= 0) !== invert
  return (
    <div className={clsx('min-w-0', !bare && 'panel px-4 py-3.5')}>
      <div className="eyebrow">{label}</div>
      <div className={clsx('display text-ink mt-1.5', size === 'lg' ? 'text-[34px] leading-none' : 'text-[24px] leading-none')}>{value}</div>
      <div className="mt-2 text-[11.5px] text-ink-3 flex items-center gap-1.5 flex-wrap">
        {delta != null && (
          <span className={clsx('num font-medium px-1.5 py-px rounded', good ? 'text-pos bg-pos/10' : 'text-neg bg-neg/10')}>
            {delta > 0 ? '↑' : delta < 0 ? '↓' : '→'} {fmtPct(Math.abs(delta), 1)}
          </span>
        )}
        {delta != null && <span>{deltaLabel}</span>}
        {hint}
      </div>
    </div>
  )
}

export function Delta({ v, invert = false, d = 1 }: { v: number | null | undefined; invert?: boolean; d?: number }) {
  if (v == null) return <span className="text-ink-3">–</span>
  const good = (v >= 0) !== invert
  return (
    <span className={clsx('num', Math.abs(v) < 2 ? 'text-ink-3' : good ? 'text-pos' : 'text-neg')}>
      {v > 0 ? '+' : ''}
      {fmtPct(v, d)}
    </span>
  )
}

/* ---------- Badges / chips ---------- */

export function Tag({ children, color, className }: { children: ReactNode; color?: string; className?: string }) {
  return (
    <span className={clsx('chip', className)}>
      {color && <i className="swatch" style={{ background: color }} />}
      {children}
    </span>
  )
}

export function Severity({ level }: { level: 'watch' | 'elevated' | 'critical' | string }) {
  const map: Record<string, { c: string; icon: string }> = {
    watch: { c: 'var(--status-warn)', icon: '◔' },
    elevated: { c: 'var(--status-serious)', icon: '◑' },
    critical: { c: 'var(--status-critical)', icon: '●' },
  }
  const m = map[level] ?? map.watch
  return (
    <span className="inline-flex items-center gap-1 text-[11.5px] font-semibold uppercase tracking-wide" style={{ color: m.c }}>
      <span aria-hidden>{m.icon}</span>
      {level}
    </span>
  )
}

/* ---------- Bars ---------- */

export function Bar({ pct, color = 'var(--accent)', track = true, h = 6 }: { pct: number; color?: string; track?: boolean; h?: number }) {
  return (
    <div className="w-full rounded-full overflow-hidden" style={{ height: h, background: track ? 'var(--surface-3)' : 'transparent' }}>
      <div style={{ width: `${Math.max(0, Math.min(100, pct))}%`, height: '100%', background: color, borderRadius: 999 }} />
    </div>
  )
}

export function StackBar({ parts, h = 8 }: { parts: { v: number; color: string; label: string }[]; h?: number }) {
  const total = parts.reduce((a, p) => a + p.v, 0) || 1
  return (
    <div className="flex w-full rounded-full overflow-hidden gap-[2px]" style={{ height: h }} title={parts.map((p) => `${p.label}: ${p.v}`).join(' · ')}>
      {parts.map((p) => (
        <div key={p.label} style={{ width: `${(p.v / total) * 100}%`, background: p.color }} />
      ))}
    </div>
  )
}

/* ---------- Sparkline ---------- */

export function Spark({ values, color = 'var(--ink-2)', w = 96, h = 24, fill = true }: { values: (number | null)[]; color?: string; w?: number; h?: number; fill?: boolean }) {
  const v = values.map((x) => x ?? 0)
  if (!v.length) return null
  const max = Math.max(...v, 1)
  const min = Math.min(...v, 0)
  const step = w / Math.max(v.length - 1, 1)
  const pts = v.map((y, i) => [i * step, h - ((y - min) / (max - min || 1)) * (h - 2) - 1] as const)
  const d = pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const last = pts[pts.length - 1]
  return (
    <svg width={w} height={h} className="block overflow-visible" aria-hidden>
      {fill && <path d={`${d} L${w},${h} L0,${h} Z`} fill={color} opacity={0.12} />}
      <path d={d} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" />
      <circle cx={last[0]} cy={last[1]} r={2} fill={color} />
    </svg>
  )
}

/* ---------- States ---------- */

export function Empty({ children = 'No data for this slice.', action }: { children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="py-10 text-center text-ink-3 text-[13px]">
      <div className="display-md text-[18px] text-ink-2 mb-1">Nothing here</div>
      {children}
      {action && <div className="mt-3">{action}</div>}
    </div>
  )
}

export function ErrorBox({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : String(error)
  return (
    <div className="border border-neg/40 text-neg rounded-md px-3 py-2 text-[13px]">
      <span className="font-medium">Request failed.</span> {msg}
    </div>
  )
}

export function Skeleton({ h = 240 }: { h?: number }) {
  return <div className="skeleton w-full" style={{ height: h }} />
}

export function Loading<T>({ q, h, children }: { q: { isLoading: boolean; error: unknown; data?: T }; h?: number; children: (d: T) => ReactNode }) {
  if (q.isLoading) return <Skeleton h={h} />
  if (q.error) return <ErrorBox error={q.error} />
  if (!q.data) return null
  return <>{children(q.data)}</>
}

/* ---------- Links ---------- */

export function IssueLink({ issue, children, className }: { issue: string; children?: ReactNode; className?: string }) {
  return (
    <Link to={`/issues?issue=${encodeURIComponent(issue)}`} className={clsx('hover:text-accent transition-colors', className)}>
      {children ?? issue}
    </Link>
  )
}

export function Toggle({ on, onChange, label }: { on: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" className="btn" aria-pressed={on} onClick={() => onChange(!on)}>
      <span className="relative inline-block w-6 h-3.5 rounded-full transition-colors" style={{ background: on ? 'var(--signal)' : 'var(--line-2)' }}>
        <span className="absolute top-[2px] w-2.5 h-2.5 rounded-full bg-white transition-all" style={{ left: on ? 12 : 2 }} />
      </span>
      {label}
    </button>
  )
}

export function Segmented<T extends string>({ value, options, onChange }: { value: T; options: { v: T; label: string }[]; onChange: (v: T) => void }) {
  return (
    <div className="inline-flex bg-surface-2 border border-line rounded-full p-0.5 h-8">
      {options.map((o) => (
        <button
          key={o.v}
          type="button"
          onClick={() => onChange(o.v)}
          className={clsx('px-3 rounded-full text-[12px] font-semibold transition-all', o.v === value ? 'bg-ink text-paper shadow-sm' : 'text-ink-2 hover:text-ink')}
        >
          {o.label}
        </button>
      ))}
    </div>
  )
}

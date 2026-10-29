import clsx from 'clsx'
import { useMemo } from 'react'
import { useApi } from '../lib/api'
import { useFilters, type Filters } from '../lib/filters'
import { fmtDate } from '../lib/format'

interface Vocab {
  date_range: { min: string; max: string }
  models: { name: string; posts: number }[]
  ios_versions: { name: string; posts: number; major: string }[]
  ios_majors: { name: string; posts: number }[]
  features: { name: string; issues: { issue: string; mentions: number }[] }[]
}

/** `supports` lists the filters the current page honours; others are dimmed with a tooltip. */
export default function FilterBar({ supports }: { supports: (keyof Filters)[] }) {
  const { filters, set, clear, active } = useFilters()
  const vocab = useApi<Vocab>('/meta/filters')
  const v = vocab.data?.data

  const presets = useMemo(() => {
    if (!v) return []
    const max = v.date_range.max
    const d = (iso: string, days: number) => {
      const t = new Date(iso + 'T00:00:00Z')
      t.setUTCDate(t.getUTCDate() - days + 1)
      return t.toISOString().slice(0, 10)
    }
    return [
      { label: 'All', from: '', to: '' },
      { label: '14d', from: d(max, 14), to: max },
      { label: '30d', from: d(max, 30), to: max },
      { label: 'May', from: '2026-05-01', to: '2026-05-31' },
      { label: 'Jun', from: '2026-06-01', to: '2026-06-30' },
      { label: 'Jul', from: '2026-07-01', to: '2026-07-31' },
    ]
  }, [v])

  const dis = (k: keyof Filters) => !supports.includes(k)
  const title = (k: keyof Filters) => (dis(k) ? 'This page does not slice by this dimension; the filter stays in the URL for other pages.' : undefined)

  return (
    <div className="sticky top-14 z-20 -mx-5 lg:-mx-8 px-5 lg:px-8 py-2.5 bg-paper/85 backdrop-blur-md border-b border-line">
      <div className="flex flex-wrap items-center gap-2">
        <div className={clsx('flex items-center gap-1', dis('date_from') && 'opacity-40')} title={title('date_from')}>
          <div className="inline-flex bg-surface-2 border border-line rounded-full p-0.5 h-8">
            {presets.map((p) => {
              const on = (filters.date_from ?? '') === p.from && (filters.date_to ?? '') === p.to
              return (
                <button
                  key={p.label}
                  type="button"
                  className={clsx('px-2.5 rounded-full text-[12px] font-semibold transition-all', on ? 'bg-ink text-paper shadow-sm' : 'text-ink-2 hover:text-ink')}
                  onClick={() => set({ date_from: p.from, date_to: p.to })}
                >
                  {p.label}
                </button>
              )
            })}
          </div>
          <input type="date" className="field ml-1" value={filters.date_from ?? ''} min={v?.date_range.min} max={v?.date_range.max} onChange={(e) => set({ date_from: e.target.value })} aria-label="From date" />
          <span className="text-ink-3 text-xs">→</span>
          <input type="date" className="field" value={filters.date_to ?? ''} min={v?.date_range.min} max={v?.date_range.max} onChange={(e) => set({ date_to: e.target.value })} aria-label="To date" />
        </div>

        <select className={clsx('field', dis('model') && 'opacity-40', filters.model && 'border-accent text-accent')} title={title('model')} value={filters.model ?? ''} onChange={(e) => set({ model: e.target.value })} aria-label="iPhone model">
          <option value="">All models</option>
          {v?.models.map((m) => (
            <option key={m.name} value={m.name}>
              {m.name} · {m.posts}
            </option>
          ))}
        </select>

        <select className={clsx('field', dis('ios') && 'opacity-40', filters.ios && 'border-accent text-accent')} title={title('ios')} value={filters.ios ?? ''} onChange={(e) => set({ ios: e.target.value })} aria-label="iOS version">
          <option value="">All iOS</option>
          {v?.ios_majors.map((m) => (
            <option key={m.name} value={m.name}>
              {m.name} (all point releases) · {m.posts}
            </option>
          ))}
          <option disabled>──</option>
          {v?.ios_versions.map((m) => (
            <option key={m.name} value={m.name}>
              {m.name} · {m.posts}
            </option>
          ))}
        </select>

        <select
          className={clsx('field', dis('issue') && dis('feature') && 'opacity-40', (filters.issue || filters.feature) && 'border-accent text-accent')}
          title={title('issue')}
          value={filters.issue ? `i:${filters.issue}` : filters.feature ? `f:${filters.feature}` : ''}
          onChange={(e) => {
            const val = e.target.value
            if (!val) set({ issue: '', feature: '' })
            else if (val.startsWith('f:')) set({ feature: val.slice(2), issue: '' })
            else set({ issue: val.slice(2), feature: '' })
          }}
          aria-label="Feature or issue"
        >
          <option value="">All features & issues</option>
          {v?.features.map((f) => (
            <optgroup key={f.name} label={f.name}>
              <option value={`f:${f.name}`}>All {f.name}</option>
              {f.issues.map((i) => (
                <option key={i.issue} value={`i:${i.issue}`}>
                  {i.issue} · {i.mentions}
                </option>
              ))}
            </optgroup>
          ))}
        </select>

        {active.length > 0 && (
          <button type="button" className="btn text-ink-3" onClick={clear}>
            Clear ×
          </button>
        )}

        <span className="ml-auto eyebrow hidden lg:inline">{v ? `${fmtDate(v.date_range.min, 'd MMM')} – ${fmtDate(v.date_range.max, 'd MMM yyyy')} · r/iphone` : ''}</span>
      </div>
    </div>
  )
}

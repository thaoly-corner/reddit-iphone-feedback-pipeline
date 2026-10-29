import { createContext, useCallback, useContext, useMemo, type ReactNode } from 'react'
import { useSearchParams } from 'react-router-dom'

export type Filters = {
  date_from?: string
  date_to?: string
  model?: string
  ios?: string
  feature?: string
  issue?: string
}

export const FILTER_KEYS: (keyof Filters)[] = ['date_from', 'date_to', 'model', 'ios', 'feature', 'issue']

interface Ctx {
  filters: Filters
  set: (patch: Partial<Filters>) => void
  clear: () => void
  active: (keyof Filters)[]
}

const FilterCtx = createContext<Ctx | null>(null)

export function FilterProvider({ children }: { children: ReactNode }) {
  const [sp, setSp] = useSearchParams()
  const filters = useMemo(() => {
    const f: Filters = {}
    for (const k of FILTER_KEYS) {
      const v = sp.get(k)
      if (v) f[k] = v
    }
    return f
  }, [sp])

  const set = useCallback(
    (patch: Partial<Filters>) => {
      setSp(
        (prev) => {
          const next = new URLSearchParams(prev)
          for (const [k, v] of Object.entries(patch)) {
            if (v) next.set(k, v)
            else next.delete(k)
          }
          return next
        },
        { replace: true },
      )
    },
    [setSp],
  )

  const clear = useCallback(() => {
    setSp(
      (prev) => {
        const next = new URLSearchParams(prev)
        for (const k of FILTER_KEYS) next.delete(k)
        return next
      },
      { replace: true },
    )
  }, [setSp])

  const active = FILTER_KEYS.filter((k) => filters[k])
  return <FilterCtx.Provider value={{ filters, set, clear, active }}>{children}</FilterCtx.Provider>
}

export function useFilters() {
  const c = useContext(FilterCtx)
  if (!c) throw new Error('FilterProvider missing')
  return c
}

/** Human description of the active slice, used in leads. */
export function describeSlice(f: Filters): string {
  const parts: string[] = []
  if (f.model) parts.push(f.model)
  if (f.ios) parts.push(f.ios)
  if (f.issue) parts.push(f.issue)
  else if (f.feature) parts.push(f.feature)
  return parts.length ? parts.join(' · ') : 'all r/iphone feedback'
}

import { useQuery, type UseQueryOptions } from '@tanstack/react-query'

export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api/v1'

export interface Envelope<T = any, M = Record<string, any>> {
  data: T
  meta: M & { total?: number; db_ms?: number; queries?: number; cache_hits?: number; source?: string; filters_applied?: Record<string, any> }
}

export type Params = { [key: string]: string | number | boolean | null | undefined }

export function qs(params: Params): string {
  const u = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined || v === null || v === '') continue
    u.set(k, String(v))
  }
  const s = u.toString()
  return s ? `?${s}` : ''
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

export async function getJson<T = any>(path: string, params: Params = {}): Promise<Envelope<T> & { _ms: number }> {
  const t0 = performance.now()
  const r = await fetch(`${API_BASE}${path}${qs(params)}`)
  const ms = performance.now() - t0
  if (!r.ok) {
    let detail = r.statusText
    try {
      const b = await r.json()
      detail = b.detail ? (typeof b.detail === 'string' ? b.detail : JSON.stringify(b.detail)) : detail
    } catch {
      /* ignore */
    }
    throw new ApiError(r.status, detail)
  }
  const body = (await r.json()) as Envelope<T>
  return { ...body, _ms: Math.round(ms) }
}

export function useApi<T = any>(path: string, params: Params = {}, opts: Partial<UseQueryOptions<any>> = {}) {
  return useQuery<Envelope<T> & { _ms: number }>({
    queryKey: [path, params],
    queryFn: () => getJson<T>(path, params),
    staleTime: 5 * 60 * 1000,
    ...(opts as any),
  })
}

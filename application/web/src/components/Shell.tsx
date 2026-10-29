import clsx from 'clsx'
import { useEffect, useState, type ReactNode } from 'react'
import { NavLink, useLocation, useNavigate } from 'react-router-dom'
import { useApi } from '../lib/api'
import { PAGES, PERSONAS, usePersona } from '../lib/persona'

export default function Shell({ children }: { children: ReactNode }) {
  const { persona, setPersona, theme, toggleTheme } = usePersona()
  const nav = useNavigate()
  const loc = useLocation()
  const fresh = useApi<{ latest_feedback_date: string; latest_alert_date: string }>('/meta/freshness')
  const [open, setOpen] = useState(false)
  const search = loc.search

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === '/' && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLSelectElement)) {
        e.preventDefault()
        setOpen(true)
      }
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const ordered = persona.nav.map((id) => PAGES.find((p) => p.id === id)!).filter(Boolean)

  return (
    <div className="min-h-screen">
      {/* ---- top bar ---- */}
      <header className="sticky top-0 z-30 bg-paper/85 backdrop-blur-md border-b border-line">
        <div className="max-w-[1480px] mx-auto px-5 lg:px-8">
          <div className="h-14 flex items-center gap-6">
            <NavLink to={persona.home + search} className="flex items-center gap-2.5 shrink-0">
              <span className="grid grid-cols-3 gap-[2px] w-4 h-4 items-end" aria-hidden>
                <i className="block bg-accent rounded-[1px] h-[40%]" />
                <i className="block bg-accent rounded-[1px] h-[70%]" />
                <i className="block bg-signal rounded-[1px] h-full" />
              </span>
              <span className="display text-[17px] tracking-[-0.02em]">BrandVoice</span>
              <span className="hidden 2xl:inline eyebrow ml-1">iPhone · r/iphone</span>
            </NavLink>

            <nav className="hidden md:flex items-center gap-0.5 ml-2 overflow-x-auto">
              {ordered.map((p, i) => (
                <NavLink
                  key={p.id}
                  to={p.path + search}
                  className={({ isActive }) =>
                    clsx(
                      'relative h-14 flex items-center px-2.5 text-[13px] whitespace-nowrap transition-colors',
                      isActive ? 'text-ink font-semibold' : 'text-ink-3 hover:text-ink',
                    )
                  }
                >
                  {({ isActive }) => (
                    <>
                      {i === 0 && <i className="w-1.5 h-1.5 rounded-full bg-signal mr-1.5" title={`${persona.title} home`} />}
                      {p.label}
                      {isActive && <i className="absolute left-3 right-3 -bottom-px h-[2px] bg-accent rounded-full" />}
                    </>
                  )}
                </NavLink>
              ))}
            </nav>

            <div className="ml-auto flex items-center gap-2">
              <div className="hidden xl:flex items-center gap-2 text-[11.5px] text-ink-3 num mr-2 whitespace-nowrap">
                <span className="pulse" />
                <span>
                  data to <span className="text-ink-2">{fresh.data?.data.latest_feedback_date ?? '…'}</span>
                </span>
              </div>

              <div className="flex items-center bg-surface-2 rounded-full p-0.5 border border-line">
                {PERSONAS.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    title={p.title}
                    onClick={() => {
                      setPersona(p.id)
                      nav(p.home + search)
                    }}
                    className={clsx(
                      'h-7 px-3 rounded-full text-[12px] font-semibold transition-all',
                      p.id === persona.id ? 'bg-ink text-paper shadow-sm' : 'text-ink-2 hover:text-ink',
                    )}
                  >
                    {p.short}
                  </button>
                ))}
              </div>

              <button type="button" className="btn h-8 w-8 px-0 justify-center" onClick={() => setOpen(true)} title="Jump (/)">
                <span className="num text-[12px]">/</span>
              </button>
              <button type="button" className="btn h-8 w-8 px-0 justify-center" onClick={toggleTheme} title="Toggle theme">
                {theme === 'dark' ? <SunIcon /> : <MoonIcon />}
              </button>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-[1480px] mx-auto px-5 lg:px-8 pb-20">
        <div className="md:hidden flex gap-2 py-3 overflow-x-auto">
          {ordered.map((p) => (
            <NavLink key={p.id} to={p.path + search} className={({ isActive }) => clsx('btn whitespace-nowrap', isActive && 'is-active')}>
              {p.label}
            </NavLink>
          ))}
        </div>
        <div className="flex items-start gap-3 py-3 text-[12.5px] text-ink-3 border-b border-line">
          <span className="eyebrow mt-[3px]">Viewing as</span>
          <span>
            <b className="text-ink font-semibold">{persona.title}.</b> {persona.brief}
          </span>
        </div>
        {children}
      </main>

      {open && <Palette onClose={() => setOpen(false)} />}
    </div>
  )
}

function SunIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" />
    </svg>
  )
}
function MoonIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
    </svg>
  )
}

function Palette({ onClose }: { onClose: () => void }) {
  const nav = useNavigate()
  const loc = useLocation()
  const [q, setQ] = useState('')
  const vocab = useApi<any>('/meta/filters')
  const v = vocab.data?.data
  const items: { label: string; hint: string; go: () => void }[] = [
    ...PAGES.map((p) => ({ label: p.label, hint: p.br, go: () => nav(p.path + loc.search) })),
    ...(v?.models ?? []).map((m: any) => ({ label: m.name, hint: 'model filter', go: () => nav(withParam(loc, 'model', m.name)) })),
    ...(v?.features ?? []).flatMap((f: any) => f.issues.map((i: any) => ({ label: i.issue, hint: 'issue', go: () => nav(`/issues${withParamStr(loc.search, 'issue', i.issue)}`) }))),
  ]
  const hits = items.filter((i) => i.label.toLowerCase().includes(q.toLowerCase())).slice(0, 12)
  return (
    <div className="fixed inset-0 z-50 bg-ink/40 backdrop-blur-[2px] flex items-start justify-center pt-[12vh]" onClick={onClose}>
      <div className="w-[560px] max-w-[92vw] panel shadow-2xl overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 px-4 h-12 border-b border-line">
          <span className="num text-ink-3">›</span>
          <input
            autoFocus
            className="flex-1 h-full bg-transparent outline-none text-[14px]"
            placeholder="Jump to a page, model or issue…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && hits[0]) {
                hits[0].go()
                onClose()
              }
            }}
          />
          <kbd className="eyebrow border border-line rounded px-1.5 py-0.5">esc</kbd>
        </div>
        <ul className="max-h-[50vh] overflow-auto py-1">
          {hits.map((h, i) => (
            <li key={h.label + i}>
              <button
                type="button"
                className="w-full flex justify-between items-center px-4 h-9 text-[13px] hover:bg-surface-2"
                onClick={() => {
                  h.go()
                  onClose()
                }}
              >
                <span>{h.label}</span>
                <span className="eyebrow">{h.hint}</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

function withParamStr(search: string, k: string, v: string) {
  const u = new URLSearchParams(search)
  u.set(k, v)
  return `?${u.toString()}`
}
function withParam(loc: { pathname: string; search: string }, k: string, v: string) {
  return loc.pathname + withParamStr(loc.search, k, v)
}

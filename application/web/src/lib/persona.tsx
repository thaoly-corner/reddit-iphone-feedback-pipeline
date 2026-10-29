import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

export type PersonaId = 'pm' | 'cx' | 'brand' | 'marketing'

export interface Persona {
  id: PersonaId
  short: string
  title: string
  brief: string
  home: string
  nav: string[] // page ids in priority order
  vocabulary: Record<string, string>
}

export const PAGES = [
  { id: 'overview', path: '/overview', label: 'Overview', br: 'BR01' },
  { id: 'issues', path: '/issues', label: 'Issues', br: 'BR02 · BR07' },
  { id: 'emerging', path: '/emerging', label: 'Emerging', br: 'BR03' },
  { id: 'sentiment', path: '/sentiment', label: 'Sentiment', br: 'BR04' },
  { id: 'features', path: '/features', label: 'Features', br: 'BR05' },
  { id: 'complaints', path: '/complaints', label: 'Complaints', br: 'BR06' },
  { id: 'compare', path: '/compare', label: 'Compare', br: 'BR08' },
  { id: 'support', path: '/support', label: 'Support', br: 'BR09 · BR10' },
  { id: 'pipeline', path: '/pipeline', label: 'Pipeline', br: 'Evaluation' },
] as const

export const PERSONAS: Persona[] = [
  {
    id: 'pm',
    short: 'PM',
    title: 'Product Manager',
    brief: 'Which defects are most reported, which are growing, and on which models.',
    home: '/issues',
    nav: ['issues', 'emerging', 'features', 'compare', 'overview', 'sentiment', 'complaints', 'support', 'pipeline'],
    vocabulary: { volume: 'Defect reports', share: 'Share of defects', growth: 'WoW growth' },
  },
  {
    id: 'cx',
    short: 'CX',
    title: 'Customer Experience Analyst',
    brief: 'Where customers are hurting right now: alerts, loud complaints, support demand.',
    home: '/emerging',
    nav: ['emerging', 'complaints', 'support', 'sentiment', 'issues', 'overview', 'features', 'compare', 'pipeline'],
    vocabulary: { volume: 'Customer reports', share: 'Share of reports', growth: 'Change vs last week' },
  },
  {
    id: 'brand',
    short: 'Brand',
    title: 'Brand Manager',
    brief: 'How the community feels about iPhone and which conversations reach the furthest.',
    home: '/sentiment',
    nav: ['sentiment', 'complaints', 'overview', 'compare', 'issues', 'emerging', 'features', 'support', 'pipeline'],
    vocabulary: { volume: 'Conversations', share: 'Share of voice', growth: 'Momentum' },
  },
  {
    id: 'marketing',
    short: 'Mkt',
    title: 'Marketing Analyst',
    brief: 'Model-by-model and release-by-release differences in what people talk about.',
    home: '/compare',
    nav: ['compare', 'features', 'overview', 'support', 'sentiment', 'issues', 'emerging', 'complaints', 'pipeline'],
    vocabulary: { volume: 'Mentions', share: 'Share of mentions', growth: 'Momentum' },
  },
]

interface Ctx {
  persona: Persona
  setPersona: (id: PersonaId) => void
  theme: 'light' | 'dark'
  toggleTheme: () => void
}

const PersonaCtx = createContext<Ctx | null>(null)

export function PersonaProvider({ children }: { children: ReactNode }) {
  const [id, setId] = useState<PersonaId>(() => {
    try {
      return (localStorage.getItem('bv-persona') as PersonaId) || 'pm'
    } catch {
      return 'pm'
    }
  })
  const [theme, setTheme] = useState<'light' | 'dark'>(() => (document.documentElement.dataset.theme === 'dark' ? 'dark' : 'light'))

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    try {
      localStorage.setItem('bv-theme', theme)
    } catch {
      /* ignore */
    }
  }, [theme])

  const value = useMemo<Ctx>(
    () => ({
      persona: PERSONAS.find((p) => p.id === id) ?? PERSONAS[0],
      setPersona: (p) => {
        setId(p)
        try {
          localStorage.setItem('bv-persona', p)
        } catch {
          /* ignore */
        }
      },
      theme,
      toggleTheme: () => setTheme((t) => (t === 'dark' ? 'light' : 'dark')),
    }),
    [id, theme],
  )
  return <PersonaCtx.Provider value={value}>{children}</PersonaCtx.Provider>
}

export function usePersona() {
  const c = useContext(PersonaCtx)
  if (!c) throw new Error('PersonaProvider missing')
  return c
}

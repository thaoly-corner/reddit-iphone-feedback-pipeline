import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import { FilterProvider } from './lib/filters'
import { PersonaProvider } from './lib/persona'
import './theme.css'

const qc = new QueryClient({ defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } } })

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={qc}>
      <BrowserRouter>
        <PersonaProvider>
          <FilterProvider>
            <App />
          </FilterProvider>
        </PersonaProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)

import { Navigate, Route, Routes } from 'react-router-dom'
import Shell from './components/Shell'
import { usePersona } from './lib/persona'
import Compare from './pages/Compare'
import Complaints from './pages/Complaints'
import Emerging from './pages/Emerging'
import Features from './pages/Features'
import Issues from './pages/Issues'
import Overview from './pages/Overview'
import Pipeline from './pages/Pipeline'
import Sentiment from './pages/Sentiment'
import Support from './pages/Support'

export default function App() {
  const { persona } = usePersona()
  return (
    <Shell>
      <Routes>
        <Route path="/" element={<Navigate to={persona.home} replace />} />
        <Route path="/overview" element={<Overview />} />
        <Route path="/issues" element={<Issues />} />
        <Route path="/emerging" element={<Emerging />} />
        <Route path="/sentiment" element={<Sentiment />} />
        <Route path="/features" element={<Features />} />
        <Route path="/complaints" element={<Complaints />} />
        <Route path="/compare" element={<Compare />} />
        <Route path="/support" element={<Support />} />
        <Route path="/pipeline" element={<Pipeline />} />
        <Route path="*" element={<Navigate to={persona.home} replace />} />
      </Routes>
    </Shell>
  )
}

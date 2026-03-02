import { Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import Footer from './components/Footer'
import LandingPage from './pages/LandingPage'
import SkillsPage from './pages/SkillsPage'
import PricingPage from './pages/PricingPage'
import SuccessPage from './pages/SuccessPage'

function App() {
  return (
    <div className="min-h-screen bg-gray-950 text-white">
      <Navbar />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/skills" element={<SkillsPage />} />
        <Route path="/pricing" element={<PricingPage />} />
        <Route path="/success" element={<SuccessPage />} />
      </Routes>
      <Footer />
    </div>
  )
}

export default App

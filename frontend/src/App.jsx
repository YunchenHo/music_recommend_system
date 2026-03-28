import { Routes, Route } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import HomePage from './pages/HomePage'
import SongOnboardingPage from './pages/SongOnboardingPage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/song-onboarding" element={<SongOnboardingPage />} />
      <Route path="/home" element={<HomePage />} />
    </Routes>
  )
}

export default App
import { Routes, Route } from 'react-router-dom'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'
import ArtistOnboardingPage from "./pages/ArtistOnboardingPage"
import SongOnboardingPage from './pages/SongOnboardingPage'
import HomePage from './pages/HomePage'

function App() {
  return (
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/artist-onboarding" element={<ArtistOnboardingPage />} />
      <Route path="/song-onboarding" element={<SongOnboardingPage />} />
      <Route path="/home" element={<HomePage />} />
    </Routes>
  )
}

export default App
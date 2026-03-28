import { useState, useEffect } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import "../styles/ArtistOnboardingPage.css"

const artistData = {
  Chinese: [
    { id: 1, name: "Jay Chou", image: "/artists/jaychou.jpg" },
    { id: 2, name: "G.E.M.", image: "/artists/jaychou.jpg" },
    { id: 3, name: "JJ Lin", image: "/artists/jaychou.jpg" },
    { id: 4, name: "A-Lin", image: "/artists/jaychou.jpg" },
    { id: 5, name: "Jolin Tsai", image: "/artists/jaychou.jpg" },
    { id: 6, name: "Eric Chou", image: "/artists/jaychou.jpg" },
    { id: 7, name: "Mayday", image: "/artists/jaychou.jpg" },
    { id: 8, name: "Yoga Lin", image: "/artists/jaychou.jpg" },
  ],
  English: [
    { id: 101, name: "Taylor Swift", image: "/artists/jaychou.jpg" },
    { id: 102, name: "Ed Sheeran", image: "/artists/jaychou.jpg" },
    { id: 103, name: "Billie Eilish", image: "/artists/jaychou.jpg" },
    { id: 104, name: "The Weeknd", image: "/artists/jaychou.jpg" },
    { id: 105, name: "Ariana Grande", image: "/artists/jaychou.jpg" },
    { id: 106, name: "Dua Lipa", image: "/artists/jaychou.jpg" },
    { id: 107, name: "Bruno Mars", image: "/artists/jaychou.jpg" },
    { id: 108, name: "Olivia Rodrigo", image: "/artists/jaychou.jpg" },
  ],
  Japanese: [
    { id: 201, name: "YOASOBI", image: "/artists/jaychou.jpg" },
    { id: 202, name: "米津玄師", image: "/artists/jaychou.jpg" },
    { id: 203, name: "Aimer", image: "/artists/jaychou.jpg" },
    { id: 204, name: "Higedan", image: "/artists/jaychou.jpg" },
    { id: 205, name: "LiSA", image: "/artists/jaychou.jpg" },
    { id: 206, name: "優里", image: "/artists/jaychou.jpg" },
    { id: 207, name: "King Gnu", image: "/artists/jaychou.jpg" },
    { id: 208, name: "あいみょん", image: "/artists/jaychou.jpg" },
  ],
  Korean: [
    { id: 301, name: "BTS", image: "/artists/jaychou.jpg" },
    { id: 302, name: "BLACKPINK", image: "/artists/jaychou.jpg" },
    { id: 303, name: "NewJeans", image: "/artists/jaychou.jpg" },
    { id: 304, name: "IVE", image: "/artists/jaychou.jpg" },
    { id: 305, name: "IU", image: "/artists/jaychou.jpg" },
    { id: 306, name: "SEVENTEEN", image: "/artists/jaychou.jpg" },
    { id: 307, name: "aespa", image: "/artists/jaychou.jpg" },
    { id: 308, name: "EXO", image: "/artists/jaychou.jpg" },
  ],
}

function ArtistOnboardingPage() {
  const location = useLocation()
  const navigate = useNavigate()

  const selectedLanguages = location.state?.selectedLanguages || []
  const [currentStep, setCurrentStep] = useState(0)
  const [selectedArtists, setSelectedArtists] = useState({})

  useEffect(() => {
    if (selectedLanguages.length === 0) {
        navigate("/register")
        return
    }

    const initialSelections = {}
    selectedLanguages.forEach((lang) => {
        initialSelections[lang] = []
    })
    setSelectedArtists(initialSelections)
    }, [selectedLanguages, navigate])

  const currentLanguage = selectedLanguages[currentStep]
  const artists = artistData[currentLanguage] || []

  const toggleArtist = (artistId) => {
    const current = selectedArtists[currentLanguage] || []
    const isSelected = current.includes(artistId)

    if (isSelected) {
      setSelectedArtists({
        ...selectedArtists,
        [currentLanguage]: current.filter((id) => id !== artistId),
      })
    } else {
      setSelectedArtists({
        ...selectedArtists,
        [currentLanguage]: [...current, artistId],
      })
    }
  }

  const selectedCount = (selectedArtists[currentLanguage] || []).length
  const canGoNext = selectedCount >= 2
  const isLastStep = currentStep === selectedLanguages.length - 1

  const handleNext = () => {
    if (!canGoNext) return

    if (isLastStep) {
      navigate("/song-onboarding", {
        state: {
          selectedLanguages,
          selectedArtists,
        },
      })
    } else {
      setCurrentStep((prev) => prev + 1)
    }
  }

  const handleBack = () => {
    if (currentStep === 0) {
      navigate("/register")
    } else {
      setCurrentStep((prev) => prev - 1)
    }
  }

  return (
    <div className="artist-page">
      <div className="artist-panel">
        <p className="artist-step">
          Step {currentStep + 1} / {selectedLanguages.length}
        </p>

        <h1 className="artist-title">
          Pick at least 2 artists you like in{" "}
          <span>{currentLanguage}</span>
        </h1>

        <p className="artist-subtitle">Selected: {selectedCount} / 2</p>

        <div className="artist-grid">
          {artists.map((artist) => {
            const isSelected =
              selectedArtists[currentLanguage]?.includes(artist.id)

            return (
              <button
                key={artist.id}
                type="button"
                className={`artist-card ${isSelected ? "selected" : ""}`}
                onClick={() => toggleArtist(artist.id)}
              >
                <div className="artist-avatar-wrapper">
                  <div className="artist-avatar-ring">
                    <img
                      src={artist.image}
                      alt={artist.name}
                      className="artist-avatar"
                    />
                    <div className="artist-wave-label">
                      <span>{artist.name}</span>
                    </div>
                  </div>
                </div>
              </button>
            )
          })}
        </div>

        <div className="artist-actions">
          <button
            type="button"
            className="artist-back-button"
            onClick={handleBack}
          >
            ← Back
          </button>

          <button
            type="button"
            className={`artist-next-button ${canGoNext ? "active" : "disabled"}`}
            onClick={handleNext}
            disabled={!canGoNext}
          >
            {isLastStep ? "CONTINUE →" : "NEXT →"}
          </button>
        </div>
      </div>
    </div>
  )
}

export default ArtistOnboardingPage
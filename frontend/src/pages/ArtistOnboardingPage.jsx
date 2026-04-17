import { useState, useEffect } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import "../styles/ArtistOnboardingPage.css"

const artistData = {
  Chinese: [
    { id: 213320, name: "Jay Chou", image: "/artists/jaychou.jpg" },
    { id: 66286, name: "G.E.M.", image: "/artists/gem.jpg" },
    { id: 216168, name: "JJ Lin", image: "/artists/jjlin.jpg" },
    { id: 2528, name: "A-Lin", image: "/artists/alin.jpg" },
    { id: 218875, name: "Jolin Tsai", image: "/artists/jolin.jpg" },
    { id: 58626, name: "Eric Chou", image: "/artists/ericchou.jpg" },
    { id: 212101, name: "Mayday", image: "/artists/mayday.jpg" },
    { id: 216221, name: "Yoga Lin", image: "/artists/yogalin.jpg" },
  ],

  English: [
    { id: 175638, name: "Taylor Swift", image: "/artists/taylorswift.jpg" },
    { id: 54966, name: "Ed Sheeran", image: "/artists/edsheeran.jpg" },
    { id: 21835, name: "Billie Eilish", image: "/artists/billie.jpg" },
    { id: 186296, name: "The Weeknd", image: "/artists/theweeknd.jpg" },
    { id: 13396, name: "Ariana Grande", image: "/artists/ariana.jpg" },
    { id: 53286, name: "Dua Lipa", image: "/artists/dualipa.jpg" },
    { id: 26702, name: "Bruno Mars", image: "/artists/brunomars.jpg" },
    { id: 102703, name: "Lady Gaga", image: "/artists/ladygaga.jpg" },
  ],

  Japanese: [
    { id: 2998, name: "AKB48", image: "/artists/akb48.jpg" },
    { id: 97509, name: "Kenshi Yonezu", image: "/artists/米津玄師.jpg" },
    { id: 5684, name: "Aimer", image: "/artists/aimer.jpg" },
    { id: 101256, name: "Kyary", image: "/artists/kyarypamyupamyu.jpg" },
    { id: 105936, name: "LiSA", image: "/artists/lisa.jpg" },
    { id: 128744, name: "Namie Amuro", image: "/artists/namie.jpg" },
    { id: 204927, name: "Yui Aragaki", image: "/artists/yui.jpg" },
    { id: 111645, name: "Mamoru Miyano", image: "/artists/mamoru.jpg" },
  ],

  Korean: [
    { id: 128087, name: "NCT 127", image: "/artists/nct127.jpg" },
    { id: 16523, name: "BLACKPINK", image: "/artists/blackpink.jpg" },
    { id: 157035, name: "SUPER JUNIOR", image: "/artists/superjunior.png" },
    { id: 66449, name: "GFRIEND", image: "/artists/gfriend.jpg" },
    { id: 79228, name: "IU", image: "/artists/iu.jpg" },
    { id: 156534, name: "SEVENTEEN", image: "/artists/seventeen.jpg" },
    { id: 69454, name: "SNSD", image: "/artists/snsd.jpg" },
    { id: 54451, name: "EXO", image: "/artists/exo.jpg" },
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
      return // 直接不做任何事
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
            disabled={currentStep === 0}
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
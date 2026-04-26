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

  Chinese_Page2: [
    { id: 214729, name: "Jeff Chang", image: "/artists/jeffchang.jpg" },
    { id: 156252, name: "S.H.E", image: "/artists/she.jpg" },
    { id: 214008, name: "Stefanie Sun", image: "/artists/stefaniesun.jpg" },
    { id: 216456, name: "Fish Leong", image: "/artists/fishleong.jpg" },
    { id: 217397, name: "Leehom Wang", image: "/artists/leehomwang.jpg" },
    { id: 212761, name: "Rene Liu", image: "/artists/reneliu.jpg" },
    { id: 218879, name: "Tanya Chua", image: "/artists/tanyachua.jpg" },
    { id: 218950, name: "Elva Hsiao", image: "/artists/elvahsiao.jpg" },
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

  English_Page2: [
    { id: 36938, name: "Coldplay", image: "/artists/coldplay.png" },
    { id: 96515, name: "Katy Perry", image: "/artists/katyperry.jpg" },
    { id: 80089, name: "Imagine D.", image: "/artists/imaginedragons.jpg" },
    { id: 24304, name: "Bon Jovi", image: "/artists/bonjovi.png" },
    { id: 135900, name: "One Direction", image: "/artists/onedirection.png" },
    { id: 4663, name: "Adele", image: "/artists/adele.jpg" },
    { id: 146507, name: "Queen", image: "/artists/queen.png" },
    { id: 136038, name: "OneRepublic", image: "/artists/onerepublic.png" },
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

  Japanese_Page2: [
    { id: 15903, name: "Ayumi Hamasaki", image: "/artists/ayumihamasaki.jpg" },
    { id: 66582, name: "GReeeeN", image: "/artists/greeeeen.jpeg" },
    { id: 51113, name: "Do As Infinity", image: "/artists/doasinfinity.jpg" },
    { id: 5591, name: "Ai Otsuka", image: "/artists/aiotsuka.jpg" },
    { id: 95181, name: "Kalafina", image: "/artists/kalafina.jpg" },
    { id: 121836, name: "Mika Nakashima", image: "/artists/mikanakashima.jpg" },
    { id: 188861, name: "Tohoshinki", image: "/artists/tohoshinki.jpg" },
    { id: 133079, name: "Nogizaka46", image: "/artists/nogizaka46.jpg" },
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

  Korean_Page2: [
    { id: 16471, name: "TAEYANG", image: "/artists/taeyang.jpg" },
    { id: 66198, name: "G-DRAGON", image: "/artists/gdragon.jpg" },
    { id: 207300, name: "f(x)", image: "/artists/fx.jpg" },
    { id: 3182, name: "AOA", image: "/artists/aoa.jpeg" },
    { id: 12943, name: "Apink", image: "/artists/apink.jpg" },
    { id: 147203, name: "ROY KIM", image: "/artists/roykim.jpg" },
    { id: 16467, name: "BIGBANG", image: "/artists/bigbang.jpg" },
    { id: 3000, name: "AKMU", image: "/artists/akmu.jpg" },
  ],
}

function ArtistOnboardingPage() {
  const location = useLocation()
  const navigate = useNavigate()

  const selectedLanguages = location.state?.selectedLanguages || []
  const [currentStep, setCurrentStep] = useState(0)
  const [selectedArtists, setSelectedArtists] = useState({})
  const [pageIndex, setPageIndex] = useState(0)

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

  useEffect(() => {
    setPageIndex(0)
  }, [currentStep])

  const currentLanguage = selectedLanguages[currentStep]
  const pageKey = pageIndex === 0 ? currentLanguage : `${currentLanguage}_Page2`
  const artists = artistData[pageKey] || []
  const hasPage2 = !!artistData[`${currentLanguage}_Page2`]

  const handleRefresh = () => {
    setPageIndex((prev) => (prev === 0 ? 1 : 0))
  }

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
        <div className="artist-header">
          <div>
            <p className="artist-step">
              Step {currentStep + 1} / {selectedLanguages.length}
            </p>

            <h1 className="artist-title">
              Pick at least 2 artists you like in{" "}
              <span>{currentLanguage}</span>
            </h1>
          </div>

          {hasPage2 && (
            <button
              type="button"
              className="artist-refresh-button"
              onClick={handleRefresh}
            >
              ↺ Refresh
            </button>
          )}
        </div>

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
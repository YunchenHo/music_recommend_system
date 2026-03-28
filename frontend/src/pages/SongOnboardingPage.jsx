import { useState, useEffect } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import "../styles/SongOnboardingPage.css"

const songData = {
  Chinese: [
    { id: 1, title: "晴天", artist: "周杰倫" },
    { id: 2, title: "泡沫", artist: "鄧紫棋" },
    { id: 3, title: "演員", artist: "薛之謙" },
    { id: 4, title: "告白氣球", artist: "周杰倫" },
    { id: 5, title: "光年之外", artist: "鄧紫棋" },
  ],
  English: [
    { id: 101, title: "reputation", artist: "Taylor Swift" },
    { id: 102, title: "Shape of You", artist: "Ed Sheeran" },
    { id: 103, title: "Bad Guy", artist: "Billie Eilish" },
    { id: 104, title: "Blinding Lights", artist: "The Weeknd" },
    { id: 105, title: "Levitating", artist: "Dua Lipa" },
  ],
  Japanese: [
    { id: 201, title: "Lemon", artist: "米津玄師" },
    { id: 202, title: "Pretender", artist: "Official髭男dism" },
    { id: 203, title: "紅蓮華", artist: "LiSA" },
    { id: 204, title: "夜に駆ける", artist: "YOASOBI" },
  ],
  Korean: [
    { id: 301, title: "Dynamite", artist: "BTS" },
    { id: 302, title: "How You Like That", artist: "BLACKPINK" },
    { id: 303, title: "Love Dive", artist: "IVE" },
    { id: 304, title: "Ditto", artist: "NewJeans" },
  ],
}

function SongOnboardingPage() {
  const location = useLocation()
  const navigate = useNavigate()

  const selectedLanguages = location.state?.selectedLanguages || []

  const [currentStep, setCurrentStep] = useState(0)

  const [selectedSongs, setSelectedSongs] = useState({})

  useEffect(() => {
    if (selectedLanguages.length === 0) {
      navigate("/register")
    } else {
      // 初始化每個語言的選擇
      const initial = {}
      selectedLanguages.forEach((lang) => {
        initial[lang] = []
      })
      setSelectedSongs(initial)
    }
  }, [])

  const currentLanguage = selectedLanguages[currentStep]
  const songs = songData[currentLanguage] || []

  const toggleSong = (id) => {
    const current = selectedSongs[currentLanguage] || []

    const isSelected = current.includes(id)

    if (isSelected) {
      setSelectedSongs({
        ...selectedSongs,
        [currentLanguage]: current.filter((s) => s !== id),
      })
    } else {
      if (current.length >= 4) return

      setSelectedSongs({
        ...selectedSongs,
        [currentLanguage]: [...current, id],
      })
    }
  }

  const canGoNext = (selectedSongs[currentLanguage] || []).length === 4
  const isLastStep = currentStep === selectedLanguages.length - 1

  const handleNext = () => {
    if (!canGoNext) return

    if (isLastStep) {
      console.log("送出資料:", selectedSongs)
      navigate("/home")
    } else {
      setCurrentStep((prev) => prev + 1)
    }
  }

  return (
    <div className="song-page">
      <h1 className="song-title">
        Choose Your Favorite Songs ({currentLanguage})
      </h1>

      <p className="song-subtitle">
        Select 4 songs ({(selectedSongs[currentLanguage] || []).length}/4)
      </p>

      <div className="song-grid">
        {songs.map((song) => {
          const isSelected =
            selectedSongs[currentLanguage]?.includes(song.id)

          return (
            <div
              key={song.id}
              className={`song-card ${isSelected ? "selected" : ""}`}
              onClick={() => toggleSong(song.id)}
            >
              <div className="song-cover" />

              <div className="song-info">
                <p className="song-name">{song.title}</p>
                <p className="song-artist">{song.artist}</p>
              </div>
            </div>
          )
        })}
      </div>

      <button
        className={`next-button ${canGoNext ? "active" : "disabled"}`}
        onClick={handleNext}
        disabled={!canGoNext}
      >
        {isLastStep ? "START →" : "NEXT →"}
      </button>
    </div>
  )
}

export default SongOnboardingPage
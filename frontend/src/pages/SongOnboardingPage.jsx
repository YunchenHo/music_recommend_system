import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import "../styles/SongOnboardingPage.css";

export default function SongOnboardingPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const selectedLanguages = location.state?.selectedLanguages || ["Chinese", "English","Japanese", "Korean"];
  const selectedArtists = location.state?.selectedArtists || [];

  /*const selectedLanguages = ["Chinese", "English", "Japanese", "Korean"]; */

  const songData = {
    Chinese: [
      { id: 1, title: "晴天", artist: "周杰倫", cover: "/songs-cover/song-cover.png" },
      { id: 2, title: "小幸運", artist: "田馥甄", cover: "/songs-cover/song-cover.png" },
      { id: 3, title: "慢冷", artist: "梁靜茹", cover: "/songs-cover/song-cover.png" },
      { id: 4, title: "演員", artist: "薛之謙", cover: "/songs-cover/song-cover.png" },
      { id: 5, title: "告白氣球", artist: "周杰倫", cover: "/songs-cover/song-cover.png" },
      { id: 6, title: "我很好騙", artist: "動力火車", cover: "/songs-cover/song-cover.png" },
      { id: 7, title: "說好的幸福呢", artist: "周杰倫", cover: "/songs-cover/song-cover.png" },
      { id: 8, title: "年少有為", artist: "李榮浩", cover: "/songs-cover/song-cover.png" },
      { id: 9, title: "體面", artist: "于文文", cover: "/songs-cover/song-cover.png" },
      { id: 10, title: "追光者", artist: "岑寧兒", cover: "/songs-cover/song-cover.png" },
      { id: 11, title: "如果可以", artist: "韋禮安", cover: "/songs-cover/song-cover.png" },
      { id: 12, title: "倒帶", artist: "蔡依林", cover: "/songs-cover/song-cover.png" },
    ],

    English: [
      { id: 101, title: "Shape of You", artist: "Ed Sheeran", cover: "/songs-cover/song-cover.png" },
      { id: 102, title: "Love Story", artist: "Taylor Swift", cover: "/songs-cover/song-cover.png" },
      { id: 103, title: "Blinding Lights", artist: "The Weeknd", cover: "/songs-cover/song-cover.png" },
      { id: 104, title: "Photograph", artist: "Ed Sheeran", cover: "/songs-cover/song-cover.png" },
      { id: 105, title: "Someone Like You", artist: "Adele", cover: "/songs-cover/song-cover.png" },
      { id: 106, title: "Perfect", artist: "Ed Sheeran", cover: "/songs-cover/song-cover.png" },
      { id: 107, title: "Thinking Out Loud", artist: "Ed Sheeran", cover: "/songs-cover/song-cover.png" },
      { id: 108, title: "All of Me", artist: "John Legend", cover: "/songs-cover/song-cover.png" },
      { id: 109, title: "Stay", artist: "The Kid LAROI", cover: "/songs-cover/song-cover.png" },
      { id: 110, title: "Senorita", artist: "Shawn Mendes", cover: "/songs-cover/song-cover.png" },
      { id: 111, title: "Bad Guy", artist: "Billie Eilish", cover: "/songs-cover/song-cover.png" },
      { id: 112, title: "Levitating", artist: "Dua Lipa", cover: "/songs-cover/song-cover.png" },
    ],

    Japanese: [
      { id: 201, title: "Lemon", artist: "米津玄師", cover: "/songs-cover/song-cover.png" },
      { id: 202, title: "Pretender", artist: "Official髭男dism", cover: "/songs-cover/song-cover.png" },
      { id: 203, title: "夜に駆ける", artist: "YOASOBI", cover: "/songs-cover/song-cover.png" },
      { id: 204, title: "マリーゴールド", artist: "あいみょん", cover: "/songs-cover/song-cover.png" },
      { id: 205, title: "残響散歌", artist: "Aimer", cover: "/songs-cover/song-cover.png" },
      { id: 206, title: "ドライフラワー", artist: "優里", cover: "/songs-cover/song-cover.png" },
      { id: 207, title: "群青", artist: "YOASOBI", cover: "/songs-cover/song-cover.png" },
      { id: 208, title: "なんでもないや", artist: "RADWIMPS", cover: "/songs-cover/song-cover.png" },
      { id: 209, title: "ひまわりの約束", artist: "秦基博", cover: "/songs-cover/song-cover.png" },
      { id: 210, title: "炎", artist: "LiSA", cover: "/songs-cover/song-cover.png" },
      { id: 211, title: "打上花火", artist: "DAOKO × 米津玄師", cover: "/songs-cover/song-cover.png" },
      { id: 212, title: "アイドル", artist: "YOASOBI", cover: "/songs-cover/song-cover.png" },
    ],

    Korean: [
      { id: 301, title: "Dynamite", artist: "BTS", cover: "/songs-cover/song-cover.png" },
      { id: 302, title: "How You Like That", artist: "BLACKPINK", cover: "/songs-cover/song-cover.png" },
      { id: 303, title: "Love Scenario", artist: "iKON", cover: "/songs-cover/song-cover.png" },
      { id: 304, title: "Next Level", artist: "aespa", cover: "/songs-cover/song-cover.png" },
      { id: 305, title: "Hype Boy", artist: "NewJeans", cover: "/songs-cover/song-cover.png" },
      { id: 306, title: "Ditto", artist: "NewJeans", cover: "/songs-cover/song-cover.png" },
      { id: 307, title: "Seven", artist: "Jungkook", cover: "/songs-cover/song-cover.png" },
      { id: 308, title: "Love Dive", artist: "IVE", cover: "/songs-cover/song-cover.png" },
      { id: 309, title: "Growl", artist: "EXO", cover: "/songs-cover/song-cover.png" },
      { id: 310, title: "Gee", artist: "Girls' Generation", cover: "/songs-cover/song-cover.png" },
      { id: 311, title: "Spring Day", artist: "BTS", cover: "/songs-cover/song-cover.png" },
      { id: 312, title: "Psycho", artist: "Red Velvet", cover: "/songs-cover/song-cover.png" },
    ],
  };

  const [currentStep, setCurrentStep] = useState(0);
  const stepKeys = selectedLanguages;
  const currentLanguage = stepKeys[currentStep];

  const [selectedSongs, setSelectedSongs] = useState({
    Chinese: [],
    English: [],
    Japanese: [],
    Korean: [],
  });

  const songs = songData[currentLanguage] || [];

  const toggleSong = (id) => {
    const current = selectedSongs[currentLanguage] || [];

    if (current.includes(id)) {
      setSelectedSongs({
        ...selectedSongs,
        [currentLanguage]: current.filter((songId) => songId !== id),
      });
    } else {
      if (current.length >= 4) return;
      setSelectedSongs({
        ...selectedSongs,
        [currentLanguage]: [...current, id],
      });
    }
  };

  const canGoNext = (selectedSongs[currentLanguage] || []).length === 4;
  const isLastStep = currentStep === stepKeys.length - 1;

  const handleNext = () => {
    if (!canGoNext) return;

    if (isLastStep) {
      console.log("Selected songs:", selectedSongs);
      navigate("/home");
    } else {
      setCurrentStep((prev) => prev + 1);
    }
  };

  const handlePrev = () => {
    if (currentStep === 0) return;
    setCurrentStep((prev) => prev - 1);
  };

  return (
    <div className="song-onboarding-page">
      <div className="song-onboarding-card">
        <p className="song-step-text">
          Step {currentStep + 1} / {stepKeys.length}
        </p>

        <h1 className="song-onboarding-title">
          Pick at least 4 songs you like in <span>{currentLanguage}</span>
        </h1>

        <p className="song-onboarding-subtitle">
          Selected: {(selectedSongs[currentLanguage] || []).length} / 4
        </p>

        <div className="song-grid">
          {songs.map((song) => {
            const isSelected = (selectedSongs[currentLanguage] || []).includes(song.id);

            return (
              <button
                key={song.id}
                className={`song-card ${isSelected ? "selected" : ""}`}
                onClick={() => toggleSong(song.id)}
                type="button"
              >
                <div className="song-card-inner">
                  <img src={song.cover} alt={song.title} className="song-cover" />
                  <div className="song-info">
                    <h3>{song.title}</h3>
                    <p>{song.artist}</p>
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        <div className="song-onboarding-actions">
          <button
            className="nav-button secondary"
            onClick={handlePrev}
            disabled={currentStep === 0}
            type="button"
          >
            ← Back
          </button>

          <button
            className={`nav-button primary ${!canGoNext ? "disabled" : ""}`}
            onClick={handleNext}
            disabled={!canGoNext}
            type="button"
          >
            {isLastStep ? "START →" : "NEXT →"}
          </button>
        </div>
      </div>
    </div>
  );
}
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
      { id: 1262202, title: "晴天", artist: "周杰倫", cover: "/songs-cover/song-cover.png" },
      { id: 1654654, title: "小幸運", artist: "田馥甄", cover: "/songs-cover/song-cover.png" },
      { id: 904399, title: "夢醒時分", artist: "伍佰 & China Blue", cover: "/songs-cover/song-cover.png" }, 
      { id: 551976, title: "演員", artist: "薛之謙", cover: "/songs-cover/song-cover.png" },
      { id: 1118607, title: "告白氣球", artist: "周杰倫", cover: "/songs-cover/song-cover.png" },
      { id: 1262259, title: "我很好騙", artist: "動力火車", cover: "/songs-cover/song-cover.png" },
      { id: 556389, title: "說好的幸福呢", artist: "周杰倫", cover: "/songs-cover/song-cover.png" },
      { id: 523020, title: "焚情", artist: "張信哲 ", cover: "/songs-cover/song-cover.png" },
      { id: 1589161, title: "私奔到月球", artist: "五月天 ", cover: "/songs-cover/song-cover.png" },
      { id: 334128, title: "夜會", artist: "王菲 ", cover: "/songs-cover/song-cover.png" },
      { id: 1567790, title: "如果可以", artist: "韋禮安", cover: "/songs-cover/song-cover.png" },
      { id: 803123, title: "倒帶", artist: "蔡依林", cover: "/songs-cover/song-cover.png" },
    ],

    English: [
      { id: 689229, title: "Shape of You", artist: "Ed Sheeran", cover: "/songs-cover/song-cover.png" },
      { id: 1919590, title: "Love Story", artist: "Taylor Swift", cover: "/songs-cover/song-cover.png" },
      { id: 1392127, title: "Everglow", artist: "Coldplay", cover: "/songs-cover/song-cover.png" },
      { id: 2109591, title: "Photograph", artist: "Ed Sheeran", cover: "/songs-cover/song-cover.png" },
      { id: 1453829, title: "Someone Like You", artist: "Adele", cover: "/songs-cover/song-cover.png" },
      { id: 13468, title: "Losers", artist: "The Weeknd", cover: "/songs-cover/song-cover.png" },
      { id: 402252, title: "Thinking Out Loud", artist: "Ed Sheeran", cover: "/songs-cover/song-cover.png" },
      { id: 1804300, title: "All of Me", artist: "John Legend", cover: "/songs-cover/song-cover.png" },
      { id: 139694, title: "Do What U Want", artist: "Lady Gaga", cover: "/songs-cover/song-cover.png" },
      { id: 50398, title: "The One That Got Away", artist: "Katy Perry", cover: "/songs-cover/song-cover.png" },
      { id: 416909, title: "Eagle", artist: "ABBA", cover: "/songs-cover/song-cover.png" },
      { id: 1779285, title: "Youth", artist: "Daughter", cover: "/songs-cover/song-cover.png" },
    ],

    Japanese: [
      { id: 1938707, title: "うつし絵", artist: "Yui Aragaki (新垣結衣)", cover: "/songs-cover/song-cover.png" },
      { id: 1221880	, title: "誕生日の夜", artist: "AKB48", cover: "/songs-cover/song-cover.png" },
      { id: 1644537, title: "ブラックアウト", artist: "Tokyo Incidents", cover: "/songs-cover/song-cover.png" },
      { id: 2155543, title: "make it happen", artist: "Namie Amuro (安室奈美恵)", cover: "/songs-cover/song-cover.png" },
      { id: 1697710, title: "shooting star", artist: "Ai Otsuka (大塚愛)", cover: "/songs-cover/song-cover.png" },
      { id: 422571, title: "ドライフラワー", artist: "優里", cover: "/songs-cover/song-cover.png" },
      { id: 1502091, title: "Risky", artist: "LiSA", cover: "/songs-cover/song-cover.png" },
      { id: 552011, title: "夏日情懷", artist: "MISIA", cover: "/songs-cover/song-cover.png" },
      { id: 78734, title: "ひまわりの約束", artist: "秦基博", cover: "/songs-cover/song-cover.png" },
      { id: 1073371, title: "Love in the Ice", artist: "Tohoshinki (東方神起)", cover: "/songs-cover/song-cover.png" },
      { id: 407150, title: "胸キュン", artist: "AOA", cover: "/songs-cover/song-cover.png" },
      { id: 925086, title: "アイドル", artist: "YOASOBI", cover: "/songs-cover/song-cover.png" },
    ],

    Korean: [
      { id: 1867000, title: "PLAYING WITH FIRE", artist: "BLACKPINK", cover: "/songs-cover/song-cover.png" },
      { id: 792933	, title: "Believe", artist: "SUPER JUNIOR", cover: "/songs-cover/song-cover.png" },
      { id: 1021592, title: "Shake It", artist: "BIGBANG", cover: "/songs-cover/song-cover.png" },
      { id: 1358918	, title: "미운오리", artist: "IU", cover: "/songs-cover/song-cover.png" },
      { id: 1543538, title: "Very Very Very", artist: "I.O.I", cover: "/songs-cover/song-cover.png" },
      { id: 2126048, title: "THE LEADERS", artist: "G-DRAGON", cover: "/songs-cover/song-cover.png" },
      { id: 335663, title: "So Good", artist: "Jay Park", cover: "/songs-cover/song-cover.png" },
      { id: 308, title: "My Romeo", artist: "Jessi", cover: "/songs-cover/song-cover.png" },
      { id: 1217522, title: "Growl", artist: "EXO", cover: "/songs-cover/song-cover.png" },
      { id: 488759, title: "Gee", artist: "Girls' Generation", cover: "/songs-cover/song-cover.png" },
      { id: 2096562, title: "그렇게 하면 돼", artist: "Lena Park", cover: "/songs-cover/song-cover.png" },
      { id: 1721221, title: "왜 나만 아프죠", artist: "IVY", cover: "/songs-cover/song-cover.png" },
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
      
      setSelectedSongs({
        ...selectedSongs,
        [currentLanguage]: [...current, id],
      });
    }
  };

  const canGoNext = (selectedSongs[currentLanguage] || []).length >= 4;
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
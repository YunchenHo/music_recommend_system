import { useState } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import "../styles/SongOnboardingPage.css";
import axios from "axios";

export default function SongOnboardingPage() {
  const navigate = useNavigate();
  const location = useLocation();

  const selectedLanguages = location.state?.selectedLanguages || ["Chinese", "English","Japanese", "Korean"];
  const selectedArtists = location.state?.selectedArtists || [];

  /*const selectedLanguages = ["Chinese", "English", "Japanese", "Korean"]; */

  const songData = {
    Chinese: [
      { id: 1262202, title: "晴天", artist: "周杰倫", cover: "/songs-cover/1262202.png" },
      { id: 1654654, title: "小幸運", artist: "田馥甄", cover: "/songs-cover/1654654.png" },
      { id: 904399, title: "夢醒時分", artist: "伍佰 & China Blue", cover: "/songs-cover/904399.png" }, 
      { id: 551976, title: "演員", artist: "薛之謙", cover: "/songs-cover/551976.png" },
      { id: 1118607, title: "告白氣球", artist: "周杰倫", cover: "/songs-cover/1118607.png" },
      { id: 892838, title: "沒空", artist: "小男孩樂團", cover: "/songs-cover/892838.png" },
      { id: 556389, title: "說好的幸福呢", artist: "周杰倫", cover: "/songs-cover/556389.png" },
      { id: 523020, title: "焚情", artist: "張信哲 ", cover: "/songs-cover/523020.png" },
      { id: 1589161, title: "私奔到月球", artist: "五月天 ", cover: "/songs-cover/1589161.png" },
      /*{ id: 334128, title: "夜會", artist: "王菲 ", cover: "/songs-cover/334128.png" },*/
      { id: 1567790, title: "如果可以", artist: "韋禮安", cover: "/songs-cover/1567790.png" },
      { id: 803123, title: "倒帶", artist: "蔡依林", cover: "/songs-cover/803123.png" },
      { id: 1053126, title: "煙", artist: "王菲", cover: "/songs-cover/1053126.png" },
    ],

    English: [
      /*{ id: 1456067, title: "Ballers Night Out", artist: "Snoop Dogg", cover: "/songs-cover/1456067.png" },*/
      { id: 1919590, title: "Love Story", artist: "Taylor Swift", cover: "/songs-cover/1919590.png" },
      { id: 1392127, title: "Everglow", artist: "Coldplay", cover: "/songs-cover/1392127.png" },
      { id: 2109591, title: "Photograph", artist: "Ed Sheeran", cover: "/songs-cover/2109591.png" },
      { id: 1453829, title: "Someone Like You", artist: "Adele", cover: "/songs-cover/1453829.png" },
      { id: 13468, title: "Losers", artist: "The Weeknd", cover: "/songs-cover/13468.png" },
      { id: 402252, title: "Thinking Out Loud", artist: "Ed Sheeran", cover: "/songs-cover/402252.png" },
      { id: 1804300, title: "All of Me", artist: "John Legend", cover: "/songs-cover/1804300.png" },
      { id: 139694, title: "Do What U Want", artist: "Lady Gaga", cover: "/songs-cover/139694.png" },
      { id: 50398, title: "The One That Got Away", artist: "Katy Perry", cover: "/songs-cover/50398.png" },
      { id: 416909, title: "Eagle", artist: "ABBA", cover: "/songs-cover/416909.png" },
      { id: 1779285, title: "Youth", artist: "Daughter", cover: "/songs-cover/1779285.png" },
      { id: 737112, title: "Unconditionally", artist: "Katy Perry", cover: "/songs-cover/737112.png" },
    ],

    Japanese: [
      /*{ id: 1938707, title: "うつし絵", artist: "Yui Aragaki (新垣結衣)", cover: "/songs-cover/1938707.png" },*/
      /*{ id: 1498037	, title: "Aishiteru", artist: "Base Ball Bear", cover: "/songs-cover/1498037.png" },*/
      /*{ id: 1644537, title: "ブラックアウト", artist: "Tokyo Incidents", cover: "/songs-cover/1644537.png" },*/
      { id: 2155543, title: "make it happen", artist: "Namie Amuro (安室奈美恵)", cover: "/songs-cover/2155543.png" },
      { id: 1697710, title: "shooting star", artist: "Ai Otsuka (大塚愛)", cover: "/songs-cover/1697710.png" },
      /*{ id: 1561165, title: "Slow Dancin'", artist: "松下優也", cover: "/songs-cover/1561165.png" },*/
      { id: 1502091, title: "Risky", artist: "LiSA", cover: "/songs-cover/1502091.png" },
      /*{ id: 552011, title: "夏日情懷", artist: "MISIA", cover: "/songs-cover/552011.png" },*/
      /*{ id: 78734, title: "ひまわりの約束", artist: "秦基博", cover: "/songs-cover/78734.png" },*/
      /*{ id: 1073371, title: "Love in the Ice", artist: "Tohoshinki (東方神起)", cover: "/songs-cover/1073371.png" },*/
      /*{ id: 407150, title: "胸キュン", artist: "AOA", cover: "/songs-cover/407150.png" },*/
      /*{ id: 1903626, title: "The New World", artist: "平原綾香", cover: "/songs-cover/1903626.png" },*/
      
      { id: 1472375, title: "Make-up Shadow", artist: "Julee Karan (樹里からん)", cover: "/songs-cover/1472375.png" },
      { id: 1150507, title: "Armstrong", artist: "Suchmos", cover: "/songs-cover/1150507.png" },
      { id: 1277043, title: "手紙", artist: "BRIGHT", cover: "/songs-cover/1277043.png" },
      { id: 1287172, title: "ピンクメトセラ", artist: "大森靖子", cover: "/songs-cover/1287172.png" },
      { id: 676747, title: "柊", artist: "Do As Infinity", cover: "/songs-cover/676747.png" },
      { id: 1140711, title: "空と君のあいだに", artist: "Ms.OOJA", cover: "/songs-cover/1140711.png" },
      { id: 2179993, title: "Dear My Dream", artist: "大原櫻子", cover: "/songs-cover/2179993.png" },
      { id: 1572095, title: "sapphire", artist: "Kalafina", cover: "/songs-cover/1572095.png" },
      { id: 444614, title: "秘密警察 (feat. 初音ミク)", artist: "Buriru (ぶりる)", cover: "/songs-cover/444614.png" },
    ],

    Korean: [
      { id: 1867000, title: "PLAYING WITH FIRE", artist: "BLACKPINK", cover: "/songs-cover/1867000.png" },
      { id: 792933	, title: "Believe", artist: "SUPER JUNIOR", cover: "/songs-cover/792933.png" },
      { id: 1021592, title: "Shake It", artist: "BIGBANG", cover: "/songs-cover/1021592.png" },
      { id: 1358918	, title: "미운오리", artist: "IU", cover: "/songs-cover/1358918.png" },
      { id: 1543538, title: "Very Very Very", artist: "I.O.I", cover: "/songs-cover/1543538.png" },
      { id: 2126048, title: "THE LEADERS", artist: "G-DRAGON", cover: "/songs-cover/2126048.png" },
      /*{ id: 335663, title: "So Good", artist: "Jay Park", cover: "/songs-cover/335663.png" },*/
      /*{ id: 308, title: "My Romeo", artist: "Jessi", cover: "/songs-cover/308.png" },*/
      { id: 273083, title: "Heaven", artist: "Ailee", cover: "/songs-cover/273083.png" },
      { id: 488759, title: "Gee", artist: "Girls' Generation", cover: "/songs-cover/488759.png" },
      /*{ id: 2267877, title: "오늘 밤", artist: "Hyolyn", cover: "/songs-cover/2267877.png" },*/
      /*{ id: 1721221, title: "왜 나만 아프죠", artist: "IVY", cover: "/songs-cover/1721221.png" },*/
      { id: 572864, title: "SORRY SORRY", artist: "SUPER JUNIOR", cover: "/songs-cover/572864.png" },
      { id: 631589, title: "I Need A Girl", artist: "BIGBANG TAEYANG", cover: "/songs-cover/631589.png" },
      { id: 1061766, title: "Why You Think I'm In Love With You", artist: "Ailee", cover: "/songs-cover/1061766.png" },
      { id: 239868, title: "NoNoNo", artist: "Apink", cover: "/songs-cover/239868.png" },
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

const handleNext = async () => {
  if (!canGoNext) return;

  function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) {
      return parts.pop().split(";").shift();
    }
    return null;
  }

  if (isLastStep) {
    try {
      const allArtistIds = Array.isArray(selectedArtists)
        ? selectedArtists
        : Object.values(selectedArtists).flat();

      const allSongIds = Object.values(selectedSongs).flat();

      console.log("送出的資料：", {
        artist_ids: allArtistIds,
        song_ids: allSongIds,
      });

      const csrfToken = getCookie("csrftoken");

      await axios.post(
        "http://localhost:8000/api/onboarding/submit",
        {
          artist_ids: allArtistIds,
          song_ids: allSongIds,
        },
        {
          withCredentials: true,
          headers: {
            "X-CSRFToken": csrfToken,
          },
        }
      );

      navigate("/home");
    } catch (error) {
      console.error("API 錯誤:", error);
    }
  }
  else {
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
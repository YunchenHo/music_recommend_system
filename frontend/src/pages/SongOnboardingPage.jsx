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
      { id: 1567790, title: "如果可以", artist: "韋禮安", cover: "/songs-cover/1567790.png" },
      { id: 803123, title: "倒帶", artist: "蔡依林", cover: "/songs-cover/803123.png" },
      { id: 1053126, title: "煙", artist: "王菲", cover: "/songs-cover/1053126.png" },
    ],

    Chinese_page_2: [
      { id: 1483642, title: "愛我的資格", artist: "S.H.E", cover: "/songs-cover/1483642.png" },
      { id: 1883209, title: "裂縫中的陽光 (Before Sunrise)", artist: "林俊傑 (JJ Lin)", cover: "/songs-cover/1883209.png" },
      { id: 564287, title: "怎麼愛妳都不夠", artist: "蔡旻佑 (Evan Yo)", cover: "/songs-cover/564287.png" },
      { id: 1506585, title: "若你碰到他", artist: "蔡健雅 (Tanya Chua)", cover: "/songs-cover/1506585.png" },
      { id: 2273260, title: "諾言", artist: "李翊君", cover: "/songs-cover/2273260.png" },
      { id: 1232433, title: "懂事", artist: "孫燕姿 (Yanzi Sun)", cover: "/songs-cover/1232433.png" },
      { id: 2295038, title: "左邊右邊", artist: "蕭煌奇 (Ricky Hsiao)", cover: "/songs-cover/2295038.png" },
      { id: 2140547, title: "壞與更壞", artist: "林宥嘉 (Yoga Lin)", cover: "/songs-cover/2140547.png" },
      { id: 63274, title: "本色", artist: "八三夭 (The Last Day of Summer 831)", cover: "/songs-cover/63274.png" },
      { id: 1328974, title: "第三者", artist: "梁靜茹 (Fish Leong)", cover: "/songs-cover/1328974.png" },
      { id: 826361, title: "愛上每一個你", artist: "伍思凱 (Sky Wu)", cover: "/songs-cover/826361.png" },
      { id: 1589258, title: "彼得與狼", artist: "蘇打綠 (Sodagreen)", cover: "/songs-cover/1589258.png" },
    ],

    English: [
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

    English_page_2: [
      { id: 1149186, title: "Welcome To New York", artist: "Swifty", cover: "/songs-cover/1149186.png" },
      { id: 1724103, title: "Passenger", artist: "OneRepublic", cover: "/songs-cover/1724103.png" },
      { id: 677692, title: "Welcome Home", artist: "Radical Face", cover: "/songs-cover/677692.png" },
      { id: 362714, title: "I'm Alive", artist: "Celine Dion", cover: "/songs-cover/362714.png" },
      { id: 86165, title: "Moments (時時刻刻)", artist: "One Direction", cover: "/songs-cover/86165.png" },
      { id: 2172832, title: "SOS", artist: "ABBA", cover: "/songs-cover/2172832.png" },
      { id: 1279785, title: "Party", artist: "Beyoncé", cover: "/songs-cover/1279785.png" },
      { id: 689642, title: "FML", artist: "Kanye West", cover: "/songs-cover/689642.png" },
      { id: 1795422, title: "Three Empty Words", artist: "Shawn Mendes", cover: "/songs-cover/1795422.png" },
      { id: 888703, title: "#SELFIE", artist: "The Chainsmokers", cover: "/songs-cover/888703.png" },
      { id: 1999726, title: "Mercy", artist: "Kanye West", cover: "/songs-cover/1999726.png" },
      { id: 1232175, title: "Faded", artist: "Alan Walker", cover: "/songs-cover/1232175.png" },
    ],

    Japanese: [
      { id: 2155543, title: "make it happen", artist: "Namie Amuro (安室奈美恵)", cover: "/songs-cover/2155543.png" },
      { id: 1697710, title: "shooting star", artist: "Ai Otsuka (大塚愛)", cover: "/songs-cover/1697710.png" },
      { id: 1502091, title: "Risky", artist: "LiSA", cover: "/songs-cover/1502091.png" },
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

    Japanese_page_2: [
      { id: 1932928, title: "Viva Happy - feat. 初音未來", artist: "Mitchie M feat.初音未來", cover: "/songs-cover/1932928.png" },
      { id: 1096737, title: "永遠常在 (木村弓)", artist: "ジブリサウンドトラック", cover: "/songs-cover/1096737.png" },
      { id: 504248, title: "SANSARA世界", artist: "Kousuke Atari (中孝介)", cover: "/songs-cover/504248.png" },
      { id: 1206201, title: "Still Lovin' You", artist: "Namie Amuro (安室奈美恵)", cover: "/songs-cover/1206201.png" },
      { id: 988584, title: "Heart | Mind and Soul", artist: "Tohoshinki (東方神起)", cover: "/songs-cover/988584.png" },
      { id: 44970, title: "オレンジ", artist: "GReeeeN", cover: "/songs-cover/44970.png" },
      { id: 359296, title: "心心相映", artist: "Rimi Natsukawa (夏川りみ)", cover: "/songs-cover/359296.png" },
      { id: 2038056, title: "微かなカオリ", artist: "Perfume", cover: "/songs-cover/2038056.png" },
      { id: 2129156, title: "Merikoku Christmas madeni", artist: "erica", cover: "/songs-cover/2129156.png" },
      { id: 133152, title: "Gift", artist: "Mika Nakashima (中島美嘉)", cover: "/songs-cover/133152.png" },
      { id: 1175874, title: "Heavenly Star", artist: "Rei Yasuda (安田 レイ)", cover: "/songs-cover/1175874.png" },
      { id: 1733503, title: "我就是愛你", artist: "Shota Shimizu (清水翔太)", cover: "/songs-cover/1733503.png" },
    ],

    Korean: [
      { id: 1867000, title: "PLAYING WITH FIRE", artist: "BLACKPINK", cover: "/songs-cover/1867000.png" },
      { id: 792933	, title: "Believe", artist: "SUPER JUNIOR", cover: "/songs-cover/792933.png" },
      { id: 1021592, title: "Shake It", artist: "BIGBANG", cover: "/songs-cover/1021592.png" },
      { id: 1358918	, title: "미운오리", artist: "IU", cover: "/songs-cover/1358918.png" },
      { id: 1543538, title: "Very Very Very", artist: "I.O.I", cover: "/songs-cover/1543538.png" },
      { id: 2126048, title: "THE LEADERS", artist: "G-DRAGON", cover: "/songs-cover/2126048.png" },
      { id: 273083, title: "Heaven", artist: "Ailee", cover: "/songs-cover/273083.png" },
      { id: 488759, title: "Gee", artist: "Girls' Generation", cover: "/songs-cover/488759.png" },
      { id: 572864, title: "SORRY SORRY", artist: "SUPER JUNIOR", cover: "/songs-cover/572864.png" },
      { id: 631589, title: "I Need A Girl", artist: "BIGBANG TAEYANG", cover: "/songs-cover/631589.png" },
      { id: 1061766, title: "Why You Think I'm In Love With You", artist: "Ailee", cover: "/songs-cover/1061766.png" },
      { id: 239868, title: "NoNoNo", artist: "Apink", cover: "/songs-cover/239868.png" },
    ],
    
    Korean_page_2: [
      { id: 2152202, title: "I Think I'm in Love", artist: "JUNIEL", cover: "/songs-cover/2152202.png" },
      { id: 1108032, title: "리얼러브송", artist: "Baek Z Young", cover: "/songs-cover/1108032.png" },
      { id: 2283098, title: "On Top of Your Head", artist: "San E", cover: "/songs-cover/2283098.png" },
      { id: 728628, title: "TRUST", artist: "GFRIEND", cover: "/songs-cover/728628.png" },
      { id: 1786342, title: "Miniskirt", artist: "AOA", cover: "/songs-cover/1786342.png" },
      { id: 137913, title: "I’m in love (feat. 에일리)", artist: "2LSON", cover: "/songs-cover/137913.png" },
      { id: 658423, title: "공드리", artist: "hyukoh", cover: "/songs-cover/658423.png" },
      { id: 1839569, title: "White Love", artist: "MONSTA X", cover: "/songs-cover/1839569.png" },
      { id: 105862, title: "Because Of You", artist: "Parc Jae Jung", cover: "/songs-cover/105862.png" },
      { id: 1621969, title: "Raise Your Heels", artist: "Jessi", cover: "/songs-cover/1621969.png" },
      { id: 353447, title: "마음 전쟁", artist: "시나 쓰는 앨리스", cover: "/songs-cover/353447.png" },
      { id: 448302, title: "Gossip Man", artist: "G-DRAGON", cover: "/songs-cover/448302.png" },
    ],
  };
  const [songPageToggle, setSongPageToggle] = useState({
    Chinese: false,
    English: false,
    Japanese: false,
    Korean: false,
  });

  const handleRefreshSongs = () => {
    setSongPageToggle((prev) => ({
      ...prev,
      [currentLanguage]: !prev[currentLanguage],
    }));
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

const songs =
  songData[
    songPageToggle[currentLanguage]
      ? `${currentLanguage}_page_2`
      : currentLanguage
  ] || [];

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

        <div className="song-title-row">
          <h1 className="song-onboarding-title">
            Pick at least 4 songs you like in <span>{currentLanguage}</span>
          </h1>

          <button
            type="button"
            className="song-refresh-button"
            onClick={handleRefreshSongs}
          >
            ↻ Refresh
          </button>
        </div>

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
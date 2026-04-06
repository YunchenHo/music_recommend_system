import { useState } from "react"
import "../styles/HomePage.css"

// ── 假資料（之後後端替換）──────────────────────────────
// 系統內建清單：已收藏的歌曲
const FAKE_PLAYLIST = [
  { id: 1,  title: "Let it Go",        artist: "Idina Menzel" },
  { id: 2,  title: "Someone Like You", artist: "Adele" },
  { id: 3,  title: "Sorry",            artist: "Justin Bieber" },
  { id: 4,  title: "Baby",             artist: "Justin Bieber" },
  { id: 5,  title: "Honey Pie",        artist: "The Beatles" },
  { id: 6,  title: "Lover",            artist: "Taylor Swift" },
  { id: 16, title: "Catch Me If You Can", artist: "Girls' Generation" },
  { id: 17, title: "Dynamite",         artist: "BTS" },
  { id: 18, title: "Bad Guy",          artist: "Billie Eilish" },
  { id: 19, title: "Flowers",          artist: "Miley Cyrus" },
  { id: 20, title: "Anti-Hero",        artist: "Taylor Swift" },
]

const FAKE_RECOMMENDATIONS = [
  { id: 7,  title: "Perfect",              artist: "Ed Sheeran" },
  { id: 8,  title: "Shake It Off",         artist: "Taylor Swift" },
  { id: 9,  title: "小幸運",               artist: "田馥甄" },
  { id: 10, title: "Don't Leave Me Alone", artist: "David Guetta" },
  { id: 11, title: "Blinding Lights",      artist: "The Weeknd" },
  { id: 12, title: "Shape of You",         artist: "Ed Sheeran" },
  { id: 13, title: "Stay",                 artist: "Justin Bieber" },
  { id: 14, title: "Levitating",           artist: "Dua Lipa" },
  { id: 15, title: "As It Was",            artist: "Harry Styles" },
]

// ── 假用戶資料（之後從 session / context 取）──────────
const FAKE_USER = {
  nickname: "Janet",
  profilePicture: null, // null → 顯示預設頭像
}

// ─────────────────────────────────────────────────────
export default function HomePage() {
  // 目前顯示的頁面：'home' | 'search'
  const [view, setView] = useState("home")

  // 目前播放的歌曲（null = 尚未播放）
  const [currentSong, setCurrentSong] = useState(null)

  // 是否正在播放
  const [isPlaying, setIsPlaying] = useState(false)

  // 播放指定歌曲
  const handlePlay = (song) => {
    setCurrentSong(song)
    setIsPlaying(true)
  }

  // 切換播放 / 暫停
  const togglePlay = () => setIsPlaying((prev) => !prev)

  // 已收藏的歌曲清單展開/收合
  const [isPlaylistOpen, setIsPlaylistOpen] = useState(false)

  return (
    <div className="home-page">

      {/* ── 左側：音樂庫 ── */}
      <aside className="left-panel">
        <h2 className="panel-title">你的音樂庫</h2>

        {/* 系統內建清單：已收藏的歌曲 */}
        <div className="library-section">

          {/* 清單卡片按鈕 */}
          <button
            className={`playlist-card ${isPlaylistOpen ? "open" : ""}`}
            onClick={() => setIsPlaylistOpen((prev) => !prev)}
          >
            <div className="playlist-card-thumb">
              <img src="/yeah-rabbit.svg" alt="rabbit" />
            </div>
            <div className="playlist-card-info">
              <span className="playlist-card-name">已收藏的歌曲</span>
              <span className="playlist-card-meta">
                播放清單 • {FAKE_PLAYLIST.length} 首歌曲
              </span>
            </div>
            <span className="playlist-card-chevron">
              {isPlaylistOpen ? "▲" : "▼"}
            </span>
          </button>

          {/* 展開的歌曲清單 */}
          {isPlaylistOpen && (
            <ul className="playlist">
              {FAKE_PLAYLIST.map((song) => (
                <li
                  key={song.id}
                  className={`playlist-item ${currentSong?.id === song.id ? "active" : ""}`}
                  onClick={() => handlePlay(song)}
                >
                  {song.title}
                </li>
              ))}
            </ul>
          )}
        </div>
      </aside>

      {/* ── 中間：Navbar + 可切換內容 ── */}
      <main className="main-panel">

        {/* Navbar */}
        <nav className="navbar">
          {/* 左：Logo */}
          <div className="navbar-logo">
            <img src="/yeah-rabbit.svg" alt="rabbit" className="navbar-rabbit" />
            <span className="navbar-brand">Metube</span>
          </div>

          {/* 中：切換按鈕 */}
          <div className="navbar-nav">
            <button
              className={`nav-btn ${view === "home" ? "active" : ""}`}
              onClick={() => setView("home")}
              title="首頁"
            >
              🏠
            </button>
            <button
              className={`nav-btn ${view === "search" ? "active" : ""}`}
              onClick={() => setView("search")}
              title="搜尋"
            >
              🔍
            </button>
          </div>

          {/* 右：用戶資訊 */}
          <div className="navbar-user">
            <span className="navbar-greeting">一起嗨吧！{FAKE_USER.nickname}</span>
            <div className="avatar">
              {FAKE_USER.profilePicture
                ? <img src={FAKE_USER.profilePicture} alt="avatar" />
                : <span className="avatar-placeholder">🐰</span>
              }
            </div>
          </div>
        </nav>

        {/* 內容區 */}
        <div className="content-area">

          {/* Home 視圖：Recommendation 九宮格（B 負責）*/}
          {view === "home" && (
            <section className="home-view">
              <h2 className="section-title">Recommendation</h2>
              <div className="recommendation-grid">
                {FAKE_RECOMMENDATIONS.map((song) => (
                  <div
                    key={song.id}
                    className={`song-card ${currentSong?.id === song.id ? "active" : ""}`}
                    onClick={() => handlePlay(song)}
                  >
                    <p className="song-card-title">{song.title}</p>
                    <p className="song-card-artist">{song.artist}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Search 視圖：假 UI（B 負責）*/}
          {view === "search" && (
            <section className="search-view">
              <div className="search-bar-wrap">
                <input
                  className="search-input"
                  type="text"
                  placeholder="搜尋歌曲、藝人..."
                />
                <button className="search-btn">🔍</button>
              </div>
              <p className="search-hint">輸入關鍵字開始搜尋</p>
            </section>
          )}

        </div>
      </main>

      {/* ── 右側：Player（B 負責）── */}
      <aside className="right-panel">
        {!currentSong ? (
          /* 尚未播放 */
          <div className="player-welcome">
            <img src="/yeah-rabbit.svg" alt="rabbit" className="player-rabbit" />
            <p className="welcome-title">WELCOME</p>
            <p className="welcome-sub">Start Playing !</p>
          </div>
        ) : (
          /* 播放中 */
          <div className="player-playing">
            <div className={`rabbit-glow-wrap ${isPlaying ? "spinning" : ""}`}>
              <img src="/yeah-rabbit.svg" alt="rabbit" className="player-rabbit" />
            </div>
            <p className="now-title">{currentSong.title}</p>
            <p className="now-artist">{currentSong.artist}</p>

            {/* 互動按鈕 */}
            <div className="player-actions">
              <button className="action-btn" title="喜歡">👍</button>
              <button className="action-btn" title="不喜歡">👎</button>
              <button className="action-btn" title="收藏至已收藏的歌曲">🔖</button>
              <button className="action-btn add-playlist-btn" title="加入播放清單">＋</button>
            </div>

            {/* 播放控制 */}
            <button className="play-btn" onClick={togglePlay}>
              {isPlaying ? "⏸" : "▶"}
            </button>
          </div>
        )}
      </aside>

    </div>
  )
}

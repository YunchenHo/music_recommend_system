import { useState, useEffect } from "react"
import "../styles/HomePage.css"
import { getMe, getFavorites, addFavorite, removeFavorite } from "../api/songs"

// ── 推薦歌曲假資料（之後接 /api/songs/recommendations 替換）
const FAKE_RECOMMENDATIONS = [
  { id: 902,   song_title: "陽光宅男", artist_name: "周杰倫 (Jay Chou)" },
  { id: 4660,  song_title: "好久不見", artist_name: "周杰倫 (Jay Chou)" },
  { id: 11571, song_title: "Fifteen", artist_name: "Taylor Swift" },
  { id: 6573,  song_title: "When We Were Young", artist_name: "Adele" },
  { id: 16111, song_title: "Make You Feel My Love", artist_name: "Adele" },
  { id: 96999, song_title: "Runaway", artist_name: "Ed Sheeran" },
  { id: 8901,  song_title: "愛情釀的酒", artist_name: "五月天 (Mayday)" },
  { id: 7900,  song_title: "Good To Be Bad", artist_name: "G.E.M.鄧紫棋" },
  { id: 15451, song_title: "18", artist_name: "G.E.M.鄧紫棋" },
]

// ─────────────────────────────────────────────────────
export default function HomePage() {
  // 目前顯示的頁面：'home' | 'search'
  const [view, setView] = useState("home")

  // 目前播放的歌曲（null = 尚未播放）
  const [currentSong, setCurrentSong] = useState(null)

  // 是否正在播放
  const [isPlaying, setIsPlaying] = useState(false)

  // 已收藏的歌曲清單展開/收合
  const [isPlaylistOpen, setIsPlaylistOpen] = useState(false)

  const [liked, setLiked] = useState(false)
  const [disliked, setDisliked] = useState(false)

  // ── 從 API 取得的資料 ──────────────────────────────
  const [user, setUser] = useState({ nickname: "", profilePicture: null })
  const [favorites, setFavorites] = useState([])   // [{ id, song_title, artist_name }]

  // 收藏狀態由 favorites 清單推導（不需要額外 state）
  const isSaved = currentSong ? favorites.some((f) => f.id === currentSong.id) : false

  // 頁面載入時取得用戶資訊與收藏清單
  useEffect(() => {
    getMe()
      .then((data) => setUser({ nickname: data.username, profilePicture: data.profile_picture || null }))
      .catch(console.error)

    getFavorites()
      .then((data) => setFavorites(data))
      .catch(console.error)
  }, [])

  // 播放指定歌曲（切歌時重置 liked/disliked）
  const handlePlay = (song) => {
    setCurrentSong(song)
    setIsPlaying(true)
    setLiked(false)
    setDisliked(false)
  }

  // 切換播放 / 暫停
  const togglePlay = () => setIsPlaying((prev) => !prev)

  // 收藏 / 取消收藏
  const handleToggleSave = async () => {
    if (!currentSong) return

    if (isSaved) {
      try {
        await removeFavorite(currentSong.id)
        setFavorites((prev) => prev.filter((f) => f.id !== currentSong.id))
      } catch (err) {
        console.error("移除收藏失敗", err)
      }
    } else {
      try {
        await addFavorite(currentSong.id)
        setFavorites((prev) => [
          ...prev,
          { id: currentSong.id, song_title: currentSong.song_title, artist_name: currentSong.artist_name },
        ])
      } catch (err) {
        console.error("加入收藏失敗", err)
      }
    }
  }

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
                播放清單 • {favorites.length} 首歌曲
              </span>
            </div>
            <span className="playlist-card-chevron">
              {isPlaylistOpen ? "▲" : "▼"}
            </span>
          </button>

          {/* 展開的歌曲清單 */}
          {isPlaylistOpen && (
            <ul className="playlist">
              {favorites.map((song) => (
                <li
                  key={song.id}
                  className={`playlist-item ${currentSong?.id === song.id ? "active" : ""}`}
                  onClick={() => handlePlay(song)}
                >
                  {song.song_title}
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
              className={`nav-icon-btn ${view === "home" ? "active" : ""}`}
              onClick={() => setView("home")}
              title="首頁"
            >
              <img src="/home.svg" alt="home" />
            </button>

            <button
              className={`nav-icon-btn ${view === "search" ? "active" : ""}`}
              onClick={() => setView("search")}
              title="搜尋"
            >
              <img src="/search.svg" alt="search" />
            </button>
          </div>

          {/* 右：用戶資訊 */}
          <div className="navbar-user">
            <span className="navbar-greeting">一起嗨吧！{user.nickname}</span>
            <div className="avatar">
              {user.profilePicture
                ? <img src={user.profilePicture} alt="avatar" />
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
                    <p className="song-card-title">{song.song_title}</p>
                    <p className="song-card-artist">{song.artist_name}</p>
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
                <button className="search-btn">
                  <img src="/search.svg" alt="search" />
                </button>
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
            <p className="now-title">{currentSong.song_title}</p>
            <p className="now-artist">{currentSong.artist_name}</p>

            {/* 互動按鈕 */}
            <div className="player-actions">
              <button
                className={`action-btn-new ${liked ? "active" : ""}`}
                onClick={() => {
                  setLiked(prev => !prev)
                  setDisliked(false)  
                }}
                title="喜歡"
              >
                <img src="/good.svg" alt="like" className="good-icon" />
              </button>

              <button
                className={`action-btn-new ${disliked ? "active" : ""}`}
                onClick={() => {
                  setDisliked(prev => !prev)
                  setLiked(false)   
                }}
                title="不喜歡"
              >
                <img src="/bad.svg" alt="dislike" className="bad-icon" />
              </button>

              <button
                className={`action-btn-new ${isSaved ? "active" : ""}`}
                onClick={handleToggleSave}
                title="收藏至已收藏的歌曲"
              >
                <img src="/keep.svg" alt="keep" className="keep-icon" />
              </button>

              <button
                className="action-btn-new"
                title="加入播放清單"
              >
                <img src="/add.svg" alt="add" className="add-icon" />
              </button>

            </div>

            {/* 播放控制 */}
            <button className="play-btn" onClick={togglePlay} title={isPlaying ? "暫停" : "播放"}>
              <img
                src={isPlaying ? "/pause.svg" : "/play.svg"}
                alt={isPlaying ? "pause" : "play"}
                className="play-icon"
              />
            </button>
          </div>
        )}
      </aside>

    </div>
  )
}


/*
            <div className="player-actions">
              <button className="action-btn-new" title="喜歡">
                <img src="/good.svg" alt="like" className="good-icon" />
              </button>
              <button className="action-btn-new" title="不喜歡">
                <img src="/bad.svg" alt="dislike" className="bad-icon" />
              </button>
              <button className="action-btn-new" title="收藏至已收藏的歌曲">
                <img src="/keep.svg" alt="keep" className="keep-icon" />
              </button>
              <button className="action-btn-new" title="加入播放清單">
                <img src="/add.svg" alt="add" className="add-icon" />
              </button>
            </div>

            */
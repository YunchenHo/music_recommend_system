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

const FAKE_REVISIT = [
  { id: 2001, song_title: "Lover", artist_name: "Taylor Swift" },
  { id: 2002, song_title: "Baby", artist_name: "Justin Bieber" },
  { id: 2003, song_title: "Let It Go", artist_name: "Elsa" },
  { id: 2004, song_title: "Honey Pie", artist_name: "Jawny" },
  { id: 2005, song_title: "Flowers", artist_name: "Miley Cyrus" },
  { id: 2006, song_title: "Sorry", artist_name: "Justin Bieber" },
  { id: 2007, song_title: "Dynamite", artist_name: "BTS" },
  { id: 2008, song_title: "Someone Like You", artist_name: "Adele" },
]

const FAKE_FRIENDS = [
  { id: 3001, friend_name: "小美", song_title: "River Flows in You", artist_name: "Yiruma" },
  { id: 3002, friend_name: "智華", song_title: "Call Me Maybe", artist_name: "Carly Rae Jepsen" },
  { id: 3003, friend_name: "雅婷", song_title: "三天三夜", artist_name: "張惠妹" },
  { id: 3005, friend_name: "小安", song_title: "晴天", artist_name: "周杰倫" },
  { id: 3006, friend_name: "小琪", song_title: "Anti-Hero", artist_name: "Taylor Swift" },
  { id: 3007, friend_name: "小杰", song_title: "Perfect", artist_name: "Ed Sheeran" },
  { id: 3008, friend_name: "小葵", song_title: "Bad Guy", artist_name: "Billie Eilish" },
]

const FAKE_USERS = [
  {
    id: 1,
    gmail: "amy@gmail.com",
    username: "小美",
    profile_picture: null,
  },
  {
    id: 2,
    gmail: null,
    username: "智華",
    profile_picture: null,
  },
  {
    id: 3,
    gmail: "ting@gmail.com",
    username: "雅婷",
    profile_picture: null,
  },
  {
    id: 4,
    gmail: "doong@gmail.com",
    username: "昱婷",
    profile_picture: null,
  },
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

  const [isHistoryOpen, setIsHistoryOpen] = useState(false)
  const [historySongs, setHistorySongs] = useState([
    { id: 9001, song_title: "Let It Go", artist_name: "Elsa" },
    { id: 9002, song_title: "Sorry", artist_name: "Justin Bieber" },
    { id: 9003, song_title: "Flowers", artist_name: "Miley Cyrus" },
  ])

  const [liked, setLiked] = useState(false)
  const [disliked, setDisliked] = useState(false)

  const [revisitStart, setRevisitStart] = useState(0)
  const [friendStart, setFriendStart] = useState(0)

  const CARD_PAGE_SIZE = 4

  const [isFriendsModalOpen, setIsFriendsModalOpen] = useState(false)
  const [friendsModalView, setFriendsModalView] = useState("friends") // "friends" | "myFriends"
  const [friendSearchInput, setFriendSearchInput] = useState("")
  const [searchedUser, setSearchedUser] = useState(null)
  const [friendSearchError, setFriendSearchError] = useState("")
  const [myFriends, setMyFriends] = useState([
    { id: 101, username: "小美", profile_picture: null },
    { id: 102, username: "智華", profile_picture: null },
    { id: 103, username: "雅婷", profile_picture: null },
  ])

  const [customPlaylists, setCustomPlaylists] = useState([
    { id: 1, name: "Sad Songs", songs: [] },
    { id: 2, name: "Party Songs", songs: [] },
  ])

  const [isPlaylistModalOpen, setIsPlaylistModalOpen] = useState(false)
  const [playlistModalView, setPlaylistModalView] = useState("list") 
  // "list" | "create"

  const [newPlaylistName, setNewPlaylistName] = useState("")
  const [playlistNameError, setPlaylistNameError] = useState("")

  const [openCustomPlaylistId, setOpenCustomPlaylistId] = useState(null)

  // ── 從 API 取得的資料 ──────────────────────────────
  const [user, setUser] = useState({ nickname: "", profilePicture: null })
  const [favorites, setFavorites] = useState([])   // [{ id, song_title, artist_name }]

  // 收藏狀態由 favorites 清單推導（不需要額外 state）
  const isSaved = currentSong ? favorites.some((f) => f.id === currentSong.id) : false

    const revisitVisible = [
    ...FAKE_REVISIT,
    ...FAKE_REVISIT,
  ].slice(revisitStart, revisitStart + CARD_PAGE_SIZE)

  const friendVisible = [
    ...FAKE_FRIENDS,
    ...FAKE_FRIENDS,
  ].slice(friendStart, friendStart + CARD_PAGE_SIZE)

  const handleNextRevisit = () => {
    setRevisitStart((prev) => (prev + CARD_PAGE_SIZE) % FAKE_REVISIT.length)
  }

  const handleNextFriend = () => {
    setFriendStart((prev) => (prev + CARD_PAGE_SIZE) % FAKE_FRIENDS.length)
  }

  const openFriendsModal = () => {
    setIsFriendsModalOpen(true)
    setFriendsModalView("friends")
    setFriendSearchInput("")
    setSearchedUser(null)
    setFriendSearchError("")
  }

  const closeFriendsModal = () => {
    setIsFriendsModalOpen(false)
    setFriendsModalView("friends")
    setFriendSearchInput("")
    setSearchedUser(null)
    setFriendSearchError("")
  }

  const handleSearchFriend = () => {
    const keyword = friendSearchInput.trim().toLowerCase()

    if (!keyword) {
      setSearchedUser(null)
      setFriendSearchError("請輸入 Gmail")
      return
    }

    const foundUser = FAKE_USERS.find(
      (user) => user.gmail.toLowerCase() === keyword
    )

    if (foundUser) {
      setSearchedUser(foundUser)
      setFriendSearchError("")
    } else {
      setSearchedUser(null)
      setFriendSearchError("查無此人")
    }
  }

  const handleAddFriend = (user) => {
    const alreadyAdded = myFriends.some((friend) => friend.username === user.username)

    if (!alreadyAdded) {
      setMyFriends((prev) => [
        ...prev,
        {
          id: user.id,
          username: user.username,
          profile_picture: user.profile_picture || null,
        },
      ])
    }

    closeFriendsModal()
  }

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

    setHistorySongs((prev) => {
      const filtered = prev.filter((item) => item.id !== song.id)
      return [
        {
          id: song.id,
          song_title: song.song_title,
          artist_name: song.artist_name,
        },
        ...filtered,
      ]
    })
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

  const openPlaylistModal = () => {
    if (!currentSong) return
    setIsPlaylistModalOpen(true)
    setPlaylistModalView("list")
    setNewPlaylistName("")
    setPlaylistNameError("")
  }

  const closePlaylistModal = () => {
    setIsPlaylistModalOpen(false)
    setPlaylistModalView("list")
    setNewPlaylistName("")
    setPlaylistNameError("")
  }

  const handleAddSongToPlaylist = (playlistId) => {
    if (!currentSong) return

    setCustomPlaylists((prev) =>
      prev.map((playlist) => {
        if (playlist.id !== playlistId) return playlist

        const alreadyExists = playlist.songs.some((song) => song.id === currentSong.id)
        if (alreadyExists) return playlist

        return {
          ...playlist,
          songs: [...playlist.songs, currentSong],
        }
      })
    )

    closePlaylistModal()
  }

  const handleCreatePlaylist = () => {
    const trimmedName = newPlaylistName.trim()

    if (!trimmedName) {
      setPlaylistNameError("Please fill out")
      return
    }

    const duplicated = customPlaylists.some(
      (playlist) => playlist.name.trim().toLowerCase() === trimmedName.toLowerCase()
    )

    if (duplicated) {
      setPlaylistNameError("Playlist already exists")
      return
    }

    const newPlaylist = {
      id: Date.now(),
      name: trimmedName,
      songs: currentSong ? [currentSong] : [],
    }

    setCustomPlaylists((prev) => [...prev, newPlaylist])
    closePlaylistModal()
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

          <button
            className={`playlist-card ${isHistoryOpen ? "open" : ""}`}
            onClick={() => setIsHistoryOpen((prev) => !prev)}
          >
            <div className="playlist-card-thumb">
              <img src="/yeah-rabbit.svg" alt="rabbit" />
            </div>
            <div className="playlist-card-info">
              <span className="playlist-card-name">歷史紀錄</span>
              <span className="playlist-card-meta">
                最近播放 • {historySongs.length} 首歌曲
              </span>
            </div>
            <span className="playlist-card-chevron">
              {isHistoryOpen ? "▲" : "▼"}
            </span>
          </button>

          {isHistoryOpen && (
            <ul className="playlist">
              {historySongs.map((song) => (
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
          {customPlaylists.map((playlist) => (
            <div key={playlist.id}>
              <button
                className={`playlist-card ${openCustomPlaylistId === playlist.id ? "open" : ""}`}
                onClick={() =>
                  setOpenCustomPlaylistId((prev) =>
                    prev === playlist.id ? null : playlist.id
                  )
                }
              >
                <div className="playlist-card-thumb">
                  <img src="/yeah-rabbit.svg" alt="rabbit" />
                </div>
                <div className="playlist-card-info">
                  <span className="playlist-card-name">{playlist.name}</span>
                  <span className="playlist-card-meta">
                    播放清單 • {playlist.songs.length} 首歌曲
                  </span>
                </div>
                <span className="playlist-card-chevron">
                  {openCustomPlaylistId === playlist.id ? "▲" : "▼"}
                </span>
              </button>

              {openCustomPlaylistId === playlist.id && (
                <ul className="playlist">
                  {playlist.songs.length > 0 ? (
                    playlist.songs.map((song) => (
                      <li
                        key={song.id}
                        className={`playlist-item ${currentSong?.id === song.id ? "active" : ""}`}
                        onClick={() => handlePlay(song)}
                      >
                        {song.song_title}
                      </li>
                    ))
                  ) : (
                    <li className="playlist-item empty-playlist-item">
                      尚無歌曲
                    </li>
                  )}
                </ul>
              )}
            </div>
          ))}
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

              {/* 重溫舊愛 */}
              <section className="sub-section">
                <div className="sub-section-header">
                  <h3 className="sub-section-title">重溫舊愛</h3>
                  <button className="more-btn" onClick={handleNextRevisit}>
                    more &gt;
                  </button>
                </div>

                <div className="horizontal-card-list">
                  {revisitVisible.map((song) => (
                    <div
                      key={song.id}
                      className={`small-song-card ${currentSong?.id === song.id ? "active" : ""}`}
                      onClick={() => handlePlay(song)}
                    >
                      <p className="small-song-title">{song.song_title}</p>
                      <p className="small-song-artist">{song.artist_name}</p>
                    </div>
                  ))}
                </div>
              </section>

              {/* 你的朋友也在聽 */}
              <section className="sub-section">
                <div className="sub-section-header">
                  <h3 className="sub-section-title">你的朋友也在聽</h3>
                  <button className="more-btn" onClick={handleNextFriend}>
                    more &gt;
                  </button>
                </div>

                <div className="horizontal-card-list">
                  {friendVisible.slice(0, 3).map((item) => (
                    <div
                      key={item.id}
                      className="friend-card"
                      onClick={() => {
                        handlePlay({
                          id: item.id,
                          song_title: item.song_title,
                          artist_name: item.artist_name,
                        })
                      }}
                    >
                      <p className="friend-name">{item.friend_name}</p>
                      <p className="friend-song">{item.song_title}</p>
                      {item.artist_name && <p className="friend-artist">{item.artist_name}</p>}
                    </div>
                  ))}

                  <button
                    className="friend-card search-friend-card"
                    onClick={openFriendsModal}
                    type="button"
                  >
                    <p className="friend-search-text">Search Your Friends!</p>
                  </button>
                </div>
              </section>
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
                onClick={openPlaylistModal}
                disabled={!currentSong}
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
      {isFriendsModalOpen && (
        <div className="friends-modal-overlay">
          <div className="friends-modal" onClick={(e) => e.stopPropagation()}>
            {friendsModalView === "friends" && (
              <>
                <div className="friends-modal-header">
                  <h2 className="friends-modal-title">Friends</h2>
                  <button className="friends-close-btn" onClick={closeFriendsModal}>
                    ×
                  </button>
                </div>

                <div className="friends-search-row">
                  <input
                    type="text"
                    className="friends-search-input"
                    placeholder="請輸入 Gmail"
                    value={friendSearchInput}
                    onChange={(e) => setFriendSearchInput(e.target.value)}
                  />
                  <button className="friends-search-btn" onClick={handleSearchFriend}>
                    搜尋
                  </button>
                </div>

                <div className="friends-search-result-area">
                  {searchedUser && (
                    <button
                      className="searched-user-card"
                      onClick={() => handleAddFriend(searchedUser)}
                    >
                      <div className="searched-user-avatar">
                        {searchedUser.profile_picture ? (
                          <img src={searchedUser.profile_picture} alt={searchedUser.username} />
                        ) : (
                          <span>👤</span>
                        )}
                      </div>
                      <span className="searched-user-name">{searchedUser.username}</span>
                    </button>
                  )}

                  {friendSearchError && (
                    <p className="friend-search-error">{friendSearchError}</p>
                  )}
                </div>

                <div className="friends-modal-footer">
                  <button
                    className="view-my-friends-btn"
                    onClick={() => setFriendsModalView("myFriends")}
                  >
                    View My Friends
                  </button>
                </div>
              </>
            )}

            {friendsModalView === "myFriends" && (
              <>
                <div className="friends-modal-header">
                  <button
                    className="friends-back-btn"
                    onClick={() => setFriendsModalView("friends")}
                  >
                    ←
                  </button>
                  <h2 className="friends-modal-title">My Friends</h2>
                  <button className="friends-close-btn" onClick={closeFriendsModal}>
                    ×
                  </button>
                </div>

                <div className="my-friends-list">
                  {myFriends.map((friend) => (
                    <div key={friend.id} className="my-friend-item">
                      <div className="my-friend-avatar">
                        {friend.profile_picture ? (
                          <img src={friend.profile_picture} alt={friend.username} />
                        ) : (
                          <span>👤</span>
                        )}
                      </div>
                      <span className="my-friend-name">{friend.username}</span>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        </div>
      )}
      {isPlaylistModalOpen && (
        <div className="playlist-modal-overlay">
          <div className="playlist-modal" onClick={(e) => e.stopPropagation()}>
            {playlistModalView === "list" && (
              <>
                <div className="playlist-modal-header">
                  <h2 className="playlist-modal-title">My Playlist</h2>
                  <button className="playlist-close-btn" onClick={closePlaylistModal}>
                    ×
                  </button>
                </div>

                <div className="playlist-modal-list">
                  {customPlaylists.map((playlist) => (
                    <button
                      key={playlist.id}
                      className="playlist-modal-item"
                      onClick={() => handleAddSongToPlaylist(playlist.id)}
                    >
                      <div className="playlist-modal-item-icon">
                        <img src="/yeah-rabbit.svg" alt="rabbit" />
                      </div>

                      <div className="playlist-modal-item-info">
                        <span className="playlist-modal-item-name">{playlist.name}</span>
                        <span className="playlist-modal-item-count">
                          {playlist.songs.length} 首歌曲
                        </span>
                      </div>
                    </button>
                  ))}
                </div>

                <div className="playlist-modal-footer">
                  <button
                    className="create-playlist-btn"
                    onClick={() => {
                      setPlaylistModalView("create")
                      setPlaylistNameError("")
                    }}
                  >
                    + Create Playlist
                  </button>
                </div>
              </>
            )}

            {playlistModalView === "create" && (
              <>
                <div className="playlist-modal-header">
                  <button
                    className="playlist-back-btn"
                    onClick={() => {
                      setPlaylistModalView("list")
                      setPlaylistNameError("")
                    }}
                  >
                    ←
                  </button>

                  <h2 className="playlist-modal-title">Create New Playlist</h2>

                  <button className="playlist-close-btn" onClick={closePlaylistModal}>
                    ×
                  </button>
                </div>

                <div className="playlist-create-body">
                  <label className="playlist-input-label">Playlist Name</label>

                  <div className="playlist-input-row">
                    <input
                      type="text"
                      className="playlist-name-input"
                      value={newPlaylistName}
                      onChange={(e) => {
                        setNewPlaylistName(e.target.value)
                        setPlaylistNameError("")
                      }}
                      placeholder="Please fill out"
                    />

                    {playlistNameError && (
                      <span className="playlist-input-tooltip">
                        {playlistNameError}
                      </span>
                    )}
                  </div>

                  <div className="playlist-create-actions">
                    <button
                      className="playlist-create-confirm-btn"
                      onClick={handleCreatePlaylist}
                    >
                      Create
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}
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
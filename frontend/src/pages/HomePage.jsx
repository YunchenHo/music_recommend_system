import { useState, useEffect, useRef, useCallback } from "react"
import YouTube from "react-youtube"
import "../styles/HomePage.css"
import {
  getMe, getFavorites, addFavorite, removeFavorite, getRecommendations,
  getPlaylists, createPlaylist, getPlaylistSongs, addSongToPlaylist,
  removeSongFromPlaylist, 
  searchSongs,
  updatePlaylist, deletePlaylist,  
} from "../api/songs"
import { searchYouTubeVideoId } from "../api/youtube"
import { getHistory, createHistory, updateHistory, deleteHistory, HISTORY_SOURCE } from "../api/history"
import { toggleLike, getLikeStatus } from "../api/likes"
import { logoutUser } from "../api/auth"
import { useNavigate } from "react-router-dom"

import {
  searchFriend,
  getMyFriends,
  addFriend,
  getFriendListening,
} from "../api/friends"

// ── 推薦歌曲（從 API 取得）

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

const PLAYLIST_ICONS = [
  "yeah-rabbit.svg",
  "mifi.svg",
  "jojo.svg",
  "egg.svg",
  "ahhh.svg",
  "angry_heart.svg",
  "chicken_nugget.svg",
  "one_punch.svg",
  "cutie.svg",
  "star.svg",
  "tail.svg",
]

const LEVEL_TITLES = [
  "一群芝麻粒", "一塊麵包胚", "一片生菜葉",
  "一顆煎雞蛋", "一塊大雞排", "一顆漢堡王",
]
// 每個等級升到下一級所需 XP：LV1→50, LV2→100, LV3→200, LV4→400, LV5→800
const LEVEL_XP_THRESHOLDS = [50, 100, 200, 400, 800]

// TODO: 待串接後端 API
const MOCK_USER_LEVEL = { lv: 1, xp: 0 }
const MOCK_CHALLENGES = [
  { id: 1, prefix: "聆聽", n: 3, suffix: "首歌曲", done: false },
  { id: 2, prefix: "加入", n: 2, suffix: "首歌曲至個人清單", done: true },
  { id: 3, prefix: "對", n: 4, suffix: "首歌曲按讚或倒讚", done: false },
]

function BurgerVisual({ lv }) {
  return (
    <div className="burger-stack">
      {lv >= 6 && <img src="/hamburger/crown.svg" className="burger-crown" alt="crown" />}
      {lv >= 2 ? (
        <div className="burger-top-bun-wrap">
          <img src="/hamburger/top-bun.svg" className="burger-top-bun" alt="top bun" />
          <img src="/hamburger/sesame.svg"  className="burger-sesame-on-bun" alt="sesame" />
        </div>
      ) : (
        <img src="/hamburger/sesame.svg" className="burger-sesame-pile" alt="sesame" />
      )}
      {lv >= 3 && <img src="/hamburger/lettuce.svg"    className="burger-lettuce"    alt="lettuce"    />}
      {lv >= 4 && <img src="/hamburger/egg.svg"        className="burger-egg"        alt="egg"        />}
      {lv >= 5 && <img src="/hamburger/chicken.svg"    className="burger-chicken"    alt="chicken"    />}
      {lv >= 2 && <img src="/hamburger/bottom-bun.svg" className="burger-bottom-bun" alt="bottom bun" />}
    </div>
  )
}


// ─────────────────────────────────────────────────────
export default function HomePage() {

  const navigate = useNavigate()

  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false)

  const handleLogout = async () => {
    try {
      const res = await logoutUser()

      console.log("logout success", res)

      navigate("/")
    } catch (err) {
      console.log(err)
      console.log(err.response)
      console.log(err.response?.data)

      alert("logout failed")
    }
  }

  const [nameError, setNameError] = useState("")

  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false)
  const [selectedSong, setSelectedSong] = useState(null)
  const [selectedPlaylistId, setSelectedPlaylistId] = useState(null)
  // 'favorites' | 'playlist' | 'history'
  const [deleteContext, setDeleteContext] = useState("favorites")
  // 目前顯示的頁面：'home' | 'search'
  const [view, setView] = useState("home")

  // 目前播放的歌曲（null = 尚未播放）
  const [currentSong, setCurrentSong] = useState(null)

  // 是否正在播放
  const [isPlaying, setIsPlaying] = useState(false)

  // 已收藏的歌曲清單展開/收合
  const [isPlaylistOpen, setIsPlaylistOpen] = useState(false)

  const [isHistoryOpen, setIsHistoryOpen] = useState(false)
  // historySongs: [{ id, song_title, artist_name }]，由後端 history API 載入
  const [historySongs, setHistorySongs] = useState([])

  const [liked, setLiked] = useState(false)
  const [disliked, setDisliked] = useState(false)

  // 追蹤「目前正在播放」的歌曲、來源與其在後端對應的 history id
  // - historyId: POST /api/auth/history 回傳的 id（POST 還沒回來時為 null）
  // - createPromise: POST 的 Promise，flush 時用來等到 id
  const playbackRef = useRef({
    song: null,
    source: null,
    historyId: null,
    createPromise: null,
  })

  // 單曲循環
  const [isLooping, setIsLooping] = useState(false)
  const isLoopingRef = useRef(false)

  // 清單循環播放佇列：{ songs: [], index: number } | null
  const queueRef = useRef(null)

  const [youtubeVideoId, setYoutubeVideoId] = useState(null)
  const [isLoadingVideo, setIsLoadingVideo] = useState(false)
  const playerRef = useRef(null)
  const lastTimeRef = useRef(0)

  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const progressIntervalRef = useRef(null)

  useEffect(() => {
    if (isPlaying) {
      progressIntervalRef.current = setInterval(() => {
        if (playerRef.current) {
          const t = playerRef.current.getCurrentTime() || 0
          lastTimeRef.current = t
          setCurrentTime(t)
          setDuration(playerRef.current.getDuration() || 0)
        }
      }, 500)
    } else {
      clearInterval(progressIntervalRef.current)
    }
    return () => clearInterval(progressIntervalRef.current)
  }, [isPlaying, youtubeVideoId])

  const isDragging = useRef(false)
  const [dragTime, setDragTime] = useState(null)

  const formatTime = (secs) => {
    if (!secs || isNaN(secs)) return "0:00"
    const m = Math.floor(secs / 60)
    const s = Math.floor(secs % 60)
    return `${m}:${s.toString().padStart(2, "0")}`
  }

  const calcSeekTime = (e, el) => {
    const rect = el.getBoundingClientRect()
    const ratio = Math.min(Math.max((e.clientX - rect.left) / rect.width, 0), 1)
    return ratio * duration
  }

  const [revisitStart, setRevisitStart] = useState(0)
  const [friendStart, setFriendStart] = useState(0)

  const CARD_PAGE_SIZE = 4

  const [isFriendsModalOpen, setIsFriendsModalOpen] = useState(false)
  const [friendsModalView, setFriendsModalView] = useState("friends") // "friends" | "myFriends"
  const [friendSearchInput, setFriendSearchInput] = useState("")
  const [searchedUser, setSearchedUser] = useState(null)
  const [friendSearchError, setFriendSearchError] = useState("")
  const [myFriends, setMyFriends] = useState([])
  const [friendListening, setFriendListening] = useState([])

  const [customPlaylists, setCustomPlaylists] = useState([])
  // Each playlist: { id, playlist_name, song_count, songs: [...] | null }
  // songs 為 null 表示尚未載入（lazy load）

  const [isEditPlaylistModalOpen, setIsEditPlaylistModalOpen] = useState(false)
  const [editingPlaylist, setEditingPlaylist] = useState(null)

  const [editView, setEditView] = useState("menu") 
  // "menu" | "name" | "icon"

  const [editName, setEditName] = useState("")
  const [editIcon, setEditIcon] = useState(null)

  const [isPlaylistModalOpen, setIsPlaylistModalOpen] = useState(false)
  const [playlistModalView, setPlaylistModalView] = useState("list")
  // "list" | "create"
  const [selectedPlaylistIcon, setSelectedPlaylistIcon] = useState(PLAYLIST_ICONS[0])

  const [newPlaylistName, setNewPlaylistName] = useState("")
  const [playlistNameError, setPlaylistNameError] = useState("")

  const [openCustomPlaylistId, setOpenCustomPlaylistId] = useState(null)
  const [isDailyChallengeOpen, setIsDailyChallengeOpen] = useState(false)

  useEffect(() => {
    setIsDailyChallengeOpen(true)
  }, [])

  // ── 從 API 取得的資料 ──────────────────────────────
  const [user, setUser] = useState({ nickname: "", profilePicture: null })
  const [favorites, setFavorites] = useState([])   // [{ id, song_title, artist_name }]
  const [recommendations, setRecommendations] = useState([])  // [{ rank, id, song_title, artist_name, ... }]

  // ── 搜尋 ──
  const [searchQuery, setSearchQuery] = useState("")
  const [searchResults, setSearchResults] = useState([])
  const [isSearching, setIsSearching] = useState(false)
  const searchTimerRef = useRef(null)

  // 收藏狀態由 favorites 清單推導（不需要額外 state）
  const isSaved = currentSong ? favorites.some((f) => f.id === currentSong.id) : false

    const revisitVisible = [
    ...FAKE_REVISIT,
    ...FAKE_REVISIT,
  ].slice(revisitStart, revisitStart + CARD_PAGE_SIZE)

  const isRevisitUnlocked = historySongs.length >= 5
  const isFriendsUnlocked = historySongs.length >= 10

  const friendVisible = friendListening.slice(
    friendStart,
    friendStart + CARD_PAGE_SIZE
  )

  const handleNextRevisit = () => {
    setRevisitStart((prev) => (prev + CARD_PAGE_SIZE) % FAKE_REVISIT.length)
  }

  const handleNextFriend = () => {
    if (friendListening.length <= CARD_PAGE_SIZE) return

    setFriendStart((prev) => {
      const next = prev + CARD_PAGE_SIZE
      return next >= friendListening.length ? 0 : next
    })
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

  const handleSearchFriend = async () => {
    const email = friendSearchInput.trim()

    if (!email) {
      setSearchedUser(null)
      setFriendSearchError("請輸入 Gmail")
      return
    }

    try {
      const user = await searchFriend(email)

      setSearchedUser(user)
      setFriendSearchError("")
    } catch (err) {
      setSearchedUser(null)
      setFriendSearchError("查無此人")
    }
  }

  const handleAddFriend = async (user) => {
    try {
      await addFriend(user.id)

      const friends = await getMyFriends()
      setMyFriends(friends)

      const listening = await getFriendListening()
      setFriendListening(listening)

      closeFriendsModal()
    } catch (err) {
      setFriendSearchError("新增好友失敗")
    }
  }

  // 頁面載入時取得用戶資訊、收藏清單、推薦歌曲、自訂清單、歷史紀錄
  useEffect(() => {
    getMe()
      .then((data) => setUser({ nickname: data.username, profilePicture: data.profile_picture || null }))
      .catch(console.error)

    getFavorites()
      .then((data) => setFavorites(data))
      .catch(console.error)

    getRecommendations()
      .then((data) => setRecommendations(data))
      .catch(console.error)

    getPlaylists()
      .then((data) =>
        setCustomPlaylists(
          data.map((p) => ({ ...p, songs: null }))
        )
      )
      .catch(console.error)

    // 載入歷史紀錄（取最近 20 筆，去重後過濾使用者手動隱藏的歌）
    getHistory({ limit: 20 })
      .then((resp) => {
        const items = resp?.data ?? []
        const seen = new Set()
        const deduped = []
        for (const it of items) {
          if (seen.has(it.song_id)) continue
          seen.add(it.song_id)
          deduped.push({
            id: it.song_id,
            history_id: it.id,
            song_title: it.song_title,
            artist_name: it.artist_name,
            song_image: it.song_image,
            album_name: it.album_name,
            language: it.language,
          })
        }
        setHistorySongs(deduped)
      })
      .catch(console.error)

    getMyFriends()
      .then((data) => setMyFriends(data))
      .catch(console.error)

    getFriendListening()
      .then((data) => setFriendListening(data))
      .catch(console.error)

  }, [])

  // 把上一首的「實際聽到秒數」PATCH 進已建立的那筆 history
  // 在切歌、結束、卸載時呼叫；不會 await（fire-and-forget）
  const flushCurrentHistory = useCallback(() => {
    // 先把 ref snapshot 取出並清空，避免後面 handlePlay 覆寫造成競態
    const snapshot = playbackRef.current
    playbackRef.current = { song: null, source: null, historyId: null, createPromise: null }

    if (!snapshot.song || !snapshot.source) return

    const seconds = lastTimeRef.current
    // 真的沒播到就不更新（紀錄保持 watch_seconds=0）
    if (!seconds || seconds < 1) return

    // 等 POST 回來拿 id，再 PATCH watch_seconds
    ;(async () => {
      let id = snapshot.historyId
      if (!id && snapshot.createPromise) {
        try {
          const resp = await snapshot.createPromise
          id = resp?.data?.id ?? null
        } catch {
          id = null
        }
      }
      if (!id) return
      try {
        await updateHistory(id, seconds)
      } catch (err) {
        console.error("更新 history 失敗", err)
      }
    })()
  }, [])

  // 播放指定歌曲（切歌時重置 liked/disliked）
  // source: HISTORY_SOURCE.* — 點擊來源，會寫入後端 history
  const handlePlay = async (song, source = HISTORY_SOURCE.RECOMMENDATION) => {
    // 切歌前先把上一首聽到的秒數背景 PATCH 出去
    flushCurrentHistory()

    setCurrentSong(song)
    setIsPlaying(true)
    setLiked(false)
    setDisliked(false)
    setIsLooping(false)
    isLoopingRef.current = false

    // 點到歌就立刻 POST 一筆紀錄（watch_seconds=0），確保即使馬上 refresh 也不會掉
    const createPromise = createHistory({
      songId: song.id,
      watchSeconds: 0,
      source,
    })
      .then((resp) => {
        // 若此時還在播放同一首，就把後端回傳的 id 寫回 ref，後續 PATCH 用
        if (
          playbackRef.current.song?.id === song.id &&
          playbackRef.current.source === source
        ) {
          playbackRef.current.historyId = resp?.data?.id ?? null
        }
        return resp
      })
      .catch((err) => {
        console.error("建立 history 失敗", err)
        return null
      })

    playbackRef.current = { song, source, historyId: null, createPromise }

    // 從後端取得這首歌的喜歡 / 不喜歡狀態，還原 UI
    getLikeStatus(song.id)
      .then((resp) => {
        const isLiked = resp?.data?.is_liked
        setLiked(isLiked === true)
        setDisliked(isLiked === false)
      })
      .catch((err) => console.error("取得 like 狀態失敗", err))

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

    clearInterval(progressIntervalRef.current)
    playerRef.current = null
    lastTimeRef.current = 0
    setYoutubeVideoId(null)
    setCurrentTime(0)
    setDuration(0)
    setIsLoadingVideo(true)
    try {
      const videoId = await searchYouTubeVideoId(song.song_title, song.artist_name)
      setYoutubeVideoId(videoId)
    } catch (err) {
      console.error("YouTube 搜尋失敗", err)
    } finally {
      setIsLoadingVideo(false)
    }
  }

  // 卸載時送出最後一首的 history
  useEffect(() => {
    return () => {
      flushCurrentHistory()
    }
  }, [flushCurrentHistory])

  // 喜歡 / 不喜歡：呼叫後端 toggleLike，根據回傳更新 UI
  const handleToggleLike = async (intentLike) => {
    if (!currentSong) return
    try {
      const resp = await toggleLike(currentSong.id, intentLike)
      const isLiked = resp?.data?.is_liked
      // is_liked: true / false / null（取消）
      setLiked(isLiked === true)
      setDisliked(isLiked === false)
    } catch (err) {
      console.error("toggle like 失敗", err)
    }
  }

  // 切換單曲循環
  const toggleLoop = () => {
    setIsLooping((prev) => {
      isLoopingRef.current = !prev
      return !prev
    })
  }

  // 從清單播放：設定佇列並播放指定索引的歌
  const handlePlayFromQueue = (songs, index, source) => {
    queueRef.current = { songs, index, source }
    handlePlay(songs[index], source)
  }

  // 上一首 / 下一首
  const handlePrev = () => {
    const q = queueRef.current
    if (!q || q.songs.length < 2) return
    const prevIndex = (q.index - 1 + q.songs.length) % q.songs.length
    queueRef.current = { ...q, index: prevIndex }
    handlePlay(q.songs[prevIndex], q.source || HISTORY_SOURCE.PLAYLIST)
  }

  const handleNext = () => {
    const q = queueRef.current
    if (!q || q.songs.length < 2) return
    const nextIndex = (q.index + 1) % q.songs.length
    queueRef.current = { ...q, index: nextIndex }
    handlePlay(q.songs[nextIndex], q.source || HISTORY_SOURCE.PLAYLIST)
  }

  // 切換播放 / 暫停
  const togglePlay = () => {
    setIsPlaying((prev) => {
      if (prev) {
        playerRef.current?.pauseVideo()
      } else {
        playerRef.current?.playVideo()
      }
      return !prev
    })
  }

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
    setSelectedPlaylistIcon(PLAYLIST_ICONS[0])
    setPlaylistNameError("")
  }

  const handleAddSongToPlaylist = async (playlistId) => {
    if (!currentSong) return

    try {
      await addSongToPlaylist(playlistId, currentSong.id)
      // 更新 local state 的 song_count
      setCustomPlaylists((prev) =>
        prev.map((p) => {
          if (p.id !== playlistId) return p
          const newSongs = p.songs
            ? [...p.songs, currentSong]
            : null
          return { ...p, song_count: p.song_count + 1, songs: newSongs }
        })
      )
      closePlaylistModal()
    } catch (err) {
      // 409 或 400 表示歌已在清單中
      console.error("加入清單失敗", err)
      closePlaylistModal()
    }
  }

  const handleCreatePlaylist = async () => {
    const trimmedName = newPlaylistName.trim()

    if (!trimmedName) {
      setPlaylistNameError("Please fill out")
      return
    }

    const duplicated = customPlaylists.some(
      (playlist) => playlist.playlist_name.trim().toLowerCase() === trimmedName.toLowerCase()
    )

    if (duplicated) {
      setPlaylistNameError("Playlist already exists")
      return
    }

    try {
      const newPlaylist = await createPlaylist(trimmedName)
      if (currentSong) {
        await addSongToPlaylist(newPlaylist.id, currentSong.id)
        setCustomPlaylists((prev) => [...prev, {
          ...newPlaylist, playlist_icon: selectedPlaylistIcon,
          song_count: 1, songs: [currentSong],
        }])
      } else {
        setCustomPlaylists((prev) => [...prev, {
          ...newPlaylist, icon: selectedPlaylistIcon, songs: null,
        }])
      }
      closePlaylistModal()
    } catch (err) {
      console.error("建立清單失敗", err)
      setPlaylistNameError("Failed to create playlist")
    }
  }

  // 展開自訂清單時 lazy load 歌曲
  const handleToggleCustomPlaylist = async (playlistId) => {
    if (openCustomPlaylistId === playlistId) {
      setOpenCustomPlaylistId(null)
      return
    }

    setOpenCustomPlaylistId(playlistId)

    // 如果 songs 尚未載入，從 API 取得
    const playlist = customPlaylists.find((p) => p.id === playlistId)
    if (playlist && playlist.songs === null) {
      try {
        const songs = await getPlaylistSongs(playlistId)
        setCustomPlaylists((prev) =>
          prev.map((p) => (p.id === playlistId ? { ...p, songs } : p))
        )
      } catch (err) {
        console.error("載入清單歌曲失敗", err)
      }
    }
  }
    // 從歷史紀錄刪除（前端隱藏，後端資料保留供推薦系統使用）
  const handleDeleteFromHistory = async () => {
    if (selectedSong.history_id) {
      await deleteHistory(selectedSong.history_id).catch(console.error)
    }
    setHistorySongs((prev) => prev.filter((s) => s.id !== selectedSong.id))
  }

  // ⭐ 刪除收藏
  const handleDeleteFromFavorites = async () => {
    try {
      await removeFavorite(selectedSong.id)
      setFavorites(prev => prev.filter(s => s.id !== selectedSong.id))
    } catch (err) {
      console.error(err)
    }
  }

  // ⭐ 刪除自訂 playlist
  const handleDeleteFromCustomPlaylist = async () => {
    try {
      // ⭐ 1. 打 API
      await removeSongFromPlaylist(selectedPlaylistId, selectedSong.id)

      // ⭐ 2. 更新前端
      setCustomPlaylists(prev =>
        prev.map(p => {
          if (p.id !== selectedPlaylistId) return p
          return {
            ...p,
            songs: p.songs.filter(s => s.id !== selectedSong.id),
            song_count: p.song_count - 1   // ⭐別忘這個
          }
        })
      )
    } catch (err) {
      console.error("刪除 playlist 歌曲失敗", err)
    }
  }

  // 搜尋（debounce 300ms）
  const handleSearchChange = useCallback((value) => {
    setSearchQuery(value)

    if (searchTimerRef.current) {
      clearTimeout(searchTimerRef.current)
    }

    if (!value.trim()) {
      setSearchResults([])
      setIsSearching(false)
      return
    }

    setIsSearching(true)
    searchTimerRef.current = setTimeout(async () => {
      try {
        const results = await searchSongs(value.trim())
        setSearchResults(results)
      } catch (err) {
        console.error("搜尋失敗", err)
        setSearchResults([])
      } finally {
        setIsSearching(false)
      }
    }, 300)
  }, [])

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
              {favorites.map((song, idx) => (
                <li
                  key={song.id}
                  className={`playlist-item ${currentSong?.id === song.id ? "active" : ""}`}
                  onClick={() => handlePlayFromQueue(favorites, idx, HISTORY_SOURCE.PLAYLIST)}
                >
                  <span className="playlist-song-title">
                    {song.song_title}
                  </span>

                  <span
                    className="playlist-more"
                    onClick={(e) => {
                      e.stopPropagation()
                      setSelectedSong(song)
                      setSelectedPlaylistId(null)
                      setDeleteContext("favorites")
                      setIsDeleteModalOpen(true)
                    }}
                  >
                    ⋯
                  </span>
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
              {historySongs.map((song, idx) => (
                <li
                  key={song.id}
                  className={`playlist-item ${currentSong?.id === song.id ? "active" : ""}`}
                  onClick={() => handlePlayFromQueue(historySongs, idx, HISTORY_SOURCE.PLAYLIST)}
                >
                  <span className="playlist-song-title">
                    {song.song_title}
                  </span>

                  <span
                    className="playlist-more"
                    onClick={(e) => {
                      e.stopPropagation()
                      setSelectedSong(song)
                      setDeleteContext("history")
                      setIsDeleteModalOpen(true)
                    }}
                  >
                    ⋯
                  </span>
                </li>
              ))}
            </ul>
          )}
          {customPlaylists.map((playlist) => (
            <div key={playlist.id}>
              <button
                className={`playlist-card ${openCustomPlaylistId === playlist.id ? "open" : ""}`}
                onClick={() => handleToggleCustomPlaylist(playlist.id)}
              >
                <div className="playlist-card-thumb">
                  <img src={`/album_icon/${playlist.playlist_icon || PLAYLIST_ICONS[0]}`} alt={playlist.playlist_name} />
                </div>
                <div className="playlist-card-info">
                  <span
                    className="playlist-card-name"
                    onClick={(e) => {
                      e.stopPropagation()

                      setEditingPlaylist(playlist)
                      setEditName(playlist.playlist_name)
                      setEditIcon(playlist.playlist_icon || PLAYLIST_ICONS[0])
                      setEditView("menu")
                      setIsEditPlaylistModalOpen(true)
                    }}
                  >
                    {playlist.playlist_name}
                  </span>
                  <span className="playlist-card-meta">
                    播放清單 • {playlist.song_count} 首歌曲
                  </span>
                </div>
                <span className="playlist-card-chevron">
                  {openCustomPlaylistId === playlist.id ? "▲" : "▼"}
                </span>
              </button>

              {openCustomPlaylistId === playlist.id && (
                <ul className="playlist">
                  {playlist.songs === null ? (
                    <li className="playlist-item empty-playlist-item">載入中...</li>
                  ) : playlist.songs.length > 0 ? (
                    playlist.songs.map((song, idx) => (
                      <li
                        key={song.id}
                        className={`playlist-item ${currentSong?.id === song.id ? "active" : ""}`}
                        onClick={() => handlePlayFromQueue(playlist.songs, idx, HISTORY_SOURCE.PLAYLIST)}
                      >
                        <span className="playlist-song-title">
                          {song.song_title}
                        </span>

                        <span
                          className="playlist-more"
                          onClick={(e) => {
                            e.stopPropagation()
                            setSelectedSong(song)
                            setSelectedPlaylistId(playlist.id)
                            setDeleteContext("playlist")
                            setIsDeleteModalOpen(true)
                          }}
                        >
                          ⋯
                        </span>
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

            <button
              className={`nav-icon-btn ${view === "burger" ? "active" : ""}`}
              onClick={() => setView("burger")}
              title="我的漢堡"
            >
              <img src="/burger.svg" alt="burger" />
            </button>
          </div>

          {/* 右：用戶資訊 */}
          <div className="navbar-user">
            <span className="navbar-greeting">
              一起嗨吧！{user.nickname}
            </span>

            <div
              className="avatar"
              onClick={() => setIsUserMenuOpen((prev) => !prev)}
            >
              {user.profilePicture
                ? <img src={user.profilePicture} alt="avatar" />
                : <span className="avatar-placeholder">🐰</span>
              }
            </div>

            {isUserMenuOpen && (
              <>
                <div
                  className="user-dropdown-overlay"
                  onClick={() => setIsUserMenuOpen(false)}
                />
                <div className="user-dropdown">
                  <div className="user-dropdown-name">{user.nickname}</div>

                  <div className="user-dropdown-level">
                    LV.{MOCK_USER_LEVEL.lv} · {LEVEL_TITLES[MOCK_USER_LEVEL.lv - 1]}
                  </div>

                  <div className="user-dropdown-xp-wrap">
                    <div
                      className="user-dropdown-xp-fill"
                      style={{
                        width: `${MOCK_USER_LEVEL.lv < 6
                          ? Math.min((MOCK_USER_LEVEL.xp / LEVEL_XP_THRESHOLDS[MOCK_USER_LEVEL.lv - 1]) * 100, 100)
                          : 100}%`
                      }}
                    />
                  </div>
                  <p className="user-dropdown-xp-label">
                    {MOCK_USER_LEVEL.xp} / {MOCK_USER_LEVEL.lv < 6 ? LEVEL_XP_THRESHOLDS[MOCK_USER_LEVEL.lv - 1] : "MAX"} XP
                  </p>

                  <button
                    className="daily-challenge-open-btn"
                    onClick={() => {
                      setIsUserMenuOpen(false)
                      setIsDailyChallengeOpen(true)
                    }}
                  >
                    Daily Challenge
                  </button>

                  <button className="logout-btn" onClick={handleLogout}>
                    Log Out
                  </button>
                </div>
              </>
            )}
          </div>
        </nav>

        {/* 內容區 */}
        <div className="content-area">

          {view === "home" && (
            <section className="home-view">
              <h2 className="section-title">Recommendation</h2>
              <div className="recommendation-grid">
                {recommendations.map((song, idx) => (
                  <div
                    key={song.id}
                    className={`song-card ${currentSong?.id === song.id ? "active" : ""}`}
                    onClick={() => handlePlayFromQueue(recommendations, idx, HISTORY_SOURCE.RECOMMENDATION)}
                  >
                    <p className="song-card-title">{song.song_title}</p>
                    <p className="song-card-artist">{song.artist_name}</p>
                  </div>
                ))}
              </div>

              {/* 重溫舊愛 */}
              <section className="sub-section">

                {isRevisitUnlocked ? (
                  <>
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
                          onClick={() => {
                            const fullIdx = FAKE_REVISIT.findIndex((s) => s.id === song.id)
                            handlePlayFromQueue(FAKE_REVISIT, fullIdx >= 0 ? fullIdx : 0, HISTORY_SOURCE.RECOMMENDATION)
                          }}
                        >
                          <p className="small-song-title">{song.song_title}</p>
                          <p className="small-song-artist">{song.artist_name}</p>
                        </div>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="revisit-locked">
                    <p className="revisit-locked-text">
                      UNLOCK AFTER 5 SONGS
                    </p>

                    <p className="revisit-locked-sub">
                      {historySongs.length} / 5 songs listened
                    </p>
                  </div>
                )}

              </section>

              {/* 你的朋友也在聽 */}
              <section className="sub-section">

                {isFriendsUnlocked ? (
                  <>
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
                            const friendSongs = friendListening.map((f) => ({
                              id: f.song_id,
                              song_title: f.song_title,
                              artist_name: f.artist_name,
                              song_image: f.song_image,
                            }))

                            const fullIdx = friendListening.findIndex(
                              (f) => f.song_id === item.song_id
                            )

                            handlePlayFromQueue(
                              friendSongs,
                              fullIdx >= 0 ? fullIdx : 0,
                              HISTORY_SOURCE.FRIEND
                            )
                          }}
                        >
                          <p className="friend-name">{item.friend_name}</p>
                          <p className="friend-song">{item.song_title}</p>

                          {item.artist_name && (
                            <p className="friend-artist">
                              {item.artist_name}
                            </p>
                          )}
                        </div>
                      ))}

                      <button
                        className="friend-card search-friend-card"
                        onClick={openFriendsModal}
                        type="button"
                      >
                        <p className="friend-search-text">
                          Search Your Friends!
                        </p>
                      </button>
                                
                    </div>
                  </>
                ) : (
                  <div className="revisit-locked">
                    <p className="revisit-locked-text">
                      UNLOCK AFTER 10 SONGS
                    </p>

                    <p className="revisit-locked-sub">
                      {historySongs.length} / 10 songs listened
                    </p>
                  </div>
                )}

              </section>
            </section>
          )}

          {/* 漢堡視圖 */}
          {view === "burger" && (
            <section className="burger-view">
              <div className="burger-page-header">
                <h2 className="burger-page-title">你的漢堡</h2>
                <p className="burger-level-badge">
                  LV.{MOCK_USER_LEVEL.lv} · {LEVEL_TITLES[MOCK_USER_LEVEL.lv - 1]}
                </p>
              </div>

              <div className="burger-visual-container">
                <BurgerVisual lv={MOCK_USER_LEVEL.lv} />
              </div>

              <div className="burger-xp-section">
                <div className="burger-xp-bar-wrap">
                  <div
                    className="burger-xp-bar-fill"
                    style={{
                      width: `${MOCK_USER_LEVEL.lv < 6
                        ? Math.min((MOCK_USER_LEVEL.xp / LEVEL_XP_THRESHOLDS[MOCK_USER_LEVEL.lv - 1]) * 100, 100)
                        : 100}%`
                    }}
                  />
                </div>
                <p className="burger-xp-label">
                  {MOCK_USER_LEVEL.xp} / {MOCK_USER_LEVEL.lv < 6 ? LEVEL_XP_THRESHOLDS[MOCK_USER_LEVEL.lv - 1] : "MAX"} XP
                </p>
              </div>
            </section>
          )}

          {/* Search 視圖 */}
          {view === "search" && (
            <section className="search-view">
              <div className="search-bar-wrap">
                <input
                  className="search-input"
                  type="text"
                  placeholder="搜尋歌曲、藝人..."
                  value={searchQuery}
                  onChange={(e) => handleSearchChange(e.target.value)}
                />
                <button className="search-btn">
                  <img src="/search.svg" alt="search" />
                </button>
              </div>

              {!searchQuery.trim() && !isSearching && searchResults.length === 0 && (
                <p className="search-hint">輸入關鍵字開始搜尋</p>
              )}

              {isSearching && (
                <p className="search-hint">搜尋中...</p>
              )}

              {!isSearching && searchQuery.trim() && searchResults.length === 0 && (
                <p className="search-hint">找不到相關結果</p>
              )}

              {searchResults.length > 0 && (
                <div className="search-results">
                  {searchResults.map((song, idx) => (
                    <div
                      key={song.id}
                      className={`song-card ${currentSong?.id === song.id ? "active" : ""}`}
                      onClick={() => handlePlayFromQueue(searchResults, idx, HISTORY_SOURCE.SEARCH)}
                    >
                      <p className="song-card-title">{song.song_title}</p>
                      <p className="song-card-artist">{song.artist_name}</p>
                    </div>
                  ))}
                </div>
              )}
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
                onClick={() => handleToggleLike(true)}
                title="喜歡"
              >
                <img src="/good.svg" alt="like" className="good-icon" />
              </button>

              <button
                className={`action-btn-new ${disliked ? "active" : ""}`}
                onClick={() => handleToggleLike(false)}
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

              <button
                className={`action-btn-new ${isLooping ? "active" : ""}`}
                title="單曲循環"
                onClick={toggleLoop}
              >
                <img src="/repeat.svg" alt="repeat" className="repeat-icon" />
              </button>

            </div>

            {/* 進度條 */}
            <div className="progress-bar-section">
              <div
                className="progress-bar-wrap"
                onMouseDown={(e) => {
                  e.preventDefault()
                  if (!playerRef.current || !duration) return
                  isDragging.current = true
                  const bar = e.currentTarget
                  setDragTime(calcSeekTime(e, bar))

                  const onMove = (ev) => {
                    setDragTime(calcSeekTime(ev, bar))
                  }
                  const onUp = (ev) => {
                    const t = calcSeekTime(ev, bar)
                    playerRef.current.seekTo(t)
                    setCurrentTime(t)
                    setDragTime(null)
                    isDragging.current = false
                    window.removeEventListener("mousemove", onMove)
                    window.removeEventListener("mouseup", onUp)
                  }
                  window.addEventListener("mousemove", onMove)
                  window.addEventListener("mouseup", onUp)
                }}
              >
                <div
                  className="progress-bar-fill"
                  style={{
                    width: duration ? `${((dragTime ?? currentTime) / duration) * 100}%` : "0%",
                    transition: dragTime !== null ? "none" : "width 0.4s linear",
                  }}
                />
              </div>
              <div className="progress-time-row">
                <span>{formatTime(dragTime ?? currentTime)}</span>
                <span>{formatTime(duration)}</span>
              </div>
            </div>

            {/* 播放控制 */}
            <div className="player-controls-row">
              <button className="skip-btn" onClick={handlePrev} title="上一首">
                <img src="/prev.svg" alt="prev" className="skip-icon" />
              </button>
              <button className="play-btn" onClick={togglePlay} title={isPlaying ? "暫停" : "播放"}>
                <img
                  src={isPlaying ? "/pause.svg" : "/play.svg"}
                  alt={isPlaying ? "pause" : "play"}
                  className="play-icon"
                />
              </button>
              <button className="skip-btn" onClick={handleNext} title="下一首">
                <img src="/next.svg" alt="next" className="skip-icon" />
              </button>
            </div>

            {/* YouTube 播放器 */}
            <div className="youtube-player-wrap">
              {isLoadingVideo && <p className="youtube-loading">載入中...</p>}
              {youtubeVideoId && (
                <YouTube
                  videoId={youtubeVideoId}
                  opts={{
                    width: "100%",
                    height: "160",
                    playerVars: { autoplay: 1 },
                  }}
                  onReady={(e) => {
                    playerRef.current = e.target
                  }}
                  onEnd={() => {
                    if (isLoopingRef.current) {
                      playerRef.current?.seekTo(0)
                      playerRef.current?.playVideo()
                      return
                    }
                    const q = queueRef.current
                    if (q && q.songs.length > 1) {
                      const nextIndex = (q.index + 1) % q.songs.length
                      queueRef.current = { songs: q.songs, index: nextIndex }
                      handlePlay(q.songs[nextIndex], HISTORY_SOURCE.PLAYLIST)
                      return
                    }
                    flushCurrentHistory()
                    setIsPlaying(false)
                  }}
                />
              )}
            </div>
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
                        <img src={`/album_icon/${playlist.playlist_icon || PLAYLIST_ICONS[0]}`} alt={playlist.playlist_name} />
                      </div>

                      <div className="playlist-modal-item-info">
                        <span className="playlist-modal-item-name">{playlist.playlist_name}</span>
                        <span className="playlist-modal-item-count">
                          {playlist.song_count} 首歌曲
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

                  <div className="playlist-icon-section">
                    <label className="playlist-input-label">Playlist Icon</label>
                    <div className="playlist-icon-grid">
                      {PLAYLIST_ICONS.map((icon) => (
                        <button
                          key={icon}
                          type="button"
                          className={`playlist-icon-option ${selectedPlaylistIcon === icon ? "selected" : ""}`}
                          onClick={() => setSelectedPlaylistIcon(icon)}
                        >
                          <img src={`/album_icon/${icon}`} alt={icon} />
                        </button>
                      ))}
                    </div>
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

      {isDeleteModalOpen && (
        <div className="delete-modal-overlay">
          <div className="delete-modal">

            <div className="delete-modal-header">
              <h2>{selectedSong?.song_title}</h2>
              <button onClick={() => setIsDeleteModalOpen(false)}>×</button>
            </div>

            <button
              className="delete-btn"
              onClick={() => {
                if (deleteContext === "history") handleDeleteFromHistory()
                else if (deleteContext === "playlist") handleDeleteFromCustomPlaylist()
                else handleDeleteFromFavorites()
                setIsDeleteModalOpen(false)
              }}
            >
              {deleteContext === "history" ? "Delete From History" : deleteContext === "favorites" ? "Delete From Favorites" : "Delete From Playlist"}
            </button>

          </div>
        </div>
      )}    
      {isEditPlaylistModalOpen && (
        <div className="delete-modal-overlay">
          <div className="delete-modal">

            {/* Header */}
            <div className="delete-modal-header">

              {editView !== "menu" && (
                <button
                  className="back-btn"
                  onClick={() => setEditView("menu")}
                >
                  ←
                </button>
              )}

              <h2>
                {editView === "menu" && editingPlaylist?.playlist_name}
                {editView === "name" && "Change Playlist Name"}
                {editView === "icon" && "Change Playlist Icon"}
              </h2>

              <button onClick={() => setIsEditPlaylistModalOpen(false)}>×</button>

            </div>

            {/* 主選單 */}
            {editView === "menu" && (
              <>
                <button
                  className="delete-btn"
                  onClick={() => setEditView("name")}
                >
                  Change Playlist Name
                </button>

                <button
                  className="delete-btn"
                  onClick={() => setEditView("icon")}
                >
                  Change Playlist Icon
                </button>

                <button
                  className="delete-btn"
                  onClick={async () => {
                    await deletePlaylist(editingPlaylist.id)

                    setCustomPlaylists(prev =>
                      prev.filter(p => p.id !== editingPlaylist.id)
                    )

                    setIsEditPlaylistModalOpen(false)
                  }}
                >
                  Delete Playlist
                </button>
              </>
            )}

            {/* 改名稱 */}
            {editView === "name" && (
              <>
                <div>
                  <input
                    value={editName}
                    onChange={(e) => {
                      setEditName(e.target.value)
                      setNameError("")   // ⭐打字時清掉錯誤
                    }}
                    placeholder="Please fill out"
                  />

                  {nameError && (
                    <div style={{
                      background: "#f7b6b6",
                      color: "#b00020",
                      padding: "6px 10px",
                      borderRadius: "10px",
                      marginTop: "6px",
                      display: "inline-block"
                    }}>
                      {nameError}
                    </div>
                  )}
                </div>

                <button
                  className="delete-btn"
                  onClick={async () => {
                    if (!editName.trim()) {
                      setNameError("Please fill out")
                      return
                    }

                    await updatePlaylist(editingPlaylist.id, editName)

                    setCustomPlaylists(prev =>
                      prev.map(p =>
                        p.id === editingPlaylist.id
                          ? { ...p, playlist_name: editName }
                          : p
                      )
                    )

                    setIsEditPlaylistModalOpen(false)
                  }}
                >
                  Change
                </button>
              </>
            )}

            {/* 改 icon */}
            {editView === "icon" && (
              <>
                <div className="icon-grid">
                  {PLAYLIST_ICONS.map(icon => (
                    <img
                      key={icon}
                      src={`/album_icon/${icon}`}
                      onClick={() => setEditIcon(icon)}
                      style={{
                        width: 90,
                        height: 90,            // ⭐加這行（固定高度）
                        objectFit: "contain",  // ⭐加這行（不變形）
                        border: editIcon === icon ? "2px solid blue" : "none",
                        borderRadius: 8,
                        cursor: "pointer"
                      }}
                    />
                  ))}
                </div>

                <button
                  className="delete-btn"
                  onClick={() => {
                    setCustomPlaylists(prev =>
                      prev.map(p =>
                        p.id === editingPlaylist.id
                          ? { ...p, playlist_icon: editIcon }
                          : p
                      )
                    )

                    setIsEditPlaylistModalOpen(false)
                  }}
                >
                  Change
                </button>
              </>
            )}

          </div>
        </div>
      )}

      {/* ── Daily Challenge Modal ── */}
      {isDailyChallengeOpen && (
        <div className="challenge-modal-overlay" onClick={() => setIsDailyChallengeOpen(false)}>
          <div className="challenge-modal" onClick={(e) => e.stopPropagation()}>
            <div className="challenge-modal-header">
              <h2 className="challenge-modal-title">Daily Challenge</h2>
              <button className="challenge-close-btn" onClick={() => setIsDailyChallengeOpen(false)}>
                ×
              </button>
            </div>

            <div className="challenge-tasks">
              {MOCK_CHALLENGES.map((task, idx) => (
                <div key={task.id} className={`challenge-task-row ${task.done ? "done" : ""}`}>
                  <div className="challenge-task-num">{idx + 1}</div>
                  <p className="challenge-task-text">
                    {task.prefix} {task.n} {task.suffix}
                  </p>
                  <div className={`challenge-task-check ${task.done ? "checked" : ""}`}>
                    {task.done ? "✓" : ""}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
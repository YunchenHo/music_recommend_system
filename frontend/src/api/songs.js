// src/api/songs.js
import api from "./api"

/** GET /api/auth/me — 取得當前登入用戶資訊 */
export async function getMe() {
  const { data } = await api.get("/api/auth/me")
  return data.data  // { username, profile_picture }
}

/** GET /api/songs/favorites — 取得收藏清單 */
export async function getFavorites() {
  const { data } = await api.get("/api/songs/favorites")
  return data.data  // [{ id, song_title, artist_name }, ...]
}

/** POST /api/songs/favorites — 加入收藏 */
export async function addFavorite(songId) {
  const { data } = await api.post("/api/songs/favorites", { song_id: songId })
  return data
}

/** DELETE /api/songs/favorites/<song_id> — 移除收藏 */
export async function removeFavorite(songId) {
  const { data } = await api.delete(`/api/songs/favorites/${songId}`)
  return data
}

/** GET /api/songs/recommendations — 取得推薦歌曲 */
export async function getRecommendations() {
  const { data } = await api.get("/api/songs/recommendations")
  return data.data  // [{ rank, id, song_title, artist_name, song_image, language }, ...]
}

/** GET /api/songs/<song_id> — 取得歌曲詳情（含收藏狀態） */
export async function getSongDetail(songId) {
  const { data } = await api.get(`/api/songs/${songId}`)
  return data.data  // { id, song_title, artist_name, album_name, language, song_image, is_favorited }
}

// ── Playlist API ─────────────────────────────────────

/** GET /api/playlists/ — 取得使用者自訂清單（不含 archive） */
export async function getPlaylists() {
  const { data } = await api.get("/api/playlists/")
  return data.data  // [{ id, playlist_name, song_count, created_at, updated_at }, ...]
}


/** POST /api/playlists/ — 建立新清單 */
export async function createPlaylist(playlistName) {
  const { data } = await api.post("/api/playlists/", { playlist_name: playlistName })
  return data.data  // { id, playlist_name, song_count, created_at, updated_at }
}

/** PATCH /api/playlists/<id>/ — 修改清單名稱 */
export async function updatePlaylist(playlistId, playlistName) {
  const { data } = await api.patch(`/api/playlists/${playlistId}/`, { playlist_name: playlistName })
  return data.data  // { id, playlist_name }
}

/** DELETE /api/playlists/<id>/ — 刪除清單 */
export async function deletePlaylist(playlistId) {
  const { data } = await api.delete(`/api/playlists/${playlistId}/`)
  return data
}

/** GET /api/playlists/<id>/songs/ — 取得清單內歌曲 */
export async function getPlaylistSongs(playlistId) {
  const { data } = await api.get(`/api/playlists/${playlistId}/songs/`)
  return data.data  // [{ id, song_title, artist_name, song_image, album_name, added_at }, ...]
}

/** POST /api/playlists/<id>/songs/ — 加歌到清單 */
export async function addSongToPlaylist(playlistId, songId) {
  const { data } = await api.post(`/api/playlists/${playlistId}/songs/`, { song_id: songId })
  return data
}

/** DELETE /api/playlists/<id>/songs/<song_id>/ — 從清單移除歌曲 */
export async function removeSongFromPlaylist(playlistId, songId) {
  const { data } = await api.delete(`/api/playlists/${playlistId}/songs/${songId}/`)
  return data
}

// ── Search API ───────────────────────────────────────

/** GET /api/songs/search?q=<query> — 搜尋歌曲 */
export async function searchSongs(query) {
  const { data } = await api.get("/api/songs/search", { params: { q: query } })
  return data.data  // [{ id, song_title, artist_name, album_name, song_image, language }, ...]
}

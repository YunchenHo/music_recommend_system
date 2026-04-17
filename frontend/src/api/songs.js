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

/** GET /api/songs/<song_id> — 取得歌曲詳情（含收藏狀態） */
export async function getSongDetail(songId) {
  const { data } = await api.get(`/api/songs/${songId}`)
  return data.data  // { id, song_title, artist_name, album_name, language, song_image, is_favorited }
}

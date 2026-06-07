// src/api/history.js
import api from "./api"

/**
 * 後端 source 合法值：
 *   RECOMMENDATION / SEARCH / PLAYLIST / ONBOARDING / FRIEND
 */
export const HISTORY_SOURCE = {
  RECOMMENDATION: "RECOMMENDATION",
  SEARCH: "SEARCH",
  PLAYLIST: "PLAYLIST",
  ONBOARDING: "ONBOARDING",
  FRIEND: "FRIEND",
}

/**
 * GET /api/auth/history — 取得使用者歷史紀錄
 * @param {object} params { limit, offset, song_id, source }
 * @returns {{
 *   data: Array<{
 *     id, song_id, song_title, artist_name, album_name, song_image, language,
 *     watch_seconds, source, played_at, created_at
 *   }>,
 *   total, limit, offset
 * }}
 */
export async function getHistory(params = {}) {
  const { data } = await api.get("/api/auth/history", { params })
  return data
}

/**
 * POST /api/auth/history — 新增一筆播放紀錄
 * @param {{ songId: number, watchSeconds: number, source: string }} payload
 * @returns {{ status, message, data: { id, song_id, watch_seconds, source } }}
 */
export async function createHistory({ songId, watchSeconds, source }) {
  const { data } = await api.post("/api/auth/history", {
    song_id: songId,
    watch_seconds: Math.max(0, Math.floor(watchSeconds || 0)),
    source,
  })
  return data
}

/**
 * PATCH /api/auth/history/<id> — 更新某筆紀錄的 watch_seconds
 * 後端有單調遞增保護：傳入值 ≤ 現有值時不會覆蓋。
 * @param {number} historyId
 * @param {number} watchSeconds
 */
export async function updateHistory(historyId, watchSeconds) {
  const { data } = await api.patch(`/api/auth/history/${historyId}`, {
    watch_seconds: Math.max(0, Math.floor(watchSeconds || 0)),
  })
  return data
}

export async function deleteHistory(historyId) {
  const { data } = await api.delete(`/api/auth/history/${historyId}`)
  return data
}

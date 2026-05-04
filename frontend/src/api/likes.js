// src/api/likes.js
import api from "./api"

/**
 * GET /api/auth/like?song_id=<id> — 取得目前使用者對某首歌的 like 狀態
 * @param {number} songId
 * @returns {{ status: string, data: { song_id: number, is_liked: boolean | null } }}
 *   is_liked: true=喜歡, false=不喜歡, null=尚未設定
 */
export async function getLikeStatus(songId) {
  const { data } = await api.get("/api/auth/like", {
    params: { song_id: songId },
  })
  return data
}

/**
 * POST /api/auth/like — 切換喜歡 / 不喜歡
 *
 * 行為：
 *   - 沒紀錄 → 新增，回傳 is_liked: intentLike
 *   - 已有紀錄且狀態相同 → 刪除（取消），回傳 is_liked: null
 *   - 已有紀錄但狀態不同 → 更新為新狀態，回傳 is_liked: intentLike
 *
 * @param {number} songId
 * @param {boolean} intentLike  true=喜歡, false=不喜歡
 * @returns {{ status: string, data: { is_liked: boolean | null } }}
 */
export async function toggleLike(songId, intentLike) {
  const { data } = await api.post("/api/auth/like", {
    song_id: songId,
    is_like: intentLike,
  })
  return data
}

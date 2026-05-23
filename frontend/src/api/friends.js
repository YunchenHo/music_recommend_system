// src/api/friends.js
import api from "./api"

/** GET /api/auth/friends/search?email=<email> — 搜尋好友 */
export async function searchFriend(email) {
  const { data } = await api.get("/api/auth/friends/search", {
    params: { email },
  })
  return data.data
}

/** GET /api/auth/friends — 取得我的好友 */
export async function getMyFriends() {
  const { data } = await api.get("/api/auth/friends")
  return data.data
}

/** POST /api/auth/friends — 新增好友 */
export async function addFriend(friendId) {
  const { data } = await api.post("/api/auth/friends", {
    friend_id: friendId,
  })
  return data
}

/** GET /api/auth/friends/listening — 你的朋友也在聽 */
export async function getFriendListening() {
  const { data } = await api.get("/api/auth/friends/listening")
  return data.data
}
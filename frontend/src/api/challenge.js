import api from "./api"

export async function getChallengeXP() {
  const { data } = await api.get("/api/challenge/xp/")
  return data  // { lv, xp, xp_in_level, xp_for_level }
}

export async function getTodayChallenges() {
  const { data } = await api.get("/api/challenge/today/")
  return data  // [{ id, challenge_type, prefix, n, suffix, current_count, is_completed }, ...]
}

export async function completeChallenge(id) {
  const { data } = await api.post(`/api/challenge/complete/${id}/`)
  return data  // { message, lv, xp } or { already_done: true }
}

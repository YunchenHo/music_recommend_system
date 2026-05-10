// src/api/auth.js
import api from "./api"

export async function googleLogin(idToken) {
  const { data } = await api.post("/api/auth/google-login", {
    token: idToken,
  })
  return data
}

export async function registerUser(payload) {
  const { data } = await api.post("/api/auth/register", payload)
  return data
}

export async function logoutUser() {
  const { data } = await api.post("/api/auth/logout")
  return data
}
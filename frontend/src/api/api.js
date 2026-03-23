// src/api/api.js
import axios from "axios"

const BASE_URL = "http://localhost:8000"

export function getCookie(name) {
  const value = `; ${document.cookie}`
  const parts = value.split(`; ${name}=`)
  if (parts.length === 2) return parts.pop().split(";").shift()
  return ""
}

const api = axios.create({
  baseURL: BASE_URL,
  withCredentials: true,
  headers: {
    "Content-Type": "application/json",
  },
})

api.interceptors.request.use((config) => {
  const method = config.method?.toLowerCase()

  if (["post", "put", "patch", "delete"].includes(method)) {
    const csrfToken = getCookie("csrftoken")
    if (csrfToken) {
      config.headers["X-CSRFToken"] = csrfToken
    }
  }

  return config
})

export default api
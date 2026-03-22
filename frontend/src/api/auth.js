// src/api/auth.js

import { apiFetch } from "./api";

export async function googleLogin(idToken) {
  return apiFetch("/api/auth/google-login", {
    method: "POST",
    body: JSON.stringify({
      token: idToken,
    }),
  });
}
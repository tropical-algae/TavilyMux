import { defineStore } from "pinia"
import { ref } from "vue"

import { api } from "../api/client"

export const useAuthStore = defineStore("auth", () => {
  const authenticated = ref(false)
  const checked = ref(false)

  async function check(): Promise<boolean> {
    try {
      await api.get("/auth/me")
      authenticated.value = true
    } catch {
      authenticated.value = false
    } finally {
      checked.value = true
    }
    return authenticated.value
  }

  async function login(secret: string, remember: boolean): Promise<void> {
    await api.post("/auth/login", { secret, remember })
    authenticated.value = true
    checked.value = true
  }

  async function logout(): Promise<void> {
    try {
      await api.post("/auth/logout")
    } finally {
      authenticated.value = false
      checked.value = true
    }
  }

  return { authenticated, checked, check, login, logout }
})

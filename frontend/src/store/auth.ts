import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, type UserInfo } from '@/api/auth'

const TOKEN_KEY = 'media_manager_access_token'
const REFRESH_KEY = 'media_manager_refresh_token'

// 一次性把旧品牌的 localStorage key 迁到新品牌
// MediaHub → Media Manager (rebrand 2026-05)
const LEGACY_TOKEN_KEY = 'mediahub_access_token'
const LEGACY_REFRESH_KEY = 'mediahub_refresh_token'

function migrateLegacyKeys() {
  for (const [legacy, current] of [
    [LEGACY_TOKEN_KEY, TOKEN_KEY],
    [LEGACY_REFRESH_KEY, REFRESH_KEY],
  ]) {
    const legacyValue = localStorage.getItem(legacy)
    if (legacyValue && !localStorage.getItem(current)) {
      localStorage.setItem(current, legacyValue)
    }
    if (legacyValue) localStorage.removeItem(legacy)
  }
}
migrateLegacyKeys()

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string>(localStorage.getItem(TOKEN_KEY) || '')
  const refreshToken = ref<string>(localStorage.getItem(REFRESH_KEY) || '')
  const user = ref<UserInfo | null>(null)

  const isAuthenticated = computed(() => !!accessToken.value)
  const isAdmin = computed(() => user.value?.role === 'admin')

  const setTokens = (access: string, refresh: string) => {
    accessToken.value = access
    refreshToken.value = refresh
    localStorage.setItem(TOKEN_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
  }

  const clearTokens = () => {
    accessToken.value = ''
    refreshToken.value = ''
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_KEY)
  }

  const setup = async (payload: { username: string; password: string; display_name?: string }) => {
    const resp = await authApi.setup(payload)
    setTokens(resp.access_token, resp.refresh_token)
    user.value = resp.user
    return resp
  }

  const login = async (payload: { username: string; password: string }) => {
    const resp = await authApi.login(payload)
    setTokens(resp.access_token, resp.refresh_token)
    user.value = resp.user
    return resp
  }

  const refresh = async () => {
    if (!refreshToken.value) throw new Error('no_refresh_token')
    const resp = await authApi.refresh(refreshToken.value)
    setTokens(resp.access_token, resp.refresh_token)
    user.value = resp.user
    return resp
  }

  const fetchMe = async () => {
    const u = await authApi.me()
    user.value = u
    return u
  }

  const logout = async () => {
    if (refreshToken.value) {
      try {
        await authApi.logout(refreshToken.value)
      } catch {
        /* ignore */
      }
    }
    clearTokens()
  }

  return {
    accessToken,
    refreshToken,
    user,
    isAuthenticated,
    isAdmin,
    setTokens,
    clearTokens,
    setup,
    login,
    refresh,
    fetchMe,
    logout,
  }
})

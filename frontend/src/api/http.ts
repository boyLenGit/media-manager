import axios, { type AxiosInstance, type AxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'

const http: AxiosInstance = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 公开端点(不带 token,不触发刷新逻辑)
const PUBLIC_PATHS = [
  '/health',
  '/info',
  '/auth/setup-required',
  '/auth/setup',
  '/auth/login',
  '/auth/refresh',
]

const isPublic = (url?: string) => {
  if (!url) return false
  return PUBLIC_PATHS.some((p) => url === p || url.startsWith(p + '?'))
}

// ---- 请求拦截器:注入 Authorization ----
http.interceptors.request.use((config) => {
  if (!isPublic(config.url)) {
    const token = localStorage.getItem('media_manager_access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
  }
  return config
})

// ---- 响应拦截器:401 自动刷新 + 单飞 ----
let refreshing: Promise<string> | null = null
let onAuthFailure: (() => void) | null = null

export const setAuthFailureHandler = (h: () => void) => {
  onAuthFailure = h
}

const tryRefresh = async (): Promise<string> => {
  const refreshToken = localStorage.getItem('media_manager_refresh_token')
  if (!refreshToken) throw new Error('no_refresh_token')
  const resp = await axios.post('/api/auth/refresh', { refresh_token: refreshToken })
  const { access_token, refresh_token } = resp.data
  localStorage.setItem('media_manager_access_token', access_token)
  localStorage.setItem('media_manager_refresh_token', refresh_token)
  return access_token
}

http.interceptors.response.use(
  (resp) => resp,
  async (error) => {
    const status = error?.response?.status
    const config: AxiosRequestConfig & { _retry?: boolean } = error.config || {}

    // 401 且不是认证接口本身,尝试刷新一次
    if (
      status === 401 &&
      !config._retry &&
      !isPublic(config.url) &&
      config.url !== '/auth/me'
    ) {
      config._retry = true
      try {
        if (!refreshing) refreshing = tryRefresh()
        const newToken = await refreshing
        refreshing = null
        config.headers = config.headers || {}
        ;(config.headers as any).Authorization = `Bearer ${newToken}`
        return http.request(config)
      } catch {
        refreshing = null
        onAuthFailure?.()
        return Promise.reject(error)
      }
    }

    // me 接口 401 直接登出
    if (status === 401 && config.url === '/auth/me') {
      onAuthFailure?.()
    }

    const msg =
      error?.response?.data?.detail ||
      error?.response?.statusText ||
      error?.message ||
      'Request failed'
    if (status !== 501 && status !== 401) {
      ElMessage.error(typeof msg === 'string' ? msg : JSON.stringify(msg))
    }
    return Promise.reject(error)
  },
)

export default http

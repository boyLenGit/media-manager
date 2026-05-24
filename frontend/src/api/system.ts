import http from './http'

export interface HealthInfo {
  status: string
  time: string
}

export interface AppInfo {
  app_name: string
  debug: boolean
  qbittorrent_configured: boolean
  jellyfin_configured: boolean
}

export const systemApi = {
  health: () => http.get<HealthInfo>('/health').then((r) => r.data),
  info: () => http.get<AppInfo>('/info').then((r) => r.data),
}

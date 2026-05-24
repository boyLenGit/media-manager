import http from './http'

export interface DashboardStats {
  media_count: number
  file_count: number
  video_count: number
  missing_count: number
  total_size_bytes: number
  favorite_count: number
  watched_count: number
  unwatched_count: number
  author_count: number
  tag_count: number
  downloading_count: number
  completed_dl_count: number
  recent_added: number
  recent_played_count: number
  last_scan?: {
    id: number
    status: string
    scanned_files: number
    new_files: number
    started_at?: string
    finished_at?: string
  }
  qbittorrent_configured: boolean
  jellyfin_configured: boolean
}

export interface RecentMediaItem {
  id: number
  title: string
  cover_path?: string
  file_count: number
  favorite: boolean
  watch_status: string
  created_at: string
}

export const statsApi = {
  get: () => http.get<DashboardStats>('/stats').then((r) => r.data),
  recentMedia: (limit = 12) =>
    http.get<RecentMediaItem[]>('/stats/recent-media', { params: { limit } }).then((r) => r.data),
}

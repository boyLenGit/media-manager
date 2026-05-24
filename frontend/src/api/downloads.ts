import http from './http'

export interface DownloaderConfig {
  provider: string
  url: string
  username: string
  password_set: boolean
  configured: boolean
}

export interface DownloadTask {
  id: number
  search_result_id?: number
  title: string
  magnet_uri?: string
  info_hash?: string
  downloader: string
  downloader_task_id?: string
  save_path?: string
  status: string
  progress: number
  download_speed: number
  upload_speed: number
  eta_seconds?: number
  error_message?: string
  started_at?: string
  completed_at?: string
  created_at: string
  updated_at: string
}

export interface DuplicateInfo {
  level: 'exact' | 'high' | 'medium' | 'low' | 'none'
  reason: string
  matched_media_id?: number
  matched_file_id?: number
  score: number
}

export const downloadsApi = {
  getConfig: () => http.get<DownloaderConfig>('/downloads/config').then((r) => r.data),
  updateConfig: (payload: { provider: string; url: string; username: string; password?: string }) =>
    http.put('/downloads/config', payload),
  testConnection: () =>
    http
      .post<{ ok: boolean; provider?: string; url?: string; error?: string }>('/downloads/test')
      .then((r) => r.data),

  list: (status?: string) =>
    http.get<DownloadTask[]>('/downloads', { params: status ? { status } : {} }).then((r) => r.data),

  detail: (id: number) => http.get<DownloadTask>(`/downloads/${id}`).then((r) => r.data),

  checkDuplicate: (payload: {
    title: string
    info_hash?: string
    magnet_uri?: string
    size_bytes?: number
  }) => http.post<DuplicateInfo>('/downloads/check-duplicate', payload).then((r) => r.data),

  create: (payload: {
    title: string
    magnet_uri: string
    info_hash?: string
    save_path?: string
    search_result_id?: number
    size_bytes?: number
    force?: boolean
  }) =>
    http
      .post<{ status: string; task?: DownloadTask; duplicate?: DuplicateInfo; hint?: string }>(
        '/downloads',
        payload,
      )
      .then((r) => r.data),

  pause: (id: number) => http.post(`/downloads/${id}/pause`),
  resume: (id: number) => http.post(`/downloads/${id}/resume`),
  remove: (id: number, deleteFiles = false) =>
    http.delete(`/downloads/${id}`, { params: { delete_files: deleteFiles } }),
}

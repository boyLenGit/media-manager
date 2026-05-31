import http from './http'

export interface ScanPath {
  id: number
  path: string
  name?: string
  enabled: boolean
  recursive: boolean
  default_media_type?: string
  default_tags?: string
  last_scan_at?: string
  created_at: string
  updated_at: string
}

export interface ScanJob {
  id: number
  scan_path_id?: number
  status: 'pending' | 'running' | 'success' | 'failed'
  total_files: number
  scanned_files: number
  new_files: number
  updated_files: number
  missing_files: number
  error_message?: string
  started_at?: string
  finished_at?: string
  created_at: string
}

export interface ScanLog {
  id: number
  scan_job_id?: number
  level: string
  message: string
  file_path?: string
  created_at: string
}

export const scanApi = {
  listPaths: () => http.get<ScanPath[]>('/scan/paths').then((r) => r.data),

  createPath: (payload: Partial<ScanPath>) =>
    http.post<ScanPath>('/scan/paths', payload).then((r) => r.data),

  updatePath: (id: number, payload: Partial<ScanPath>) =>
    http.patch<ScanPath>(`/scan/paths/${id}`, payload).then((r) => r.data),

  deletePath: (id: number) => http.delete(`/scan/paths/${id}`),

  triggerScan: (id: number) => http.post(`/scan/paths/${id}/scan`).then((r) => r.data),

  listJobs: (limit = 20) =>
    http.get<ScanJob[]>('/scan/jobs', { params: { limit } }).then((r) => r.data),

  getJob: (id: number) => http.get<ScanJob>(`/scan/jobs/${id}`).then((r) => r.data),

  getJobLogs: (id: number) => http.get<ScanLog[]>(`/scan/jobs/${id}/logs`).then((r) => r.data),

  /**
   * 列出当前进程(容器)可访问的挂载点。
   * 用于 UI 提示「你可以填这些路径」。
   */
  listMounts: () =>
    http
      .get<{
        in_container: boolean
        mounts: Array<{
          path: string
          fs_type: string
          readonly: boolean
          exists: boolean
          is_dir: boolean
        }>
      }>('/scan/mounts')
      .then((r) => r.data),
}

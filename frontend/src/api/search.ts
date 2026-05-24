import http from './http'

export interface ResourceSource {
  id: number
  name: string
  source_type: string
  base_url?: string
  enabled: boolean
  auth_config?: string
  rate_limit_config?: string
  remark?: string
  created_at: string
  updated_at: string
}

export interface SearchHit {
  title: string
  source_id: number
  source_name: string
  magnet_uri?: string
  info_hash?: string
  size_bytes?: number
  publish_time?: string
  source_url?: string
  seeders?: number
  leechers?: number
  duplicate?: {
    level: string
    reason: string
    matched_media_id?: number
    score: number
  }
}

export interface SearchResp {
  q: string
  hits: SearchHit[]
  errors: { source?: string; detail?: string; error?: string }[]
}

export interface LocalSearchHit {
  media_item_id: number
  title: string
  author_name?: string
  tag_names?: string
}

export const searchApi = {
  listSources: () => http.get<ResourceSource[]>('/search/sources').then((r) => r.data),
  createSource: (payload: Partial<ResourceSource>) =>
    http.post<ResourceSource>('/search/sources', payload).then((r) => r.data),
  updateSource: (id: number, payload: Partial<ResourceSource>) =>
    http.patch<ResourceSource>(`/search/sources/${id}`, payload).then((r) => r.data),
  removeSource: (id: number) => http.delete(`/search/sources/${id}`),
  testSource: (id: number) =>
    http.post<{ ok: boolean; error?: string }>(`/search/sources/${id}/test`).then((r) => r.data),

  search: (q: string, limitPerSource = 50) =>
    http
      .get<SearchResp>('/search', { params: { q, limit_per_source: limitPerSource } })
      .then((r) => r.data),

  searchLocal: (q: string, limit = 50) =>
    http
      .get<{ q: string; hits: LocalSearchHit[] }>('/search/local', { params: { q, limit } })
      .then((r) => r.data),
}

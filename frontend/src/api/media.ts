import http from './http'

export interface MediaTag {
  id: number
  name: string
  color?: string
  group?: string
}

export interface MediaItemBrief {
  id: number
  title: string
  original_title?: string
  normalized_title?: string
  media_type_id?: number
  media_type_name?: string
  author_id?: number
  author_name?: string
  release_date?: string
  cover_path?: string
  rating?: number
  favorite: boolean
  watch_status: string
  file_count: number
  tags: MediaTag[]
  created_at: string
  updated_at: string
}

export interface MediaFileDetail {
  id: number
  file_asset_id: number
  path: string
  filename: string
  extension?: string
  size_bytes?: number
  quality?: string
  container?: string
  video_codec?: string
  audio_codec?: string
  duration_seconds?: number
  width?: number
  height?: number
  is_primary: boolean
  missing: boolean
  /** 仅在通过 playback options 接口拼装时由前端注入 */
  web_playable?: boolean
}

export interface MediaItemDetail extends MediaItemBrief {
  description?: string
  source_url?: string
  remark?: string
  files: MediaFileDetail[]
}

export interface PlayOption {
  type: string
  label: string
  url: string
}

export interface MediaListResp {
  items: MediaItemBrief[]
  total: number
  limit: number
  offset: number
}

export interface MediaListParams {
  q?: string
  media_type_id?: number
  author_id?: number
  favorite?: boolean
  watch_status?: string
  tag_id?: number
  sort_by?: 'updated_at' | 'created_at' | 'title' | 'rating'
  order?: 'asc' | 'desc'
  limit?: number
  offset?: number
}

export const mediaApi = {
  list: (params?: MediaListParams) =>
    http.get<MediaListResp>('/media', { params }).then((r) => r.data),

  detail: (id: number) => http.get<MediaItemDetail>(`/media/${id}`).then((r) => r.data),

  update: (
    id: number,
    payload: Partial<{
      title: string
      media_type_id: number | null
      author_id: number | null
      favorite: boolean
      watch_status: string
      rating: number
      description: string
      remark: string
      tag_ids: number[]
    }>,
  ) => http.patch<MediaItemDetail>(`/media/${id}`, payload).then((r) => r.data),

  batchTag: (payload: {
    media_ids: number[]
    add_tag_ids?: number[]
    remove_tag_ids?: number[]
  }) => http.post<{ affected: number }>('/media/batch-tag', payload).then((r) => r.data),

  batchUpdate: (payload: {
    media_ids: number[]
    media_type_id?: number | null
    author_id?: number | null
    favorite?: boolean
    watch_status?: string
  }) => http.post<{ affected: number }>('/media/batch-update', payload).then((r) => r.data),

  playOptions: (id: number) =>
    http
      .get<{ media_id: number; options: PlayOption[] }>(`/playback/media/${id}/options`)
      .then((r) => r.data),
}

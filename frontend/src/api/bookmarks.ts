import http from './http'

export interface BookmarkTag {
  id: number
  name: string
  color?: string
  group_name?: string
}

export interface Bookmark {
  id: number
  media_item_id: number
  file_asset_id?: number | null
  position_seconds: number
  title: string
  note?: string | null
  created_by?: number | null
  created_by_username?: string | null
  tags: BookmarkTag[]
  created_at: string
  updated_at: string
}

export interface BookmarkCreatePayload {
  media_item_id: number
  position_seconds: number
  title: string
  note?: string
  file_asset_id?: number
  tag_ids?: number[]
}

export interface BookmarkUpdatePayload {
  position_seconds?: number
  title?: string
  note?: string | null
  tag_ids?: number[]
}

export const bookmarksApi = {
  /**
   * 列出某个 media 的所有书签(按时间升序);
   * 不传 media_item_id 则返回最近 200 条(用于"全局浏览所有标记")。
   */
  list: (params?: { media_item_id?: number; tag_id?: number }) =>
    http.get<Bookmark[]>('/bookmarks', { params }).then((r) => r.data),

  get: (id: number) => http.get<Bookmark>(`/bookmarks/${id}`).then((r) => r.data),

  create: (payload: BookmarkCreatePayload) =>
    http.post<Bookmark>('/bookmarks', payload).then((r) => r.data),

  update: (id: number, payload: BookmarkUpdatePayload) =>
    http.patch<Bookmark>(`/bookmarks/${id}`, payload).then((r) => r.data),

  remove: (id: number) => http.delete(`/bookmarks/${id}`),

  /**
   * 一次拿多个 media 的书签数(资源库列表角标用)。
   * mediaIds 长度建议 ≤ 200。
   */
  countByMedia: (mediaIds: number[]) =>
    http
      .get<Record<number, number>>('/bookmarks/_count/by-media', {
        params: { media_ids: mediaIds.join(',') },
      })
      .then((r) => r.data),
}

import http from './http'

export interface Tag {
  id: number
  name: string
  group_name?: string
  color?: string
  media_count: number
}

export const tagsApi = {
  list: () => http.get<Tag[]>('/tags').then((r) => r.data),
  create: (payload: { name: string; group_name?: string; color?: string }) =>
    http.post<Tag>('/tags', payload).then((r) => r.data),
  update: (id: number, payload: { name: string; group_name?: string; color?: string }) =>
    http.patch<Tag>(`/tags/${id}`, payload).then((r) => r.data),
  remove: (id: number) => http.delete(`/tags/${id}`),
}

import http from './http'

export interface MediaType {
  id: number
  name: string
  description?: string
  media_count: number
}

export const mediaTypesApi = {
  list: () => http.get<MediaType[]>('/media-types').then((r) => r.data),
  create: (payload: { name: string; description?: string }) =>
    http.post<MediaType>('/media-types', payload).then((r) => r.data),
  update: (id: number, payload: { name: string; description?: string }) =>
    http.patch<MediaType>(`/media-types/${id}`, payload).then((r) => r.data),
  remove: (id: number) => http.delete(`/media-types/${id}`),
}

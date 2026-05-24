import http from './http'

export interface Author {
  id: number
  name: string
  alias?: string
  description?: string
  media_count: number
}

export const authorsApi = {
  list: () => http.get<Author[]>('/authors').then((r) => r.data),
  create: (payload: { name: string; alias?: string; description?: string }) =>
    http.post<Author>('/authors', payload).then((r) => r.data),
  update: (id: number, payload: { name: string; alias?: string; description?: string }) =>
    http.patch<Author>(`/authors/${id}`, payload).then((r) => r.data),
  remove: (id: number) => http.delete(`/authors/${id}`),
}

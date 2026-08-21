import http from './http'

export interface Author {
  id: number
  name: string
  alias?: string
  description?: string
  cover_path?: string
  media_count: number
}

export const authorsApi = {
  list: () => http.get<Author[]>('/authors').then((r) => r.data),
  detail: (id: number) => http.get<Author>(`/authors/${id}`).then((r) => r.data),
  create: (payload: { name: string; alias?: string; description?: string }) =>
    http.post<Author>('/authors', payload).then((r) => r.data),
  update: (id: number, payload: { name: string; alias?: string; description?: string }) =>
    http.patch<Author>(`/authors/${id}`, payload).then((r) => r.data),
  remove: (id: number) => http.delete(`/authors/${id}`),

  uploadCover: (id: number, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return http
      .post<Author>(`/authors/${id}/cover`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data)
  },
  removeCover: (id: number) => http.delete(`/authors/${id}/cover`),
}

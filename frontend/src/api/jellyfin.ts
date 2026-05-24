import http from './http'

export const jellyfinApi = {
  getConfig: () =>
    http
      .get<{ url: string; api_key_set: boolean; configured: boolean }>('/jellyfin/config')
      .then((r) => r.data),
  updateConfig: (payload: { url: string; api_key?: string }) =>
    http.put('/jellyfin/config', payload),
  test: () =>
    http
      .post<{ ok: boolean; version?: string; server_name?: string; error?: string }>(
        '/jellyfin/test',
      )
      .then((r) => r.data),
  listLibraries: () =>
    http
      .get<{ id: string; name: string; type?: string; paths: string[] }[]>('/jellyfin/libraries')
      .then((r) => r.data),
}

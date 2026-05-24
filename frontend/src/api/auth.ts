import http from './http'

export interface UserInfo {
  id: number
  username: string
  display_name?: string
  role: 'admin' | 'viewer'
  enabled: boolean
}

export interface TokenResp {
  access_token: string
  refresh_token: string
  expires_at: string
  user: UserInfo
}

export const authApi = {
  setupRequired: () =>
    http.get<{ setup_required: boolean }>('/auth/setup-required').then((r) => r.data),

  setup: (payload: { username: string; password: string; display_name?: string }) =>
    http.post<TokenResp>('/auth/setup', payload).then((r) => r.data),

  login: (payload: { username: string; password: string }) =>
    http.post<TokenResp>('/auth/login', payload).then((r) => r.data),

  refresh: (refresh_token: string) =>
    http.post<TokenResp>('/auth/refresh', { refresh_token }).then((r) => r.data),

  logout: (refresh_token: string) => http.post('/auth/logout', { refresh_token }),

  me: () => http.get<UserInfo>('/auth/me').then((r) => r.data),

  listUsers: () => http.get<UserInfo[]>('/auth/users').then((r) => r.data),

  createUser: (payload: {
    username: string
    password: string
    display_name?: string
    role: 'admin' | 'viewer'
  }) => http.post<UserInfo>('/auth/users', payload).then((r) => r.data),

  updateUser: (
    id: number,
    payload: {
      display_name?: string
      role?: 'admin' | 'viewer'
      enabled?: boolean
      password?: string
    },
  ) => http.patch<UserInfo>(`/auth/users/${id}`, payload).then((r) => r.data),

  deleteUser: (id: number) => http.delete(`/auth/users/${id}`),
}

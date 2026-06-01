import http from './http'

export interface AppSetting {
  id: number
  key: string
  value?: string
  value_type: string
  description?: string
}

export const settingsApi = {
  list: () => http.get<AppSetting[]>('/settings').then((r) => r.data),

  get: async (key: string): Promise<string | null> => {
    const all = await http.get<AppSetting[]>('/settings').then((r) => r.data)
    return all.find((s) => s.key === key)?.value ?? null
  },

  upsert: (key: string, value: string, value_type = 'string') =>
    http.put<AppSetting>(`/settings/${key}`, { value, value_type }).then((r) => r.data),

  remove: (key: string) => http.delete(`/settings/${key}`),

  /**
   * 危险:清空除当前管理员之外的所有数据。
   * 需要传当前管理员的登录密码做二次确认(服务端 bcrypt 校验)。
   */
  resetAll: (password: string, purge_thumbnails = true) =>
    http
      .post<{
        cleared_tables: string[]
        thumbnails_purged: boolean
        note: string
      }>('/settings/reset-all', {
        password,
        purge_thumbnails,
      })
      .then((r) => r.data),
}

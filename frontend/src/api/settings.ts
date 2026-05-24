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
}

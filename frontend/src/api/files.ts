import http from './http'

export interface FileMeta {
  id: number
  filename: string
  extension?: string
  size_bytes?: number
  file_type?: string
  missing: boolean
  web_playable: boolean
  media_file?: {
    id: number
    media_item_id: number
    duration_seconds?: number
    width?: number
    height?: number
    video_codec?: string
    audio_codec?: string
  }
}

export interface SubtitleInfo {
  id: number
  filename: string
  extension?: string
  language_hint?: string
  match: string
  url: string
  /** 'auto' = 同目录文件名自动匹配;'custom' = 用户手动上传 */
  source?: 'auto' | 'custom'
}

export interface StreamToken {
  token: string
  url: string
  expires_in: number
}

export const filesApi = {
  meta: (id: number) => http.get<FileMeta>(`/files/${id}`).then((r) => r.data),

  subtitles: (id: number) => http.get<SubtitleInfo[]>(`/files/${id}/subtitles`).then((r) => r.data),

  streamToken: (id: number) =>
    http.get<StreamToken>(`/files/${id}/stream-token`).then((r) => r.data),

  // 完整可播放 URL(已含签名 token)
  buildStreamUrl: async (id: number): Promise<string> => {
    const t = await http.get<StreamToken>(`/files/${id}/stream-token`).then((r) => r.data)
    return t.url
  },
}

export const customSubtitlesApi = {
  list: (fileAssetId: number) =>
    http.get<SubtitleInfo[]>(`/custom-subtitles/by-file/${fileAssetId}`).then((r) => r.data),

  upload: (fileAssetId: number, file: File, languageHint?: string) => {
    const form = new FormData()
    form.append('file', file)
    if (languageHint) form.append('language_hint', languageHint)
    return http
      .post(`/custom-subtitles/by-file/${fileAssetId}`, form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      .then((r) => r.data)
  },

  remove: (subtitleId: number) => http.delete(`/custom-subtitles/${subtitleId}`),

  streamToken: (subtitleId: number) =>
    http.get<StreamToken>(`/custom-subtitles/${subtitleId}/stream-token`).then((r) => r.data),
}

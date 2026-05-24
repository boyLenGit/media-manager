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

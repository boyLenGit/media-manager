import http from './http'

export interface PlaybackOption {
  type: string
  label: string
  url: string
  available: boolean
}

export interface PlaybackFileEntry {
  file_asset_id: number
  filename: string
  extension?: string
  missing: boolean
  is_primary: boolean
  quality?: string
  container?: string
  duration_seconds?: number
  width?: number
  height?: number
  web_playable: boolean
  options: PlaybackOption[]
}

export interface PlaybackOptionsResp {
  media_id: number
  files: PlaybackFileEntry[]
  options: PlaybackOption[]
}

export interface PlaybackTarget {
  id: number
  name: string
  target_type: string
  enabled: boolean
  config_json?: string
  sort_order: number
}

export interface ResumePosition {
  position_seconds: number
  duration_seconds?: number
  file_asset_id?: number
  played_at?: string
}

export const playbackApi = {
  getOptions: (mediaId: number) =>
    http.get<PlaybackOptionsResp>(`/playback/media/${mediaId}/options`).then((r) => r.data),

  getResume: (mediaId: number, fileAssetId?: number) =>
    http
      .get<ResumePosition>(`/playback/media/${mediaId}/resume`, {
        params: fileAssetId ? { file_asset_id: fileAssetId } : {},
      })
      .then((r) => r.data),

  reportProgress: (payload: {
    media_item_id: number
    file_asset_id?: number
    playback_target_id?: number
    position_seconds: number
    duration_seconds?: number
    completed?: boolean
  }) => http.post('/playback/progress', payload).then((r) => r.data),

  listTargets: () => http.get<PlaybackTarget[]>('/playback/targets').then((r) => r.data),

  updateTarget: (
    id: number,
    payload: Partial<{
      name: string
      enabled: boolean
      sort_order: number
      config_json: string
    }>,
  ) => http.patch<PlaybackTarget>(`/playback/targets/${id}`, payload).then((r) => r.data),
}

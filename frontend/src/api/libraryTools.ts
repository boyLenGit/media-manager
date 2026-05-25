import http from './http'

export interface ParserInfo {
  name: string
  description: string
  is_default: boolean
}

export interface ParseTestResult {
  title: string
  normalized_title: string
  year?: number
  season?: number
  episode?: number
  quality?: string
  release_group?: string
  language_tags: string[]
  pipeline: string[]
}

export interface DuplicateMember {
  media_id: number
  title: string
  cover_path?: string
  file_count: number
  total_size_bytes: number
  primary_filename?: string
  primary_path?: string
  primary_codec?: string
  primary_container?: string
  primary_quality?: string
  primary_width?: number
  primary_height?: number
  primary_duration_seconds?: number
  primary_partial_hash?: string
  created_at?: string
  watch_status: string
  favorite: boolean
}

export interface DuplicateGroup {
  group_key: string
  match_level: 'exact' | 'high' | 'medium'
  match_reason: string
  members: DuplicateMember[]
}

export interface DuplicateListResp {
  total_groups: number
  total_media: number
  groups: DuplicateGroup[]
}

export const libraryToolsApi = {
  // ---- 解析器 ----
  getParsers: () =>
    http
      .get<{ available: ParserInfo[]; active: string[] }>('/library/parsers')
      .then((r) => r.data),

  updateParsers: (active: string[]) =>
    http.put('/library/parsers', { active }),

  testParse: (filename: string, parsers?: string[]) =>
    http
      .post<ParseTestResult>('/library/parsers/test', { filename, parsers })
      .then((r) => r.data),

  reparseAll: () =>
    http
      .post<{ total: number; updated: number }>('/library/parsers/reparse-all')
      .then((r) => r.data),

  // ---- 重复检测 ----
  listDuplicates: (similarity = 0.9) =>
    http
      .get<DuplicateListResp>('/library/duplicates', { params: { similarity } })
      .then((r) => r.data),

  mergeMedia: (keep_media_id: number, merge_media_ids: number[]) =>
    http
      .post<{ keep_media_id: number; affected_files: number }>(
        '/library/duplicates/merge',
        { keep_media_id, merge_media_ids },
      )
      .then((r) => r.data),

  deleteMedia: (media_ids: number[]) =>
    http
      .post<{ deleted: number }>('/library/duplicates/delete', { media_ids })
      .then((r) => r.data),
}

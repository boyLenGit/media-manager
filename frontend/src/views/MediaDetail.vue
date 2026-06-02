<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Star,
  StarFilled,
  Folder,
  Document,
  ArrowLeft,
  VideoPlay,
  Monitor,
  Link,
  CopyDocument,
  FolderOpened,
  Delete,
} from '@element-plus/icons-vue'
import { mediaApi, type MediaItemDetail } from '@/api/media'
import {
  playbackApi,
  type PlaybackOption,
  type PlaybackOptionsResp,
  type ResumePosition,
} from '@/api/playback'
import { filesApi } from '@/api/files'
import { bookmarksApi, type Bookmark } from '@/api/bookmarks'
import { useAuthStore } from '@/store/auth'
import { copyText } from '@/utils/clipboard'
import PlayerDialog from '@/components/PlayerDialog.vue'
import MediaEditDialog from '@/components/MediaEditDialog.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const id = Number(route.params.id)

const isAdmin = computed(() => auth.user?.role === 'admin')

const media = ref<MediaItemDetail | null>(null)
const playOpts = ref<PlaybackOptionsResp | null>(null)
const resume = ref<ResumePosition | null>(null)
const loading = ref(true)

// 播放器状态
const playerOpen = ref(false)
const playingFileId = ref(0)
const playingFilename = ref('')
const playingDuration = ref<number | undefined>(undefined)
const playingInitialSeek = ref<number | undefined>(undefined)

// 书签
const bookmarks = ref<Bookmark[]>([])

// 编辑弹窗
const editOpen = ref(false)

const onMediaSaved = (updated: MediaItemDetail) => {
  media.value = updated
}

const primaryFile = computed(() => {
  if (!media.value?.files.length) return null
  return media.value.files.find((f) => f.is_primary) || media.value.files[0]
})

// 主文件是否可网页播放(从 playOpts 查)
const primaryWebPlayable = computed(() => {
  if (!primaryFile.value || !playOpts.value) return false
  const entry = playOpts.value.files.find(
    (f) => f.file_asset_id === primaryFile.value!.file_asset_id,
  )
  return entry?.web_playable || false
})

// 主文件不可网播的原因(后端给出的精确说明)
const primaryUnplayableReason = computed(() => {
  if (!primaryFile.value || !playOpts.value) return null
  const entry = playOpts.value.files.find(
    (f) => f.file_asset_id === primaryFile.value!.file_asset_id,
  )
  return entry?.web_unplayable_reason || null
})

// 「本地播放」下拉选项 = 所有非 web 选项
const localOptions = computed(() => {
  if (!playOpts.value) return []
  return playOpts.value.options.filter((o) => o.type !== 'web')
})

const totalSize = computed(() => {
  if (!media.value?.files.length) return 0
  return media.value.files.reduce((s, f) => s + (f.size_bytes || 0), 0)
})

const fileSize = (bytes?: number) => {
  if (!bytes) return '-'
  const u = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let n = bytes
  while (n >= 1024 && i < u.length - 1) {
    n /= 1024
    i++
  }
  return `${n.toFixed(1)} ${u[i]}`
}

const formatDuration = (s?: number) => {
  if (!s) return '-'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  return h > 0
    ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
    : `${m}:${String(sec).padStart(2, '0')}`
}

const fetch = async () => {
  loading.value = true
  try {
    media.value = await mediaApi.detail(id)
    playOpts.value = await playbackApi.getOptions(id)
    resume.value = await playbackApi.getResume(id)
    // 拉书签(失败不阻塞主流程)
    try {
      bookmarks.value = await bookmarksApi.list({ media_item_id: id })
    } catch {
      bookmarks.value = []
    }
  } finally {
    loading.value = false
  }
}

const openWebPlayer = (
  fileId: number,
  filename: string,
  duration?: number,
  initialSeek?: number,
) => {
  playingFileId.value = fileId
  playingFilename.value = filename
  playingDuration.value = duration
  playingInitialSeek.value = initialSeek
  playerOpen.value = true
}

// 跳到书签:打开播放器并 seek 到该位置
const playFromBookmark = (b: Bookmark) => {
  if (!primaryFile.value) {
    ElMessage.warning('暂无可播放文件')
    return
  }
  // 使用书签 file_asset_id(若有),否则主文件
  const fid = b.file_asset_id || primaryFile.value.file_asset_id
  const target =
    media.value?.files.find((f) => f.file_asset_id === fid) || primaryFile.value
  // 检查可网播
  const entry = playOpts.value?.files.find((f) => f.file_asset_id === fid)
  if (!entry?.web_playable) {
    ElMessage.warning(
      entry?.web_unplayable_reason ||
        '该文件无法在浏览器直放,请用「本地播放」复制链接到 IINA / VLC',
    )
    return
  }
  openWebPlayer(fid, target.filename, target.duration_seconds, b.position_seconds)
}

const playPrimary = () => {
  if (!primaryFile.value) return
  if (!primaryWebPlayable.value) {
    ElMessage.warning(
      primaryUnplayableReason.value || '该文件无法在浏览器直放,请使用「本地播放」',
    )
    return
  }
  openWebPlayer(
    primaryFile.value.file_asset_id,
    primaryFile.value.filename,
    primaryFile.value.duration_seconds,
  )
}

const playFile = (fileId: number, filename: string, duration?: number) => {
  const entry = playOpts.value?.files.find((f) => f.file_asset_id === fileId)
  if (!entry?.web_playable) {
    ElMessage.warning(
      entry?.web_unplayable_reason || '该文件无法在浏览器直放,请使用「本地播放」',
    )
    return
  }
  openWebPlayer(fileId, filename, duration)
}

// 处理本地/外部播放选项
const handleLocalOption = async (opt: PlaybackOption, fileId?: number) => {
  switch (opt.type) {
    case 'jellyfin':
      window.open(opt.url, '_blank')
      break

    case 'external_url': {
      // 复制完整带签名的可播放 URL
      const targetFid = fileId ?? primaryFile.value?.file_asset_id
      if (!targetFid) return
      try {
        const t = await filesApi.streamToken(targetFid)
        const fullUrl = `${window.location.origin}${t.url}`
        const ok = await copyText(fullUrl)
        if (ok) {
          ElMessage.success('已复制带签名的播放链接(1 小时内有效),可粘贴到 IINA / VLC / mpv')
        } else {
          ElMessage.error('复制失败,请手动选中文本复制')
        }
      } catch {
        ElMessage.error('生成播放链接失败')
      }
      break
    }

    case 'smb_path': {
      const ok = await copyText(opt.url)
      if (ok) ElMessage.success(`已复制 SMB 路径:${opt.url}`)
      else ElMessage.error('复制失败,请手动选中文本复制')
      break
    }

    case 'reveal_dir': {
      const ok = await copyText(opt.url)
      if (ok) ElMessage.success(`已复制目录:${opt.url}`)
      else ElMessage.error('复制失败,请手动选中文本复制')
      break
    }

    case 'custom_protocol':
      // 触发自定义协议(由本地助手程序处理)
      window.location.href = opt.url
      break

    default:
      ElMessage.info(`目标 ${opt.type}:${opt.url}`)
  }
}

const optionIcon = (type: string) => {
  return (
    {
      jellyfin: Monitor,
      external_url: Link,
      smb_path: CopyDocument,
      reveal_dir: FolderOpened,
      custom_protocol: VideoPlay,
    } as Record<string, any>
  )[type] || Link
}

// 复制本地路径
const copyPath = async (path: string) => {
  const ok = await copyText(path)
  if (ok) ElMessage.success('已复制本地路径')
  else ElMessage.error('复制失败,请手动选中文本复制')
}

// 文件列表中的「网页播放」按钮 (使用上面已定义的 playFile)
// 注:为复用 reason 提示,playFile 已上移到 playPrimary 后

const toggleFavorite = async () => {
  if (!media.value) return
  const r = await mediaApi.update(media.value.id, { favorite: !media.value.favorite })
  media.value = r
}

const setWatchStatus = async (status: string) => {
  if (!media.value) return
  const r = await mediaApi.update(media.value.id, { watch_status: status })
  media.value = r
}

// ============================================================
// 删除
// ============================================================
const deleteMedia = async () => {
  if (!media.value) return

  // 第一步: 先问是否要同时删磁盘文件
  let deleteFiles = false
  try {
    const action = await ElMessageBox.confirm(
      `确定要删除「${media.value.title}」?\n\n` +
        '• 仅清理资源库:不动磁盘文件,以后再扫描会重新加回来\n' +
        '• 一并删除磁盘文件:会尝试删除真实视频文件(无权限会保留并提示)',
      '删除资源',
      {
        distinguishCancelAndClose: true,
        confirmButtonText: '一并删除磁盘文件',
        cancelButtonText: '仅清理资源库',
        type: 'warning',
      },
    )
    deleteFiles = action === 'confirm'
  } catch (e) {
    // close() 即取消
    if (e === 'close') return
    // cancel() 走"仅清理"
    deleteFiles = false
  }

  try {
    const r = await mediaApi.remove(media.value.id, deleteFiles)
    if (r.failed_files.length > 0) {
      // 部分文件删失败(权限) — 但 DB 已清理
      const reasons = r.failed_files
        .map((f) => `• ${f.path}\n  ${f.reason === 'permission_denied' ? '权限不足' : f.reason}`)
        .join('\n')
      ElMessageBox.alert(
        `资源库已清理,但磁盘文件未全部删除:\n\n${reasons}\n\n` +
          '请检查容器对该路径是否只读挂载(:ro),' +
          '或文件 owner 是否与容器 user (一般 1026:100) 匹配。',
        '部分删除失败',
        { type: 'warning', confirmButtonText: '我知道了' },
      )
    } else if (deleteFiles && r.deleted_files.length > 0) {
      ElMessage.success(`已删除资源,并删除 ${r.deleted_files.length} 个磁盘文件`)
    } else {
      ElMessage.success('已从资源库删除')
    }
    router.push('/library')
  } catch (e: any) {
    if (e?.response?.status === 403) {
      ElMessage.error('删除失败:仅管理员可执行')
    } else if (e?.response?.status === 404) {
      ElMessage.error('资源不存在或已被删除')
    } else {
      ElMessage.error(`删除失败:${e?.response?.data?.detail || e?.message || '未知错误'}`)
    }
  }
}

// ============================================================
// 视频技术信息(取主文件)
// ============================================================
const formatBitrate = (sizeBytes?: number, durationSec?: number) => {
  if (!sizeBytes || !durationSec || durationSec < 1) return '-'
  // 估算总码率 = size * 8 / duration (bps)
  const bps = (sizeBytes * 8) / durationSec
  if (bps >= 1_000_000) return `${(bps / 1_000_000).toFixed(2)} Mbps`
  if (bps >= 1_000) return `${(bps / 1_000).toFixed(0)} Kbps`
  return `${bps.toFixed(0)} bps`
}

const resolutionLabel = (w?: number, h?: number) => {
  if (!w || !h) return '-'
  const name =
    h >= 2160
      ? '4K'
      : h >= 1440
        ? '2K'
        : h >= 1080
          ? '1080p'
          : h >= 720
            ? '720p'
            : h >= 480
              ? '480p'
              : ''
  return name ? `${w}×${h} (${name})` : `${w}×${h}`
}

const codecLabel = (codec?: string) => {
  if (!codec) return '-'
  // 简单美化:hevc → HEVC / H.265
  const m: Record<string, string> = {
    hevc: 'HEVC (H.265)',
    h264: 'H.264 (AVC)',
    av1: 'AV1',
    vp9: 'VP9',
    aac: 'AAC',
    opus: 'Opus',
    flac: 'FLAC',
    mp3: 'MP3',
    ac3: 'AC-3',
    eac3: 'E-AC-3',
    dts: 'DTS',
  }
  const lc = codec.toLowerCase()
  return m[lc] || codec.toUpperCase()
}

onMounted(fetch)
</script>

<template>
  <div v-loading="loading" class="detail-page">
    <div class="back-bar">
      <el-button :icon="ArrowLeft" link @click="router.back()">返回</el-button>
    </div>

    <div v-if="media" class="detail">
      <el-card>
        <el-row :gutter="24">
          <el-col :xs="24" :sm="24" :md="8" :lg="6" :xl="5">
            <div class="cover">
              <el-image v-if="media.cover_path" :src="media.cover_path" fit="cover" />
              <div v-else class="cover-placeholder">{{ media.title.slice(0, 1) }}</div>
            </div>
          </el-col>

          <el-col :xs="24" :sm="24" :md="16" :lg="18" :xl="19">
            <div class="head">
              <h2 class="title">{{ media.title }}</h2>
              <el-button
                :icon="media.favorite ? StarFilled : Star"
                :type="media.favorite ? 'warning' : ''"
                circle
                @click="toggleFavorite"
              />
            </div>
            <div v-if="media.original_title" class="orig">{{ media.original_title }}</div>

            <div class="actions">
              <!-- 主按钮:网页播放 -->
              <el-button
                v-if="primaryFile"
                type="primary"
                size="large"
                :icon="VideoPlay"
                :disabled="!primaryWebPlayable"
                @click="playPrimary"
              >
                {{
                  resume && resume.position_seconds > 5
                    ? `网页播放 · 续播 ${formatDuration(resume.position_seconds)}`
                    : '网页播放'
                }}
              </el-button>

              <!-- 本地播放下拉:复制链接 / SMB / 本地路径 / Jellyfin / 自定义协议 -->
              <el-dropdown
                trigger="click"
                :disabled="localOptions.length === 0 && !primaryFile"
              >
                <el-button
                  size="large"
                  :icon="Monitor"
                  :type="!primaryWebPlayable ? 'warning' : 'default'"
                >
                  本地播放<el-icon class="el-icon--right">▾</el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <!-- 复制本地物理路径(总是可用) -->
                    <el-dropdown-item
                      v-if="primaryFile"
                      :icon="Folder"
                      @click="copyPath(primaryFile.path)"
                    >
                      复制本地路径
                    </el-dropdown-item>
                    <!-- 后端返回的可用播放目标 -->
                    <el-dropdown-item
                      v-for="opt in localOptions"
                      :key="opt.type + opt.url"
                      :icon="optionIcon(opt.type)"
                      @click="handleLocalOption(opt, primaryFile?.file_asset_id)"
                    >
                      {{ opt.label }}
                    </el-dropdown-item>
                    <el-dropdown-item v-if="localOptions.length === 0" disabled>
                      无其它播放方式 — 请到设置页启用更多
                    </el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>

              <!-- 观看状态 -->
              <el-dropdown trigger="click">
                <el-button size="large">
                  {{
                    media.watch_status === 'watched'
                      ? '已看'
                      : media.watch_status === 'watching'
                        ? '观看中'
                        : '未看'
                  }}
                  <el-icon class="el-icon--right">▾</el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item @click="setWatchStatus('unwatched')">未看</el-dropdown-item>
                    <el-dropdown-item @click="setWatchStatus('watching')">观看中</el-dropdown-item>
                    <el-dropdown-item @click="setWatchStatus('watched')">已看</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>

              <el-button size="large" @click="editOpen = true">编辑</el-button>
              <el-button
                v-if="isAdmin"
                size="large"
                type="danger"
                plain
                :icon="Delete"
                @click="deleteMedia"
              >
                删除
              </el-button>
            </div>

            <!-- 不可网页直放时的精确原因提示 -->
            <el-alert
              v-if="primaryFile && !primaryWebPlayable && primaryUnplayableReason"
              type="warning"
              :closable="false"
              show-icon
              class="reason-alert"
            >
              <template #title>
                {{ primaryUnplayableReason }} — 请用「本地播放」复制链接到 IINA / VLC / mpv 播放
              </template>
            </el-alert>

            <el-descriptions :column="3" class="mt-12" border>
              <el-descriptions-item label="作者">{{ media.author_name || '-' }}</el-descriptions-item>
              <el-descriptions-item label="类型">{{ media.media_type_name || '-' }}</el-descriptions-item>
              <el-descriptions-item label="发布日期">{{ media.release_date || '-' }}</el-descriptions-item>
              <el-descriptions-item label="评分">{{ media.rating ?? '-' }}</el-descriptions-item>
              <el-descriptions-item label="文件数">{{ media.file_count }}</el-descriptions-item>
              <el-descriptions-item label="总大小">{{ fileSize(totalSize) }}</el-descriptions-item>
              <el-descriptions-item label="标签" :span="3">
                <el-tag
                  v-for="t in media.tags"
                  :key="t.id"
                  size="small"
                  :color="t.color"
                  effect="light"
                  style="margin-right: 4px"
                >
                  {{ t.name }}
                </el-tag>
                <span v-if="media.tags.length === 0" class="muted">无</span>
              </el-descriptions-item>
              <el-descriptions-item label="描述" :span="3">
                {{ media.description || '暂无描述' }}
              </el-descriptions-item>
            </el-descriptions>
          </el-col>
        </el-row>
      </el-card>

      <!-- 视频技术信息 (取主文件) -->
      <el-card v-if="primaryFile" class="mt-16" header="视频信息">
        <div class="info-grid">
          <div class="info-item">
            <div class="info-label">分辨率</div>
            <div class="info-value">
              {{ resolutionLabel(primaryFile.width, primaryFile.height) }}
            </div>
          </div>
          <div class="info-item">
            <div class="info-label">视频编码</div>
            <div class="info-value">{{ codecLabel(primaryFile.video_codec) }}</div>
          </div>
          <div class="info-item">
            <div class="info-label">音频编码</div>
            <div class="info-value">{{ codecLabel(primaryFile.audio_codec) }}</div>
          </div>
          <div class="info-item">
            <div class="info-label">封装格式</div>
            <div class="info-value">{{ primaryFile.container?.toUpperCase() || '-' }}</div>
          </div>
          <div class="info-item">
            <div class="info-label">时长</div>
            <div class="info-value">{{ formatDuration(primaryFile.duration_seconds) }}</div>
          </div>
          <div class="info-item">
            <div class="info-label">文件大小</div>
            <div class="info-value">{{ fileSize(primaryFile.size_bytes) }}</div>
          </div>
          <div class="info-item">
            <div class="info-label">总码率</div>
            <div class="info-value">
              {{ formatBitrate(primaryFile.size_bytes, primaryFile.duration_seconds) }}
            </div>
          </div>
          <div class="info-item">
            <div class="info-label">清晰度标记</div>
            <div class="info-value">{{ primaryFile.quality || '-' }}</div>
          </div>
        </div>
      </el-card>

      <!-- 书签 -->
      <el-card v-if="bookmarks.length > 0" class="mt-16" header="书签">
        <div class="bookmark-list">
          <div
            v-for="b in bookmarks"
            :key="b.id"
            class="bookmark-item"
            @click="playFromBookmark(b)"
          >
            <el-button size="small" type="primary" :icon="VideoPlay" class="bm-time-btn">
              {{ formatDuration(b.position_seconds) }}
            </el-button>
            <div class="bm-content">
              <div class="bm-title">{{ b.title }}</div>
              <div v-if="b.note" class="bm-note">{{ b.note }}</div>
              <div v-if="b.tags.length" class="bm-tags">
                <el-tag
                  v-for="t in b.tags"
                  :key="t.id"
                  size="small"
                  :color="t.color"
                  effect="light"
                >
                  {{ t.name }}
                </el-tag>
              </div>
            </div>
          </div>
        </div>
      </el-card>

      <el-card class="mt-16" header="文件列表">
        <el-empty v-if="!media.files.length" description="无文件" />
        <el-table v-else :data="media.files" stripe>
          <el-table-column label="主" width="60">
            <template #default="{ row }">
              <el-tag v-if="row.is_primary" type="success" size="small">主</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="filename" label="文件名" min-width="240" show-overflow-tooltip>
            <template #default="{ row }">
              <el-icon><Document /></el-icon>
              {{ row.filename }}
              <el-tag v-if="row.missing" type="danger" size="small">失踪</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="清晰度" width="100">
            <template #default="{ row }">{{ row.quality || '-' }}</template>
          </el-table-column>
          <el-table-column label="编码" width="120">
            <template #default="{ row }">
              {{ row.video_codec || '-' }}{{ row.audio_codec ? ` / ${row.audio_codec}` : '' }}
            </template>
          </el-table-column>
          <el-table-column label="分辨率" width="120">
            <template #default="{ row }">
              {{ row.width && row.height ? `${row.width}×${row.height}` : '-' }}
            </template>
          </el-table-column>
          <el-table-column label="时长" width="100">
            <template #default="{ row }">{{ formatDuration(row.duration_seconds) }}</template>
          </el-table-column>
          <el-table-column label="大小" width="100">
            <template #default="{ row }">{{ fileSize(row.size_bytes) }}</template>
          </el-table-column>
          <el-table-column label="操作" width="240" fixed="right">
            <template #default="{ row }">
              <el-button
                size="small"
                type="primary"
                :icon="VideoPlay"
                :disabled="!playOpts?.files.find((f) => f.file_asset_id === row.file_asset_id)?.web_playable"
                @click="playFile(row.file_asset_id, row.filename, row.duration_seconds)"
              >
                播放
              </el-button>
              <el-button size="small" :icon="Folder" @click="copyPath(row.path)">路径</el-button>
              <el-button
                size="small"
                :icon="Link"
                @click="handleLocalOption({ type: 'external_url', label: '', url: '', available: true }, row.file_asset_id)"
              >
                链接
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <el-empty v-else-if="!loading" description="资源不存在" />

    <PlayerDialog
      v-model="playerOpen"
      :media-id="id"
      :file-asset-id="playingFileId"
      :filename="playingFilename"
      :duration-hint="playingDuration"
      :initial-seek="playingInitialSeek"
    />

    <MediaEditDialog v-model="editOpen" :media="media" @saved="onMediaSaved" />
  </div>
</template>

<style scoped>
.detail-page {
  display: flex;
  flex-direction: column;
}
.back-bar {
  display: flex;
  margin-bottom: 8px;
}
.detail {
  display: flex;
  flex-direction: column;
}
.head {
  display: flex;
  align-items: center;
  gap: 12px;
}
.title {
  margin: 0;
}
.orig {
  color: #6b7280;
  margin-bottom: 12px;
}
.actions {
  display: flex;
  gap: 8px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}
.reason-alert {
  margin-bottom: 12px;
}
.mt-12 {
  margin-top: 12px;
}
.mt-16 {
  margin-top: 16px;
}
.cover {
  aspect-ratio: 16/9;
  border-radius: 6px;
  overflow: hidden;
  background: #f3f4f6;
}
.cover :deep(.el-image),
.cover :deep(.el-image__inner) {
  width: 100%;
  height: 100%;
}

@media (max-width: 768px) {
  .cover {
    margin-bottom: 12px;
  }
}
.cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 56px;
  color: #9ca3af;
  background: linear-gradient(135deg, #e5e7eb, #f3f4f6);
}
.muted {
  color: #9ca3af;
}

/* 视频信息 grid */
.info-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.info-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px 0;
}
.info-label {
  font-size: 12px;
  color: #9ca3af;
  letter-spacing: 0.02em;
}
.info-value {
  font-size: 14px;
  color: #1f2937;
  font-weight: 500;
  word-break: break-word;
}

@media (max-width: 768px) {
  .info-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
  }
  .info-value {
    font-size: 13px;
  }
}

/* 书签列表 */
.bookmark-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.bookmark-item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 8px 10px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.15s;
}
.bookmark-item:hover {
  background: #f3f4f6;
}
.bm-time-btn {
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}
.bm-content {
  flex: 1;
  min-width: 0;
}
.bm-title {
  font-weight: 500;
  font-size: 14px;
  color: #1f2937;
}
.bm-note {
  font-size: 12px;
  color: #6b7280;
  margin-top: 4px;
  white-space: pre-wrap;
}
.bm-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 6px;
}
</style>

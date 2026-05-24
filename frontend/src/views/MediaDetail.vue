<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
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
} from '@element-plus/icons-vue'
import { mediaApi, type MediaItemDetail } from '@/api/media'
import {
  playbackApi,
  type PlaybackOption,
  type PlaybackOptionsResp,
  type ResumePosition,
} from '@/api/playback'
import { filesApi } from '@/api/files'
import PlayerDialog from '@/components/PlayerDialog.vue'
import MediaEditDialog from '@/components/MediaEditDialog.vue'

const route = useRoute()
const router = useRouter()
const id = Number(route.params.id)

const media = ref<MediaItemDetail | null>(null)
const playOpts = ref<PlaybackOptionsResp | null>(null)
const resume = ref<ResumePosition | null>(null)
const loading = ref(true)

// 播放器状态
const playerOpen = ref(false)
const playingFileId = ref(0)
const playingFilename = ref('')
const playingDuration = ref<number | undefined>(undefined)

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
  } finally {
    loading.value = false
  }
}

const openWebPlayer = (fileId: number, filename: string, duration?: number) => {
  playingFileId.value = fileId
  playingFilename.value = filename
  playingDuration.value = duration
  playerOpen.value = true
}

const playPrimary = () => {
  if (!primaryFile.value) return
  if (!primaryWebPlayable.value) {
    ElMessage.warning('该文件容器不支持网页直放,请使用「本地播放」中的方式')
    return
  }
  openWebPlayer(
    primaryFile.value.file_asset_id,
    primaryFile.value.filename,
    primaryFile.value.duration_seconds,
  )
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
        await navigator.clipboard.writeText(fullUrl)
        ElMessage.success('已复制带签名的播放链接(1 小时内有效),可粘贴到 IINA / VLC / mpv')
      } catch {
        ElMessage.error('复制失败')
      }
      break
    }

    case 'smb_path':
      try {
        await navigator.clipboard.writeText(opt.url)
        ElMessage.success(`已复制 SMB 路径:${opt.url}`)
      } catch {
        ElMessage.error('复制失败')
      }
      break

    case 'reveal_dir':
      try {
        await navigator.clipboard.writeText(opt.url)
        ElMessage.success(`已复制目录:${opt.url}`)
      } catch {
        ElMessage.error('复制失败')
      }
      break

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
  try {
    await navigator.clipboard.writeText(path)
    ElMessage.success('已复制本地路径')
  } catch {
    ElMessage.error('复制失败')
  }
}

// 文件列表中的「网页播放」按钮
const playFile = (fileId: number, filename: string, duration?: number) => {
  const entry = playOpts.value?.files.find((f) => f.file_asset_id === fileId)
  if (!entry?.web_playable) {
    ElMessage.warning('该文件容器不支持网页直放,请使用「本地播放」复制链接')
    return
  }
  openWebPlayer(fileId, filename, duration)
}

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
          <el-col :span="5">
            <div class="cover">
              <el-image v-if="media.cover_path" :src="media.cover_path" fit="cover" />
              <div v-else class="cover-placeholder">{{ media.title.slice(0, 1) }}</div>
            </div>
          </el-col>

          <el-col :span="19">
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
              <el-dropdown trigger="click" :disabled="localOptions.length === 0 && !primaryFile">
                <el-button size="large" :icon="Monitor">
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
            </div>

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
.mt-12 {
  margin-top: 12px;
}
.mt-16 {
  margin-top: 16px;
}
.cover {
  aspect-ratio: 2/3;
  border-radius: 6px;
  overflow: hidden;
  background: #f3f4f6;
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
</style>

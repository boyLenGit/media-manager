<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, Document, Folder, Delete, Connection } from '@element-plus/icons-vue'
import { libraryToolsApi, type DuplicateGroup, type DuplicateMember } from '@/api/libraryTools'
import { copyText } from '@/utils/clipboard'

const router = useRouter()
const groups = ref<DuplicateGroup[]>([])
const totalGroups = ref(0)
const totalMedia = ref(0)
const loading = ref(false)
const similarity = ref(0.9)

const fetch = async () => {
  loading.value = true
  try {
    const r = await libraryToolsApi.listDuplicates(similarity.value)
    groups.value = r.groups
    totalGroups.value = r.total_groups
    totalMedia.value = r.total_media
  } finally {
    loading.value = false
  }
}

const fileSize = (bytes: number) => {
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

const formatTime = (s?: string) => (s ? new Date(s).toLocaleString() : '-')

const formatDuration = (s?: number) => {
  if (!s) return '-'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  return h > 0
    ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
    : `${m}:${String(sec).padStart(2, '0')}`
}

const levelType = (level: string) =>
  ({ exact: 'danger', high: 'warning', medium: 'info' } as Record<string, any>)[level] || ''

const levelLabel = (level: string) =>
  ({ exact: '确定重复', high: '高度疑似', medium: '可能重复' } as Record<string, string>)[level] ||
  level

const openDetail = (id: number) => router.push(`/media/${id}`)

const copyPath = async (path?: string) => {
  if (!path) return
  const ok = await copyText(path)
  if (ok) ElMessage.success('已复制路径')
  else ElMessage.error('复制失败,请手动选中文本复制')
}

// 合并:把组里其他成员合并到 keep
const mergeInto = async (group: DuplicateGroup, keep: DuplicateMember) => {
  const others = group.members.filter((m) => m.media_id !== keep.media_id)
  await ElMessageBox.confirm(
    `把以下 ${others.length} 个资源合并到「${keep.title}」?\n\n` +
      `它们关联的文件会改挂到「${keep.title}」上,被合并的资源会从资源库删除(磁盘文件保留)。`,
    '确认合并',
    { type: 'warning' },
  ).catch(() => null)
  try {
    const r = await libraryToolsApi.mergeMedia(
      keep.media_id,
      others.map((m) => m.media_id),
    )
    ElMessage.success(`已合并 ${r.affected_files} 个文件到主资源`)
    await fetch()
  } catch {
    /* error toasted */
  }
}

// 删除单个成员(只删 DB 记录,不删磁盘)
const removeMember = async (m: DuplicateMember) => {
  await ElMessageBox.confirm(
    `从资源库移除「${m.title}」?\n\n仅删除资源库记录,磁盘文件保留(下次扫描可能重新入库)。`,
    '确认',
    { type: 'warning' },
  ).catch(() => null)
  try {
    await libraryToolsApi.deleteMedia([m.media_id])
    ElMessage.success('已移除')
    await fetch()
  } catch {
    /* error toasted */
  }
}

const refreshSimilarity = () => fetch()

onMounted(fetch)
</script>

<template>
  <div class="dup-page">
    <div class="page-header">
      <h2 class="title">重复检测</h2>
      <div class="actions">
        <span class="similarity-label">模糊匹配阈值:</span>
        <el-slider
          v-model="similarity"
          :min="0.7"
          :max="1.0"
          :step="0.05"
          :format-tooltip="(v: number) => `${Math.round(v * 100)}%`"
          style="width: 200px"
          @change="refreshSimilarity"
        />
        <el-button :icon="Refresh" @click="fetch">刷新</el-button>
      </div>
    </div>

    <el-alert
      v-if="!loading && totalGroups === 0"
      type="success"
      :closable="false"
      title="资源库里没找到疑似重复的资源 ✨"
      style="margin-bottom: 12px"
    />

    <el-alert
      v-else-if="!loading"
      type="warning"
      :closable="false"
      style="margin-bottom: 12px"
    >
      <template #title>
        发现 <strong>{{ totalGroups }}</strong> 组疑似重复,共 <strong>{{ totalMedia }}</strong> 个资源
      </template>
      <template #default>
        每组里你可以选择「合并」(把多个合到一个主资源)或「移除」(从资源库删除某一个)。
        操作不会动磁盘上的视频文件。
      </template>
    </el-alert>

    <el-skeleton v-if="loading" :rows="6" animated />

    <div v-else class="groups">
      <el-card v-for="group in groups" :key="group.group_key" class="group-card" body-style="padding:0">
        <template #header>
          <div class="group-header">
            <el-tag :type="levelType(group.match_level)" effect="dark">
              {{ levelLabel(group.match_level) }}
            </el-tag>
            <span class="group-reason">{{ group.match_reason }}</span>
            <span class="group-count">{{ group.members.length }} 个资源</span>
          </div>
        </template>

        <el-table :data="group.members" stripe>
          <el-table-column label="封面" width="80">
            <template #default="{ row }">
              <div class="mini-cover" @click="openDetail(row.media_id)">
                <el-image
                  v-if="row.cover_path"
                  :src="row.cover_path"
                  fit="cover"
                  style="width: 56px; height: 80px; border-radius: 4px"
                />
                <div v-else class="cover-ph">{{ row.title.slice(0, 1) }}</div>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="标题" min-width="220" show-overflow-tooltip>
            <template #default="{ row }">
              <a class="title-link" @click="openDetail(row.media_id)">{{ row.title }}</a>
              <div class="filename">
                <el-icon><Document /></el-icon>
                {{ row.primary_filename || '-' }}
              </div>
            </template>
          </el-table-column>
          <el-table-column label="编码 / 分辨率" width="160">
            <template #default="{ row }">
              <div>
                {{ row.primary_codec || '?' }} /
                {{ row.primary_container || '?' }}
              </div>
              <div class="sub">
                {{ row.primary_width && row.primary_height
                  ? `${row.primary_width}×${row.primary_height}`
                  : (row.primary_quality || '-') }}
              </div>
            </template>
          </el-table-column>
          <el-table-column label="时长 / 大小" width="140">
            <template #default="{ row }">
              <div>{{ formatDuration(row.primary_duration_seconds) }}</div>
              <div class="sub">{{ fileSize(row.total_size_bytes) }} ({{ row.file_count }} 个文件)</div>
            </template>
          </el-table-column>
          <el-table-column label="入库时间" width="170">
            <template #default="{ row }">
              <div class="sub">{{ formatTime(row.created_at) }}</div>
            </template>
          </el-table-column>
          <el-table-column label="状态" width="100">
            <template #default="{ row }">
              <el-tag size="small">{{ row.watch_status }}</el-tag>
              <el-tag v-if="row.favorite" size="small" type="warning" style="margin-top: 2px"
                >★ 收藏</el-tag
              >
            </template>
          </el-table-column>
          <el-table-column label="操作" width="220" fixed="right">
            <template #default="{ row }">
              <el-button
                size="small"
                type="primary"
                :icon="Connection"
                @click="mergeInto(group, row)"
              >
                以此为主合并
              </el-button>
              <el-button size="small" :icon="Folder" @click="copyPath(row.primary_path)">
                复制路径
              </el-button>
              <el-button
                size="small"
                type="danger"
                :icon="Delete"
                @click="removeMember(row)"
              />
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.dup-page {
  display: flex;
  flex-direction: column;
}
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.title {
  margin: 0;
}
.actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.similarity-label {
  font-size: 13px;
  color: #6b7280;
}
.groups {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.group-card {
  border: 1px solid #e5e7eb;
}
.group-header {
  display: flex;
  align-items: center;
  gap: 12px;
}
.group-reason {
  flex: 1;
  font-size: 13px;
  color: #374151;
}
.group-count {
  font-size: 13px;
  color: #6b7280;
}
.mini-cover {
  cursor: pointer;
}
.cover-ph {
  width: 56px;
  height: 80px;
  border-radius: 4px;
  background: linear-gradient(135deg, #e5e7eb, #f3f4f6);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
  font-size: 22px;
}
.title-link {
  color: #2563eb;
  cursor: pointer;
  font-weight: 500;
}
.title-link:hover {
  text-decoration: underline;
}
.filename {
  font-size: 12px;
  color: #6b7280;
  margin-top: 2px;
  display: flex;
  align-items: center;
  gap: 4px;
}
.sub {
  font-size: 12px;
  color: #6b7280;
}
</style>

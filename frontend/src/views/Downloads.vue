<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, VideoPlay, VideoPause, Delete } from '@element-plus/icons-vue'
import { downloadsApi, type DownloadTask } from '@/api/downloads'
import { formatDateTime } from '@/utils/datetime'

const tasks = ref<DownloadTask[]>([])
const loading = ref(false)
const filterStatus = ref<string>('')

let pollTimer: number | null = null

const filtered = computed(() => {
  if (!filterStatus.value) return tasks.value
  return tasks.value.filter((t) => t.status === filterStatus.value)
})

const fetch = async () => {
  loading.value = true
  try {
    tasks.value = await downloadsApi.list()
  } finally {
    loading.value = false
  }
}

const startPolling = () => {
  stopPolling()
  pollTimer = window.setInterval(fetch, 3000)
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const statusType = (s: string) =>
  ({
    completed: 'success',
    downloading: 'warning',
    paused: 'info',
    pending: 'info',
    failed: 'danger',
    removed: 'danger',
    unknown: 'info',
  } as Record<string, any>)[s] || 'info'

const statusLabel = (s: string) =>
  ({
    completed: '已完成',
    downloading: '下载中',
    paused: '已暂停',
    pending: '排队中',
    failed: '失败',
    removed: '已移除',
    unknown: '未知',
  } as Record<string, string>)[s] || s

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

const speed = (bps: number) => {
  if (!bps) return '-'
  return `${fileSize(bps)}/s`
}

const formatEta = (sec?: number) => {
  if (!sec || sec <= 0 || sec > 86400 * 365) return '-'
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  const s = sec % 60
  if (h > 0) return `${h}h ${m}m`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

const pause = async (t: DownloadTask) => {
  await downloadsApi.pause(t.id)
  ElMessage.success('已暂停')
  await fetch()
}

const resume = async (t: DownloadTask) => {
  await downloadsApi.resume(t.id)
  ElMessage.success('已恢复')
  await fetch()
}

const remove = async (t: DownloadTask) => {
  const result = await ElMessageBox.confirm(
    `删除任务「${t.title}」?`,
    '确认',
    {
      confirmButtonText: '仅移除任务',
      cancelButtonText: '取消',
      distinguishCancelAndClose: true,
      type: 'warning',
      showCancelButton: true,
    },
  ).catch(() => null)
  if (!result) return
  await downloadsApi.remove(t.id, false)
  ElMessage.success('已删除')
  await fetch()
}

const removeWithFiles = async (t: DownloadTask) => {
  await ElMessageBox.confirm(
    `删除任务「${t.title}」并删除磁盘文件?此操作不可恢复!`,
    '危险操作',
    { type: 'warning', confirmButtonText: '删除任务和文件', cancelButtonText: '取消' },
  ).catch(() => null)
  await downloadsApi.remove(t.id, true)
  ElMessage.success('已删除任务和文件')
  await fetch()
}

const formatTime = formatDateTime

onMounted(() => {
  fetch()
  startPolling()
})

onUnmounted(stopPolling)
</script>

<template>
  <div class="downloads">
    <el-card>
      <div class="toolbar">
        <el-radio-group v-model="filterStatus">
          <el-radio-button value="">全部</el-radio-button>
          <el-radio-button value="downloading">下载中</el-radio-button>
          <el-radio-button value="paused">已暂停</el-radio-button>
          <el-radio-button value="completed">已完成</el-radio-button>
          <el-radio-button value="failed">失败</el-radio-button>
        </el-radio-group>
        <div class="spacer" />
        <el-button :icon="Refresh" @click="fetch">刷新</el-button>
      </div>

      <el-empty
        v-if="!loading && filtered.length === 0"
        description="暂无下载任务,可在「搜索」页中添加(待第五阶段实现)"
      />

      <el-table v-else :data="filtered" v-loading="loading" stripe>
        <el-table-column label="标题" min-width="240" show-overflow-tooltip>
          <template #default="{ row }">
            <div class="title-cell">{{ row.title }}</div>
            <div class="hash">{{ row.info_hash }}</div>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="110">
          <template #default="{ row }">
            <el-tag :type="statusType(row.status)" size="small">
              {{ statusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="进度" width="220">
          <template #default="{ row }">
            <el-progress
              :percentage="Math.round(row.progress * 100)"
              :status="
                row.status === 'completed'
                  ? 'success'
                  : row.status === 'failed'
                    ? 'exception'
                    : undefined
              "
            />
          </template>
        </el-table-column>
        <el-table-column label="↓速度" width="110">
          <template #default="{ row }">{{ speed(row.download_speed) }}</template>
        </el-table-column>
        <el-table-column label="↑速度" width="110">
          <template #default="{ row }">{{ speed(row.upload_speed) }}</template>
        </el-table-column>
        <el-table-column label="剩余" width="100">
          <template #default="{ row }">{{ formatEta(row.eta_seconds) }}</template>
        </el-table-column>
        <el-table-column label="保存路径" min-width="200" show-overflow-tooltip>
          <template #default="{ row }">{{ row.save_path || '-' }}</template>
        </el-table-column>
        <el-table-column label="创建时间" width="170">
          <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <el-button
              v-if="row.status === 'downloading' || row.status === 'pending'"
              size="small"
              :icon="VideoPause"
              @click="pause(row)"
            />
            <el-button
              v-if="row.status === 'paused'"
              size="small"
              type="primary"
              :icon="VideoPlay"
              @click="resume(row)"
            />
            <el-button size="small" :icon="Delete" @click="remove(row)">移除</el-button>
            <el-button size="small" type="danger" @click="removeWithFiles(row)">删文件</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.downloads {
  display: flex;
  flex-direction: column;
}
.toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}
.spacer {
  flex: 1;
}
.title-cell {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.hash {
  font-size: 11px;
  color: #9ca3af;
  font-family: monospace;
}
</style>

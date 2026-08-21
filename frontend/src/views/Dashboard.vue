<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import {
  Film,
  Folder,
  Download,
  Search,
  Star,
  View,
  PriceTag,
  User,
  Refresh,
  CopyDocument,
  Close,
} from '@element-plus/icons-vue'
import { statsApi, type DashboardStats, type RecentMediaItem } from '@/api/stats'
import { scanApi, type ScanJob } from '@/api/scan'
import { toDate } from '@/utils/datetime'

const router = useRouter()
const stats = ref<DashboardStats | null>(null)
const recent = ref<RecentMediaItem[]>([])
const recentJobs = ref<ScanJob[]>([])
const loading = ref(true)

// 最近一次成功扫描里检测到的重复组数(只读 status=success 的)
const lastDedupGroups = computed(() => {
  const successJobs = recentJobs.value.filter((j) => j.status === 'success')
  if (!successJobs.length) return 0
  return successJobs[0].dedup_groups_found || 0
})

// 用户可手动关闭这个提示(localStorage 记忆,直到下次扫描产生新值)
const dedupHintDismissed = ref(
  localStorage.getItem('media-manager.dedupHintDismissedAt') ===
    String(recentJobs.value[0]?.finished_at || ''),
)
const dismissDedupHint = () => {
  const ts = String(recentJobs.value[0]?.finished_at || Date.now())
  localStorage.setItem('media-manager.dedupHintDismissedAt', ts)
  dedupHintDismissed.value = true
}
const showDedupHint = computed(
  () => lastDedupGroups.value > 0 && !dedupHintDismissed.value,
)
const goDuplicates = () => router.push('/duplicates')

const fileSize = (bytes: number) => {
  if (!bytes) return '0 B'
  const u = ['B', 'KB', 'MB', 'GB', 'TB']
  let i = 0
  let n = bytes
  while (n >= 1024 && i < u.length - 1) {
    n /= 1024
    i++
  }
  return `${n.toFixed(1)} ${u[i]}`
}

const formatTime = (s?: string) => {
  if (!s) return '-'
  const date = toDate(s)
  const now = new Date()
  const diffMin = Math.floor((now.getTime() - date.getTime()) / 60000)
  if (diffMin < 1) return '刚刚'
  if (diffMin < 60) return `${diffMin} 分钟前`
  if (diffMin < 1440) return `${Math.floor(diffMin / 60)} 小时前`
  return date.toLocaleString()
}

const fetch = async () => {
  loading.value = true
  try {
    const [s, r, j] = await Promise.all([
      statsApi.get(),
      statsApi.recentMedia(12),
      scanApi.listJobs(5),
    ])
    stats.value = s
    recent.value = r
    recentJobs.value = j
  } finally {
    loading.value = false
  }
}

const open = (id: number) => router.push(`/media/${id}`)

onMounted(fetch)
</script>

<template>
  <div class="dashboard" v-loading="loading">
    <div class="title-bar">
      <h2 class="title">总览</h2>
      <el-button :icon="Refresh" @click="fetch">刷新</el-button>
    </div>

    <!-- 重复检测提示条 -->
    <el-alert
      v-if="showDedupHint"
      type="warning"
      :closable="false"
      show-icon
      class="dedup-hint"
    >
      <template #title>
        <div class="dedup-hint-row">
          <el-icon><CopyDocument /></el-icon>
          <span>
            最近一次扫描检测到 <strong>{{ lastDedupGroups }}</strong> 个疑似重复资源组
          </span>
          <el-button size="small" type="warning" @click="goDuplicates">
            前往处理
          </el-button>
          <el-button size="small" :icon="Close" link @click="dismissDedupHint">
            稍后
          </el-button>
        </div>
      </template>
    </el-alert>

    <!-- 主统计卡片 -->
    <el-row :gutter="16" v-if="stats">
      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="stat-card stat-blue" shadow="hover" @click="router.push('/library')">
          <div class="stat-row">
            <el-icon class="stat-icon"><Film /></el-icon>
            <div>
              <div class="stat-label">资源总数</div>
              <div class="stat-value">{{ stats.media_count }}</div>
            </div>
          </div>
          <div class="stat-hint">
            视频 {{ stats.video_count }} · 收藏 {{ stats.favorite_count }}
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="stat-card stat-green" shadow="hover">
          <div class="stat-row">
            <el-icon class="stat-icon"><Folder /></el-icon>
            <div>
              <div class="stat-label">文件总数</div>
              <div class="stat-value">{{ stats.file_count }}</div>
            </div>
          </div>
          <div class="stat-hint">
            总大小 {{ fileSize(stats.total_size_bytes) }}
            <span v-if="stats.missing_count > 0" class="warn">
              · 失踪 {{ stats.missing_count }}
            </span>
          </div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="stat-card stat-orange" shadow="hover" @click="router.push('/downloads')">
          <div class="stat-row">
            <el-icon class="stat-icon"><Download /></el-icon>
            <div>
              <div class="stat-label">下载中</div>
              <div class="stat-value">{{ stats.downloading_count }}</div>
            </div>
          </div>
          <div class="stat-hint">已完成 {{ stats.completed_dl_count }}</div>
        </el-card>
      </el-col>

      <el-col :xs="24" :sm="12" :md="6">
        <el-card class="stat-card stat-purple" shadow="hover">
          <div class="stat-row">
            <el-icon class="stat-icon"><View /></el-icon>
            <div>
              <div class="stat-label">观看进度</div>
              <div class="stat-value">{{ stats.watched_count }} / {{ stats.media_count }}</div>
            </div>
          </div>
          <div class="stat-hint">
            未看 {{ stats.unwatched_count }} · 最近 7 天新增 {{ stats.recent_added }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 副统计 -->
    <el-row :gutter="16" class="mt-12" v-if="stats">
      <el-col :xs="24" :sm="12" :md="6">
        <el-card body-style="padding:12px">
          <div class="mini-row">
            <el-icon><User /></el-icon>
            <span>作者</span>
            <span class="mini-value">{{ stats.author_count }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card body-style="padding:12px">
          <div class="mini-row">
            <el-icon><PriceTag /></el-icon>
            <span>标签</span>
            <span class="mini-value">{{ stats.tag_count }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card body-style="padding:12px">
          <div class="mini-row">
            <el-icon><Star /></el-icon>
            <span>收藏</span>
            <span class="mini-value">{{ stats.favorite_count }}</span>
          </div>
        </el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="6">
        <el-card body-style="padding:12px">
          <div class="mini-row">
            <el-icon><Search /></el-icon>
            <span>最近播放</span>
            <span class="mini-value">{{ stats.recent_played_count }}</span>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 最近入库 -->
    <el-card class="mt-12">
      <template #header>
        <div class="card-header">
          <span>最近入库</span>
          <el-button text @click="router.push('/library')">查看全部 →</el-button>
        </div>
      </template>
      <el-empty v-if="recent.length === 0" description="还没扫描任何资源,去「设置 → 扫描路径」添加目录" />
      <el-row v-else :gutter="12">
        <el-col
          v-for="m in recent"
          :key="m.id"
          :xs="12"
          :sm="8"
          :md="6"
          :lg="4"
          :xl="4"
        >
          <div class="mini-card" @click="open(m.id)">
            <div class="mini-cover">
              <el-image v-if="m.cover_path" :src="m.cover_path" fit="cover" lazy />
              <div v-else class="mini-cover-ph">{{ m.title.slice(0, 1) }}</div>
              <el-tag v-if="m.favorite" type="warning" size="small" effect="dark" class="fav-badge">
                ★
              </el-tag>
            </div>
            <div class="mini-title" :title="m.title">{{ m.title }}</div>
            <div class="mini-time">{{ formatTime(m.created_at) }}</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 系统状态 -->
    <el-row :gutter="16" class="mt-12" v-if="stats">
      <el-col :xs="24" :md="12">
        <el-card>
          <template #header>系统状态</template>
          <el-descriptions :column="1" size="small">
            <el-descriptions-item label="qBittorrent">
              <el-tag :type="stats.qbittorrent_configured ? 'success' : 'info'" size="small">
                {{ stats.qbittorrent_configured ? '已配置' : '未配置' }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="Jellyfin">
              <el-tag :type="stats.jellyfin_configured ? 'success' : 'info'" size="small">
                {{ stats.jellyfin_configured ? '已配置' : '未配置' }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <el-col :xs="24" :md="12">
        <el-card>
          <template #header>最近扫描</template>
          <el-empty v-if="!stats.last_scan" description="未执行过扫描" :image-size="60" />
          <el-descriptions v-else :column="1" size="small">
            <el-descriptions-item label="状态">
              <el-tag size="small" :type="stats.last_scan.status === 'success' ? 'success' : 'warning'">
                {{ stats.last_scan.status }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="扫描文件数">
              {{ stats.last_scan.scanned_files }} (新增 {{ stats.last_scan.new_files }})
            </el-descriptions-item>
            <el-descriptions-item label="完成时间">
              {{ formatTime(stats.last_scan.finished_at) }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
}
.title-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.dedup-hint {
  margin-bottom: 16px;
}
.dedup-hint-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.title {
  margin: 0;
}
.mt-12 {
  margin-top: 12px;
}

.stat-card {
  cursor: default;
  border-left: 4px solid #94a3b8;
  transition: transform 0.15s;
}
.stat-card:hover {
  transform: translateY(-2px);
}
.stat-blue {
  border-left-color: #3b82f6;
}
.stat-green {
  border-left-color: #10b981;
}
.stat-orange {
  border-left-color: #f59e0b;
}
.stat-purple {
  border-left-color: #8b5cf6;
}
.stat-row {
  display: flex;
  align-items: center;
  gap: 12px;
}
.stat-icon {
  font-size: 32px;
  color: #6b7280;
}
.stat-label {
  font-size: 13px;
  color: #6b7280;
}
.stat-value {
  font-size: 28px;
  font-weight: 600;
  line-height: 1.2;
}
.stat-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #9ca3af;
}
.warn {
  color: #f59e0b;
}

.mini-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: #374151;
}
.mini-value {
  margin-left: auto;
  font-weight: 600;
  font-size: 18px;
  color: #111827;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.mini-card {
  cursor: pointer;
  margin-bottom: 8px;
  transition: transform 0.15s;
}
.mini-card:hover {
  transform: translateY(-2px);
}
.mini-cover {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  border-radius: 4px;
  overflow: hidden;
  background: #f3f4f6;
}
.mini-cover :deep(.el-image),
.mini-cover :deep(.el-image__inner) {
  width: 100%;
  height: 100%;
}
.mini-cover-ph {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  color: #9ca3af;
  background: linear-gradient(135deg, #e5e7eb, #f3f4f6);
}
.fav-badge {
  position: absolute;
  top: 4px;
  right: 4px;
}
.mini-title {
  margin-top: 6px;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mini-time {
  font-size: 11px;
  color: #9ca3af;
}
</style>

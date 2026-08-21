<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Download } from '@element-plus/icons-vue'
import { searchApi, type SearchHit } from '@/api/search'
import { downloadsApi } from '@/api/downloads'
import { formatDate } from '@/utils/datetime'

const router = useRouter()
const q = ref('')
const hits = ref<SearchHit[]>([])
const errors = ref<{ source?: string; error?: string; detail?: string }[]>([])
const loading = ref(false)
const searched = ref(false)

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

const formatTime = formatDate

const search = async () => {
  if (!q.value) return
  loading.value = true
  searched.value = true
  try {
    const r = await searchApi.search(q.value)
    hits.value = r.hits
    errors.value = r.errors
  } finally {
    loading.value = false
  }
}

const dupTagType = (level?: string) =>
  ({
    exact: 'danger',
    high: 'warning',
    medium: 'warning',
    low: 'info',
  } as Record<string, any>)[level || ''] || ''

const dupLabel = (level?: string) =>
  ({
    exact: '已存在',
    high: '高度疑似',
    medium: '可能重复',
    low: '弱匹配',
  } as Record<string, string>)[level || ''] || ''

const download = async (h: SearchHit, force = false) => {
  if (!h.magnet_uri) {
    ElMessage.error('该结果没有磁力链接')
    return
  }

  // 二次确认重复
  if (h.duplicate && (h.duplicate.level === 'exact' || h.duplicate.level === 'high') && !force) {
    const action = await ElMessageBox.confirm(
      `${h.duplicate.reason}\n\n是否仍然下载?`,
      '检测到重复资源',
      {
        type: 'warning',
        confirmButtonText: '强制下载',
        cancelButtonText: '取消',
      },
    ).catch(() => null)
    if (!action) return
    return download(h, true)
  }

  try {
    const r = await downloadsApi.create({
      title: h.title,
      magnet_uri: h.magnet_uri,
      info_hash: h.info_hash,
      size_bytes: h.size_bytes,
      force,
    })
    if (r.status === 'duplicate') {
      ElMessage.warning(r.duplicate?.reason || '检测到重复资源')
    } else {
      ElMessage.success('已添加到下载队列')
    }
  } catch (e: any) {
    if (e?.response?.data?.detail === 'downloader_not_configured') {
      ElMessage.error('请先在「设置 → 下载器」中配置 qBittorrent')
    }
  }
}

const openMatched = (id: number) => router.push(`/media/${id}`)
</script>

<template>
  <div class="search-page">
    <el-card>
      <div class="bar">
        <el-input
          v-model="q"
          placeholder="输入关键词搜索资源(支持中英文)"
          size="large"
          clearable
          :prefix-icon="Search"
          style="flex: 1"
          @keyup.enter="search"
        />
        <el-button size="large" type="primary" :loading="loading" @click="search">搜索</el-button>
      </div>
      <div class="hint">
        搜索源在「设置 → 搜索源」中配置,本系统不内置任何搜索源。
      </div>
    </el-card>

    <el-card v-if="errors.length > 0" class="mt-12">
      <template #header>搜索告警</template>
      <el-alert
        v-for="(e, i) in errors"
        :key="i"
        :title="e.source ? `${e.source}: ${e.error}` : e.detail"
        type="warning"
        :closable="false"
        style="margin-bottom: 4px"
      />
    </el-card>

    <el-card v-if="searched" class="mt-12">
      <template #header>
        搜索结果 ({{ hits.length }})
      </template>

      <el-empty v-if="!loading && hits.length === 0" description="未找到结果" />

      <el-table v-else :data="hits" v-loading="loading" stripe>
        <el-table-column label="标题" min-width="320" show-overflow-tooltip>
          <template #default="{ row }">
            <a v-if="row.source_url" :href="row.source_url" target="_blank">{{ row.title }}</a>
            <span v-else>{{ row.title }}</span>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="120">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.source_name }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="大小" width="100">
          <template #default="{ row }">{{ fileSize(row.size_bytes) }}</template>
        </el-table-column>
        <el-table-column label="种子" width="80">
          <template #default="{ row }">
            <span class="seeders">{{ row.seeders ?? '?' }}</span>
            <span class="leechers" v-if="row.leechers !== null && row.leechers !== undefined">
              / {{ row.leechers }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="发布" width="110">
          <template #default="{ row }">{{ formatTime(row.publish_time) }}</template>
        </el-table-column>
        <el-table-column label="重复" width="160">
          <template #default="{ row }">
            <div v-if="row.duplicate">
              <el-tag :type="dupTagType(row.duplicate.level)" size="small">
                {{ dupLabel(row.duplicate.level) }}
              </el-tag>
              <el-button
                v-if="row.duplicate.matched_media_id"
                size="small"
                link
                type="primary"
                @click="openMatched(row.duplicate.matched_media_id)"
              >
                查看
              </el-button>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="140" fixed="right">
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              :icon="Download"
              :disabled="!row.magnet_uri"
              @click="download(row)"
            >
              下载
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.search-page {
  display: flex;
  flex-direction: column;
}
.bar {
  display: flex;
  gap: 8px;
}
.hint {
  margin-top: 12px;
  color: #6b7280;
  font-size: 13px;
}
.mt-12 {
  margin-top: 12px;
}
.seeders {
  color: #16a34a;
  font-weight: 500;
}
.leechers {
  color: #dc2626;
}
a {
  color: #2563eb;
  text-decoration: none;
}
a:hover {
  text-decoration: underline;
}
</style>

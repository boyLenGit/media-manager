<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Refresh } from '@element-plus/icons-vue'
import { settingsApi } from '@/api/settings'

interface AuditRow {
  id: number
  actor_user_id: number | null
  actor_username: string | null
  action: string
  target_type: string | null
  target_id: string | null
  metadata_json: string | null
  ip: string | null
  user_agent: string | null
  created_at: string
}

const logs = ref<AuditRow[]>([])
const loading = ref(false)
const filterAction = ref('')

const fetchLogs = async () => {
  loading.value = true
  try {
    logs.value = await settingsApi.listAuditLogs({
      limit: 200,
      action: filterAction.value || undefined,
    })
  } finally {
    loading.value = false
  }
}

const formatTime = (s: string) => new Date(s).toLocaleString()

const actionLabel = (a: string) => {
  const m: Record<string, string> = {
    reset_all: '抹掉所有数据',
    'reset_all.failed': '抹掉所有数据(失败)',
    media_delete: '删除资源',
  }
  return m[a] || a
}

const actionType = (a: string) => {
  if (a.includes('reset_all')) return 'danger'
  if (a.includes('delete')) return 'warning'
  return 'info'
}

const prettyMeta = (j: string | null) => {
  if (!j) return '-'
  try {
    const obj = JSON.parse(j)
    return Object.entries(obj)
      .map(([k, v]) => `${k}=${typeof v === 'object' ? JSON.stringify(v) : v}`)
      .join(' · ')
  } catch {
    return j
  }
}

// 已知 action 列表(用于筛选下拉)
const knownActions = computed(() => {
  const s = new Set(logs.value.map((l) => l.action))
  return Array.from(s).sort()
})

onMounted(fetchLogs)
</script>

<template>
  <div class="audit-tab">
    <div class="header">
      <h3 class="title">审计日志</h3>
      <div class="actions">
        <el-select
          v-model="filterAction"
          placeholder="全部操作"
          clearable
          style="width: 200px"
          @change="fetchLogs"
        >
          <el-option v-for="a in knownActions" :key="a" :label="actionLabel(a)" :value="a" />
        </el-select>
        <el-button :icon="Refresh" @click="fetchLogs">刷新</el-button>
      </div>
    </div>

    <p class="hint">
      仅记录敏感/不可逆操作(目前包括:抹掉所有数据、删除资源)。
      最多展示最近 200 条;审计日志本身不会被「抹掉所有数据」清除。
    </p>

    <el-table :data="logs" v-loading="loading" stripe size="small">
      <el-table-column label="时间" width="180">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160">
        <template #default="{ row }">
          <el-tag :type="actionType(row.action)" size="small">{{ actionLabel(row.action) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作人" width="140">
        <template #default="{ row }">
          {{ row.actor_username || (row.actor_user_id ? `#${row.actor_user_id}` : '系统') }}
        </template>
      </el-table-column>
      <el-table-column label="对象" width="160">
        <template #default="{ row }">
          <span v-if="row.target_type">
            {{ row.target_type }}{{ row.target_id ? ` #${row.target_id}` : '' }}
          </span>
          <span v-else>-</span>
        </template>
      </el-table-column>
      <el-table-column label="详情" min-width="280" show-overflow-tooltip>
        <template #default="{ row }">{{ prettyMeta(row.metadata_json) }}</template>
      </el-table-column>
      <el-table-column label="IP" width="140">
        <template #default="{ row }">{{ row.ip || '-' }}</template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.audit-tab {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
.title {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
}
.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.hint {
  font-size: 12px;
  color: #6b7280;
  margin: 0;
}
</style>

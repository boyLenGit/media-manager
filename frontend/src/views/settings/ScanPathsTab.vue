<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Delete, VideoPlay } from '@element-plus/icons-vue'
import { scanApi, type ScanPath, type ScanJob } from '@/api/scan'

const paths = ref<ScanPath[]>([])
const jobs = ref<ScanJob[]>([])
const loadingPaths = ref(false)
const loadingJobs = ref(false)

const dialogVisible = ref(false)
const editing = ref<Partial<ScanPath> | null>(null)
const form = reactive<Partial<ScanPath>>({
  path: '',
  name: '',
  enabled: true,
  recursive: true,
})

let pollTimer: number | null = null

const fetchPaths = async () => {
  loadingPaths.value = true
  try {
    paths.value = await scanApi.listPaths()
  } finally {
    loadingPaths.value = false
  }
}

const fetchJobs = async () => {
  loadingJobs.value = true
  try {
    jobs.value = await scanApi.listJobs(20)
  } finally {
    loadingJobs.value = false
  }
}

const startPolling = () => {
  stopPolling()
  pollTimer = window.setInterval(async () => {
    await fetchJobs()
    if (!jobs.value.some((j) => j.status === 'running' || j.status === 'pending')) {
      stopPolling()
      await fetchPaths() // last_scan_at 可能更新了
    }
  }, 2000)
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

const openCreate = () => {
  editing.value = null
  Object.assign(form, { id: undefined, path: '', name: '', enabled: true, recursive: true })
  dialogVisible.value = true
}

const openEdit = (p: ScanPath) => {
  editing.value = p
  Object.assign(form, p)
  dialogVisible.value = true
}

const save = async () => {
  if (!form.path) {
    ElMessage.warning('请输入路径')
    return
  }
  try {
    if (editing.value?.id) {
      await scanApi.updatePath(editing.value.id, form)
      ElMessage.success('已更新')
    } else {
      await scanApi.createPath(form)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await fetchPaths()
  } catch (e: any) {
    if (e?.response?.data?.detail === 'path_already_exists') {
      ElMessage.error('该路径已存在')
    }
  }
}

const remove = async (p: ScanPath) => {
  await ElMessageBox.confirm(`删除扫描路径「${p.path}」?这不会删除磁盘文件。`, '确认', {
    type: 'warning',
  }).catch(() => null)
  await scanApi.deletePath(p.id)
  ElMessage.success('已删除')
  await fetchPaths()
}

const triggerScan = async (p: ScanPath) => {
  await scanApi.triggerScan(p.id)
  ElMessage.success('扫描已触发,正在执行')
  await fetchJobs()
  startPolling()
}

const jobStatusType = (s: string) => {
  return (
    {
      success: 'success',
      running: 'warning',
      pending: 'info',
      failed: 'danger',
    } as Record<string, any>
  )[s] || 'info'
}

const progressPercent = (j: ScanJob) => {
  if (!j.total_files) return 0
  return Math.round((j.scanned_files / j.total_files) * 100)
}

const formatTime = (s?: string) => (s ? new Date(s).toLocaleString() : '-')

onMounted(async () => {
  await Promise.all([fetchPaths(), fetchJobs()])
  if (jobs.value.some((j) => j.status === 'running')) startPolling()
})
</script>

<template>
  <div class="paths">
    <div class="header">
      <h3 class="section-title">扫描路径</h3>
      <div class="actions">
        <el-button :icon="Refresh" @click="fetchPaths">刷新</el-button>
        <el-button type="primary" :icon="Plus" @click="openCreate">添加路径</el-button>
      </div>
    </div>

    <el-table :data="paths" v-loading="loadingPaths" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="名称" min-width="120">
        <template #default="{ row }">{{ row.name || '-' }}</template>
      </el-table-column>
      <el-table-column prop="path" label="路径" min-width="280" show-overflow-tooltip />
      <el-table-column label="启用" width="80">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'" size="small">
            {{ row.enabled ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="递归" width="80">
        <template #default="{ row }">{{ row.recursive ? '是' : '否' }}</template>
      </el-table-column>
      <el-table-column label="上次扫描" width="180">
        <template #default="{ row }">{{ formatTime(row.last_scan_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" :icon="VideoPlay" @click="triggerScan(row)" :disabled="!row.enabled">
            扫描
          </el-button>
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" :icon="Delete" @click="remove(row)" />
        </template>
      </el-table-column>
    </el-table>

    <h3 class="section-title">扫描任务</h3>
    <el-table :data="jobs" v-loading="loadingJobs" stripe size="small">
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="jobStatusType(row.status)" size="small">{{ row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="进度" width="240">
        <template #default="{ row }">
          <el-progress
            v-if="row.status === 'running'"
            :percentage="progressPercent(row)"
            :format="() => `${row.scanned_files}/${row.total_files}`"
          />
          <span v-else>{{ row.scanned_files }} / {{ row.total_files }}</span>
        </template>
      </el-table-column>
      <el-table-column label="新增" width="80" prop="new_files" />
      <el-table-column label="更新" width="80" prop="updated_files" />
      <el-table-column label="失踪" width="80" prop="missing_files" />
      <el-table-column label="开始时间" width="180">
        <template #default="{ row }">{{ formatTime(row.started_at) }}</template>
      </el-table-column>
      <el-table-column label="结束时间" width="180">
        <template #default="{ row }">{{ formatTime(row.finished_at) }}</template>
      </el-table-column>
      <el-table-column label="错误" min-width="200" show-overflow-tooltip>
        <template #default="{ row }">{{ row.error_message || '-' }}</template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="editing?.id ? '编辑扫描路径' : '添加扫描路径'"
      width="540px"
    >
      <el-form label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="便于辨识的名字,可选" />
        </el-form-item>
        <el-form-item label="路径" required>
          <el-input v-model="form.path" placeholder="/volume1/media" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
        <el-form-item label="递归">
          <el-switch v-model="form.recursive" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.paths {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.section-title {
  margin: 8px 0;
  font-size: 16px;
  font-weight: 500;
}
.actions {
  display: flex;
  gap: 8px;
}
</style>

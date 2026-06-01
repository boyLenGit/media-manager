<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Refresh, Delete, VideoPlay, QuestionFilled } from '@element-plus/icons-vue'
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

// 容器挂载信息(给输入框提示用)
const mountInfo = ref<{
  in_container: boolean
  mounts: Array<{
    path: string
    fs_type: string
    readonly: boolean
    exists: boolean
    is_dir: boolean
  }>
} | null>(null)

// 用户实际能填的挂载(过滤掉只读不存在的等)
const usableMounts = computed(() => {
  if (!mountInfo.value) return []
  return mountInfo.value.mounts.filter((m) => m.exists && m.is_dir)
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

const fetchMounts = async () => {
  try {
    mountInfo.value = await scanApi.listMounts()
  } catch {
    /* 不阻塞主流程 */
  }
}

const startPolling = () => {
  stopPolling()
  pollTimer = window.setInterval(async () => {
    await fetchJobs()
    // 只要还有 running / pending / enriching 都继续轮询
    const stillBusy = jobs.value.some(
      (j) => j.status === 'running' || j.status === 'pending' || j.status === 'enriching',
    )
    if (!stillBusy) {
      stopPolling()
      await fetchPaths()
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

const useMountAsPath = (mountPath: string) => {
  form.path = mountPath
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
      enriching: 'warning',
      pending: 'info',
      failed: 'danger',
    } as Record<string, any>
  )[s] || 'info'
}

const jobStatusLabel = (s: string) => {
  return (
    {
      pending: '排队中',
      running: '扫描中',
      enriching: '后处理中',
      success: '成功',
      failed: '失败',
    } as Record<string, string>
  )[s] || s
}

// 当前阶段进度(扫描 X/Y → 后处理 X/Y)
const phasePercent = (j: ScanJob) => {
  if (j.status === 'enriching') {
    if (!j.enrich_total) return 100
    return Math.round((j.enrich_done / j.enrich_total) * 100)
  }
  if (!j.total_files) return 0
  return Math.round((j.scanned_files / j.total_files) * 100)
}

const phaseLabel = (j: ScanJob) => {
  if (j.status === 'enriching') {
    return `后处理 ${j.enrich_done}/${j.enrich_total}`
  }
  if (j.status === 'running') {
    return `扫描 ${j.scanned_files}/${j.total_files}`
  }
  // 已完成: 同时显示两个阶段的最终数
  if (j.enrich_total > 0) {
    return `${j.scanned_files}/${j.total_files} · 缩略图 ${j.enrich_done}/${j.enrich_total}`
  }
  return `${j.scanned_files}/${j.total_files}`
}

const formatTime = (s?: string) => (s ? new Date(s).toLocaleString() : '-')

onMounted(async () => {
  await Promise.all([fetchPaths(), fetchJobs(), fetchMounts()])
  if (jobs.value.some((j) => j.status === 'running' || j.status === 'enriching')) startPolling()
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
          <el-tag :type="jobStatusType(row.status)" size="small">{{ jobStatusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="进度" min-width="280">
        <template #default="{ row }">
          <el-progress
            v-if="row.status === 'running' || row.status === 'enriching'"
            :percentage="phasePercent(row)"
            :status="row.status === 'enriching' ? 'success' : undefined"
            :format="() => phaseLabel(row)"
          />
          <span v-else>{{ phaseLabel(row) }}</span>
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

    <!-- 添加 / 编辑路径对话框 -->
    <el-dialog
      v-model="dialogVisible"
      :title="editing?.id ? '编辑扫描路径' : '添加扫描路径'"
      width="640px"
    >
      <el-form label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="便于辨识的名字,可选" />
        </el-form-item>

        <el-form-item required>
          <!-- label slot 加问号 popover -->
          <template #label>
            <span class="label-with-help">
              路径
              <el-popover
                placement="right"
                :width="420"
                trigger="hover"
                popper-class="path-help-popper"
              >
                <template #reference>
                  <el-icon class="help-icon"><QuestionFilled /></el-icon>
                </template>

                <div class="help-content">
                  <div class="help-section">
                    <strong>这里要填「容器内路径」,不是 NAS 真实路径。</strong>
                  </div>

                  <div class="help-section">
                    Docker 容器自己有独立文件系统,**只能看到通过 volumes 挂进来的目录**。
                    docker-compose.yml 里这样的配置:
                    <pre class="help-code">volumes:
  - "/volume1/你的视频目录:/media:ro"</pre>
                    意思是:**NAS 的 <code>/volume1/你的视频目录</code>
                    在容器里叫 <code>/media</code>**。这里要填的是右边那个,即 <code>/media</code>。
                  </div>

                  <div class="help-section">
                    <strong>当前容器实际可用的挂载根目录:</strong>
                    <div v-if="!mountInfo" class="help-loading">加载中...</div>
                    <div v-else-if="!mountInfo.in_container" class="help-meta">
                      (本地开发模式,直接填你电脑上的路径即可)
                    </div>
                    <div v-else-if="usableMounts.length === 0" class="help-meta warn">
                      ⚠ 没检测到任何用户挂载。请检查 docker-compose.yml 的 volumes 配置。
                    </div>
                    <ul v-else class="mount-list">
                      <li
                        v-for="m in usableMounts"
                        :key="m.path"
                        class="mount-item"
                        @click="useMountAsPath(m.path)"
                        title="点击填入"
                      >
                        <code>{{ m.path }}</code>
                        <el-tag v-if="m.readonly" size="small" type="info">只读</el-tag>
                        <el-tag v-else size="small" type="success">读写</el-tag>
                        <span class="fs">{{ m.fs_type }}</span>
                      </li>
                    </ul>
                  </div>

                  <div class="help-section help-meta">
                    递归选 ✅ 时,会扫描该目录下所有子目录里的视频。
                  </div>
                </div>
              </el-popover>
            </span>
          </template>
          <el-input v-model="form.path" placeholder="/media 或 /media/movies" />
          <!-- 候选 chips,点了直接填 -->
          <div v-if="usableMounts.length > 0" class="quick-pick">
            <span class="quick-pick-label">快速填入:</span>
            <el-tag
              v-for="m in usableMounts"
              :key="m.path"
              :type="m.readonly ? 'info' : 'success'"
              effect="plain"
              class="quick-pick-tag"
              @click="useMountAsPath(m.path)"
            >
              {{ m.path }}
            </el-tag>
          </div>
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
  flex-wrap: wrap;
  gap: 8px;
}
.section-title {
  margin: 8px 0;
  font-size: 16px;
  font-weight: 500;
}
.actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* 表格在小屏内置水平滚动,避免列被挤爆 */
@media (max-width: 768px) {
  .paths :deep(.el-table) {
    font-size: 12px;
  }
}

.label-with-help {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}
.help-icon {
  color: #909399;
  cursor: help;
  font-size: 16px;
}
.help-icon:hover {
  color: #409eff;
}

.quick-pick {
  margin-top: 6px;
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
}
.quick-pick-label {
  font-size: 12px;
  color: #909399;
}
.quick-pick-tag {
  cursor: pointer;
}
.quick-pick-tag:hover {
  opacity: 0.8;
}
</style>

<style>
/* 全局样式: popover 内容(scoped 不能穿透 popper) */
.path-help-popper .help-content {
  font-size: 13px;
  line-height: 1.7;
}
.path-help-popper .help-section {
  margin-bottom: 12px;
}
.path-help-popper .help-section:last-child {
  margin-bottom: 0;
}
.path-help-popper code {
  background: #f3f4f6;
  padding: 1px 6px;
  border-radius: 3px;
  font-family: 'SF Mono', Monaco, Consolas, monospace;
  font-size: 12px;
}
.path-help-popper .help-code {
  background: #1f2937;
  color: #f9fafb;
  padding: 8px 12px;
  border-radius: 4px;
  font-size: 12px;
  margin: 6px 0;
  overflow-x: auto;
  white-space: pre;
}
.path-help-popper .help-meta {
  color: #6b7280;
  font-size: 12px;
}
.path-help-popper .help-meta.warn {
  color: #d97706;
}
.path-help-popper .help-loading {
  color: #9ca3af;
  font-size: 12px;
  font-style: italic;
}
.path-help-popper .mount-list {
  list-style: none;
  padding: 0;
  margin: 6px 0 0;
  max-height: 180px;
  overflow-y: auto;
}
.path-help-popper .mount-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  border-radius: 4px;
  cursor: pointer;
  margin-bottom: 2px;
}
.path-help-popper .mount-item:hover {
  background: #eff6ff;
}
.path-help-popper .mount-item .fs {
  margin-left: auto;
  font-size: 11px;
  color: #9ca3af;
}
</style>

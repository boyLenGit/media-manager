<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Warning, Delete } from '@element-plus/icons-vue'
import { settingsApi } from '@/api/settings'
import { useAuthStore } from '@/store/auth'
import { useRouter } from 'vue-router'

const auth = useAuthStore()
const router = useRouter()

const purgeThumbnails = ref(true)
const confirmText = ref('')
const loading = ref(false)

const isAdmin = auth.user?.role === 'admin'

const doReset = async () => {
  if (confirmText.value !== 'ERASE_ALL') {
    ElMessage.warning('请输入确认文本 ERASE_ALL')
    return
  }
  try {
    await ElMessageBox.confirm(
      '这将清空所有视频资源、扫描历史、标签、作者、用户(除当前管理员)、播放历史等数据。\n\n' +
        '磁盘上的真实视频文件不会被删除。\n\n' +
        '确定继续吗?',
      '最终确认',
      {
        type: 'error',
        confirmButtonText: '确认清空',
        cancelButtonText: '取消',
      },
    )
  } catch {
    return
  }

  loading.value = true
  try {
    const r = await settingsApi.resetAll(purgeThumbnails.value)
    ElMessageBox.alert(
      `${r.note}\n\n已清理表 (${r.cleared_tables.length} 个):\n` +
        r.cleared_tables.join(', ') +
        (r.thumbnails_purged ? '\n\n缩略图文件已清理' : ''),
      '清空完成',
      { type: 'success', confirmButtonText: '回到首页' },
    ).finally(() => {
      confirmText.value = ''
      // 刷整页,避免缓存的列表/计数继续显示
      window.location.href = '/'
    })
  } catch (e: any) {
    if (e?.response?.status === 403) {
      ElMessage.error('仅管理员可执行')
    } else {
      ElMessage.error(`失败: ${e?.response?.data?.detail || e?.message}`)
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="danger-zone">
    <el-alert type="error" :closable="false" show-icon class="mb-16">
      <template #title>
        <strong>危险区</strong> · 这里的操作不可逆,请谨慎使用
      </template>
    </el-alert>

    <el-card class="danger-card">
      <template #header>
        <div class="card-title">
          <el-icon class="warn-icon"><Warning /></el-icon>
          <strong>清空所有数据</strong>
        </div>
      </template>

      <div class="desc">
        <p>
          清空除你(当前管理员)之外的所有数据,包括:
        </p>
        <ul>
          <li>所有视频资源、扫描记录、文件索引</li>
          <li>所有标签、作者、资源类型</li>
          <li>其他所有用户账号(及其会话)</li>
          <li>所有播放历史、下载任务、播放目标配置</li>
          <li>所有 SMB / Jellyfin / 解析器等应用配置</li>
          <li v-if="purgeThumbnails">所有缩略图文件</li>
        </ul>
        <p class="reassure">
          <strong>不会动磁盘上的真实视频文件</strong>,所以你随时可以重新进入「扫描路径」重扫一次。
        </p>
      </div>

      <el-divider />

      <el-form label-width="120px" v-if="isAdmin">
        <el-form-item label="同时清理缩略图">
          <el-switch v-model="purgeThumbnails" />
          <span class="muted">
            建议保持开启 — 不清理的话旧缩略图会作为孤儿文件残留在磁盘上
          </span>
        </el-form-item>

        <el-form-item label="输入确认">
          <el-input
            v-model="confirmText"
            placeholder="为防误操作,请输入: ERASE_ALL"
            class="confirm-input"
          />
        </el-form-item>

        <el-form-item label-width="0">
          <el-button
            type="danger"
            :icon="Delete"
            :loading="loading"
            :disabled="confirmText !== 'ERASE_ALL'"
            @click="doReset"
          >
            清空所有数据
          </el-button>
        </el-form-item>
      </el-form>

      <el-empty v-else description="此操作仅管理员可执行" />
    </el-card>
  </div>
</template>

<style scoped>
.danger-zone {
  max-width: 720px;
}
.mb-16 {
  margin-bottom: 16px;
}
.danger-card {
  border: 1px solid #fecaca;
}
.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
}
.warn-icon {
  color: #dc2626;
}
.desc {
  font-size: 13px;
  color: #4b5563;
  line-height: 1.7;
}
.desc ul {
  margin: 8px 0;
  padding-left: 20px;
}
.reassure {
  background: #fef3c7;
  border-left: 3px solid #f59e0b;
  padding: 8px 12px;
  margin: 12px 0;
  border-radius: 4px;
  color: #78350f;
}
.muted {
  color: #9ca3af;
  font-size: 12px;
  margin-left: 12px;
}
.confirm-input {
  max-width: 320px;
}
</style>

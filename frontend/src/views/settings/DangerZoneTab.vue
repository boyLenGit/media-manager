<script setup lang="ts">
import { reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Warning, Delete, Lock } from '@element-plus/icons-vue'
import { settingsApi } from '@/api/settings'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()
const isAdmin = auth.user?.role === 'admin'

const dialogVisible = ref(false)
const submitting = ref(false)
const resultVisible = ref(false)
const resultText = ref('')

const form = reactive({
  password: '',
  purgeThumbnails: true,
})

const openDialog = () => {
  form.password = ''
  form.purgeThumbnails = true
  dialogVisible.value = true
}

const submit = async () => {
  if (!form.password) {
    ElMessage.warning('请输入管理员密码')
    return
  }
  submitting.value = true
  try {
    const r = await settingsApi.resetAll(form.password, form.purgeThumbnails)
    dialogVisible.value = false
    resultText.value =
      `${r.note}\n\n清理表 (${r.cleared_tables.length}):\n` +
      r.cleared_tables.join(', ') +
      (r.thumbnails_purged ? '\n\n缩略图文件已清理' : '')
    resultVisible.value = true
  } catch (e: any) {
    if (e?.response?.status === 403) {
      const detail = e?.response?.data?.detail
      if (detail === 'password_incorrect') {
        ElMessage.error('密码错误')
      } else if (detail === 'admin_required') {
        ElMessage.error('仅管理员可执行')
      } else {
        ElMessage.error(`权限不足:${detail || ''}`)
      }
    } else {
      ElMessage.error(`失败:${e?.response?.data?.detail || e?.message || '未知错误'}`)
    }
  } finally {
    submitting.value = false
  }
}

const onResultClose = () => {
  resultVisible.value = false
  // 重新进入,清前端缓存
  window.location.href = '/'
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
          <strong>抹掉所有内容</strong>
        </div>
      </template>

      <div class="desc">
        <p>抹掉除你(当前管理员)之外的所有数据,包括:</p>
        <ul>
          <li>所有视频资源、扫描记录、文件索引</li>
          <li>所有标签、作者、资源类型</li>
          <li>其他所有用户账号(及其会话)</li>
          <li>所有播放历史、下载任务、播放目标配置</li>
          <li>所有 SMB / Jellyfin / 解析器等应用配置</li>
          <li>所有缩略图文件(可选)</li>
        </ul>
        <p class="reassure">
          <strong>不会动磁盘上的真实视频文件</strong>。你随时可以重新进入「扫描路径」重扫一次。
        </p>
      </div>

      <el-divider />

      <div v-if="isAdmin" class="action-row">
        <el-button
          type="danger"
          size="large"
          :icon="Delete"
          @click="openDialog"
        >
          抹掉所有内容
        </el-button>
        <span class="muted">点击后需输入管理员密码二次确认</span>
      </div>

      <el-empty v-else description="此操作仅管理员可执行" />
    </el-card>

    <!-- 二次确认弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      title="二次确认 · 抹掉所有内容"
      width="480px"
      :close-on-click-modal="false"
      :close-on-press-escape="!submitting"
    >
      <el-alert type="error" :closable="false" show-icon class="mb-16">
        <template #title>此操作不可逆。请输入你的管理员密码以确认。</template>
      </el-alert>

      <el-form label-width="100px" @submit.prevent="submit">
        <el-form-item label="管理员账号">
          <span class="user-display">{{ auth.user?.username }}</span>
        </el-form-item>
        <el-form-item label="登录密码" required>
          <el-input
            v-model="form.password"
            type="password"
            show-password
            autocomplete="current-password"
            :prefix-icon="Lock"
            placeholder="输入你的登录密码"
            @keyup.enter="submit"
          />
        </el-form-item>
        <el-form-item label="清理缩略图">
          <el-switch v-model="form.purgeThumbnails" />
          <span class="muted small">
            建议保持开启,否则旧缩略图会作为孤儿文件残留
          </span>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogVisible = false" :disabled="submitting">取消</el-button>
        <el-button
          type="danger"
          :icon="Delete"
          :loading="submitting"
          :disabled="!form.password"
          @click="submit"
        >
          确认抹掉
        </el-button>
      </template>
    </el-dialog>

    <!-- 结果弹窗 -->
    <el-dialog
      v-model="resultVisible"
      title="抹掉完成"
      width="520px"
      :close-on-click-modal="false"
      :show-close="false"
    >
      <pre class="result-text">{{ resultText }}</pre>
      <template #footer>
        <el-button type="primary" @click="onResultClose">回到首页</el-button>
      </template>
    </el-dialog>
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
.action-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.muted {
  color: #9ca3af;
  font-size: 12px;
}
.muted.small {
  margin-left: 12px;
}
.user-display {
  font-weight: 500;
  color: #1f2937;
}
.result-text {
  font-family: inherit;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 13px;
  line-height: 1.7;
  color: #374151;
  margin: 0;
}
</style>

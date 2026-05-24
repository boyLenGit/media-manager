<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { playbackApi, type PlaybackTarget } from '@/api/playback'

const targets = ref<PlaybackTarget[]>([])
const loading = ref(false)

const fetch = async () => {
  loading.value = true
  try {
    targets.value = await playbackApi.listTargets()
  } finally {
    loading.value = false
  }
}

const toggleEnabled = async (t: PlaybackTarget) => {
  try {
    const updated = await playbackApi.updateTarget(t.id, { enabled: t.enabled })
    Object.assign(t, updated)
    ElMessage.success(`已${updated.enabled ? '启用' : '禁用'}「${updated.name}」`)
  } catch {
    t.enabled = !t.enabled
  }
}

const updateOrder = async (t: PlaybackTarget) => {
  try {
    await playbackApi.updateTarget(t.id, { sort_order: t.sort_order })
    ElMessage.success('排序已保存')
  } catch {
    /* error toasted */
  }
}

const targetTypeLabel = (type: string) => {
  return (
    {
      web: '浏览器播放',
      jellyfin: 'Jellyfin 跳转',
      external_url: '复制带签名链接',
      smb_path: 'SMB 路径',
      reveal_dir: '复制目录',
      custom_protocol: '自定义协议',
    } as Record<string, string>
  )[type] || type
}

const targetHint = (type: string) => {
  return (
    {
      web: 'mp4 / webm / m4v 文件可用,需要后端支持 HTTP Range',
      jellyfin: '需在「Jellyfin」设置中配置服务地址',
      external_url: '复制带 1 小时签名的播放链接,可贴到 IINA / VLC',
      smb_path: '需在「SMB 配置」中设置 NAS 主机和共享映射',
      reveal_dir: '复制视频文件所在目录,方便手动打开',
      custom_protocol: '需要本地安装协议助手程序(MVP 不支持)',
    } as Record<string, string>
  )[type] || ''
}

onMounted(fetch)
</script>

<template>
  <div class="targets">
    <div class="header">
      <h3 class="section-title">播放目标</h3>
      <el-button :icon="Refresh" @click="fetch">刷新</el-button>
    </div>

    <el-alert
      type="info"
      :closable="false"
      title="播放目标控制了「播放」按钮下拉菜单中显示哪些选项,以及它们的顺序。"
      style="margin-bottom: 12px"
    />

    <el-table :data="targets" v-loading="loading" stripe>
      <el-table-column label="启用" width="80">
        <template #default="{ row }">
          <el-switch v-model="row.enabled" @change="toggleEnabled(row)" />
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" width="180" />
      <el-table-column label="类型" width="200">
        <template #default="{ row }">
          {{ targetTypeLabel(row.target_type) }}
        </template>
      </el-table-column>
      <el-table-column label="排序" width="120">
        <template #default="{ row }">
          <el-input-number
            v-model="row.sort_order"
            size="small"
            :min="0"
            :max="999"
            @change="updateOrder(row)"
          />
        </template>
      </el-table-column>
      <el-table-column label="说明" min-width="280">
        <template #default="{ row }">
          <span class="hint">{{ targetHint(row.target_type) }}</span>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<style scoped>
.targets {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.section-title {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
}
.hint {
  font-size: 13px;
  color: #6b7280;
}
</style>

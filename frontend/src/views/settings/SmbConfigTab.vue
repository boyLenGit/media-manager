<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import { settingsApi } from '@/api/settings'

interface ShareEntry {
  local: string
  share: string
}

const smbHost = ref('')
const shares = ref<ShareEntry[]>([])
const loading = ref(false)

const fetch = async () => {
  loading.value = true
  try {
    const all = await settingsApi.list()
    smbHost.value = all.find((s) => s.key === 'smb_host')?.value || ''
    const mapStr = all.find((s) => s.key === 'smb_share_map')?.value || '{}'
    try {
      const m = JSON.parse(mapStr) as Record<string, string>
      shares.value = Object.entries(m).map(([local, share]) => ({ local, share }))
    } catch {
      shares.value = []
    }
  } finally {
    loading.value = false
  }
}

const addRow = () => {
  shares.value.push({ local: '', share: '' })
}

const removeRow = (i: number) => {
  shares.value.splice(i, 1)
}

const save = async () => {
  // 校验
  const map: Record<string, string> = {}
  for (const s of shares.value) {
    if (!s.local || !s.share) {
      ElMessage.warning('每行的本地路径和共享名都不能为空')
      return
    }
    map[s.local] = s.share
  }
  try {
    await settingsApi.upsert('smb_host', smbHost.value)
    await settingsApi.upsert('smb_share_map', JSON.stringify(map), 'json')
    ElMessage.success('SMB 配置已保存')
  } catch {
    /* error toasted */
  }
}

onMounted(fetch)
</script>

<template>
  <div class="smb">
    <div class="header">
      <h3 class="section-title">SMB 主机映射</h3>
    </div>

    <el-alert
      type="info"
      :closable="false"
      style="margin-bottom: 12px"
      title="配置后,资源详情页的「复制 SMB 路径」选项才会出现。"
    >
      <template #default>
        <div>
          示例:NAS 主机为 <code>nas.local</code>,将本地路径
          <code>/volume1/media</code> 映射为共享名 <code>media</code>,则会生成
          <code>smb://nas.local/media/movie.mp4</code> 这样的链接。
        </div>
      </template>
    </el-alert>

    <el-form v-loading="loading" label-width="120px">
      <el-form-item label="NAS 主机">
        <el-input
          v-model="smbHost"
          placeholder="例如 nas.local 或 192.168.1.100"
          style="max-width: 400px"
        />
      </el-form-item>

      <el-form-item label="路径映射">
        <div class="shares">
          <div v-for="(s, i) in shares" :key="i" class="row">
            <el-input v-model="s.local" placeholder="本地路径,如 /volume1/media" style="flex: 2" />
            <span class="arrow">→</span>
            <el-input v-model="s.share" placeholder="共享名,如 media" style="flex: 1" />
            <el-button :icon="Delete" type="danger" @click="removeRow(i)" />
          </div>
          <el-button :icon="Plus" plain @click="addRow">添加映射</el-button>
        </div>
      </el-form-item>

      <el-form-item>
        <el-button type="primary" @click="save">保存</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<style scoped>
.smb {
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
.shares {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-width: 720px;
}
.row {
  display: flex;
  gap: 8px;
  align-items: center;
}
.arrow {
  color: #6b7280;
}
code {
  background: #f3f4f6;
  padding: 0 4px;
  border-radius: 3px;
}
</style>

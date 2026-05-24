<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'
import { jellyfinApi } from '@/api/jellyfin'

const loading = ref(false)
const testing = ref(false)
const form = reactive({
  url: '',
  api_key: '',
  api_key_set: false,
})

const libraries = ref<{ id: string; name: string; type?: string; paths: string[] }[]>([])
const serverInfo = ref<{ version?: string; server_name?: string } | null>(null)

const fetch = async () => {
  loading.value = true
  try {
    const cfg = await jellyfinApi.getConfig()
    form.url = cfg.url
    form.api_key_set = cfg.api_key_set
    form.api_key = ''
    if (cfg.configured) {
      await loadServerInfo()
      await loadLibraries()
    }
  } finally {
    loading.value = false
  }
}

const loadServerInfo = async () => {
  try {
    const r = await jellyfinApi.test()
    if (r.ok) {
      serverInfo.value = { version: r.version, server_name: r.server_name }
    }
  } catch {
    /* ignore */
  }
}

const loadLibraries = async () => {
  try {
    libraries.value = await jellyfinApi.listLibraries()
  } catch {
    libraries.value = []
  }
}

const save = async () => {
  if (!form.url) {
    ElMessage.warning('请输入 Jellyfin 地址')
    return
  }
  try {
    await jellyfinApi.updateConfig({
      url: form.url,
      api_key: form.api_key || undefined,
    })
    ElMessage.success('已保存')
    await fetch()
  } catch {
    /* error toasted */
  }
}

const test = async () => {
  testing.value = true
  try {
    const r = await jellyfinApi.test()
    if (r.ok) {
      ElMessage.success(`连接成功:${r.server_name} (${r.version})`)
      serverInfo.value = { version: r.version, server_name: r.server_name }
      await loadLibraries()
    } else {
      ElMessage.error(`失败:${r.error}`)
    }
  } finally {
    testing.value = false
  }
}

onMounted(fetch)
</script>

<template>
  <div class="jellyfin-cfg" v-loading="loading">
    <div class="header">
      <h3 class="section-title">Jellyfin 集成</h3>
      <el-button :icon="Refresh" @click="fetch">刷新</el-button>
    </div>

    <el-alert
      type="info"
      :closable="false"
      style="margin-bottom: 16px"
      title="配置后,资源详情页的「Jellyfin 播放」会跳转到 Jellyfin 搜索页。"
    >
      <template #default>
        <div>
          1) 在 Jellyfin Web 控制面板 → 仪表板 → 高级 → API 密钥,生成一个 API Key<br>
          2) 把 URL 和 API Key 填入下方<br>
          3) 在「设置 → 播放目标」中启用「Jellyfin 播放」
        </div>
      </template>
    </el-alert>

    <el-form label-width="120px" style="max-width: 600px">
      <el-form-item label="服务地址" required>
        <el-input v-model="form.url" placeholder="http://nas.local:8096" />
      </el-form-item>
      <el-form-item label="API Key">
        <el-input
          v-model="form.api_key"
          type="password"
          show-password
          autocomplete="off"
          :placeholder="form.api_key_set ? '已设置(留空表示不修改)' : '在 Jellyfin 仪表板生成'"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="save">保存</el-button>
        <el-button :loading="testing" @click="test">连通性测试</el-button>
      </el-form-item>
    </el-form>

    <el-card v-if="serverInfo" class="mt-16" header="服务器信息">
      <el-descriptions :column="2" border>
        <el-descriptions-item label="服务器名">{{ serverInfo.server_name }}</el-descriptions-item>
        <el-descriptions-item label="版本">{{ serverInfo.version }}</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-card v-if="libraries.length > 0" class="mt-16" header="媒体库">
      <el-table :data="libraries" stripe size="small">
        <el-table-column prop="name" label="名称" min-width="160" />
        <el-table-column prop="type" label="类型" width="120" />
        <el-table-column label="路径" min-width="320">
          <template #default="{ row }">
            <div v-for="p in row.paths" :key="p" class="path">{{ p }}</div>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<style scoped>
.jellyfin-cfg {
  display: flex;
  flex-direction: column;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.section-title {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
}
.mt-16 {
  margin-top: 16px;
}
.path {
  font-family: monospace;
  font-size: 12px;
  color: #6b7280;
}
</style>

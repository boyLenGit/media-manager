<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { downloadsApi } from '@/api/downloads'

const loading = ref(false)
const testing = ref(false)
const form = reactive({
  provider: 'qbittorrent',
  url: '',
  username: '',
  password: '',
  password_set: false,
})

const fetch = async () => {
  loading.value = true
  try {
    const cfg = await downloadsApi.getConfig()
    form.provider = cfg.provider
    form.url = cfg.url
    form.username = cfg.username
    form.password_set = cfg.password_set
    form.password = ''
  } finally {
    loading.value = false
  }
}

const save = async () => {
  if (!form.url || !form.username) {
    ElMessage.warning('URL 和用户名必填')
    return
  }
  try {
    await downloadsApi.updateConfig({
      provider: form.provider,
      url: form.url,
      username: form.username,
      password: form.password || undefined,
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
    const r = await downloadsApi.testConnection()
    if (r.ok) {
      ElMessage.success(`连接成功:${r.provider} @ ${r.url}`)
    } else {
      ElMessage.error(`连接失败:${r.error || '未知错误'}`)
    }
  } finally {
    testing.value = false
  }
}

onMounted(fetch)
</script>

<template>
  <div class="downloader-cfg" v-loading="loading">
    <div class="header">
      <h3 class="section-title">下载器配置</h3>
    </div>

    <el-alert
      type="info"
      :closable="false"
      style="margin-bottom: 16px"
      title="第一阶段仅支持 qBittorrent。需要先在 qB 中开启 WebUI(默认端口 8080)。"
    />

    <el-form label-width="120px" style="max-width: 600px">
      <el-form-item label="下载器类型">
        <el-radio-group v-model="form.provider">
          <el-radio value="qbittorrent">qBittorrent</el-radio>
          <el-radio value="transmission" disabled>Transmission(待支持)</el-radio>
        </el-radio-group>
      </el-form-item>
      <el-form-item label="WebUI 地址" required>
        <el-input v-model="form.url" placeholder="http://nas.local:8080" />
      </el-form-item>
      <el-form-item label="用户名" required>
        <el-input v-model="form.username" autocomplete="off" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input
          v-model="form.password"
          type="password"
          show-password
          autocomplete="new-password"
          :placeholder="form.password_set ? '已设置(留空表示不修改)' : '请输入密码'"
        />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="save">保存</el-button>
        <el-button :loading="testing" @click="test">连通性测试</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<style scoped>
.downloader-cfg {
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
</style>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import { searchApi, type ResourceSource } from '@/api/search'

const list = ref<ResourceSource[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editing = ref<ResourceSource | null>(null)
const form = reactive({
  name: '',
  source_type: 'torznab',
  base_url: '',
  enabled: true,
  api_key: '',
  category: '',
  remark: '',
})

const fetch = async () => {
  loading.value = true
  try {
    list.value = await searchApi.listSources()
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  editing.value = null
  Object.assign(form, {
    name: '',
    source_type: 'torznab',
    base_url: '',
    enabled: true,
    api_key: '',
    category: '',
    remark: '',
  })
  dialogVisible.value = true
}

const openEdit = (s: ResourceSource) => {
  editing.value = s
  let auth: any = {}
  try {
    auth = s.auth_config ? JSON.parse(s.auth_config) : {}
  } catch {
    /* ignore */
  }
  Object.assign(form, {
    name: s.name,
    source_type: s.source_type,
    base_url: s.base_url || '',
    enabled: s.enabled,
    api_key: auth.api_key || '',
    category: auth.category || '',
    remark: s.remark || '',
  })
  dialogVisible.value = true
}

const save = async () => {
  if (!form.name || !form.base_url) {
    ElMessage.warning('名称和地址必填')
    return
  }
  const auth: any = {}
  if (form.api_key) auth.api_key = form.api_key
  if (form.category) auth.category = form.category
  const payload = {
    name: form.name,
    source_type: form.source_type,
    base_url: form.base_url,
    enabled: form.enabled,
    auth_config: Object.keys(auth).length ? JSON.stringify(auth) : undefined,
    remark: form.remark || undefined,
  }
  try {
    if (editing.value) {
      await searchApi.updateSource(editing.value.id, payload)
      ElMessage.success('已更新')
    } else {
      await searchApi.createSource(payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await fetch()
  } catch {
    /* error toasted */
  }
}

const remove = async (s: ResourceSource) => {
  await ElMessageBox.confirm(`删除搜索源「${s.name}」?`, '确认', {
    type: 'warning',
  }).catch(() => null)
  await searchApi.removeSource(s.id)
  ElMessage.success('已删除')
  await fetch()
}

const test = async (s: ResourceSource) => {
  try {
    const r = await searchApi.testSource(s.id)
    if (r.ok) ElMessage.success(`「${s.name}」连接正常`)
    else ElMessage.error(`「${s.name}」失败:${r.error || '未知错误'}`)
  } catch {
    /* error toasted */
  }
}

const toggleEnabled = async (s: ResourceSource) => {
  // 后端 PATCH 需要传完整 payload,这里手动重新组装
  let auth: any = {}
  try {
    auth = s.auth_config ? JSON.parse(s.auth_config) : {}
  } catch {
    /* ignore */
  }
  await searchApi.updateSource(s.id, {
    name: s.name,
    source_type: s.source_type,
    base_url: s.base_url,
    enabled: s.enabled,
    auth_config: Object.keys(auth).length ? JSON.stringify(auth) : undefined,
    remark: s.remark,
  })
}

onMounted(fetch)
</script>

<template>
  <div class="sources">
    <div class="header">
      <h3 class="section-title">搜索源</h3>
      <el-button type="primary" :icon="Plus" @click="openCreate">添加搜索源</el-button>
    </div>

    <el-alert
      type="warning"
      :closable="false"
      style="margin-bottom: 12px"
      title="Media Manager 不内置任何搜索源,请自行配置 Jackett / Prowlarr 等服务,并确保你下载的资源拥有合法授权。"
    />

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column label="启用" width="80">
        <template #default="{ row }">
          <el-switch v-model="row.enabled" @change="toggleEnabled(row)" />
        </template>
      </el-table-column>
      <el-table-column prop="name" label="名称" min-width="160" />
      <el-table-column prop="source_type" label="类型" width="120" />
      <el-table-column prop="base_url" label="地址" min-width="280" show-overflow-tooltip />
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="test(row)">测试</el-button>
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" :icon="Delete" @click="remove(row)" />
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑搜索源' : '添加搜索源'"
      width="600px"
    >
      <el-form label-width="120px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="如 Jackett-合集" />
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="form.source_type" style="width: 100%">
            <el-option label="Torznab (Jackett/Prowlarr)" value="torznab" />
            <el-option label="RSS" value="rss" disabled />
            <el-option label="Manual" value="manual" disabled />
          </el-select>
        </el-form-item>
        <el-form-item label="API 地址" required>
          <el-input
            v-model="form.base_url"
            placeholder="http://nas.local:9117/api/v2.0/indexers/all/results/torznab/api"
          />
        </el-form-item>
        <el-form-item label="API Key">
          <el-input v-model="form.api_key" type="password" show-password placeholder="可选" />
        </el-form-item>
        <el-form-item label="默认分类">
          <el-input v-model="form.category" placeholder="如 2000(电影)/ 5000(剧集),可选" />
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" />
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
.sources {
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
</style>

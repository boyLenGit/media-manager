<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import { mediaTypesApi, type MediaType } from '@/api/mediaTypes'

const list = ref<MediaType[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editing = ref<MediaType | null>(null)
const form = reactive({ name: '', description: '' })

const fetch = async () => {
  loading.value = true
  try {
    list.value = await mediaTypesApi.list()
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  editing.value = null
  Object.assign(form, { name: '', description: '' })
  dialogVisible.value = true
}

const openEdit = (t: MediaType) => {
  editing.value = t
  Object.assign(form, { name: t.name, description: t.description || '' })
  dialogVisible.value = true
}

const save = async () => {
  if (!form.name) {
    ElMessage.warning('请输入类型名')
    return
  }
  try {
    if (editing.value) {
      await mediaTypesApi.update(editing.value.id, form)
      ElMessage.success('已更新')
    } else {
      await mediaTypesApi.create(form)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await fetch()
  } catch (e: any) {
    if (e?.response?.data?.detail === 'type_name_taken') ElMessage.error('类型名已存在')
  }
}

const remove = async (t: MediaType) => {
  await ElMessageBox.confirm(
    `删除类型「${t.name}」?关联的 ${t.media_count} 个资源会解除关联。`,
    '确认',
    { type: 'warning' },
  ).catch(() => null)
  await mediaTypesApi.remove(t.id)
  ElMessage.success('已删除')
  await fetch()
}

onMounted(fetch)
</script>

<template>
  <div class="types">
    <div class="header">
      <h3 class="section-title">资源类型</h3>
      <el-button type="primary" :icon="Plus" @click="openCreate">添加类型</el-button>
    </div>

    <el-alert
      type="info"
      :closable="false"
      title="系统已内置常用类型,你可以新增、修改或删除。删除时关联资源不受影响。"
      style="margin-bottom: 12px"
    />

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="名称" min-width="180" />
      <el-table-column prop="description" label="描述" min-width="240" show-overflow-tooltip>
        <template #default="{ row }">{{ row.description || '-' }}</template>
      </el-table-column>
      <el-table-column label="资源数" width="100">
        <template #default="{ row }">{{ row.media_count }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="openEdit(row)">编辑</el-button>
          <el-button size="small" type="danger" :icon="Delete" @click="remove(row)" />
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑类型' : '添加类型'"
      width="500px"
    >
      <el-form label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" placeholder="如 movie / series / anime" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="form.description" />
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
.types {
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

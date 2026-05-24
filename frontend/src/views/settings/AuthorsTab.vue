<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import { authorsApi, type Author } from '@/api/authors'

const list = ref<Author[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editing = ref<Author | null>(null)
const form = reactive({ name: '', alias: '', description: '' })

const fetch = async () => {
  loading.value = true
  try {
    list.value = await authorsApi.list()
  } finally {
    loading.value = false
  }
}

const openCreate = () => {
  editing.value = null
  Object.assign(form, { name: '', alias: '', description: '' })
  dialogVisible.value = true
}

const openEdit = (a: Author) => {
  editing.value = a
  Object.assign(form, {
    name: a.name,
    alias: a.alias || '',
    description: a.description || '',
  })
  dialogVisible.value = true
}

const save = async () => {
  if (!form.name) {
    ElMessage.warning('请输入作者名')
    return
  }
  try {
    if (editing.value) {
      await authorsApi.update(editing.value.id, form)
      ElMessage.success('已更新')
    } else {
      await authorsApi.create(form)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await fetch()
  } catch (e: any) {
    if (e?.response?.data?.detail === 'author_name_taken') ElMessage.error('作者名已存在')
  }
}

const remove = async (a: Author) => {
  await ElMessageBox.confirm(
    `删除作者「${a.name}」?该作者关联的 ${a.media_count} 个资源会解除关联但不会被删除。`,
    '确认',
    { type: 'warning' },
  ).catch(() => null)
  await authorsApi.remove(a.id)
  ElMessage.success('已删除')
  await fetch()
}

onMounted(fetch)
</script>

<template>
  <div class="authors">
    <div class="header">
      <h3 class="section-title">作者管理</h3>
      <el-button type="primary" :icon="Plus" @click="openCreate">添加作者</el-button>
    </div>

    <el-table :data="list" v-loading="loading" stripe>
      <el-table-column prop="id" label="ID" width="60" />
      <el-table-column prop="name" label="姓名" min-width="160" />
      <el-table-column prop="alias" label="别名" min-width="160">
        <template #default="{ row }">{{ row.alias || '-' }}</template>
      </el-table-column>
      <el-table-column prop="description" label="备注" min-width="200" show-overflow-tooltip>
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
      :title="editing ? '编辑作者' : '添加作者'"
      width="500px"
    >
      <el-form label-width="80px">
        <el-form-item label="姓名" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="别名">
          <el-input
            v-model="form.alias"
            placeholder="多个别名用逗号分隔"
          />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.description" type="textarea" :rows="3" />
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
.authors {
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

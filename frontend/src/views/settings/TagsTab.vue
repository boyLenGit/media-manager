<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import { tagsApi, type Tag } from '@/api/tags'

const list = ref<Tag[]>([])
const loading = ref(false)
const dialogVisible = ref(false)
const editing = ref<Tag | null>(null)
const form = reactive({ name: '', group_name: '', color: '#6b7280' })

// 按分组聚合
const groups = computed(() => {
  const m: Record<string, Tag[]> = {}
  for (const t of list.value) {
    const g = t.group_name || '(未分组)'
    ;(m[g] ||= []).push(t)
  }
  return m
})

const fetch = async () => {
  loading.value = true
  try {
    list.value = await tagsApi.list()
  } finally {
    loading.value = false
  }
}

const openCreate = (groupName?: string) => {
  editing.value = null
  Object.assign(form, { name: '', group_name: groupName || '', color: '#6b7280' })
  dialogVisible.value = true
}

const openEdit = (t: Tag) => {
  editing.value = t
  Object.assign(form, {
    name: t.name,
    group_name: t.group_name || '',
    color: t.color || '#6b7280',
  })
  dialogVisible.value = true
}

const save = async () => {
  if (!form.name) {
    ElMessage.warning('请输入标签名')
    return
  }
  try {
    const payload = {
      name: form.name,
      group_name: form.group_name || undefined,
      color: form.color,
    }
    if (editing.value) {
      await tagsApi.update(editing.value.id, payload)
      ElMessage.success('已更新')
    } else {
      await tagsApi.create(payload)
      ElMessage.success('已创建')
    }
    dialogVisible.value = false
    await fetch()
  } catch (e: any) {
    if (e?.response?.data?.detail === 'tag_already_exists') ElMessage.error('标签已存在')
  }
}

const remove = async (t: Tag) => {
  await ElMessageBox.confirm(
    `删除标签「${t.name}」?会同时移除 ${t.media_count} 个资源的此标签关联。`,
    '确认',
    { type: 'warning' },
  ).catch(() => null)
  await tagsApi.remove(t.id)
  ElMessage.success('已删除')
  await fetch()
}

onMounted(fetch)
</script>

<template>
  <div class="tags">
    <div class="header">
      <h3 class="section-title">标签管理</h3>
      <el-button type="primary" :icon="Plus" @click="openCreate()">添加标签</el-button>
    </div>

    <div v-loading="loading" class="groups">
      <div v-for="(items, g) in groups" :key="g" class="group">
        <div class="group-header">
          <span class="group-name">{{ g }}</span>
          <el-button text size="small" :icon="Plus" @click="openCreate(g === '(未分组)' ? '' : g)">
            添加到此分组
          </el-button>
        </div>
        <div class="tag-list">
          <el-tag
            v-for="t in items"
            :key="t.id"
            :color="t.color"
            effect="dark"
            closable
            class="tag-item"
            @click="openEdit(t)"
            @close="remove(t)"
          >
            {{ t.name }} ({{ t.media_count }})
          </el-tag>
        </div>
      </div>
    </div>

    <el-dialog
      v-model="dialogVisible"
      :title="editing ? '编辑标签' : '添加标签'"
      width="500px"
    >
      <el-form label-width="80px">
        <el-form-item label="名称" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="分组">
          <el-input
            v-model="form.group_name"
            placeholder="如 状态 / 清晰度 / 语言,可留空"
          />
        </el-form-item>
        <el-form-item label="颜色">
          <el-color-picker v-model="form.color" show-alpha />
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
.tags {
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
.groups {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.group {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 12px;
}
.group-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.group-name {
  font-weight: 500;
  color: #374151;
}
.tag-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.tag-item {
  cursor: pointer;
}
</style>

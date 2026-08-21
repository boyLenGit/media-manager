<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Delete } from '@element-plus/icons-vue'
import { authorsApi, type Author } from '@/api/authors'
import { useAuthStore } from '@/store/auth'

const router = useRouter()
const auth = useAuthStore()

const list = ref<Author[]>([])
const loading = ref(false)

const createDlgOpen = ref(false)
const newName = ref('')
const creating = ref(false)

const fetchList = async () => {
  loading.value = true
  try {
    list.value = await authorsApi.list()
  } finally {
    loading.value = false
  }
}

const openDetail = (id: number) => router.push(`/authors/${id}`)

const openCreate = () => {
  newName.value = ''
  createDlgOpen.value = true
}

const submitCreate = async () => {
  const name = newName.value.trim()
  if (!name) {
    ElMessage.warning('请输入作者名')
    return
  }
  creating.value = true
  try {
    const a = await authorsApi.create({ name })
    ElMessage.success(`已创建作者「${a.name}」`)
    createDlgOpen.value = false
    await fetchList()
  } catch (e: any) {
    if (e?.response?.data?.detail === 'author_name_taken') {
      ElMessage.error('该作者已存在')
    }
  } finally {
    creating.value = false
  }
}

const remove = async (a: Author, ev: Event) => {
  ev.stopPropagation()
  try {
    await ElMessageBox.confirm(
      `删除作者「${a.name}」?该作者关联的 ${a.media_count} 个资源会解除关联但不会被删除。`,
      '确认删除',
      { type: 'warning' },
    )
  } catch {
    return
  }
  await authorsApi.remove(a.id)
  ElMessage.success('已删除')
  await fetchList()
}

onMounted(fetchList)
</script>

<template>
  <div class="authors-page">
    <div class="toolbar">
      <span class="total-hint" v-if="!loading">共 {{ list.length }} 位作者</span>
      <div class="spacer" />
      <el-button type="primary" :icon="Plus" @click="openCreate">添加作者</el-button>
    </div>

    <el-card v-loading="loading" body-style="padding: 16px" class="list-card">
      <el-empty v-if="!loading && list.length === 0" description="暂无作者,点击右上角添加" />

      <el-row v-else :gutter="16" class="author-grid">
        <el-col
          v-for="a in list"
          :key="a.id"
          :xs="12"
          :sm="8"
          :md="6"
          :lg="4"
          :xl="4"
        >
          <div class="author-card" @click="openDetail(a.id)">
            <div class="cover">
              <el-image v-if="a.cover_path" :src="a.cover_path" fit="cover" lazy />
              <div v-else class="cover-placeholder">{{ a.name.slice(0, 1) }}</div>
              <div v-if="auth.user?.role === 'admin'" class="delete-badge" @click="(e) => remove(a, e)">
                <el-icon><Delete /></el-icon>
              </div>
            </div>
            <div class="meta">
              <div class="name" :title="a.name">{{ a.name }}</div>
              <div class="sub">
                <span v-if="a.alias">{{ a.alias }}</span>
                <span>· {{ a.media_count }} 个资源</span>
              </div>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 快速新建弹窗 -->
    <el-dialog v-model="createDlgOpen" title="添加作者" width="420px">
      <el-form label-width="60px">
        <el-form-item label="姓名" required>
          <el-input v-model="newName" placeholder="作者名" @keyup.enter="submitCreate" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDlgOpen = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="submitCreate">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.authors-page {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 8px;
}
.spacer {
  flex: 1;
}
.total-hint {
  font-size: 13px;
  color: #6b7280;
}
.list-card {
  flex: 1;
}
.author-card {
  cursor: pointer;
  margin-bottom: 16px;
  transition: transform 0.15s;
}
.author-card:hover {
  transform: translateY(-2px);
}
.cover {
  position: relative;
  width: 100%;
  aspect-ratio: 1/1;
  overflow: hidden;
  border-radius: 8px;
  background: #f3f4f6;
}
.cover :deep(.el-image),
.cover :deep(.el-image__inner) {
  width: 100%;
  height: 100%;
}
.cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  color: #9ca3af;
  background: linear-gradient(135deg, #e5e7eb, #f3f4f6);
}
.delete-badge {
  position: absolute;
  top: 6px;
  right: 6px;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  border-radius: 4px;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.15s;
}
.author-card:hover .delete-badge {
  opacity: 1;
}
.meta {
  margin-top: 8px;
  text-align: center;
}
.name {
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sub {
  font-size: 12px;
  color: #6b7280;
  margin-top: 2px;
}

@media (max-width: 768px) {
  .toolbar {
    flex-wrap: wrap;
  }
}
</style>

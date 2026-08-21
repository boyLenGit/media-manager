<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ArrowLeft, Camera, Delete, Edit, Star } from '@element-plus/icons-vue'
import { authorsApi, type Author } from '@/api/authors'
import { mediaApi, type MediaItemBrief } from '@/api/media'
import { useAuthStore } from '@/store/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const id = Number(route.params.id)

const isAdmin = computed(() => auth.user?.role === 'admin')

const author = ref<Author | null>(null)
const loading = ref(false)

const works = ref<MediaItemBrief[]>([])
const worksLoading = ref(false)
const worksTotal = ref(0)

const editOpen = ref(false)
const form = reactive({ name: '', alias: '', description: '' })
const saving = ref(false)

const coverInput = ref<HTMLInputElement | null>(null)
const uploadingCover = ref(false)

const fetchAuthor = async () => {
  loading.value = true
  try {
    author.value = await authorsApi.detail(id)
  } finally {
    loading.value = false
  }
}

const fetchWorks = async () => {
  worksLoading.value = true
  try {
    const r = await mediaApi.list({ author_id: id, limit: 24, sort_by: 'updated_at', order: 'desc' })
    works.value = r.items
    worksTotal.value = r.total
  } finally {
    worksLoading.value = false
  }
}

const openEdit = () => {
  if (!author.value) return
  Object.assign(form, {
    name: author.value.name,
    alias: author.value.alias || '',
    description: author.value.description || '',
  })
  editOpen.value = true
}

const save = async () => {
  if (!form.name.trim()) {
    ElMessage.warning('姓名不能为空')
    return
  }
  saving.value = true
  try {
    const updated = await authorsApi.update(id, {
      name: form.name.trim(),
      alias: form.alias.trim() || undefined,
      description: form.description.trim() || undefined,
    })
    author.value = { ...author.value, ...updated }
    ElMessage.success('已保存')
    editOpen.value = false
  } catch (e: any) {
    if (e?.response?.data?.detail === 'author_name_taken') {
      ElMessage.error('该作者名已存在')
    }
  } finally {
    saving.value = false
  }
}

const triggerCoverPick = () => coverInput.value?.click()

const onCoverPicked = async (ev: Event) => {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  uploadingCover.value = true
  try {
    const updated = await authorsApi.uploadCover(id, file)
    author.value = { ...author.value, ...updated }
    ElMessage.success('封面已更新')
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    if (detail === 'unsupported_image_type') ElMessage.error('仅支持 jpg/png/webp 格式')
    else if (detail === 'file_too_large') ElMessage.error('图片超过 8MB 限制')
  } finally {
    uploadingCover.value = false
  }
}

const removeCover = async () => {
  try {
    await ElMessageBox.confirm('移除当前封面?', '确认', { type: 'warning' })
  } catch {
    return
  }
  await authorsApi.removeCover(id)
  if (author.value) author.value.cover_path = undefined
  ElMessage.success('已移除封面')
}

const removeAuthor = async () => {
  if (!author.value) return
  try {
    await ElMessageBox.confirm(
      `删除作者「${author.value.name}」?关联的 ${author.value.media_count} 个资源会解除关联但不会被删除。`,
      '确认删除',
      { type: 'warning' },
    )
  } catch {
    return
  }
  await authorsApi.remove(id)
  ElMessage.success('已删除')
  router.push('/authors')
}

const openMedia = (mid: number) => router.push(`/media/${mid}`)

onMounted(async () => {
  await Promise.all([fetchAuthor(), fetchWorks()])
})
</script>

<template>
  <div v-loading="loading" class="author-detail-page">
    <div class="back-bar">
      <el-button :icon="ArrowLeft" link @click="router.back()">返回</el-button>
    </div>

    <div v-if="author" class="detail">
      <el-card>
        <el-row :gutter="24">
          <el-col :xs="24" :sm="24" :md="6" :lg="5" :xl="4">
            <div class="cover">
              <el-image v-if="author.cover_path" :src="author.cover_path" fit="cover" />
              <div v-else class="cover-placeholder">{{ author.name.slice(0, 1) }}</div>
            </div>
            <input
              ref="coverInput"
              type="file"
              accept="image/jpeg,image/png,image/webp"
              style="display: none"
              @change="onCoverPicked"
            />
            <div class="cover-actions">
              <el-button size="small" :icon="Camera" :loading="uploadingCover" @click="triggerCoverPick">
                更换封面
              </el-button>
              <el-button v-if="author.cover_path" size="small" :icon="Delete" @click="removeCover">
                移除
              </el-button>
            </div>
          </el-col>

          <el-col :xs="24" :sm="24" :md="18" :lg="19" :xl="20">
            <div class="head">
              <h2 class="title">{{ author.name }}</h2>
              <el-button :icon="Edit" @click="openEdit">编辑</el-button>
              <el-button v-if="isAdmin" type="danger" :icon="Delete" @click="removeAuthor">
                删除
              </el-button>
            </div>
            <div v-if="author.alias" class="alias">别名:{{ author.alias }}</div>
            <div class="stat">关联资源:{{ author.media_count }} 个</div>
            <div v-if="author.description" class="description">{{ author.description }}</div>
            <div v-else class="description muted">暂无简介,点击「编辑」补充</div>
          </el-col>
        </el-row>
      </el-card>

      <el-card class="mt-16" header="关联资源">
        <el-empty v-if="!worksLoading && works.length === 0" description="该作者暂无关联资源" />
        <el-row v-else :gutter="12" class="work-grid">
          <el-col
            v-for="m in works"
            :key="m.id"
            :xs="12"
            :sm="8"
            :md="6"
            :lg="4"
            :xl="4"
          >
            <div class="work-card" @click="openMedia(m.id)">
              <div class="w-cover">
                <el-image v-if="m.cover_path" :src="m.cover_path" fit="cover" lazy />
                <div v-else class="w-cover-placeholder">{{ m.title.slice(0, 1) }}</div>
                <div class="w-overlay-badges">
                  <el-tag v-if="m.favorite" type="warning" size="small" effect="dark">
                    <el-icon><Star /></el-icon>
                  </el-tag>
                  <el-tag v-if="m.file_count > 1" type="info" size="small" effect="dark">
                    ×{{ m.file_count }}
                  </el-tag>
                </div>
              </div>
              <div class="w-meta">
                <div class="w-title" :title="m.title">{{ m.title }}</div>
                <div class="w-sub">
                  <span v-if="m.release_date">{{ m.release_date }}</span>
                  <span v-if="m.media_type_name">· {{ m.media_type_name }}</span>
                </div>
                <div v-if="m.tags.length" class="w-tags">
                  <el-tag
                    v-for="t in m.tags"
                    :key="t.id"
                    size="small"
                    :color="t.color"
                    effect="light"
                  >
                    {{ t.name }}
                  </el-tag>
                </div>
              </div>
            </div>
          </el-col>
        </el-row>
        <div v-if="worksTotal > works.length" class="more-hint">
          共 {{ worksTotal }} 个,
          <el-link type="primary" @click="router.push(`/library?author_id=${id}`)">
            去资源库查看全部
          </el-link>
        </div>
      </el-card>
    </div>

    <el-empty v-else-if="!loading" description="作者不存在" />

    <!-- 编辑弹窗 -->
    <el-dialog v-model="editOpen" title="编辑作者" width="500px" :close-on-click-modal="false">
      <el-form label-width="80px">
        <el-form-item label="姓名" required>
          <el-input v-model="form.name" />
        </el-form-item>
        <el-form-item label="别名">
          <el-input v-model="form.alias" placeholder="多个别名用逗号分隔" />
        </el-form-item>
        <el-form-item label="简介">
          <el-input v-model="form.description" type="textarea" :rows="4" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editOpen = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.author-detail-page {
  display: flex;
  flex-direction: column;
}
.back-bar {
  display: flex;
  margin-bottom: 8px;
}
.detail {
  display: flex;
  flex-direction: column;
}
.cover {
  aspect-ratio: 1/1;
  border-radius: 8px;
  overflow: hidden;
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
  font-size: 56px;
  color: #9ca3af;
  background: linear-gradient(135deg, #e5e7eb, #f3f4f6);
}
.cover-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
  justify-content: center;
  flex-wrap: wrap;
}
.head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}
.title {
  margin: 0;
  flex: 1;
}
.alias {
  color: #6b7280;
  margin-bottom: 4px;
}
.stat {
  color: #6b7280;
  font-size: 13px;
  margin-bottom: 12px;
}
.description {
  white-space: pre-wrap;
  line-height: 1.6;
}
.muted {
  color: #9ca3af;
}
.mt-16 {
  margin-top: 16px;
}
.work-card {
  cursor: pointer;
  margin-bottom: 12px;
  transition: transform 0.15s;
}
.work-card:hover {
  transform: translateY(-2px);
}
.w-cover {
  position: relative;
  aspect-ratio: 16/9;
  border-radius: 6px;
  overflow: hidden;
  background: #f3f4f6;
}
.w-cover :deep(.el-image),
.w-cover :deep(.el-image__inner) {
  width: 100%;
  height: 100%;
}
.w-cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  color: #9ca3af;
  background: linear-gradient(135deg, #e5e7eb, #f3f4f6);
}
.w-overlay-badges {
  position: absolute;
  top: 6px;
  right: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.w-meta {
  margin-top: 6px;
}
.w-title {
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.w-sub {
  font-size: 12px;
  color: #6b7280;
  margin-top: 2px;
}
.w-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  margin-top: 4px;
}
.more-hint {
  margin-top: 12px;
  text-align: center;
  font-size: 13px;
  color: #6b7280;
}

@media (max-width: 768px) {
  .cover {
    margin-bottom: 12px;
  }
  .head {
    flex-wrap: wrap;
  }
}
</style>

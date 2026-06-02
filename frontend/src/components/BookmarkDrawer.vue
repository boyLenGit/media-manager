<script setup lang="ts">
/**
 * 视频书签抽屉
 *
 * 以右侧抽屉形式展示当前视频的所有时间点书签。
 * 提供:
 *   - 列表(按时间升序)
 *   - 跳转(点击发出 jump 事件,父组件调 player.currentTime)
 *   - 增加(自动取当前播放时间)
 *   - 编辑 / 删除
 *   - 标签:复用全局 tag 表,内联快速创建
 *
 * 父组件用法:
 *   <BookmarkDrawer
 *     v-model="drawerOpen"
 *     :media-id="mediaId"
 *     :file-asset-id="fileId"
 *     :current-time="curT"
 *     @jump="onJump"
 *   />
 */
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Delete, Position, Bell } from '@element-plus/icons-vue'
import { bookmarksApi, type Bookmark } from '@/api/bookmarks'
import { tagsApi, type Tag } from '@/api/tags'

interface Props {
  modelValue: boolean
  mediaId: number
  fileAssetId?: number
  /** 当前视频播放时间(秒),用于"添加书签到此处" */
  currentTime: number
  /** 抽屉宽度 */
  size?: string | number
}
const props = withDefaults(defineProps<Props>(), {
  size: '380px',
})

const emit = defineEmits<{
  'update:modelValue': [boolean]
  /** 点击书签的"跳转",参数是 position_seconds */
  jump: [number]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const bookmarks = ref<Bookmark[]>([])
const allTags = ref<Tag[]>([])
const loading = ref(false)

// 编辑表单
const dialogOpen = ref(false)
const editingId = ref<number | null>(null)
const form = reactive({
  position_seconds: 0,
  title: '',
  note: '',
  tag_ids: [] as number[],
})

// 内联创建标签
const newTagName = ref('')
const newTagGroup = ref('知识点')
const creatingTag = ref(false)

// ------------------------------------------------------------
// 数据加载
// ------------------------------------------------------------
const fetchBookmarks = async () => {
  loading.value = true
  try {
    bookmarks.value = await bookmarksApi.list({ media_item_id: props.mediaId })
  } catch (e: any) {
    ElMessage.error(`加载书签失败:${e?.response?.data?.detail || e?.message || ''}`)
  } finally {
    loading.value = false
  }
}

const fetchTags = async () => {
  try {
    allTags.value = await tagsApi.list()
  } catch {
    /* 静默 */
  }
}

watch(
  () => props.modelValue,
  async (open) => {
    if (open) {
      await Promise.all([fetchBookmarks(), fetchTags()])
    }
  },
)

watch(
  () => props.mediaId,
  async (id) => {
    if (id && props.modelValue) await fetchBookmarks()
  },
)

// ------------------------------------------------------------
// 行为
// ------------------------------------------------------------
const formatTime = (s: number) => {
  if (!s || !Number.isFinite(s)) return '0:00'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  return h > 0
    ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
    : `${m}:${String(sec).padStart(2, '0')}`
}

const onJump = (b: Bookmark) => {
  emit('jump', b.position_seconds)
  ElMessage.success(`跳转到 ${formatTime(b.position_seconds)}`)
}

const openCreate = () => {
  editingId.value = null
  form.position_seconds = props.currentTime || 0
  form.title = ''
  form.note = ''
  form.tag_ids = []
  dialogOpen.value = true
}

const openEdit = (b: Bookmark) => {
  editingId.value = b.id
  form.position_seconds = b.position_seconds
  form.title = b.title
  form.note = b.note || ''
  form.tag_ids = b.tags.map((t) => t.id)
  dialogOpen.value = true
}

const save = async () => {
  if (!form.title.trim()) {
    ElMessage.warning('请输入标题')
    return
  }
  try {
    if (editingId.value === null) {
      await bookmarksApi.create({
        media_item_id: props.mediaId,
        file_asset_id: props.fileAssetId,
        position_seconds: form.position_seconds,
        title: form.title.trim(),
        note: form.note.trim() || undefined,
        tag_ids: form.tag_ids,
      })
      ElMessage.success('书签已添加')
    } else {
      await bookmarksApi.update(editingId.value, {
        position_seconds: form.position_seconds,
        title: form.title.trim(),
        note: form.note.trim() || null,
        tag_ids: form.tag_ids,
      })
      ElMessage.success('书签已更新')
    }
    dialogOpen.value = false
    await fetchBookmarks()
  } catch (e: any) {
    if (e?.response?.status === 403) {
      ElMessage.error('只能编辑自己创建的书签')
    } else {
      ElMessage.error(`保存失败:${e?.response?.data?.detail || e?.message || ''}`)
    }
  }
}

const remove = async (b: Bookmark) => {
  try {
    await ElMessageBox.confirm(`删除书签「${b.title}」?`, '确认', { type: 'warning' })
  } catch {
    return
  }
  try {
    await bookmarksApi.remove(b.id)
    ElMessage.success('已删除')
    await fetchBookmarks()
  } catch (e: any) {
    if (e?.response?.status === 403) {
      ElMessage.error('只能删除自己创建的书签')
    } else {
      ElMessage.error('删除失败')
    }
  }
}

// 内联快速创建标签
const createTagInline = async () => {
  const name = newTagName.value.trim()
  if (!name) return
  creatingTag.value = true
  try {
    const t = await tagsApi.create({
      name,
      group_name: newTagGroup.value.trim() || undefined,
    })
    allTags.value.push({ ...t, media_count: 0 })
    form.tag_ids.push(t.id)
    newTagName.value = ''
    ElMessage.success(`已创建标签「${t.name}」`)
  } catch (e: any) {
    if (e?.response?.data?.detail === 'tag_already_exists') {
      ElMessage.error('该标签已存在')
    }
  } finally {
    creatingTag.value = false
  }
}

// 标签按 group 分组(便于 UI 展示)
const groupedTags = computed(() => {
  const m: Record<string, Tag[]> = {}
  for (const t of allTags.value) {
    const g = t.group_name || '其他'
    ;(m[g] ||= []).push(t)
  }
  return m
})

const onAddFromCurrent = () => {
  openCreate()
}

onMounted(() => {
  if (props.modelValue) {
    fetchBookmarks()
    fetchTags()
  }
})
</script>

<template>
  <el-drawer
    v-model="visible"
    direction="rtl"
    :size="size"
    :with-header="false"
    class="bookmark-drawer"
  >
    <div class="drawer-inner">
      <div class="drawer-header">
        <div class="title">
          <el-icon><Bell /></el-icon>
          <span>书签 ({{ bookmarks.length }})</span>
        </div>
        <el-button type="primary" :icon="Plus" size="small" @click="onAddFromCurrent">
          在 {{ formatTime(currentTime) }} 添加
        </el-button>
      </div>

      <div v-loading="loading" class="drawer-body">
        <el-empty
          v-if="!loading && bookmarks.length === 0"
          description="还没有书签 · 播放到要标记的位置后,点上方按钮添加"
        />

        <div v-for="b in bookmarks" :key="b.id" class="bm-card">
          <div class="bm-row">
            <el-button
              size="small"
              type="primary"
              :icon="Position"
              class="bm-time"
              @click="onJump(b)"
            >
              {{ formatTime(b.position_seconds) }}
            </el-button>
            <div class="bm-title" :title="b.title">{{ b.title }}</div>
          </div>

          <div v-if="b.note" class="bm-note">{{ b.note }}</div>

          <div v-if="b.tags.length" class="bm-tags">
            <el-tag
              v-for="t in b.tags"
              :key="t.id"
              size="small"
              :color="t.color"
              effect="light"
            >
              {{ t.name }}
            </el-tag>
          </div>

          <div class="bm-meta">
            <span class="bm-creator">{{ b.created_by_username || '-' }}</span>
            <div class="spacer" />
            <el-button :icon="Edit" link size="small" @click="openEdit(b)" />
            <el-button :icon="Delete" link size="small" type="danger" @click="remove(b)" />
          </div>
        </div>
      </div>
    </div>

    <!-- 编辑/新增对话框 -->
    <el-dialog
      v-model="dialogOpen"
      :title="editingId === null ? '添加书签' : '编辑书签'"
      width="480px"
      append-to-body
      :close-on-click-modal="false"
    >
      <el-form label-width="80px">
        <el-form-item label="时间点" required>
          <el-input-number
            v-model="form.position_seconds"
            :min="0"
            :step="1"
            :precision="1"
            style="width: 160px"
          />
          <span class="hint">秒 · 当前 = {{ formatTime(form.position_seconds) }}</span>
          <el-button
            v-if="editingId === null"
            link
            size="small"
            @click="form.position_seconds = currentTime"
          >
            用当前播放位置
          </el-button>
        </el-form-item>

        <el-form-item label="标题" required>
          <el-input
            v-model="form.title"
            placeholder="例如:介绍 hooks 用法"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>

        <el-form-item label="备注">
          <el-input
            v-model="form.note"
            type="textarea"
            :rows="3"
            placeholder="可空"
          />
        </el-form-item>

        <el-form-item label="标签">
          <div class="tag-groups">
            <div v-if="Object.keys(groupedTags).length === 0" class="muted small">
              暂无标签 · 用下方输入框新增
            </div>
            <div v-for="(items, g) in groupedTags" :key="g" class="group">
              <div class="group-name">{{ g }}</div>
              <div class="tag-row">
                <el-check-tag
                  v-for="t in items"
                  :key="t.id"
                  :checked="form.tag_ids.includes(t.id)"
                  :type="form.tag_ids.includes(t.id) ? 'primary' : undefined"
                  @change="
                    form.tag_ids.includes(t.id)
                      ? (form.tag_ids = form.tag_ids.filter((i) => i !== t.id))
                      : form.tag_ids.push(t.id)
                  "
                >
                  {{ t.name }}
                </el-check-tag>
              </div>
            </div>
          </div>
          <div class="inline-create">
            <el-input
              v-model="newTagName"
              placeholder="新标签名"
              size="small"
              class="create-input"
              @keyup.enter="createTagInline"
            />
            <el-input
              v-model="newTagGroup"
              placeholder="分组(默认知识点)"
              size="small"
              class="create-input-group"
            />
            <el-button
              size="small"
              :icon="Plus"
              :loading="creatingTag"
              :disabled="!newTagName.trim()"
              @click="createTagInline"
            >
              新建
            </el-button>
          </div>
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="dialogOpen = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </el-drawer>
</template>

<style scoped>
.drawer-inner {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.drawer-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border-bottom: 1px solid #e5e7eb;
}
.title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 15px;
}
.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.bm-card {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 10px 12px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.bm-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.bm-time {
  flex-shrink: 0;
}
.bm-title {
  flex: 1;
  font-weight: 500;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: #1f2937;
}
.bm-note {
  font-size: 12px;
  color: #4b5563;
  line-height: 1.5;
  white-space: pre-wrap;
}
.bm-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.bm-meta {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #9ca3af;
}
.bm-creator {
  font-size: 12px;
  color: #6b7280;
}
.spacer {
  flex: 1;
}

/* dialog 内 */
.tag-groups {
  display: flex;
  flex-direction: column;
  gap: 8px;
  width: 100%;
}
.group-name {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 4px;
}
.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.inline-create {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #e5e7eb;
}
.create-input {
  flex: 1;
  max-width: 180px;
}
.create-input-group {
  flex: 1;
  max-width: 140px;
}
.hint {
  font-size: 12px;
  color: #6b7280;
  margin-left: 8px;
}
.muted {
  color: #9ca3af;
}
.muted.small {
  font-size: 12px;
}

/* 移动端:抽屉变全屏 */
@media (max-width: 768px) {
  .bookmark-drawer :deep(.el-drawer) {
    width: 100% !important;
  }
}
</style>

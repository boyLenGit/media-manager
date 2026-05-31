<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Grid, List as ListIcon, Star } from '@element-plus/icons-vue'
import { mediaApi, type MediaItemBrief, type MediaListParams } from '@/api/media'
import { authorsApi, type Author } from '@/api/authors'
import { mediaTypesApi, type MediaType } from '@/api/mediaTypes'
import { tagsApi, type Tag } from '@/api/tags'

const router = useRouter()
const items = ref<MediaItemBrief[]>([])
const total = ref(0)
const loading = ref(false)

const authors = ref<Author[]>([])
const mediaTypes = ref<MediaType[]>([])
const tags = ref<Tag[]>([])

const filters = reactive<MediaListParams>({
  q: '',
  media_type_id: undefined,
  author_id: undefined,
  favorite: undefined,
  watch_status: undefined,
  tag_id: undefined,
  sort_by: 'updated_at',
  order: 'desc',
  limit: 24,
  offset: 0,
})

const view = ref<'card' | 'list'>('card')

// 多选
const selectedIds = ref<number[]>([])
const isSelected = (id: number) => selectedIds.value.includes(id)
const toggleSelect = (id: number) => {
  const idx = selectedIds.value.indexOf(id)
  if (idx >= 0) selectedIds.value.splice(idx, 1)
  else selectedIds.value.push(id)
}
const selectAll = () => {
  if (selectedIds.value.length === items.value.length) {
    selectedIds.value = []
  } else {
    selectedIds.value = items.value.map((i) => i.id)
  }
}
const clearSelection = () => (selectedIds.value = [])

// 批量打标签弹窗
const batchDlgOpen = ref(false)
const batchAddIds = ref<number[]>([])
const batchRemoveIds = ref<number[]>([])

const groupedTags = computed(() => {
  const m: Record<string, Tag[]> = {}
  for (const t of tags.value) {
    const g = t.group_name || '其他'
    ;(m[g] ||= []).push(t)
  }
  return m
})

const fetch = async () => {
  loading.value = true
  try {
    const cleaned: MediaListParams = {}
    Object.entries(filters).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') (cleaned as any)[k] = v
    })
    const r = await mediaApi.list(cleaned)
    items.value = r.items
    total.value = r.total
  } finally {
    loading.value = false
  }
}

const loadOptions = async () => {
  const [a, t, tg] = await Promise.all([authorsApi.list(), mediaTypesApi.list(), tagsApi.list()])
  authors.value = a
  mediaTypes.value = t
  tags.value = tg
}

const openDetail = (id: number) => router.push(`/media/${id}`)

const handlePageChange = (page: number) => {
  filters.offset = (page - 1) * (filters.limit || 24)
  fetch()
}

const currentPage = computed(() =>
  Math.floor((filters.offset || 0) / (filters.limit || 24)) + 1,
)

const resetFilters = () => {
  Object.assign(filters, {
    q: '',
    media_type_id: undefined,
    author_id: undefined,
    favorite: undefined,
    watch_status: undefined,
    tag_id: undefined,
    offset: 0,
  })
  fetch()
}

const openBatchDialog = () => {
  if (selectedIds.value.length === 0) {
    ElMessage.warning('请先选择资源')
    return
  }
  batchAddIds.value = []
  batchRemoveIds.value = []
  batchDlgOpen.value = true
}

const submitBatch = async () => {
  if (batchAddIds.value.length === 0 && batchRemoveIds.value.length === 0) {
    ElMessage.warning('请至少选择一个要添加或移除的标签')
    return
  }
  try {
    const r = await mediaApi.batchTag({
      media_ids: selectedIds.value,
      add_tag_ids: batchAddIds.value,
      remove_tag_ids: batchRemoveIds.value,
    })
    ElMessage.success(`已更新 ${r.affected} 个资源`)
    batchDlgOpen.value = false
    clearSelection()
    await fetch()
  } catch {
    /* error toasted */
  }
}

const batchSetWatched = async () => {
  if (selectedIds.value.length === 0) return
  await ElMessageBox.confirm(
    `将 ${selectedIds.value.length} 个资源标为已看?`,
    '确认',
  ).catch(() => null)
  await mediaApi.batchUpdate({
    media_ids: selectedIds.value,
    watch_status: 'watched',
  })
  ElMessage.success('已更新')
  clearSelection()
  await fetch()
}

const batchToggleFavorite = async (favorite: boolean) => {
  if (selectedIds.value.length === 0) return
  await mediaApi.batchUpdate({
    media_ids: selectedIds.value,
    favorite,
  })
  ElMessage.success('已更新')
  clearSelection()
  await fetch()
}

watch(
  () => filters.q,
  () => {
    filters.offset = 0
    fetch()
  },
)

onMounted(async () => {
  await Promise.all([fetch(), loadOptions()])
})
</script>

<template>
  <div class="library">
    <el-row :gutter="12">
      <!-- 左侧筛选 -->
      <el-col :span="5">
        <el-card body-style="padding: 12px">
          <h4 class="filter-title">筛选</h4>
          <div class="filter-section">
            <div class="filter-label">观看状态</div>
            <el-radio-group v-model="filters.watch_status" @change="fetch">
              <el-radio-button :value="undefined">全部</el-radio-button>
              <el-radio-button value="unwatched">未看</el-radio-button>
              <el-radio-button value="watching">观看中</el-radio-button>
              <el-radio-button value="watched">已看</el-radio-button>
            </el-radio-group>
          </div>

          <div class="filter-section">
            <div class="filter-label">收藏</div>
            <el-radio-group v-model="filters.favorite" @change="fetch">
              <el-radio-button :value="undefined">全部</el-radio-button>
              <el-radio-button :value="true">已收藏</el-radio-button>
              <el-radio-button :value="false">未收藏</el-radio-button>
            </el-radio-group>
          </div>

          <div class="filter-section">
            <div class="filter-label">类型</div>
            <el-select
              v-model="filters.media_type_id"
              placeholder="全部"
              clearable
              filterable
              style="width: 100%"
              @change="fetch"
            >
              <el-option
                v-for="t in mediaTypes"
                :key="t.id"
                :label="`${t.name} (${t.media_count})`"
                :value="t.id"
              />
            </el-select>
          </div>

          <div class="filter-section">
            <div class="filter-label">作者</div>
            <el-select
              v-model="filters.author_id"
              placeholder="全部"
              clearable
              filterable
              style="width: 100%"
              @change="fetch"
            >
              <el-option
                v-for="a in authors"
                :key="a.id"
                :label="`${a.name} (${a.media_count})`"
                :value="a.id"
              />
            </el-select>
          </div>

          <div class="filter-section">
            <div class="filter-label">标签</div>
            <div v-for="(items, g) in groupedTags" :key="g" class="tag-group">
              <div class="group-name">{{ g }}</div>
              <div class="tag-row">
                <el-tag
                  v-for="t in items"
                  :key="t.id"
                  :color="filters.tag_id === t.id ? t.color : undefined"
                  :effect="filters.tag_id === t.id ? 'dark' : 'plain'"
                  class="tag-pill"
                  @click="filters.tag_id = filters.tag_id === t.id ? undefined : t.id; fetch()"
                >
                  {{ t.name }}
                </el-tag>
              </div>
            </div>
          </div>

          <div class="filter-section">
            <el-button @click="resetFilters" style="width: 100%">清空筛选</el-button>
          </div>
        </el-card>
      </el-col>

      <!-- 右侧主内容 -->
      <el-col :span="19">
        <div class="toolbar">
          <el-input
            v-model="filters.q"
            placeholder="搜索资源标题"
            clearable
            :prefix-icon="Search"
            style="width: 280px"
          />
          <el-select v-model="filters.sort_by" style="width: 140px" @change="fetch">
            <el-option label="最近更新" value="updated_at" />
            <el-option label="最近创建" value="created_at" />
            <el-option label="标题" value="title" />
            <el-option label="评分" value="rating" />
          </el-select>
          <el-select v-model="filters.order" style="width: 100px" @change="fetch">
            <el-option label="降序" value="desc" />
            <el-option label="升序" value="asc" />
          </el-select>

          <div class="spacer" />

          <span class="total-hint" v-if="!loading">共 {{ total }} 个资源</span>
          <el-button-group>
            <el-button :type="view === 'card' ? 'primary' : ''" :icon="Grid" @click="view = 'card'" />
            <el-button :type="view === 'list' ? 'primary' : ''" :icon="ListIcon" @click="view = 'list'" />
          </el-button-group>
          <el-button :icon="Refresh" @click="fetch" />
        </div>

        <!-- 多选工具栏 -->
        <transition name="el-fade-in-linear">
          <el-card v-if="selectedIds.length > 0" class="batch-bar" body-style="padding: 8px 12px">
            <div class="batch-row">
              <span>已选 {{ selectedIds.length }} 个</span>
              <el-button size="small" @click="selectAll">
                {{ selectedIds.length === items.length ? '取消全选' : '全选当页' }}
              </el-button>
              <el-button size="small" @click="clearSelection">清除选择</el-button>
              <div class="spacer" />
              <el-button size="small" type="primary" @click="openBatchDialog">批量打标签</el-button>
              <el-button size="small" @click="batchSetWatched">标为已看</el-button>
              <el-button size="small" @click="batchToggleFavorite(true)">收藏</el-button>
              <el-button size="small" @click="batchToggleFavorite(false)">取消收藏</el-button>
            </div>
          </el-card>
        </transition>

        <el-card v-loading="loading" body-style="padding: 12px">
          <el-empty
            v-if="!loading && items.length === 0"
            description="暂无资源,请先去「设置 → 扫描路径」添加目录并执行扫描"
          />

          <!-- 卡片视图 -->
          <el-row v-if="view === 'card'" :gutter="12">
            <el-col v-for="m in items" :key="m.id" :span="4">
              <div class="media-card" :class="{ selected: isSelected(m.id) }">
                <div class="cover" @click.stop="openDetail(m.id)">
                  <el-image v-if="m.cover_path" :src="m.cover_path" fit="cover" />
                  <div v-else class="cover-placeholder">{{ m.title.slice(0, 1) }}</div>
                  <div class="overlay-badges">
                    <el-tag v-if="m.favorite" type="warning" size="small" effect="dark">
                      <el-icon><Star /></el-icon>
                    </el-tag>
                    <el-tag v-if="m.file_count > 1" type="info" size="small" effect="dark">
                      ×{{ m.file_count }}
                    </el-tag>
                  </div>
                  <div class="select-badge" @click.stop="toggleSelect(m.id)">
                    <el-checkbox :model-value="isSelected(m.id)" />
                  </div>
                </div>
                <div class="meta" @click="openDetail(m.id)">
                  <div class="title" :title="m.title">{{ m.title }}</div>
                  <div class="sub">
                    <span v-if="m.release_date">{{ m.release_date }}</span>
                    <span v-if="m.media_type_name">· {{ m.media_type_name }}</span>
                  </div>
                </div>
              </div>
            </el-col>
          </el-row>

          <!-- 列表视图 -->
          <el-table
            v-else
            :data="items"
            stripe
            @selection-change="(rows: MediaItemBrief[]) => (selectedIds = rows.map((r) => r.id))"
          >
            <el-table-column type="selection" width="50" />
            <el-table-column prop="title" label="标题" min-width="240" show-overflow-tooltip>
              <template #default="{ row }">
                <a class="title-link" @click="openDetail(row.id)">{{ row.title }}</a>
              </template>
            </el-table-column>
            <el-table-column label="作者" width="140">
              <template #default="{ row }">{{ row.author_name || '-' }}</template>
            </el-table-column>
            <el-table-column label="类型" width="100">
              <template #default="{ row }">{{ row.media_type_name || '-' }}</template>
            </el-table-column>
            <el-table-column label="发布" width="120">
              <template #default="{ row }">{{ row.release_date || '-' }}</template>
            </el-table-column>
            <el-table-column label="文件" width="80">
              <template #default="{ row }">{{ row.file_count }}</template>
            </el-table-column>
            <el-table-column label="状态" width="100">
              <template #default="{ row }">
                <el-tag size="small">{{ row.watch_status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column label="标签" min-width="160">
              <template #default="{ row }">
                <el-tag
                  v-for="t in row.tags"
                  :key="t.id"
                  size="small"
                  :color="t.color"
                  effect="light"
                  style="margin-right: 4px"
                >
                  {{ t.name }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>

          <div v-if="total > (filters.limit || 24)" class="pager">
            <el-pagination
              background
              layout="prev, pager, next, total"
              :total="total"
              :page-size="filters.limit"
              :current-page="currentPage"
              @current-change="handlePageChange"
            />
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 批量打标签弹窗 -->
    <el-dialog v-model="batchDlgOpen" title="批量打标签" width="600px">
      <div class="batch-tag-form">
        <div class="form-section">
          <div class="form-label">添加标签 (绿色 = 选中)</div>
          <div v-for="(items, g) in groupedTags" :key="g" class="tag-group">
            <div class="group-name">{{ g }}</div>
            <div class="checkbox-row">
              <el-check-tag
                v-for="t in items"
                :key="t.id"
                :checked="batchAddIds.includes(t.id)"
                type="success"
                @change="
                  batchAddIds.includes(t.id)
                    ? (batchAddIds = batchAddIds.filter((i) => i !== t.id))
                    : batchAddIds.push(t.id)
                "
              >
                {{ t.name }}
              </el-check-tag>
            </div>
          </div>
        </div>

        <el-divider />

        <div class="form-section">
          <div class="form-label">移除标签 (红色 = 选中)</div>
          <div v-for="(items, g) in groupedTags" :key="g" class="tag-group">
            <div class="group-name">{{ g }}</div>
            <div class="checkbox-row">
              <el-check-tag
                v-for="t in items"
                :key="t.id"
                :checked="batchRemoveIds.includes(t.id)"
                type="danger"
                @change="
                  batchRemoveIds.includes(t.id)
                    ? (batchRemoveIds = batchRemoveIds.filter((i) => i !== t.id))
                    : batchRemoveIds.push(t.id)
                "
              >
                {{ t.name }}
              </el-check-tag>
            </div>
          </div>
        </div>

        <el-alert
          v-if="batchAddIds.length === 0 && batchRemoveIds.length === 0"
          type="info"
          :closable="false"
          title="请至少选择一个要添加或移除的标签"
        />
      </div>

      <template #footer>
        <el-button @click="batchDlgOpen = false">取消</el-button>
        <el-button type="primary" @click="submitBatch">应用到 {{ selectedIds.length }} 个资源</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.library {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
}
.spacer {
  flex: 1;
}
.total-hint {
  font-size: 13px;
  color: #6b7280;
  margin-right: 8px;
}

.filter-title {
  margin: 0 0 12px;
  font-size: 14px;
  color: #374151;
}
.filter-section {
  margin-bottom: 16px;
}
.filter-label {
  font-size: 12px;
  color: #6b7280;
  margin-bottom: 6px;
}
.tag-group {
  margin-bottom: 8px;
}
.group-name {
  font-size: 11px;
  color: #9ca3af;
  margin-bottom: 4px;
}
.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.tag-pill {
  cursor: pointer;
}

.batch-bar {
  margin-bottom: 12px;
  border: 1px solid #3b82f6;
}
.batch-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}

.media-card {
  cursor: pointer;
  margin-bottom: 12px;
  position: relative;
  transition: transform 0.15s;
  border-radius: 6px;
}
.media-card:hover {
  transform: translateY(-2px);
}
.media-card.selected {
  outline: 2px solid #3b82f6;
  outline-offset: 2px;
}
.cover {
  position: relative;
  width: 100%;
  aspect-ratio: 16/9;
  overflow: hidden;
  border-radius: 6px;
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
  font-size: 36px;
  color: #9ca3af;
  background: linear-gradient(135deg, #e5e7eb, #f3f4f6);
}
.overlay-badges {
  position: absolute;
  top: 6px;
  right: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.select-badge {
  position: absolute;
  top: 6px;
  left: 6px;
  background: rgba(255, 255, 255, 0.9);
  border-radius: 3px;
  padding: 2px 4px;
}
.meta {
  margin-top: 6px;
}
.title {
  font-size: 13px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.sub {
  font-size: 12px;
  color: #6b7280;
}
.title-link {
  color: #2563eb;
  cursor: pointer;
}
.title-link:hover {
  text-decoration: underline;
}
.pager {
  margin-top: 12px;
  display: flex;
  justify-content: center;
}
.batch-tag-form {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.form-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.form-label {
  font-size: 13px;
  color: #374151;
  font-weight: 500;
}
.checkbox-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
</style>

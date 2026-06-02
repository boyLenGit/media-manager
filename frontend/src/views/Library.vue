<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Refresh, Grid, List as ListIcon, Star, ZoomIn, ZoomOut } from '@element-plus/icons-vue'
import { mediaApi, type MediaItemBrief, type MediaListParams } from '@/api/media'
import { authorsApi, type Author } from '@/api/authors'
import { mediaTypesApi, type MediaType } from '@/api/mediaTypes'
import { tagsApi, type Tag } from '@/api/tags'
import { useAuthStore } from '@/store/auth'

const auth = useAuthStore()

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

// 卡片列数 (1 行多少个卡片) — 桌面 6 默认, 持久化
const COLS_KEY = 'media-manager.libraryCols'
const PAGE_SIZE_KEY = 'media-manager.libraryPageSize'
const cardCols = ref<number>(Number(localStorage.getItem(COLS_KEY)) || 6)
const setCardCols = (n: number) => {
  cardCols.value = Math.min(12, Math.max(2, Math.round(n)))
  localStorage.setItem(COLS_KEY, String(cardCols.value))
}
// 卡片 col span (24 栅格制): 24 / cardCols, 向下取整
const cardSpan = computed(() => {
  const s = Math.floor(24 / cardCols.value)
  return s < 1 ? 1 : s
})

// 每页条数(可调) — 默认 24
filters.limit = Number(localStorage.getItem(PAGE_SIZE_KEY)) || 24
const onPageSizeChange = (size: number) => {
  filters.limit = size
  filters.offset = 0
  localStorage.setItem(PAGE_SIZE_KEY, String(size))
  fetch()
}

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

const batchSetStatus = async (status: 'unwatched' | 'watching' | 'watched') => {
  if (selectedIds.value.length === 0) return
  const labelMap = { unwatched: '未看', watching: '观看中', watched: '已看' }
  try {
    await ElMessageBox.confirm(
      `将 ${selectedIds.value.length} 个资源标为「${labelMap[status]}」?`,
      '确认',
    )
  } catch {
    return
  }
  await mediaApi.batchUpdate({
    media_ids: selectedIds.value,
    watch_status: status,
  })
  ElMessage.success('已更新')
  clearSelection()
  await fetch()
}

// 批量收藏/取消收藏
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

// 批量删除(只清 DB,不删磁盘)
const batchDelete = async () => {
  if (selectedIds.value.length === 0) return
  try {
    await ElMessageBox.confirm(
      `从资源库删除 ${selectedIds.value.length} 个资源?\n\n` +
        '仅清理资源库记录,磁盘文件保留(下次扫描会重新加回来)。',
      '确认删除',
      { type: 'warning' },
    )
  } catch {
    return
  }

  let success = 0
  let failed = 0
  for (const mid of selectedIds.value) {
    try {
      await mediaApi.remove(mid, false)
      success++
    } catch {
      failed++
    }
  }
  if (failed === 0) {
    ElMessage.success(`已删除 ${success} 个资源`)
  } else {
    ElMessage.warning(`已删除 ${success} 个,失败 ${failed} 个(可能权限不足)`)
  }
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
      <!-- 左侧筛选 (移动端整列堆叠) -->
      <el-col :xs="24" :sm="24" :md="7" :lg="6" :xl="5">
        <el-card body-style="padding: 12px" class="filter-card">
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
            <div v-if="tags.length === 0" class="empty-hint">
              <span>还没有标签 ·</span>
              <el-link type="primary" @click="router.push('/settings')">去设置创建</el-link>
            </div>
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
      <el-col :xs="24" :sm="24" :md="17" :lg="18" :xl="19" class="main-col">
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

          <!-- 卡片缩放(仅卡片视图,移动端隐藏) -->
          <div v-if="view === 'card'" class="zoom-control">
            <el-icon class="zoom-icon" @click="setCardCols(cardCols + 1)" title="缩小卡片"><ZoomOut /></el-icon>
            <el-slider
              :model-value="cardCols"
              :min="2"
              :max="12"
              :step="1"
              :show-tooltip="false"
              class="zoom-slider"
              @update:model-value="(v: number | number[]) => setCardCols(Array.isArray(v) ? v[0] : v)"
            />
            <el-icon class="zoom-icon" @click="setCardCols(cardCols - 1)" title="放大卡片"><ZoomIn /></el-icon>
          </div>

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
              <el-dropdown trigger="click">
                <el-button size="small">
                  改观看状态 <el-icon class="el-icon--right">▾</el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item @click="batchSetStatus('unwatched')">标为未看</el-dropdown-item>
                    <el-dropdown-item @click="batchSetStatus('watching')">标为观看中</el-dropdown-item>
                    <el-dropdown-item @click="batchSetStatus('watched')">标为已看</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
              <el-button size="small" @click="batchToggleFavorite(true)">收藏</el-button>
              <el-button size="small" @click="batchToggleFavorite(false)">取消收藏</el-button>
              <el-button
                v-if="auth.user?.role === 'admin'"
                size="small"
                type="danger"
                @click="batchDelete"
              >
                删除
              </el-button>
            </div>
          </el-card>
        </transition>

        <el-card v-loading="loading" body-style="padding: 12px" class="list-card">
          <el-empty
            v-if="!loading && items.length === 0"
            description="暂无资源,请先去「设置 → 扫描路径」添加目录并执行扫描"
          />

          <!-- 卡片视图 -->
          <el-row v-if="view === 'card'" :gutter="12" class="card-grid">
            <el-col
              v-for="m in items"
              :key="m.id"
              :xs="12"
              :sm="cardSpan * 2 < 24 ? cardSpan * 2 : 12"
              :md="cardSpan"
              :lg="cardSpan"
              :xl="cardSpan"
            >
              <div class="media-card" :class="{ selected: isSelected(m.id) }">
                <div class="cover" @click.stop="openDetail(m.id)">
                  <el-image
                    v-if="m.cover_path"
                    :src="m.cover_path"
                    fit="cover"
                    lazy
                  />
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
            class="list-table"
            height="100%"
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

          <div v-if="total > 0" class="pager">
            <el-pagination
              background
              layout="prev, pager, next, sizes, total"
              :total="total"
              :page-size="filters.limit"
              :current-page="currentPage"
              :page-sizes="[12, 24, 48, 96, 200]"
              @current-change="handlePageChange"
              @size-change="onPageSizeChange"
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
  /* 撑满 el-main 可视区(el-main 默认 flex:1 + padding:16px),
     不让整页滚动 — 卡片网格自己滚 */
  height: 100%;
  min-height: 0;
  overflow: hidden;
}
.library > .el-row {
  flex: 1;
  min-height: 0;
}
.library > .el-row :deep(> .el-col) {
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
}

/* 左侧筛选 — 自身可滚 */
.filter-card {
  max-height: 100%;
  overflow-y: auto;
  align-self: flex-start;
  width: 100%;
}

/* 右侧主区列容器 — 占满纵向空间 */
.main-col {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-height: 0;
}
.main-col > .toolbar {
  flex-shrink: 0;
}
.main-col > .batch-bar {
  flex-shrink: 0;
}
/* 卡片区 card 容器 撑满剩余高度,内部滚动 */
.list-card {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.list-card :deep(> .el-card__body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 12px;
  overflow: hidden;
}
/* 卡片网格滚动区 */
.card-grid {
  flex: 1;
  overflow-y: auto;
  align-content: flex-start;
}
.list-table {
  flex: 1;
}
.pager {
  flex-shrink: 0;
  display: flex;
  justify-content: center;
  padding-top: 12px;
  border-top: 1px solid #f3f4f6;
}

.toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  flex-wrap: wrap;
}
.zoom-control {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 0 6px;
  border-left: 1px solid #e5e7eb;
  border-right: 1px solid #e5e7eb;
}
.zoom-icon {
  cursor: pointer;
  color: #6b7280;
  transition: color 0.15s;
}
.zoom-icon:hover {
  color: #3b82f6;
}
.zoom-slider {
  width: 100px;
}
.spacer {
  flex: 1;
  min-width: 8px;
}
.total-hint {
  font-size: 13px;
  color: #6b7280;
  margin-right: 8px;
}

/* 移动端: filter-card 顶部堆叠,toolbar 文字小一些, input 单独占一行 */
@media (max-width: 768px) {
  .library {
    /* 移动端不强制 100% 高度,允许整页滚动(filter card + 卡片网格 一起) */
    height: auto;
    min-height: 100%;
  }
  .library > .el-row {
    flex: initial;
  }
  .filter-card {
    margin-bottom: 12px;
    max-height: none;
  }
  .list-card {
    flex: initial;
  }
  .card-grid {
    overflow-y: visible;
  }
  .toolbar :deep(.el-input),
  .toolbar :deep(.el-select) {
    flex: 1 1 140px;
    min-width: 0;
    width: auto !important;
  }
  .total-hint {
    width: 100%;
    margin-right: 0;
  }
  .zoom-control {
    display: none; /* 触屏调整列数没意义 */
  }
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
.empty-hint {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #6b7280;
  padding: 4px 0;
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

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { authorsApi, type Author } from '@/api/authors'
import { mediaTypesApi, type MediaType } from '@/api/mediaTypes'
import { tagsApi, type Tag } from '@/api/tags'
import { mediaApi, type MediaItemDetail } from '@/api/media'

const props = defineProps<{
  modelValue: boolean
  media: MediaItemDetail | null
}>()

const emit = defineEmits<{
  'update:modelValue': [boolean]
  saved: [MediaItemDetail]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const authors = ref<Author[]>([])
const mediaTypes = ref<MediaType[]>([])
const tags = ref<Tag[]>([])

const form = reactive({
  title: '',
  media_type_id: null as number | null,
  author_id: null as number | null,
  rating: undefined as number | undefined,
  watch_status: 'unwatched',
  description: '',
  remark: '',
  tag_ids: [] as number[],
})

// ============================================================
// 内联创建用的临时 input
// ============================================================
const newAuthorName = ref('')
const newTypeName = ref('')
const newTagName = ref('')
const newTagGroup = ref('')
const creatingAuthor = ref(false)
const creatingType = ref(false)
const creatingTag = ref(false)

const loadOptions = async () => {
  try {
    ;[authors.value, mediaTypes.value, tags.value] = await Promise.all([
      authorsApi.list(),
      mediaTypesApi.list(),
      tagsApi.list(),
    ])
  } catch {
    /* error toasted */
  }
}

const createAuthorInline = async () => {
  const name = newAuthorName.value.trim()
  if (!name) return
  creatingAuthor.value = true
  try {
    const a = await authorsApi.create({ name })
    authors.value.push({ ...a, media_count: 0 })
    form.author_id = a.id
    newAuthorName.value = ''
    ElMessage.success(`已创建作者「${a.name}」`)
  } catch (e: any) {
    if (e?.response?.data?.detail === 'author_name_taken') {
      ElMessage.error('该作者已存在')
    }
  } finally {
    creatingAuthor.value = false
  }
}

const createTypeInline = async () => {
  const name = newTypeName.value.trim()
  if (!name) return
  creatingType.value = true
  try {
    const t = await mediaTypesApi.create({ name })
    mediaTypes.value.push({ ...t, media_count: 0 } as MediaType)
    form.media_type_id = t.id
    newTypeName.value = ''
    ElMessage.success(`已创建类型「${t.name}」`)
  } catch (e: any) {
    if (e?.response?.status === 409) {
      ElMessage.error('该类型已存在')
    }
  } finally {
    creatingType.value = false
  }
}

const createTagInline = async () => {
  const name = newTagName.value.trim()
  if (!name) return
  const group = newTagGroup.value.trim() || undefined
  creatingTag.value = true
  try {
    const t = await tagsApi.create({ name, group_name: group })
    tags.value.push({ ...t, media_count: 0 })
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

watch(
  () => props.media,
  (m) => {
    if (!m) return
    form.title = m.title
    form.media_type_id = m.media_type_id ?? null
    form.author_id = m.author_id ?? null
    form.rating = m.rating ?? undefined
    form.watch_status = m.watch_status
    form.description = m.description || ''
    form.remark = m.remark || ''
    form.tag_ids = m.tags.map((t) => t.id)
  },
  { immediate: true },
)

watch(visible, async (open) => {
  if (open) await loadOptions()
})

const save = async () => {
  if (!props.media) return
  if (!form.title) {
    ElMessage.warning('标题不能为空')
    return
  }
  try {
    const updated = await mediaApi.update(props.media.id, {
      title: form.title,
      media_type_id: form.media_type_id,
      author_id: form.author_id,
      rating: form.rating,
      watch_status: form.watch_status,
      description: form.description,
      remark: form.remark,
      tag_ids: form.tag_ids,
    })
    ElMessage.success('已保存')
    emit('saved', updated)
    visible.value = false
  } catch {
    /* error toasted */
  }
}

// 标签按分组展示
const groupedTags = computed(() => {
  const m: Record<string, Tag[]> = {}
  for (const t of tags.value) {
    const g = t.group_name || '其他'
    ;(m[g] ||= []).push(t)
  }
  return m
})

onMounted(loadOptions)
</script>

<template>
  <el-dialog
    v-model="visible"
    title="编辑资源"
    width="600px"
    :close-on-click-modal="false"
    append-to-body
  >
    <el-form label-width="80px" v-if="media">
      <el-form-item label="标题" required>
        <el-input v-model="form.title" />
      </el-form-item>

      <el-form-item label="类型">
        <div class="inline-row">
          <el-select
            v-model="form.media_type_id"
            placeholder="未分类"
            clearable
            filterable
            class="grow"
          >
            <el-option
              v-for="t in mediaTypes"
              :key="t.id"
              :label="t.description ? `${t.name} (${t.description})` : t.name"
              :value="t.id"
            />
          </el-select>
        </div>
        <div class="inline-create">
          <el-input
            v-model="newTypeName"
            placeholder="新建类型..."
            size="small"
            class="create-input"
            @keyup.enter="createTypeInline"
          />
          <el-button
            size="small"
            :icon="Plus"
            :loading="creatingType"
            :disabled="!newTypeName.trim()"
            @click="createTypeInline"
          >
            新建
          </el-button>
        </div>
      </el-form-item>

      <el-form-item label="作者">
        <div class="inline-row">
          <el-select
            v-model="form.author_id"
            placeholder="未指定"
            clearable
            filterable
            class="grow"
          >
            <el-option
              v-for="a in authors"
              :key="a.id"
              :label="a.alias ? `${a.name} (${a.alias})` : a.name"
              :value="a.id"
            />
          </el-select>
        </div>
        <div class="inline-create">
          <el-input
            v-model="newAuthorName"
            placeholder="新建作者..."
            size="small"
            class="create-input"
            @keyup.enter="createAuthorInline"
          />
          <el-button
            size="small"
            :icon="Plus"
            :loading="creatingAuthor"
            :disabled="!newAuthorName.trim()"
            @click="createAuthorInline"
          >
            新建
          </el-button>
        </div>
      </el-form-item>

      <el-form-item label="观看状态">
        <el-radio-group v-model="form.watch_status">
          <el-radio value="unwatched">未看</el-radio>
          <el-radio value="watching">观看中</el-radio>
          <el-radio value="watched">已看</el-radio>
        </el-radio-group>
      </el-form-item>

      <el-form-item label="评分">
        <el-rate v-model="form.rating" :max="10" allow-half show-score />
      </el-form-item>

      <el-form-item label="标签">
        <div class="tag-groups">
          <div v-if="Object.keys(groupedTags).length === 0" class="muted">
            暂无标签,使用下方输入框添加新标签
          </div>
          <div v-for="(items, g) in groupedTags" :key="g" class="group">
            <div class="group-name">{{ g }}</div>
            <div class="checkbox-row">
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
        <div class="inline-create tag-create">
          <el-input
            v-model="newTagName"
            placeholder="标签名"
            size="small"
            class="create-input"
            @keyup.enter="createTagInline"
          />
          <el-input
            v-model="newTagGroup"
            placeholder="分组(可选)"
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

      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" :rows="3" />
      </el-form-item>
      <el-form-item label="备注">
        <el-input v-model="form.remark" type="textarea" :rows="2" />
      </el-form-item>
    </el-form>

    <template #footer>
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" @click="save">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.inline-row {
  display: flex;
  width: 100%;
}
.grow {
  flex: 1;
}
.inline-create {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 6px;
}
.tag-create {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed #e5e7eb;
}
.create-input {
  flex: 1;
  max-width: 240px;
}
.create-input-group {
  flex: 1;
  max-width: 140px;
}
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
.checkbox-row {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.muted {
  color: #9ca3af;
  font-size: 12px;
}
</style>

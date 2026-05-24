<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
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
  <el-dialog v-model="visible" title="编辑资源" width="600px" :close-on-click-modal="false">
    <el-form label-width="100px" v-if="media">
      <el-form-item label="标题" required>
        <el-input v-model="form.title" />
      </el-form-item>
      <el-form-item label="类型">
        <el-select v-model="form.media_type_id" placeholder="未分类" clearable filterable style="width: 100%">
          <el-option
            v-for="t in mediaTypes"
            :key="t.id"
            :label="t.description ? `${t.name} (${t.description})` : t.name"
            :value="t.id"
          />
        </el-select>
      </el-form-item>
      <el-form-item label="作者">
        <el-select v-model="form.author_id" placeholder="未指定" clearable filterable style="width: 100%">
          <el-option
            v-for="a in authors"
            :key="a.id"
            :label="a.alias ? `${a.name} (${a.alias})` : a.name"
            :value="a.id"
          />
        </el-select>
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
</style>

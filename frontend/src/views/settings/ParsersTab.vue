<script setup lang="ts">
/**
 * 解析器配置 Tab
 *
 * 功能:
 * - 列出所有可用解析器,可拖拽排序、勾选启用
 * - 在线测试:输入文件名,实时看解析结果
 * - 一键重解析全部资源(用当前激活的 pipeline 重新跑标题)
 */
import { onMounted, reactive, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh, MagicStick, ArrowUp, ArrowDown } from '@element-plus/icons-vue'
import { libraryToolsApi, type ParserInfo, type ParseTestResult } from '@/api/libraryTools'

const available = ref<ParserInfo[]>([])
const active = ref<string[]>([])
const loading = ref(false)
const saving = ref(false)
const reparsing = ref(false)

// 在线测试
const testInput = ref('我们其实是未出道的女团W&M2 - 1.我们其实是女团(Av10285316,P1).mp4')
const testResult = ref<ParseTestResult | null>(null)
const testing = ref(false)

const fetch = async () => {
  loading.value = true
  try {
    const r = await libraryToolsApi.getParsers()
    available.value = r.available
    active.value = r.active
  } finally {
    loading.value = false
  }
}

const isActive = (name: string) => active.value.includes(name)

const toggle = (name: string) => {
  if (isActive(name)) {
    // 不允许禁用 default(因为它是兜底)
    if (name === 'default') {
      ElMessage.warning('default 是兜底解析器,不能禁用')
      return
    }
    active.value = active.value.filter((n) => n !== name)
  } else {
    active.value = [...active.value, name]
  }
}

const moveUp = (idx: number) => {
  if (idx === 0) return
  const arr = [...active.value]
  ;[arr[idx - 1], arr[idx]] = [arr[idx], arr[idx - 1]]
  active.value = arr
}

const moveDown = (idx: number) => {
  if (idx >= active.value.length - 1) return
  const arr = [...active.value]
  ;[arr[idx], arr[idx + 1]] = [arr[idx + 1], arr[idx]]
  active.value = arr
}

const save = async () => {
  saving.value = true
  try {
    await libraryToolsApi.updateParsers(active.value)
    ElMessage.success('解析器配置已保存')
  } finally {
    saving.value = false
  }
}

const runTest = async () => {
  if (!testInput.value.trim()) {
    ElMessage.warning('请输入文件名')
    return
  }
  testing.value = true
  try {
    testResult.value = await libraryToolsApi.testParse(
      testInput.value.trim(),
      active.value,
    )
  } finally {
    testing.value = false
  }
}

const reparseAll = async () => {
  await ElMessageBox.confirm(
    '将用当前激活的解析器重新解析所有资源标题。\n会覆盖现有标题(自定义改过的也会),确认?',
    '重解析全部',
    { type: 'warning' },
  ).catch(() => null)

  reparsing.value = true
  try {
    const r = await libraryToolsApi.reparseAll()
    ElMessage.success(`已重解析 ${r.updated}/${r.total} 个资源`)
  } finally {
    reparsing.value = false
  }
}

const findInfo = (name: string) =>
  available.value.find((p) => p.name === name) || { description: '' }

onMounted(fetch)
</script>

<template>
  <div class="parsers-tab" v-loading="loading">
    <div class="header">
      <h3 class="section-title">文件名解析器</h3>
      <div class="actions">
        <el-button :icon="Refresh" @click="fetch">刷新</el-button>
        <el-button
          type="warning"
          :icon="MagicStick"
          :loading="reparsing"
          @click="reparseAll"
        >
          重解析全部资源
        </el-button>
      </div>
    </div>

    <el-alert
      type="info"
      :closable="false"
      style="margin-bottom: 12px"
      title="解析器流水线"
    >
      <template #default>
        <div>
          解析器按顺序串联执行,前面的解析器(如 bilibili / anime)负责剥离平台特化的后缀,
          后面的 default 负责通用清洗(分辨率/编码/语言标记/年份)。
          <strong>default 总是兜底</strong>,即使你没勾选,系统也会自动追加。
        </div>
      </template>
    </el-alert>

    <el-row :gutter="16">
      <!-- 左:可用列表 -->
      <el-col :xs="24" :sm="24" :md="10" :lg="10" :xl="10">
        <el-card body-style="padding: 12px">
          <template #header>
            <strong>可用解析器</strong>
            <span class="hint">点击启用/停用</span>
          </template>
          <div class="parser-list">
            <div
              v-for="p in available"
              :key="p.name"
              class="parser-item"
              :class="{ active: isActive(p.name) }"
              @click="toggle(p.name)"
            >
              <div class="parser-row">
                <el-checkbox :model-value="isActive(p.name)" @click.stop @change="toggle(p.name)" />
                <div class="parser-info">
                  <div class="parser-name">
                    {{ p.name }}
                    <el-tag v-if="p.is_default" size="small" type="warning">兜底</el-tag>
                  </div>
                  <div class="parser-desc">{{ p.description }}</div>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>

      <!-- 右:激活顺序 -->
      <el-col :xs="24" :sm="24" :md="14" :lg="14" :xl="14">
        <el-card body-style="padding: 12px">
          <template #header>
            <strong>已启用顺序</strong>
            <span class="hint">从上到下依次执行</span>
          </template>
          <div v-if="active.length === 0" class="empty-active">
            还没启用任何解析器(系统会自动用 default 兜底)
          </div>
          <div v-else class="active-list">
            <div v-for="(name, idx) in active" :key="name" class="active-item">
              <span class="seq-num">{{ idx + 1 }}</span>
              <div class="active-info">
                <div class="active-name">{{ name }}</div>
                <div class="active-desc">{{ findInfo(name).description }}</div>
              </div>
              <div class="active-ops">
                <el-button
                  size="small"
                  :icon="ArrowUp"
                  :disabled="idx === 0"
                  @click="moveUp(idx)"
                />
                <el-button
                  size="small"
                  :icon="ArrowDown"
                  :disabled="idx === active.length - 1"
                  @click="moveDown(idx)"
                />
                <el-button
                  size="small"
                  type="danger"
                  :disabled="name === 'default'"
                  @click="toggle(name)"
                >
                  禁用
                </el-button>
              </div>
            </div>
          </div>
          <div class="save-bar">
            <el-button type="primary" :loading="saving" @click="save">
              保存配置
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 在线测试 -->
    <el-card class="mt-16" body-style="padding: 16px">
      <template #header>
        <strong>在线测试</strong>
        <span class="hint">输入文件名,看解析效果(不会写库)</span>
      </template>
      <div class="test-bar">
        <el-input
          v-model="testInput"
          placeholder="输入文件名,例如:Inception.2010.1080p.BluRay.x264-GROUP.mp4"
          @keyup.enter="runTest"
        />
        <el-button type="primary" :loading="testing" @click="runTest">
          解析
        </el-button>
      </div>
      <el-descriptions v-if="testResult" :column="2" class="mt-12" border>
        <el-descriptions-item label="标题">
          <strong style="color: #16a34a">{{ testResult.title }}</strong>
        </el-descriptions-item>
        <el-descriptions-item label="规范化(去重用)">
          <code>{{ testResult.normalized_title }}</code>
        </el-descriptions-item>
        <el-descriptions-item label="年份">{{ testResult.year ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="季 / 集">
          {{ testResult.season ?? '-' }} / {{ testResult.episode ?? '-' }}
        </el-descriptions-item>
        <el-descriptions-item label="清晰度">{{ testResult.quality ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="发布组">{{ testResult.release_group ?? '-' }}</el-descriptions-item>
        <el-descriptions-item label="语言标记" :span="2">
          <el-tag
            v-for="t in testResult.language_tags"
            :key="t"
            size="small"
            style="margin-right: 4px"
          >{{ t }}</el-tag>
          <span v-if="testResult.language_tags.length === 0" class="hint">无</span>
        </el-descriptions-item>
        <el-descriptions-item label="经过的解析器" :span="2">
          <el-tag
            v-for="p in testResult.pipeline"
            :key="p"
            size="small"
            type="info"
            style="margin-right: 4px"
          >{{ p }}</el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-card>
  </div>
</template>

<style scoped>
.parsers-tab {
  display: flex;
  flex-direction: column;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.section-title {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
}
.actions {
  display: flex;
  gap: 8px;
}
.hint {
  margin-left: 8px;
  font-size: 12px;
  color: #9ca3af;
  font-weight: normal;
}
.parser-list,
.active-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.parser-item {
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 8px 12px;
  cursor: pointer;
  transition: all 0.15s;
}
.parser-item:hover {
  border-color: #3b82f6;
}
.parser-item.active {
  background: #eff6ff;
  border-color: #3b82f6;
}
.parser-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.parser-info {
  flex: 1;
}
.parser-name {
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 6px;
}
.parser-desc {
  font-size: 12px;
  color: #6b7280;
  margin-top: 2px;
}
.active-item {
  border: 1px solid #d1d5db;
  border-radius: 6px;
  padding: 8px 12px;
  display: flex;
  align-items: center;
  gap: 12px;
  background: #f9fafb;
}
.seq-num {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: #3b82f6;
  color: white;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
}
.active-info {
  flex: 1;
}
.active-name {
  font-weight: 500;
}
.active-desc {
  font-size: 12px;
  color: #6b7280;
}
.active-ops {
  display: flex;
  gap: 4px;
}
.empty-active {
  text-align: center;
  color: #9ca3af;
  padding: 24px;
}
.save-bar {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
}
.mt-12 {
  margin-top: 12px;
}
.mt-16 {
  margin-top: 16px;
}
.test-bar {
  display: flex;
  gap: 8px;
}
code {
  background: #f3f4f6;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 13px;
}
</style>

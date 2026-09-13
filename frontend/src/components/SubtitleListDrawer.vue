<script setup lang="ts">
/**
 * 字幕明细抽屉
 *
 * 以右侧抽屉展示当前播放器"正在使用"的字幕轨道的全部字幕行(时间+文本),
 * 每行有"跳转"按钮,点击后 emit jump 事件,由父组件(PlayerDialog)执行
 * player.currentTime = 时间点。
 *
 * 数据来源:直接读 Artplayer 暴露的 `player.subtitle.cues`(VTTCue[])。
 * Artplayer 内部已经把 srt/ass 转换成 vtt 并塞进标准 <track>,浏览器原生
 * TextTrack 解析出的 cues 就是这里展示的数据,不需要自己解析字幕文件。
 *
 * 注意:
 * - 只能展示"当前已加载到播放器"的字幕轨道,不是任意字幕文件都能查看
 *   (如果需要查看未激活字幕的内容,需要额外拉取字幕原文并解析,当前不支持)。
 * - 字幕切换是异步的,父组件需要在 subtitleLoad 事件后重新传入最新 cues。
 *
 * 父组件用法:
 *   <SubtitleListDrawer
 *     v-model="drawerOpen"
 *     :cues="subtitleCues"
 *     :active-name="activeSubtitleName"
 *     :current-time="curT"
 *     @jump="onJump"
 *   />
 */
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Position, Notebook } from '@element-plus/icons-vue'
import { formatSeconds } from '@/utils/time'

interface Props {
  modelValue: boolean
  /** 当前字幕轨道的全部 cue(来自 player.subtitle.cues) */
  cues: VTTCue[]
  /** 当前字幕的显示名称(语言/文件名),仅用于标题展示 */
  activeName?: string
  /** 当前播放时间(秒),用于高亮"正在播放"的这一行 */
  currentTime?: number
  size?: string | number
}
const props = withDefaults(defineProps<Props>(), {
  size: '380px',
  currentTime: 0,
})

const emit = defineEmits<{
  'update:modelValue': [boolean]
  /** 点击某一行的"跳转",参数是 cue.startTime(秒) */
  jump: [number]
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

// 按开始时间升序展示(标准 TextTrackCueList 本身已经是按时间排好的,这里
// 转成数组顺便兜底,避免上游传入顺序异常)
const sortedCues = computed(() =>
  [...props.cues].sort((a, b) => a.startTime - b.startTime),
)

const isActive = (cue: VTTCue) =>
  props.currentTime >= cue.startTime && props.currentTime < cue.endTime

const onJump = (cue: VTTCue) => {
  emit('jump', cue.startTime)
  ElMessage.success(`跳转到 ${formatSeconds(cue.startTime)}`)
}
</script>

<template>
  <el-drawer
    v-model="visible"
    direction="rtl"
    :size="size"
    :with-header="false"
    class="subtitle-list-drawer"
  >
    <div class="drawer-inner">
      <div class="drawer-header">
        <div class="title">
          <el-icon><Notebook /></el-icon>
          <span>字幕明细 ({{ sortedCues.length }})</span>
        </div>
        <span v-if="activeName" class="active-name" :title="activeName">{{ activeName }}</span>
      </div>

      <div class="drawer-body">
        <el-empty
          v-if="sortedCues.length === 0"
          description="当前没有已加载的字幕,或该字幕没有任何内容"
        />

        <div
          v-for="(cue, idx) in sortedCues"
          :key="idx"
          class="cue-card"
          :class="{ active: isActive(cue) }"
        >
          <el-button
            size="small"
            type="primary"
            :icon="Position"
            class="cue-time"
            @click="onJump(cue)"
          >
            {{ formatSeconds(cue.startTime) }}
          </el-button>
          <div class="cue-text">{{ cue.text }}</div>
        </div>
      </div>
    </div>
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
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid #e5e7eb;
}
.title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 15px;
  flex-shrink: 0;
}
.active-name {
  font-size: 12px;
  color: #6b7280;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: 12px 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.cue-card {
  background: #f9fafb;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  padding: 8px 10px;
  display: flex;
  align-items: flex-start;
  gap: 10px;
}
.cue-card.active {
  background: #eff6ff;
  border-color: #3b82f6;
}
.cue-time {
  flex-shrink: 0;
  margin-top: 1px;
}
.cue-text {
  flex: 1;
  font-size: 13px;
  line-height: 1.5;
  color: #1f2937;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 移动端:抽屉变全屏 */
@media (max-width: 768px) {
  .subtitle-list-drawer :deep(.el-drawer) {
    width: 100% !important;
  }
}
</style>

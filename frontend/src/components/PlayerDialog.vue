<script setup lang="ts">
/**
 * 播放器弹窗
 *
 * 设计要点:
 * - Artplayer 5.x 初始化时不传 subtitle 字段,避免类型校验错误
 * - 等播放器 ready 后再用 player.subtitle.switch() 加载字幕
 * - HLS 通过 customType 注入 hls.js
 * - 续播位置在 ready 事件中跳转
 * - 进度每 5s 防抖上报,关闭时上报一次
 */
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import Artplayer from 'artplayer'
import Hls from 'hls.js'
import { ElMessage } from 'element-plus'
import { filesApi, type SubtitleInfo } from '@/api/files'
import { playbackApi } from '@/api/playback'

interface Props {
  modelValue: boolean
  mediaId: number
  fileAssetId: number
  filename?: string
  durationHint?: number
}

const props = defineProps<Props>()
const emit = defineEmits<{ 'update:modelValue': [boolean] }>()

const visible = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})

const containerRef = ref<HTMLDivElement | null>(null)
const loading = ref(false)
const errorMsg = ref('')
const subtitles = ref<SubtitleInfo[]>([])
const activeSubId = ref<number | null>(null)

let player: Artplayer | null = null
let hls: Hls | null = null
let progressTimer: number | null = null
let lastReportedPosition = -1

const cleanup = () => {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
  if (hls) {
    try {
      hls.destroy()
    } catch {
      /* ignore */
    }
    hls = null
  }
  if (player) {
    try {
      player.destroy(false)
    } catch {
      /* ignore */
    }
    player = null
  }
  lastReportedPosition = -1
  activeSubId.value = null
}

const reportProgress = async (completed = false) => {
  if (!player) return
  const pos = player.currentTime
  const dur = player.duration || props.durationHint
  if (!completed && Math.abs(pos - lastReportedPosition) < 5) return
  try {
    await playbackApi.reportProgress({
      media_item_id: props.mediaId,
      file_asset_id: props.fileAssetId,
      position_seconds: pos,
      duration_seconds: dur && Number.isFinite(dur) ? dur : undefined,
      completed,
    })
    lastReportedPosition = pos
  } catch {
    /* 静默失败 */
  }
}

const setupPlayer = async () => {
  if (!containerRef.value) {
    console.warn('[PlayerDialog] container not ready')
    return
  }
  loading.value = true
  errorMsg.value = ''

  try {
    // 1. 拿带签名的 stream URL
    const tokenResp = await filesApi.streamToken(props.fileAssetId)
    const streamUrl = tokenResp.url
    console.log('[PlayerDialog] stream URL:', streamUrl)

    // 2. 拿同名字幕(失败不阻塞播放)
    let subList: SubtitleInfo[] = []
    try {
      subList = await filesApi.subtitles(props.fileAssetId)
    } catch {
      /* ignore */
    }
    subtitles.value = subList

    // 3. 拿续播位置
    let resumePos = 0
    try {
      const r = await playbackApi.getResume(props.mediaId, props.fileAssetId)
      resumePos = r.position_seconds || 0
    } catch {
      /* ignore */
    }

    // 4. 初始化 Artplayer (不传 subtitle,后续用 switch 加载)
    const isHls = streamUrl.includes('.m3u8')

    // Artplayer 5.x 对 undefined 字段也会做类型校验,需要按需构造 options
    const options: any = {
      container: containerRef.value,
      url: streamUrl,
      volume: 0.8,
      autoplay: false,
      pip: true,
      autoSize: false,
      autoMini: false,
      screenshot: true,
      setting: true,
      loop: false,
      flip: true,
      playbackRate: true,
      aspectRatio: true,
      fullscreen: true,
      fullscreenWeb: true,
      subtitleOffset: true,
      miniProgressBar: true,
      mutex: true,
      backdrop: true,
      playsInline: true,
      airplay: true,
      theme: '#3b82f6',
    }

    if (isHls) {
      options.type = 'm3u8'
      options.customType = {
        m3u8: (video: HTMLMediaElement, url: string) => {
          if (Hls.isSupported()) {
            hls = new Hls({ debug: false })
            hls.loadSource(url)
            hls.attachMedia(video)
          } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
            video.src = url
          } else {
            ElMessage.error('当前浏览器不支持 HLS 播放')
          }
        },
      }
    }

    player = new Artplayer(options)

    // 5. ready 后处理字幕和续播
    player.on('ready', async () => {
      // 续播跳转
      if (
        resumePos > 5 &&
        player!.duration > 0 &&
        resumePos < player!.duration - 5
      ) {
        player!.currentTime = resumePos
        ElMessage.info(`已跳转到上次位置 ${formatTime(resumePos)}`)
      }

      // 自动加载第一个字幕轨道
      const defaultSub =
        subList.find((s) => s.extension === '.vtt') || subList[0] || null
      if (defaultSub && player) {
        await loadSubtitle(defaultSub)
      }
    })

    // 6. 事件监听
    player.on('video:ended', () => reportProgress(true))
    player.on('pause', () => reportProgress(false))

    progressTimer = window.setInterval(() => {
      if (player && player.video && !player.video.paused) {
        reportProgress(false)
      }
    }, 15000)
  } catch (e: any) {
    console.error('[PlayerDialog] init error:', e)
    errorMsg.value = e?.message || '播放器初始化失败'
    cleanup()
  } finally {
    loading.value = false
  }
}

const loadSubtitle = async (sub: SubtitleInfo) => {
  if (!player) return
  try {
    const t = await filesApi.streamToken(sub.id)
    const ext = (sub.extension || '.srt').replace(/^\./, '') || 'srt'
    // Artplayer 5.x:第二个参数是 options 对象
    player.subtitle.switch(t.url, {
      type: ext,
      name: sub.language_hint || sub.filename,
      escape: true,
    })
    activeSubId.value = sub.id
  } catch (e) {
    console.warn('[PlayerDialog] subtitle load failed:', e)
  }
}

const formatTime = (s: number) => {
  if (!s || !Number.isFinite(s)) return '0:00'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  return h > 0
    ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
    : `${m}:${String(sec).padStart(2, '0')}`
}

const closeSubtitle = () => {
  if (player?.subtitle) {
    player.subtitle.show = false
    activeSubId.value = null
  }
}

watch(
  () => props.modelValue,
  async (open) => {
    if (!open) {
      await reportProgress(false)
      cleanup()
    }
    // 打开时由 dialog 的 @opened 触发,不在这里初始化
  },
)

const onDialogOpened = async () => {
  await nextTick()
  if (props.modelValue && !player) {
    await setupPlayer()
  }
}

onBeforeUnmount(() => {
  reportProgress(false)
  cleanup()
})
</script>

<template>
  <el-dialog
    v-model="visible"
    :title="filename || '播放器'"
    width="80%"
    top="5vh"
    destroy-on-close
    align-center
    @opened="onDialogOpened"
    @close="cleanup"
  >
    <div v-loading="loading" class="player-wrap">
      <el-alert v-if="errorMsg" type="error" :title="errorMsg" :closable="false" />
      <div ref="containerRef" class="player" />

      <div v-if="subtitles.length > 0" class="sub-bar">
        <span class="label">字幕:</span>
        <el-button size="small" :type="activeSubId === null ? 'primary' : ''" @click="closeSubtitle">
          关闭
        </el-button>
        <el-button
          v-for="s in subtitles"
          :key="s.id"
          size="small"
          :type="activeSubId === s.id ? 'primary' : ''"
          @click="loadSubtitle(s)"
        >
          {{ s.language_hint || s.filename }}
        </el-button>
      </div>
    </div>
  </el-dialog>
</template>

<style scoped>
.player-wrap {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.player {
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #000;
  border-radius: 4px;
  overflow: hidden;
}
.sub-bar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.label {
  font-size: 13px;
  color: #6b7280;
}
</style>

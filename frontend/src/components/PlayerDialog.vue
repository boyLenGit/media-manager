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
import { ElMessage, ElMessageBox } from 'element-plus'
import { Upload, Delete } from '@element-plus/icons-vue'
import { customSubtitlesApi, filesApi, type SubtitleInfo } from '@/api/files'
import { playbackApi } from '@/api/playback'
import BookmarkDrawer from './BookmarkDrawer.vue'

interface Props {
  modelValue: boolean
  mediaId: number
  fileAssetId: number
  filename?: string
  durationHint?: number
  /** 播放器打开时直接跳到的位置(秒)。优先于 resume position。 */
  initialSeek?: number
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
const subtitleInput = ref<HTMLInputElement | null>(null)
const uploadingSubtitle = ref(false)

// 书签抽屉
const bookmarkDrawerOpen = ref(false)
// 当前播放时间(秒) — 用于打开抽屉时给"在当前位置添加"按钮提供初值
const currentTime = ref(0)

let player: Artplayer | null = null
let hls: Hls | null = null
let progressTimer: number | null = null
let lastReportedPosition = -1
let keydownHandler: ((e: KeyboardEvent) => void) | null = null

const onJumpTo = (sec: number) => {
  if (player && Number.isFinite(sec)) {
    player.currentTime = sec
    if (player.video?.paused) {
      try {
        player.play()
      } catch {
        /* ignore */
      }
    }
  }
}

const openBookmarks = () => {
  if (player) {
    currentTime.value = player.currentTime || 0
    // 抽屉默认 append 到 body,在浏览器全屏元素之外会不可见。
    // 简单稳妥的做法:打开抽屉时退出全屏,让 dialog + drawer 走正常 DOM。
    try {
      if (player.fullscreen) player.fullscreen = false
      if (player.fullscreenWeb) player.fullscreenWeb = false
    } catch {
      /* ignore */
    }
  }
  bookmarkDrawerOpen.value = true
}

const cleanup = () => {
  if (progressTimer) {
    clearInterval(progressTimer)
    progressTimer = null
  }
  if (keydownHandler) {
    window.removeEventListener('keydown', keydownHandler, true)
    keydownHandler = null
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

    // 3. 拿续播位置(initialSeek 优先)
    let resumePos = 0
    if (props.initialSeek && Number.isFinite(props.initialSeek) && props.initialSeek > 0) {
      resumePos = props.initialSeek
    } else {
      try {
        const r = await playbackApi.getResume(props.mediaId, props.fileAssetId)
        resumePos = r.position_seconds || 0
      } catch {
        /* ignore */
      }
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
      // 自定义控件:在控件栏右侧加一个"书签"按钮
      // 这样无论是否全屏都能打开书签抽屉
      controls: [
        {
          name: 'bookmark',
          position: 'right',
          tooltip: '书签',
          html: `
            <div style="display:flex;align-items:center;justify-content:center;width:36px;height:100%;cursor:pointer;color:#fff;">
              <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true">
                <path d="M6 3a2 2 0 0 0-2 2v16l8-4 8 4V5a2 2 0 0 0-2-2H6Z"/>
              </svg>
            </div>
          `,
          click: () => openBookmarks(),
        },
      ],
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

    // 注册全局键盘快捷键 (capture 阶段)
    // dialog 容器吞掉按键事件,所以走 capture 在到达 dialog 之前接管
    // 同时把 player.isFocus 主动置 true,确保 artplayer 内置 hotkey 也生效
    keydownHandler = (e: KeyboardEvent) => {
      if (!player || !visible.value) return
      // 输入框 / 文本域 内不拦截
      const tag = (document.activeElement?.tagName || '').toUpperCase()
      const editable = (document.activeElement as HTMLElement | null)?.getAttribute(
        'contenteditable',
      )
      if (tag === 'INPUT' || tag === 'TEXTAREA' || editable === 'true' || editable === '') return
      if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return

      const SEEK = 5
      switch (e.key) {
        case 'ArrowLeft':
          e.preventDefault()
          e.stopPropagation()
          try {
            player.backward = SEEK
          } catch {
            /* ignore */
          }
          break
        case 'ArrowRight':
          e.preventDefault()
          e.stopPropagation()
          try {
            player.forward = SEEK
          } catch {
            /* ignore */
          }
          break
        case 'ArrowUp':
          e.preventDefault()
          e.stopPropagation()
          try {
            player.volume = Math.min(1, (player.volume || 0) + 0.1)
          } catch {
            /* ignore */
          }
          break
        case 'ArrowDown':
          e.preventDefault()
          e.stopPropagation()
          try {
            player.volume = Math.max(0, (player.volume || 0) - 0.1)
          } catch {
            /* ignore */
          }
          break
        case ' ':
        case 'Spacebar': // legacy
          e.preventDefault()
          e.stopPropagation()
          try {
            player.toggle()
          } catch {
            /* ignore */
          }
          break
      }
    }
    // capture: true,优先级最高,先于 el-dialog 默认事件
    window.addEventListener('keydown', keydownHandler, true)

    // 5. ready 后处理字幕和续播
    player.on('ready', async () => {
      // 跳转(续播 / 书签)
      if (
        resumePos > 1 &&
        player!.duration > 0 &&
        resumePos < player!.duration - 1
      ) {
        player!.currentTime = resumePos
        const isInitial = props.initialSeek && Math.abs(resumePos - props.initialSeek) < 0.1
        ElMessage.info(
          isInitial
            ? `跳转到书签 ${formatTime(resumePos)}`
            : `已跳转到上次位置 ${formatTime(resumePos)}`,
        )
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
    // 自定义上传字幕(custom_subtitle 表)和自动匹配字幕(file_asset 表)是两套独立 id 空间,
    // 换取签名 URL 要走各自对应的 token 接口
    const t =
      sub.source === 'custom'
        ? await customSubtitlesApi.streamToken(sub.id)
        : await filesApi.streamToken(sub.id)
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

const triggerSubtitlePick = () => subtitleInput.value?.click()

const onSubtitlePicked = async (ev: Event) => {
  const input = ev.target as HTMLInputElement
  const file = input.files?.[0]
  input.value = ''
  if (!file) return
  uploadingSubtitle.value = true
  try {
    await customSubtitlesApi.upload(props.fileAssetId, file)
    ElMessage.success('字幕已上传')
    // 重新拉取字幕列表(新上传的排最前),并自动切换到它
    const list = await filesApi.subtitles(props.fileAssetId)
    subtitles.value = list
    const newest = list.find((s) => s.source === 'custom')
    if (newest && player) await loadSubtitle(newest)
  } catch (e: any) {
    const detail = e?.response?.data?.detail
    if (detail === 'unsupported_subtitle_type') ElMessage.error('仅支持 srt/ass/ssa/vtt 格式')
    else if (detail === 'file_too_large') ElMessage.error('字幕文件超过 5MB 限制')
    else ElMessage.error('上传失败')
  } finally {
    uploadingSubtitle.value = false
  }
}

const removeCustomSubtitle = async (sub: SubtitleInfo, ev: Event) => {
  ev.stopPropagation()
  try {
    await ElMessageBox.confirm(`删除字幕「${sub.language_hint || sub.filename}」?`, '确认', {
      type: 'warning',
    })
  } catch {
    return
  }
  await customSubtitlesApi.remove(sub.id)
  if (activeSubId.value === sub.id) closeSubtitle()
  subtitles.value = await filesApi.subtitles(props.fileAssetId)
  ElMessage.success('已删除')
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

      <div class="sub-bar">
        <span class="label">字幕:</span>
        <template v-if="subtitles.length > 0">
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
            <el-icon
              v-if="s.source === 'custom'"
              class="sub-remove"
              @click="(e: Event) => removeCustomSubtitle(s, e)"
            >
              <Delete />
            </el-icon>
          </el-button>
        </template>
        <input
          ref="subtitleInput"
          type="file"
          accept=".srt,.ass,.ssa,.vtt"
          style="display: none"
          @change="onSubtitlePicked"
        />
        <el-button size="small" :icon="Upload" :loading="uploadingSubtitle" @click="triggerSubtitlePick">
          上传字幕
        </el-button>
      </div>
    </div>

    <BookmarkDrawer
      v-model="bookmarkDrawerOpen"
      :media-id="mediaId"
      :file-asset-id="fileAssetId"
      :current-time="currentTime"
      @jump="onJumpTo"
    />
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
.sub-remove {
  margin-left: 4px;
  cursor: pointer;
}
.sub-remove:hover {
  color: #ef4444;
}
</style>

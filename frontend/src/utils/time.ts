/**
 * 秒数 <-> 时长文本 格式化工具。
 *
 * 之前 PlayerDialog.vue 和 BookmarkDrawer.vue 里各自复制了一份完全相同的
 * formatTime 实现,这里抽成共享函数,新增字幕明细面板也复用这一份。
 */

/** 秒数格式化为 mm:ss 或 h:mm:ss(小于1小时不显示小时位)。 */
export function formatSeconds(s: number): string {
  if (!s || !Number.isFinite(s)) return '0:00'
  const h = Math.floor(s / 3600)
  const m = Math.floor((s % 3600) / 60)
  const sec = Math.floor(s % 60)
  return h > 0
    ? `${h}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
    : `${m}:${String(sec).padStart(2, '0')}`
}

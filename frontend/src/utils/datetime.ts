/**
 * 统一的时间格式化工具。
 *
 * 背景:后端历史上部分接口对不带时区的 UTC 时间字符串,忘记补 "Z"/"+00:00" 后缀,
 * 导致浏览器 `new Date(s)` 把它当成"本地时间"直接解析,显示值比真实时间偏移了
 * "本地时区与 UTC 的时差"(比如东八区偏移 8 小时)。
 *
 * 后端已经在模型层(UTCAwareModel)统一修复了这个问题,新的响应都会带时区标记。
 * 这里的 normalize 仍保留作为双重保险 —— 万一某个接口/字段漏改,或历史缓存数据里
 * 还有不带时区标记的字符串,前端也能正确兜底显示,而不是静默显示错误时间。
 */

// 已经带时区信息的 ISO 字符串:以 Z 结尾,或末尾有 +HH:MM / -HH:MM 偏移
const HAS_TZ_RE = /(Z|[+-]\d{2}:?\d{2})$/

/**
 * 把后端返回的时间字符串安全地转成 Date 对象。
 * 若字符串看起来是不带时区标记的 ISO 格式,视为 UTC(补 Z 后再解析)。
 */
export function toDate(value: string): Date {
  const normalized = HAS_TZ_RE.test(value) ? value : `${value}Z`
  return new Date(normalized)
}

/** 格式化为本地日期+时间,如 2026/8/21 15:07:19 */
export function formatDateTime(value?: string | null): string {
  if (!value) return '-'
  const d = toDate(value)
  if (Number.isNaN(d.getTime())) return '-'
  return d.toLocaleString()
}

/** 格式化为本地日期,如 2026/8/21 */
export function formatDate(value?: string | null): string {
  if (!value) return '-'
  const d = toDate(value)
  if (Number.isNaN(d.getTime())) return '-'
  return d.toLocaleDateString()
}

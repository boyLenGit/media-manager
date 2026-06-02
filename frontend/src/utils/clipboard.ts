/**
 * 跨场景剪贴板复制。
 *
 * 浏览器 `navigator.clipboard.writeText()` 仅在 secure context(HTTPS / localhost)可用。
 * 对家用 NAS 这种通常 HTTP 局域网部署,会直接抛 NotAllowedError 或同源异常。
 *
 * 这里提供两套实现,自动降级:
 *   1. 优先 navigator.clipboard.writeText(短路径,HTTPS / localhost 下用)
 *   2. 失败则用经典的 document.execCommand('copy') + 临时 textarea
 *
 * 第二种方法在所有现代浏览器(包括 HTTP 页)都可用,前提是触发它的事件
 * 是用户手势(点击 / 键盘),所以本工具必须在 click handler 内同步调用。
 *
 * 使用:
 *   import { copyText } from '@/utils/clipboard'
 *   const ok = await copyText('hello')
 *   if (ok) ElMessage.success('已复制') else ElMessage.error('复制失败')
 */

export async function copyText(text: string): Promise<boolean> {
  if (!text) return false

  // 路径 1: secure context + clipboard API
  if (
    typeof navigator !== 'undefined' &&
    navigator.clipboard &&
    typeof navigator.clipboard.writeText === 'function' &&
    window.isSecureContext
  ) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // 落到 fallback
    }
  }

  // 路径 2: execCommand 兜底(HTTP 局域网下唯一选择)
  try {
    const ta = document.createElement('textarea')
    ta.value = text
    // 防滚动 / 防可见
    ta.style.position = 'fixed'
    ta.style.top = '0'
    ta.style.left = '0'
    ta.style.opacity = '0'
    ta.style.pointerEvents = 'none'
    ta.setAttribute('readonly', '')
    document.body.appendChild(ta)
    ta.select()
    ta.setSelectionRange(0, text.length)
    const ok = document.execCommand('copy')
    document.body.removeChild(ta)
    return ok
  } catch {
    return false
  }
}

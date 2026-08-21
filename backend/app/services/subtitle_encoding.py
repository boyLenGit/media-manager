"""字幕文件编码自适应转换。

背景:
- 浏览器 <track> 标签(及 Artplayer 内置的 SRT/ASS 转 VTT 逻辑)固定用 UTF-8 解码字幕文件。
- 大量老字幕组 / Windows 工具导出的 .srt/.ass 实际是 GBK/Big5/Shift-JIS 等编码,
  用 UTF-8 解码不会报错,只会静默产生乱码(替换字符 U+FFFD),用户无法感知问题所在。

方案:
- 后端在返回字幕内容前,自动检测源编码并统一转成 UTF-8,前端/浏览器侧不用做任何改动。
- 检测策略(按优先级,越靠前越可靠/越快):
  1. 严格 UTF-8(含 BOM)解码 —— 现代字幕最常见,命中即返回,不做额外检测
  2. charset-normalizer 统计模型检测(能可靠区分 GBK/Big5/Shift-JIS/EUC-KR 等,
     比"依次硬解码候选编码列表"更准确 —— GB18030 对乱码字节的解码"过于宽容",
     会把 Big5/Shift-JIS 字节错误地解码成看似合法但实际是乱码的字符,顺序硬解码方案
     无法可靠避开这个陷阱)
  3. 全部失败:用 utf-8 + errors=replace 兜底,不让请求 500(保留现有行为,不劣化)
"""
from charset_normalizer import from_bytes


def normalize_subtitle_to_utf8(data: bytes) -> bytes:
    """把任意编码的字幕文件字节流,统一转换成 UTF-8 编码的字节流。

    对已经是 UTF-8 的内容,原样返回(BOM 会被剥离,不影响播放器解析)。
    """
    if not data:
        return data

    # 1. 严格 UTF-8(含 BOM),最常见场景,直接命中,不跑检测器(省 CPU)
    try:
        text = data.decode("utf-8-sig", errors="strict")
        return text.encode("utf-8")
    except UnicodeDecodeError:
        pass

    # 2. 统计模型自动检测编码(样本量小于几十字节时可能不准,但字幕文件通常足够大)
    try:
        result = from_bytes(data).best()
    except Exception:
        result = None

    if result is not None:
        try:
            return str(result).encode("utf-8")
        except Exception:
            pass

    # 3. 兜底:不让请求失败,尽量显示,乱码字符仅限无法识别的极端情况
    return data.decode("utf-8", errors="replace").encode("utf-8")

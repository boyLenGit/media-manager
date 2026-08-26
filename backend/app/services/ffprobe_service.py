"""ffmpeg / ffprobe 媒体处理服务。

提供:
- 启动检查 ffprobe / ffmpeg 是否可用
- probe(): 探测媒体编码/分辨率/时长 → MediaProbe
- generate_thumbnail(): 用 ffmpeg 抽某一秒的帧生成 jpg 缩略图

设计:可选依赖,缺失时所有函数返回 None,扫描流程不阻塞。
"""
import asyncio
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_ffprobe_path: str | None = None
_ffmpeg_path: str | None = None
_checked = False


@dataclass
class MediaProbe:
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    video_codec: str | None = None  # ffprobe 标准化的 codec_name (如 h264 / hevc / mpeg4 / av1)
    audio_codec: str | None = None
    container: str | None = None
    raw_json: str | None = None


def check_tools() -> bool:
    """启动时调用,日志告警,不抛异常。返回 ffprobe 是否可用。"""
    global _ffprobe_path, _ffmpeg_path, _checked
    _checked = True
    _ffprobe_path = shutil.which("ffprobe")
    _ffmpeg_path = shutil.which("ffmpeg")

    if _ffprobe_path:
        logger.info("ffprobe found: %s", _ffprobe_path)
    else:
        logger.warning(
            "ffprobe not found. Media probing disabled. "
            "Install: brew install ffmpeg / apt install ffmpeg"
        )

    if _ffmpeg_path:
        logger.info("ffmpeg found: %s", _ffmpeg_path)
    else:
        logger.warning(
            "ffmpeg not found. Thumbnail generation disabled. "
            "Install: brew install ffmpeg / apt install ffmpeg"
        )
    return _ffprobe_path is not None


# 兼容旧名字(main.py 还可能用)
check_ffprobe = check_tools


def is_available() -> bool:
    if not _checked:
        check_tools()
    return _ffprobe_path is not None


def is_ffmpeg_available() -> bool:
    if not _checked:
        check_tools()
    return _ffmpeg_path is not None


# ============================================================
# 探测
# ============================================================
async def probe(path: str | Path, timeout: float = 10.0) -> MediaProbe | None:
    if not is_available():
        return None

    cmd = [
        _ffprobe_path,  # type: ignore[list-item]
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        stdout, _stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode != 0:
            return None
        data = json.loads(stdout.decode("utf-8"))
        return _parse(data)
    except (asyncio.TimeoutError, json.JSONDecodeError, OSError) as e:
        logger.debug("ffprobe failed for %s: %s", path, e)
        return None


def _parse(data: dict) -> MediaProbe:
    fmt = data.get("format", {}) or {}
    duration = fmt.get("duration")
    container = fmt.get("format_name")

    width = height = None
    video_codec = audio_codec = None
    for s in data.get("streams", []) or []:
        if s.get("codec_type") == "video" and width is None:
            width = s.get("width")
            height = s.get("height")
            video_codec = (s.get("codec_name") or "").lower() or None
        elif s.get("codec_type") == "audio" and audio_codec is None:
            audio_codec = (s.get("codec_name") or "").lower() or None

    return MediaProbe(
        duration_seconds=float(duration) if duration else None,
        width=width,
        height=height,
        video_codec=video_codec,
        audio_codec=audio_codec,
        container=container,
        raw_json=json.dumps(data, ensure_ascii=False, separators=(",", ":")),
    )


# ============================================================
# 缩略图
# ============================================================
async def generate_thumbnail(
    video_path: str | Path,
    output_path: str | Path,
    seek_seconds: float = 5.0,
    max_height: int = 480,
    quality: int = 5,  # 2 (best) - 31 (worst)
    timeout: float = 30.0,
) -> bool:
    """用 ffmpeg 在指定秒数抽一帧,生成 JPEG 缩略图。

    - seek 用 -ss 放在 -i 之前以走快速 seek (索引粒度可能不准但够用)
    - max_height 控制最大高度,等比缩放
    - 失败返回 False
    """
    if not is_ffmpeg_available():
        return False

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        _ffmpeg_path,  # type: ignore[list-item]
        "-y",  # 覆盖
        "-ss",
        str(seek_seconds),
        "-i",
        str(video_path),
        "-vframes",
        "1",
        "-vf",
        f"scale=-2:{max_height}:flags=lanczos",  # -2 保证宽度为偶数
        "-q:v",
        str(quality),
        "-loglevel",
        "error",
        str(output),
    ]
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
        )
        _stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        if proc.returncode == 0 and output.exists() and output.stat().st_size > 0:
            return True
        # 可能 seek 超过视频长度,fallback 到第 1 秒重试一次
        if seek_seconds > 1:
            logger.debug(
                "thumbnail seek=%s failed, retry seek=1: %s", seek_seconds, stderr[:200]
            )
            return await generate_thumbnail(
                video_path, output_path, seek_seconds=1, max_height=max_height, quality=quality
            )
        logger.debug("thumbnail failed for %s: %s", video_path, stderr[:200])
        return False
    except (asyncio.TimeoutError, OSError) as e:
        logger.debug("thumbnail subprocess error: %s", e)
        return False


# ============================================================
# 浏览器可播性判断
# ============================================================
# 浏览器主流编码支持矩阵 (以 Chrome / Edge / Firefox 为基准):
# - h264 (AVC):全员支持 ✅
# - vp8 / vp9:全员支持 ✅
# - av1:Chrome 70+ 支持,Firefox 100+ 支持
# - hevc (h265):Safari 支持,Chrome 11.x+ 部分支持(系统硬件解码),Firefox 不支持
# - mpeg4 (Part 2,Xvid/DivX 时代):全员不支持 ❌
# - mpeg2:全员不支持
# - vc1 / wmv:不支持
WEB_PLAYABLE_VIDEO_CODECS = {
    "h264",
    "avc",
    "avc1",
    "vp8",
    "vp9",
    "av1",
    "av01",
    # hevc 不在此列 —— 它是否可播完全取决于用户浏览器/系统/是否装了解码
    # 扩展,服务端无法确定,归到下面的 BROWSER_DEPENDENT 类别,交给浏览器
    # 自己用 canPlayType 探测 + 播放失败时前端兜底提示。
}

# 浏览器"部分支持,取决于具体浏览器/系统"的编码:
# - Safari(含 iOS/macOS):原生硬解支持
# - Chrome/Edge(Windows):需要系统装了「HEVC 视频扩展」且硬件支持硬解才行,
#   默认大概率没装,但不是不可能
# - Firefox:基本不支持
# 之前(commit a7f8c8c)统一当作不支持,理由是"UA 嗅探不靠谱";现在改为
# "允许尝试播放 + 前端探测/失败兜底",而不是一刀切拒绝。
BROWSER_DEPENDENT_VIDEO_CODECS = {
    "hevc",
    "h265",
}

# 浏览器原生支持的容器(扩展名层级,作为快速判断的第一层)
WEB_PLAYABLE_CONTAINERS_FAST = {".mp4", ".webm", ".m4v", ".ogv"}


def is_codec_web_playable(codec: str | None) -> bool:
    if not codec:
        return False
    return codec.lower() in WEB_PLAYABLE_VIDEO_CODECS


def is_codec_browser_dependent(codec: str | None) -> bool:
    """编码是否属于"部分浏览器支持,无法在服务端确定"的类别(目前只有 HEVC)。"""
    if not codec:
        return False
    return codec.lower() in BROWSER_DEPENDENT_VIDEO_CODECS


def is_extension_potentially_playable(extension: str) -> bool:
    """扫描时还没 probe 的快速判断,只看扩展名。
    探测后用 is_codec_web_playable() 才是准确判断。
    """
    return extension.lower() in WEB_PLAYABLE_CONTAINERS_FAST

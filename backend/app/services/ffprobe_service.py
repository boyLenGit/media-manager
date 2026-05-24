"""ffprobe 媒体探测,可选依赖。

启动时检查可用性,不可用时所有探测函数返回 None,扫描流程不受影响。
"""
import asyncio
import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_ffprobe_path: str | None = None
_checked = False


@dataclass
class MediaProbe:
    duration_seconds: float | None = None
    width: int | None = None
    height: int | None = None
    video_codec: str | None = None
    audio_codec: str | None = None
    container: str | None = None
    raw_json: str | None = None


def check_ffprobe() -> bool:
    """启动时调用,检查 ffprobe 是否可用。日志告警,不抛异常。"""
    global _ffprobe_path, _checked
    _checked = True
    _ffprobe_path = shutil.which("ffprobe")
    if _ffprobe_path:
        logger.info("ffprobe found: %s", _ffprobe_path)
        return True
    logger.warning(
        "ffprobe not found in PATH. Media probing disabled. "
        "Files will still be scanned but width/height/duration will be empty. "
        "Install ffmpeg to enable: brew install ffmpeg / apt install ffmpeg"
    )
    return False


def is_available() -> bool:
    if not _checked:
        check_ffprobe()
    return _ffprobe_path is not None


async def probe(path: str | Path, timeout: float = 10.0) -> MediaProbe | None:
    """异步调用 ffprobe,返回结构化结果。失败返回 None。"""
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
            video_codec = s.get("codec_name")
        elif s.get("codec_type") == "audio" and audio_codec is None:
            audio_codec = s.get("codec_name")

    return MediaProbe(
        duration_seconds=float(duration) if duration else None,
        width=width,
        height=height,
        video_codec=video_codec,
        audio_codec=audio_codec,
        container=container,
        raw_json=json.dumps(data, ensure_ascii=False, separators=(",", ":")),
    )

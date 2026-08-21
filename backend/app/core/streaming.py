"""HTTP Range 流式响应。

参考 RFC 7233:
- 请求 Range: bytes=N-M / Range: bytes=N- / Range: bytes=-M
- 响应 206 Partial Content + Content-Range: bytes N-M/total
- 不支持 multipart/byteranges (浏览器极少用)
- 错误的 range 返回 416 Range Not Satisfiable
"""
import os
import re
import stat
from pathlib import Path
from typing import AsyncIterator

import aiofiles
from fastapi import HTTPException, Request
from starlette.responses import Response, StreamingResponse

# 默认每次读 256KB,平衡内存与吞吐
CHUNK_SIZE = 256 * 1024

# MIME 表(覆盖 mimetypes 模块未带的几个)
MIME_MAP = {
    ".mp4": "video/mp4",
    ".m4v": "video/mp4",
    ".mkv": "video/x-matroska",
    ".webm": "video/webm",
    ".avi": "video/x-msvideo",
    ".mov": "video/quicktime",
    ".ts": "video/mp2t",
    ".m2ts": "video/mp2t",
    ".flv": "video/x-flv",
    ".wmv": "video/x-ms-wmv",
    ".srt": "application/x-subrip",
    ".vtt": "text/vtt",
    ".ass": "text/x-ass",
    ".ssa": "text/x-ssa",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def guess_mime(path: str | Path) -> str:
    ext = Path(path).suffix.lower()
    return MIME_MAP.get(ext, "application/octet-stream")


_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


def parse_range_header(header: str | None, file_size: int) -> tuple[int, int] | None:
    """解析 Range 头,返回 (start, end_inclusive) 或 None。

    返回 None 表示无 Range 头(不返回 416)。
    解析失败/越界抛 416。
    """
    if not header:
        return None
    m = _RANGE_RE.match(header.strip())
    if not m:
        raise HTTPException(status_code=416, detail="invalid_range")
    start_s, end_s = m.group(1), m.group(2)

    if start_s and end_s:
        start = int(start_s)
        end = int(end_s)
    elif start_s:
        # bytes=N- → N 到末尾
        start = int(start_s)
        end = file_size - 1
    elif end_s:
        # bytes=-N → 最后 N 字节
        n = int(end_s)
        if n == 0:
            raise HTTPException(status_code=416, detail="invalid_range")
        start = max(file_size - n, 0)
        end = file_size - 1
    else:
        raise HTTPException(status_code=416, detail="invalid_range")

    if start < 0 or end >= file_size or start > end:
        raise HTTPException(
            status_code=416,
            detail="range_not_satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )
    return start, end


async def _stream_file_range(path: str, start: int, end: int) -> AsyncIterator[bytes]:
    remaining = end - start + 1
    async with aiofiles.open(path, "rb") as f:
        await f.seek(start)
        while remaining > 0:
            chunk = await f.read(min(CHUNK_SIZE, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


def make_file_response(request: Request, path: str | Path, filename: str | None = None) -> Response:
    """构造文件响应,自动处理 Range/HEAD/Last-Modified。"""
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="file_not_found")

    st = p.stat()
    file_size = st.st_size
    mime = guess_mime(p)
    last_modified = st.st_mtime

    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "private, max-age=0",
        "Last-Modified": _http_date(last_modified),
    }
    if filename:
        # inline 让浏览器尝试播放,不下载
        # RFC 5987:中文等非 latin-1 字符必须用 filename*=UTF-8'' 编码
        headers["Content-Disposition"] = _make_content_disposition(filename)

    # HEAD 请求只回头
    if request.method == "HEAD":
        headers["Content-Length"] = str(file_size)
        return Response(status_code=200, headers=headers, media_type=mime)

    range_result = parse_range_header(request.headers.get("range"), file_size)

    if range_result is None:
        # 无 Range,200 全量
        headers["Content-Length"] = str(file_size)

        async def full() -> AsyncIterator[bytes]:
            async with aiofiles.open(p, "rb") as f:
                while True:
                    chunk = await f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    yield chunk

        return StreamingResponse(full(), status_code=200, headers=headers, media_type=mime)

    start, end = range_result
    headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    headers["Content-Length"] = str(end - start + 1)
    return StreamingResponse(
        _stream_file_range(str(p), start, end),
        status_code=206,
        headers=headers,
        media_type=mime,
    )


def _http_date(ts: float) -> str:
    import time
    from email.utils import formatdate

    return formatdate(ts, usegmt=True)


def _safe_filename(name: str) -> str:
    # 简单转义,避免引号和换行
    return name.replace('"', "").replace("\n", " ").replace("\r", " ")


def _make_content_disposition(filename: str) -> str:
    """生成符合 RFC 5987 的 Content-Disposition,兼容中文等非 ASCII 文件名。

    格式:inline; filename="ascii_fallback"; filename*=UTF-8''<percent_encoded>
    """
    from urllib.parse import quote

    # ASCII 回退:把非 ASCII 字符替换为下划线,纯 latin-1 安全
    ascii_fallback = "".join(c if ord(c) < 128 else "_" for c in _safe_filename(filename))
    if not ascii_fallback.strip("_") or ascii_fallback != filename:
        # 同时给出 UTF-8 编码版本
        encoded = quote(filename, safe="")
        return f"inline; filename=\"{ascii_fallback}\"; filename*=UTF-8''{encoded}"
    return f'inline; filename="{ascii_fallback}"'


# 字幕文件按扩展名分类,走文本响应(自动编码检测转 UTF-8),不走 Range 分片
# (字幕通常几十 KB,远小于视频,分片没有意义;而且分片会破坏编码检测所需的完整样本)
SUBTITLE_TEXT_EXTENSIONS = {".srt", ".ass", ".ssa", ".vtt"}


def make_subtitle_response(path: str | Path, request: Request | None = None) -> Response:
    """构造字幕文件响应,自动检测源编码并统一转换为 UTF-8。

    与 make_file_response 分开实现的原因:
    - 字幕文件小,一次性读入内存做编码检测/转换即可,不需要 Range 分片
    - 视频走的通用二进制流式转发逻辑不应该承担"解析文本内容"的职责
    """
    from app.services.subtitle_encoding import normalize_subtitle_to_utf8

    p = Path(path)
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail="file_not_found")

    ext = p.suffix.lower()
    mime = guess_mime(p)
    content_type = f"{mime}; charset=utf-8" if ext in SUBTITLE_TEXT_EXTENSIONS else mime

    # HEAD 请求不需要真的读文件做编码转换,只回头(和 make_file_response 的 HEAD 分支行为一致)
    if request is not None and request.method == "HEAD":
        return Response(
            status_code=200,
            headers={"Cache-Control": "private, max-age=0"},
            media_type=mime,
        )

    raw = p.read_bytes()
    data = normalize_subtitle_to_utf8(raw) if ext in SUBTITLE_TEXT_EXTENSIONS else raw

    headers = {
        "Content-Length": str(len(data)),
        "Cache-Control": "private, max-age=0",
        "Content-Type": content_type,
    }
    return Response(content=data, status_code=200, headers=headers, media_type=mime)

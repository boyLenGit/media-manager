"""文件哈希工具:partial_hash 用于快速去重。

partial_hash = SHA1(头 1MB || 文件大小 || 尾 1MB)
- 不读盘整体内容,几百毫秒级
- 包含文件大小,可避免不同文件碰撞
- 对文件改名、移动不变
- 对头/尾改动敏感
"""
import hashlib
import os
from pathlib import Path

CHUNK = 1024 * 1024  # 1 MiB


def partial_hash(path: str | Path) -> str:
    p = Path(path)
    size = p.stat().st_size
    h = hashlib.sha1(usedforsecurity=False)

    with p.open("rb") as f:
        head = f.read(CHUNK)
        h.update(head)
        h.update(size.to_bytes(8, "little"))

        # 文件大于 2MB 才有「尾部」概念
        if size > 2 * CHUNK:
            f.seek(-CHUNK, os.SEEK_END)
            tail = f.read(CHUNK)
            h.update(tail)

    return h.hexdigest()


def full_sha256(path: str | Path) -> str:
    """完整 SHA256,主动调用时才执行,慢。"""
    p = Path(path)
    h = hashlib.sha256()
    with p.open("rb") as f:
        while True:
            chunk = f.read(64 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()

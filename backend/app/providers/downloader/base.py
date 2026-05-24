"""下载器适配器抽象基类。

后续可扩展:Transmission / aria2 / BitComet。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TorrentInfo:
    """下载器返回的任务信息。"""
    id: str  # 下载器侧的 ID (qB 用 info_hash)
    name: str
    info_hash: str | None = None
    save_path: str | None = None
    status: str = "unknown"  # pending/downloading/paused/completed/failed
    progress: float = 0.0  # 0-1
    download_speed: int = 0  # B/s
    upload_speed: int = 0
    eta_seconds: int | None = None
    size_bytes: int | None = None
    error_message: str | None = None
    files: list[str] | None = None


class DownloaderProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def health_check(self) -> bool: ...

    @abstractmethod
    async def add_magnet(
        self,
        magnet_uri: str,
        save_path: str | None = None,
        category: str | None = None,
    ) -> str: ...

    @abstractmethod
    async def get(self, task_id: str) -> TorrentInfo | None: ...

    @abstractmethod
    async def list_all(self) -> list[TorrentInfo]:
        """列出所有任务。注意:方法名避开 list 关键字以免与类型注解冲突。"""

    @abstractmethod
    async def pause(self, task_id: str) -> None: ...

    @abstractmethod
    async def resume(self, task_id: str) -> None: ...

    @abstractmethod
    async def remove(self, task_id: str, delete_files: bool = False) -> None: ...

    @abstractmethod
    async def get_files(self, task_id: str) -> list[str]:
        """完成后返回所有文件的绝对路径。"""

"""qBittorrent WebUI API 客户端。

参考:https://github.com/qbittorrent/qBittorrent/wiki/WebUI-API-(qBittorrent-4.1)

设计要点:
- 维护一个 httpx.AsyncClient,带 cookies
- 401 时自动重新登录(qB session 默认 1h 过期)
- 每个任务用 info_hash 作为 ID
"""
import asyncio
import logging
from typing import Any

import httpx

from app.providers.downloader.base import DownloaderProvider, TorrentInfo

logger = logging.getLogger(__name__)


# qB 状态字符串到我们内部状态的映射
_STATUS_MAP = {
    "error": "failed",
    "missingFiles": "failed",
    "uploading": "completed",
    "pausedUP": "completed",
    "queuedUP": "completed",
    "stalledUP": "completed",
    "checkingUP": "completed",
    "forcedUP": "completed",
    "allocating": "downloading",
    "downloading": "downloading",
    "metaDL": "downloading",
    "queuedDL": "pending",
    "stalledDL": "downloading",
    "checkingDL": "downloading",
    "forcedDL": "downloading",
    "checkingResumeData": "downloading",
    "moving": "downloading",
    "pausedDL": "paused",
    "unknown": "unknown",
}


def _qb_status(s: str) -> str:
    return _STATUS_MAP.get(s, "unknown")


class QBittorrentProvider(DownloaderProvider):
    name = "qbittorrent"

    def __init__(self, base_url: str, username: str, password: str, timeout: float = 10.0):
        # 标准化 URL
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self._client = httpx.AsyncClient(timeout=timeout)
        self._lock = asyncio.Lock()
        self._authenticated = False

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()

    # ============================================================
    # 内部:登录
    # ============================================================
    async def _login(self) -> None:
        async with self._lock:
            r = await self._client.post(
                f"{self.base_url}/api/v2/auth/login",
                data={"username": self.username, "password": self.password},
                headers={"Referer": self.base_url},
            )
            if r.status_code != 200 or r.text.strip() != "Ok.":
                self._authenticated = False
                raise RuntimeError(
                    f"qbittorrent login failed (status={r.status_code} body={r.text!r})"
                )
            self._authenticated = True
            logger.info("qBittorrent login OK at %s", self.base_url)

    async def _request(self, method: str, path: str, **kw: Any) -> httpx.Response:
        """带自动登录重试的请求。"""
        if not self._authenticated:
            await self._login()
        url = f"{self.base_url}{path}"
        headers = kw.pop("headers", {})
        headers.setdefault("Referer", self.base_url)
        r = await self._client.request(method, url, headers=headers, **kw)
        if r.status_code == 403:
            # session 失效,重登一次
            self._authenticated = False
            await self._login()
            r = await self._client.request(method, url, headers=headers, **kw)
        return r

    # ============================================================
    # 公开 API
    # ============================================================
    async def health_check(self) -> bool:
        try:
            await self._login()
            r = await self._request("GET", "/api/v2/app/version")
            return r.status_code == 200
        except Exception as e:  # noqa: BLE001
            logger.warning("qbittorrent health_check failed: %s", e)
            return False

    async def add_magnet(
        self,
        magnet_uri: str,
        save_path: str | None = None,
        category: str | None = None,
    ) -> str:
        data: dict[str, Any] = {"urls": magnet_uri}
        if save_path:
            data["savepath"] = save_path
        if category:
            data["category"] = category
        r = await self._request(
            "POST",
            "/api/v2/torrents/add",
            data=data,
        )
        if r.status_code != 200 or r.text.strip() != "Ok.":
            raise RuntimeError(f"add_magnet failed: {r.status_code} {r.text!r}")

        # qB 添加后不直接返回 hash,需要从 magnet 里解析
        info_hash = _extract_info_hash(magnet_uri)
        if not info_hash:
            raise RuntimeError("无法从 magnet 链接提取 info_hash")
        # 等待 qB 实际收到任务(metaDL/queuedDL),最多 5s
        for _ in range(10):
            t = await self.get(info_hash)
            if t:
                return info_hash
            await asyncio.sleep(0.5)
        return info_hash  # qB 可能延迟,直接返回

    async def get(self, task_id: str) -> TorrentInfo | None:
        r = await self._request(
            "GET",
            "/api/v2/torrents/info",
            params={"hashes": task_id.lower()},
        )
        if r.status_code != 200:
            return None
        items = r.json()
        if not items:
            return None
        return _to_info(items[0])

    async def list_all(self) -> list[TorrentInfo]:
        r = await self._request("GET", "/api/v2/torrents/info")
        if r.status_code != 200:
            return []
        return [_to_info(item) for item in r.json()]

    async def pause(self, task_id: str) -> None:
        await self._request("POST", "/api/v2/torrents/pause", data={"hashes": task_id.lower()})

    async def resume(self, task_id: str) -> None:
        await self._request("POST", "/api/v2/torrents/resume", data={"hashes": task_id.lower()})

    async def remove(self, task_id: str, delete_files: bool = False) -> None:
        await self._request(
            "POST",
            "/api/v2/torrents/delete",
            data={
                "hashes": task_id.lower(),
                "deleteFiles": "true" if delete_files else "false",
            },
        )

    async def get_files(self, task_id: str) -> list[str]:
        """返回 torrent 内所有文件的绝对路径。"""
        # qB 返回的是相对路径,需要拼接 save_path
        info = await self.get(task_id)
        if not info or not info.save_path:
            return []
        r = await self._request(
            "GET",
            "/api/v2/torrents/files",
            params={"hash": task_id.lower()},
        )
        if r.status_code != 200:
            return []
        files_json = r.json()
        out = []
        from os.path import join, normpath

        for f in files_json:
            relative = f.get("name", "")
            if relative:
                out.append(normpath(join(info.save_path, relative)))
        return out


def _extract_info_hash(magnet_uri: str) -> str | None:
    """从 magnet 链接提取 info_hash (40字符的 SHA1)。"""
    import re

    m = re.search(r"xt=urn:btih:([a-fA-F0-9]{40})", magnet_uri)
    if m:
        return m.group(1).lower()
    # base32 编码的 32 字符也支持
    m = re.search(r"xt=urn:btih:([A-Z2-7]{32})", magnet_uri)
    if m:
        # base32 转 hex
        import base64

        try:
            return base64.b32decode(m.group(1)).hex()
        except Exception:  # noqa: BLE001
            return None
    return None


def _to_info(item: dict) -> TorrentInfo:
    return TorrentInfo(
        id=item.get("hash", ""),
        name=item.get("name", ""),
        info_hash=item.get("hash"),
        save_path=item.get("save_path") or item.get("content_path"),
        status=_qb_status(item.get("state", "unknown")),
        progress=float(item.get("progress", 0)),
        download_speed=int(item.get("dlspeed", 0)),
        upload_speed=int(item.get("upspeed", 0)),
        eta_seconds=int(item.get("eta", 0)) if item.get("eta", 0) > 0 else None,
        size_bytes=int(item.get("size", 0)) or None,
    )

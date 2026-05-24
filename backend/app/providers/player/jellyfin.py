"""Jellyfin API 客户端。

第一版能力:
- 健康检查
- 列出所有 Library
- 列出所有 Item (含 Path),用于路径匹配
- 跳转到指定 Item 的 Web 详情页

API 文档:https://api.jellyfin.org/
"""
import logging

import httpx

from app.providers.player.base import PlayerProvider

logger = logging.getLogger(__name__)


class JellyfinProvider(PlayerProvider):
    name = "jellyfin"

    def __init__(self, base_url: str, api_key: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self._timeout = timeout

    @property
    def configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=self._timeout,
            headers={"X-Emby-Token": self.api_key} if self.api_key else {},
        )

    async def health_check(self) -> dict:
        if not self.configured:
            return {"ok": False, "error": "not_configured"}
        try:
            async with self._client() as client:
                r = await client.get(f"{self.base_url}/System/Info")
            if r.status_code == 200:
                data = r.json()
                return {
                    "ok": True,
                    "version": data.get("Version"),
                    "server_name": data.get("ServerName"),
                    "operating_system": data.get("OperatingSystem"),
                }
            return {"ok": False, "error": f"http_{r.status_code}"}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "error": str(e)}

    async def list_libraries(self) -> list[dict]:
        async with self._client() as client:
            r = await client.get(f"{self.base_url}/Library/MediaFolders")
        if r.status_code != 200:
            return []
        return [
            {
                "id": item.get("Id"),
                "name": item.get("Name"),
                "type": item.get("CollectionType"),
                "paths": item.get("Locations") or [],
            }
            for item in r.json().get("Items", [])
        ]

    async def find_item_by_path(self, path: str) -> dict | None:
        """通过 Path 查找 Item ID。

        Jellyfin 的 /Items 接口支持 Path 查询。
        """
        async with self._client() as client:
            r = await client.get(
                f"{self.base_url}/Items",
                params={
                    "Path": path,
                    "Recursive": "true",
                    "Fields": "Path",
                    "Limit": 5,
                },
            )
        if r.status_code != 200:
            return None
        items = r.json().get("Items", [])
        for item in items:
            if item.get("Path") == path:
                return {"id": item.get("Id"), "name": item.get("Name")}
        return items[0] if items else None

    def web_url_for_item(self, item_id: str) -> str:
        """构造 Jellyfin Web 详情页 URL。"""
        return f"{self.base_url}/web/#/details?id={item_id}"

    def web_search_url(self, query: str) -> str:
        """跳转到 Jellyfin 搜索页。"""
        from urllib.parse import quote

        return f"{self.base_url}/web/#/search.html?query={quote(query)}"

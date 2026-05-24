"""Torznab/Newznab 兼容搜索源 (Jackett / Prowlarr / Radarr 索引器协议)。

返回 RSS XML,字段映射到 SearchHit。
配置示例:
{
  "base_url": "http://nas.local:9117/api/v2.0/indexers/all/results/torznab/api",
  "api_key": "xxxxxxxx",
  "category": "2000"  // 可选,2000=电影
}

调用示例:
GET {base_url}?apikey={api_key}&t=search&q=keyword&cat=2000
"""
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from email.utils import parsedate_to_datetime

import httpx

from app.providers.search.base import SearchHit, SearchProvider

logger = logging.getLogger(__name__)


class TorznabProvider(SearchProvider):
    name = "torznab"

    @property
    def base_url(self) -> str:
        return self.config.get("base_url", "").rstrip("/")

    @property
    def api_key(self) -> str:
        return self.config.get("api_key") or self.config.get("auth", {}).get("api_key", "")

    @property
    def default_category(self) -> str | None:
        return self.config.get("category")

    async def search(self, query: str, limit: int = 50) -> list[SearchHit]:
        if not self.base_url:
            return []

        params: dict = {"t": "search", "q": query, "limit": limit}
        if self.api_key:
            params["apikey"] = self.api_key
        if self.default_category:
            params["cat"] = self.default_category

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(self.base_url, params=params)
            if r.status_code != 200:
                logger.warning("torznab %s returned %s", self.base_url, r.status_code)
                return []
            return _parse_rss(r.text)
        except Exception as e:  # noqa: BLE001
            logger.warning("torznab search failed at %s: %s", self.base_url, e)
            return []

    async def health_check(self) -> bool:
        if not self.base_url:
            return False
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                params = {"t": "caps"}
                if self.api_key:
                    params["apikey"] = self.api_key
                r = await client.get(self.base_url, params=params)
            return r.status_code == 200 and "caps" in r.text.lower()
        except Exception:  # noqa: BLE001
            return False


# ============================================================
# RSS 解析
# ============================================================
NS = {"torznab": "http://torznab.com/schemas/2015/feed"}


def _parse_rss(text: str) -> list[SearchHit]:
    try:
        root = ET.fromstring(text)
    except ET.ParseError:
        return []

    items: list[SearchHit] = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        if not title:
            continue

        # 链接(可能是 magnet 或 .torrent URL)
        magnet = None
        size_bytes = None
        info_hash = None
        seeders = leechers = None
        source_url = item.findtext("comments") or item.findtext("link")

        # enclosure 通常是 .torrent 链接
        enc = item.find("enclosure")

        # torznab attr 字段
        for attr in item.findall("torznab:attr", NS):
            n = attr.get("name", "").lower()
            v = attr.get("value")
            if not v:
                continue
            if n == "magneturl":
                magnet = v
            elif n == "infohash":
                info_hash = v.lower()
            elif n == "size":
                try:
                    size_bytes = int(v)
                except ValueError:
                    pass
            elif n == "seeders":
                try:
                    seeders = int(v)
                except ValueError:
                    pass
            elif n in ("leechers", "peers"):
                try:
                    leechers = int(v)
                except ValueError:
                    pass

        # link 字段如果是 magnet,直接拿
        link = item.findtext("link", "")
        if link and link.startswith("magnet:") and not magnet:
            magnet = link

        # size 兜底从 enclosure
        if size_bytes is None and enc is not None:
            try:
                size_bytes = int(enc.get("length", 0)) or None
            except ValueError:
                pass

        # 发布时间
        pub_time = None
        pub_date = item.findtext("pubDate")
        if pub_date:
            try:
                pub_time = parsedate_to_datetime(pub_date)
            except (TypeError, ValueError):
                pub_time = None

        items.append(
            SearchHit(
                title=title,
                magnet_uri=magnet,
                info_hash=info_hash,
                size_bytes=size_bytes,
                publish_time=pub_time,
                source_url=source_url,
                seeders=seeders,
                leechers=leechers,
            )
        )
    return items

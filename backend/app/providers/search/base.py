"""搜索源适配器抽象。

设计:
- 每种搜索源实现一个 Provider 子类
- 用户在设置页配置 base_url / 认证信息 → resource_source 表
- 聚合搜索时遍历所有 enabled 的 source,并发查询
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SearchHit:
    """搜索结果统一格式。"""
    title: str
    magnet_uri: str | None = None
    info_hash: str | None = None
    size_bytes: int | None = None
    publish_time: datetime | None = None
    source_url: str | None = None  # 详情页 URL
    seeders: int | None = None
    leechers: int | None = None
    raw: dict | None = None  # 原始 JSON,用于调试


class SearchProvider(ABC):
    """所有搜索源 Provider 的抽象基类。"""

    name: str = "base"

    def __init__(self, config: dict):
        """config 来自 resource_source 表的 base_url + auth_config 等字段。"""
        self.config = config

    @abstractmethod
    async def search(self, query: str, limit: int = 50) -> list[SearchHit]:
        """执行搜索,返回标准化结果列表。

        Provider 应自己处理超时、重试、字符编码等问题。
        失败时返回空列表(不抛异常,避免影响其他源)。
        """

    @abstractmethod
    async def health_check(self) -> bool:
        """连通性测试。"""

"""搜索 Provider 工厂。"""
import json
import logging

from app.providers.search.base import SearchProvider
from app.providers.search.torznab import TorznabProvider

logger = logging.getLogger(__name__)


_PROVIDERS = {
    "torznab": TorznabProvider,
    # 后续:
    # "rss": RssProvider,
    # "manual": ManualProvider,
}


def create_provider(source_type: str, config: dict) -> SearchProvider | None:
    cls = _PROVIDERS.get(source_type)
    if not cls:
        logger.warning("unknown search source type: %s", source_type)
        return None
    return cls(config)


def parse_source_config(source) -> dict:
    """合并 base_url + auth_config 等字段为单一 dict 传给 Provider。"""
    cfg: dict = {"base_url": source.base_url or ""}
    if source.auth_config:
        try:
            cfg.update(json.loads(source.auth_config))
        except json.JSONDecodeError:
            logger.warning("source %s auth_config invalid json", source.id)
    return cfg

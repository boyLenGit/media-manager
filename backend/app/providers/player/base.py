"""播放器/媒体服务器适配器抽象。

预留给:
- Jellyfin
- Emby (后续)
- Plex (后续)
"""
from abc import ABC, abstractmethod


class PlayerProvider(ABC):
    name: str = "base"

    @abstractmethod
    async def health_check(self) -> dict: ...

from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import RawHeroMetaPayload


class MetaDataSource(ABC):
    @abstractmethod
    async def get_hero_stats(self, season: str) -> RawHeroMetaPayload:
        raise NotImplementedError

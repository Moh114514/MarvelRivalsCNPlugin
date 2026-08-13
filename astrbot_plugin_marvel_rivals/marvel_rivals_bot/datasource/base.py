from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import PlayerStats


class DataSourceError(RuntimeError):
    """A user-safe error from the game data source."""


class RivalsDataSource(ABC):
    @abstractmethod
    async def get_player(self, uid: str, season: str | None = None) -> PlayerStats:
        raise NotImplementedError

    @abstractmethod
    async def get_recent_matches(self, uid: str, season: str | None = None) -> list[dict]:
        raise NotImplementedError

    @abstractmethod
    async def get_hero(self, uid: str, hero_id: str, season: str | None = None) -> dict:
        raise NotImplementedError

    @abstractmethod
    async def get_summary_detail(self, match_uid: str) -> dict:
        raise NotImplementedError

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import IntEnum

from ..models import MatchSummaryPage, PlayerProfile, PlayerStats


class GameMode(IntEnum):
    """CN mini-program game mode IDs used by player statistics endpoints."""

    QUICK = 1
    COMPETITIVE = 2


DEFAULT_PLAY_MODE = 0


class DataSourceError(RuntimeError):
    """A user-safe error from the game data source."""


class RivalsDataSource(ABC):
    @abstractmethod
    async def get_player(self, uid: str, season: str | None = None) -> PlayerStats:
        raise NotImplementedError

    async def get_player_profile(self, uid: str, season: str | None = None) -> PlayerProfile:
        """Return the light profile/rank context without loading statistics."""

        return (await self.get_player(uid, season)).profile

    async def get_player_profile_history(self, uid: str) -> PlayerProfile:
        """Return profile data including any source-provided rank history."""

        return await self.get_player_profile(uid)

    async def load_career(self, uid: str, season: str | None, game_mode: GameMode) -> dict:
        raise NotImplementedError

    async def load_sort_hero(self, uid: str, season: str | None, game_mode: GameMode) -> dict:
        raise NotImplementedError

    async def load_hero_career(
        self,
        uid: str,
        hero_ids: list[int | str],
        season: str | None,
        game_mode: GameMode,
    ) -> dict:
        raise NotImplementedError

    @abstractmethod
    async def get_recent_matches(self, uid: str, season: str | None = None) -> list[dict]:
        raise NotImplementedError

    async def get_match_summary_page(
        self,
        uid: str,
        season: str,
        *,
        page: int = 0,
        page_size: int = 100,
        start_timestamp: int | None = None,
        end_timestamp: int | None = None,
        game_mode_ids: tuple[int, ...] = (1, 2, 4),
        play_mode_ids: tuple[int, ...] = (0, 7, 8),
    ) -> MatchSummaryPage:
        """Load one server-filtered summary page when the source supports it."""

        raise NotImplementedError

    @abstractmethod
    async def get_hero(self, uid: str, hero_id: str, season: str | None = None) -> dict:
        raise NotImplementedError

    @abstractmethod
    async def get_summary_detail(self, match_uid: str) -> dict:
        raise NotImplementedError

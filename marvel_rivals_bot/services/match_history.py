"""Generic match-history façade separated from command and rendering code."""

from __future__ import annotations

from typing import Any

from ..models import MatchTimeWindow, MatchWindowReport
from .rivals import RivalsService


class MatchHistoryService:
    """Expose the time-window portion of the shared RivalsService.

    The plugin still constructs one ``RivalsService`` at its integration
    boundary.  This small façade gives future callers a stable history-owned
    surface without creating another data source or a second cache.
    """

    def __init__(self, service: RivalsService):
        self.service = service

    async def get_matches_by_time_range(
        self,
        uid: str,
        *,
        start_timestamp: int,
        end_timestamp: int,
        season: str | None = None,
        page_size: int | None = None,
        max_pages: int | None = None,
    ) -> list[dict[str, Any]]:
        return await self.service.get_matches_by_time_range(
            uid,
            season,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            page_size=page_size,
            max_pages=max_pages,
        )

    async def build_match_window_report(
        self,
        uid: str,
        window: MatchTimeWindow,
        *,
        season: str | None = None,
    ) -> MatchWindowReport:
        return await self.service.get_match_window_report(uid, window, season=season)

    async def aggregate_matches(
        self,
        uid: str,
        window: MatchTimeWindow,
        *,
        season: str | None = None,
    ) -> MatchWindowReport:
        return await self.build_match_window_report(uid, window, season=season)


__all__ = ["MatchHistoryService"]

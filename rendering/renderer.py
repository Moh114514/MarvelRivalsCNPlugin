"""HTML-to-PNG adapter for Marvel Rivals image pages."""

from __future__ import annotations

from typing import Awaitable, Callable

try:
    from ..marvel_rivals_bot.models import HeroQueryResult, PlayerStats
except ImportError:
    from marvel_rivals_bot.models import HeroQueryResult, PlayerStats

from .pages import (
    build_help_html,
    build_hero_query_html,
    build_match_detail_html,
    build_player_stats_html,
    build_recent_matches_html,
)

PNG_OPTIONS = {"type": "png", "full_page": True, "animations": "disabled", "caret": "hide"}


class RivalsImageRenderer:
    def __init__(self, html_render: Callable[..., Awaitable[str]]):
        self._html_render = html_render

    async def recent(self, uid: str, season_code: str, matches: list[dict]) -> str:
        return await self._html_render(build_recent_matches_html(uid, season_code, matches), {}, options=PNG_OPTIONS)

    async def detail(self, payload: dict) -> str:
        return await self._html_render(build_match_detail_html(payload), {}, options=PNG_OPTIONS)

    async def player(self, stats: PlayerStats) -> str:
        return await self._html_render(build_player_stats_html(stats), {}, options=PNG_OPTIONS)

    async def hero(self, result: HeroQueryResult) -> str:
        return await self._html_render(build_hero_query_html(result), {}, options=PNG_OPTIONS)

    async def help(self, help_text: str) -> str:
        return await self._html_render(build_help_html(help_text), {}, options=PNG_OPTIONS)


# Keep the old public name stable while callers migrate to the semantic name.
MatchImageRenderer = RivalsImageRenderer

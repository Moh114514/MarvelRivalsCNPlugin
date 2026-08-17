"""HTML-to-PNG adapter for Marvel Rivals image pages."""

from __future__ import annotations

from typing import Awaitable, Callable

try:
    from ..marvel_rivals_bot.models import HeroQueryResult, PlayerStats
    from ..marvel_rivals_bot.meta.models import (
        HeroMetaBoard,
        HeroMetaComparison,
        HeroMetaOverview,
        HeroMetaSegments,
    )
    from ..marvel_rivals_bot.analytics.models import PlayerMetaProfile
except ImportError:
    from marvel_rivals_bot.models import HeroQueryResult, PlayerStats
    from marvel_rivals_bot.meta.models import (
        HeroMetaBoard,
        HeroMetaComparison,
        HeroMetaOverview,
        HeroMetaSegments,
    )
    from marvel_rivals_bot.analytics.models import PlayerMetaProfile

from .pages import (
    build_help_html,
    build_hero_query_html,
    build_match_detail_html,
    build_meta_board_html,
    build_meta_comparison_html,
    build_meta_overview_html,
    build_meta_segments_html,
    build_meta_single_html,
    build_player_hero_pool_html,
    build_player_meta_environment_html,
    build_player_signature_html,
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

    async def meta_overview(self, overview: HeroMetaOverview) -> str:
        return await self._html_render(build_meta_overview_html(overview), {}, options=PNG_OPTIONS)

    async def meta_board(self, board: HeroMetaBoard) -> str:
        return await self._html_render(build_meta_board_html(board), {}, options=PNG_OPTIONS)

    async def meta_single(self, board: HeroMetaBoard) -> str:
        return await self._html_render(build_meta_single_html(board), {}, options=PNG_OPTIONS)

    async def meta_segments(self, segments: HeroMetaSegments) -> str:
        return await self._html_render(build_meta_segments_html(segments), {}, options=PNG_OPTIONS)

    async def meta_comparison(self, comparison: HeroMetaComparison) -> str:
        return await self._html_render(build_meta_comparison_html(comparison), {}, options=PNG_OPTIONS)

    async def player_meta_environment(self, profile: PlayerMetaProfile) -> str:
        return await self._html_render(build_player_meta_environment_html(profile), {}, options=PNG_OPTIONS)

    async def player_hero_pool(self, profile: PlayerMetaProfile) -> str:
        return await self._html_render(build_player_hero_pool_html(profile), {}, options=PNG_OPTIONS)

    async def player_signature(self, profile: PlayerMetaProfile) -> str:
        return await self._html_render(build_player_signature_html(profile), {}, options=PNG_OPTIONS)


# Keep the old public name stable while callers migrate to the semantic name.
MatchImageRenderer = RivalsImageRenderer

"""HTML-to-PNG adapter for Marvel Rivals image pages."""

from __future__ import annotations

import asyncio
from time import perf_counter
from typing import Any, Awaitable, Callable

try:
    from ..marvel_rivals_bot.models import HeroQueryResult, MatchWindowReport, PlayerStats
    from ..marvel_rivals_bot.meta.models import (
        HeroMetaBoard,
        HeroMetaComparison,
        HeroMetaInsights,
        HeroMetaOverview,
        HeroMetaSegments,
        HeroMetaVersionChanges,
        HeroRankSeries,
        RankMonsterBoard,
    )
    from ..marvel_rivals_bot.analytics.models import CareerHeroSignature, PlayerMetaProfile, PlayerSignatureProfile
except ImportError:
    from marvel_rivals_bot.models import HeroQueryResult, MatchWindowReport, PlayerStats
    from marvel_rivals_bot.meta.models import (
        HeroMetaBoard,
        HeroMetaComparison,
        HeroMetaInsights,
        HeroMetaOverview,
        HeroMetaSegments,
        HeroMetaVersionChanges,
        HeroRankSeries,
        RankMonsterBoard,
    )
    from marvel_rivals_bot.analytics.models import CareerHeroSignature, PlayerMetaProfile, PlayerSignatureProfile

from .pages import (
    build_help_html,
    build_hero_query_html,
    build_player_hero_analysis_html,
    build_player_hero_pool_analysis_html,
    build_match_detail_html,
    build_meta_board_html,
    build_meta_role_boards_html,
    build_meta_comparison_html,
    build_meta_insights_html,
    build_meta_overview_html,
    build_meta_segments_html,
    build_meta_single_html,
    build_meta_trend_html,
    build_meta_version_changes_html,
    build_rank_monsters_html,
    build_player_hero_pool_html,
    build_player_meta_environment_html,
    build_player_signature_html,
    build_player_sickness_html,
    build_player_stats_html,
    build_recent_matches_html,
    build_daily_report_html,
    build_match_window_pages,
)

PNG_OPTIONS = {"type": "png", "full_page": True, "animations": "disabled", "caret": "hide"}


class RivalsImageRenderer:
    def __init__(
        self,
        html_render: Callable[..., Awaitable[str]],
        *,
        max_concurrent_renders: int = 4,
        max_retries: int = 1,
        render_retries: int | None = None,
        queue_timeout_seconds: float | None = 15,
        logger: Any | None = None,
    ):
        self._html_render = html_render
        self.max_concurrent_renders = max(1, int(max_concurrent_renders))
        self.max_retries = max(0, int(max_retries if render_retries is None else render_retries))
        self.queue_timeout_seconds = (
            None if queue_timeout_seconds is None else max(0.1, float(queue_timeout_seconds))
        )
        self._render_semaphore = asyncio.Semaphore(self.max_concurrent_renders)
        self._logger = logger

    async def _render(self, html: str, *, render_type: str = "unknown") -> str:
        queue_started = perf_counter()
        if self.queue_timeout_seconds is None:
            await self._render_semaphore.acquire()
        else:
            try:
                await asyncio.wait_for(
                    self._render_semaphore.acquire(),
                    timeout=self.queue_timeout_seconds,
                )
            except asyncio.TimeoutError:
                if self._logger:
                    self._logger.warning(
                        f"图片渲染排队超时 render_type={render_type} "
                        f"queue_ms={(perf_counter() - queue_started) * 1000:.1f}"
                    )
                raise
        queue_ms = (perf_counter() - queue_started) * 1000
        execution_started = perf_counter()
        try:
            for attempt in range(self.max_retries + 1):
                try:
                    result = await self._html_render(html, {}, options=PNG_OPTIONS)
                    if self._logger:
                        self._logger.info(
                            f"图片渲染完成 render_type={render_type} queue_ms={queue_ms:.1f} "
                            f"execution_ms={(perf_counter() - execution_started) * 1000:.1f}"
                        )
                    return result
                except Exception:
                    if attempt >= self.max_retries:
                        raise
        finally:
            self._render_semaphore.release()
        raise RuntimeError("render attempt loop did not complete")

    async def recent(self, uid: str, season_code: str, matches: list[dict]) -> str:
        return await self._render(build_recent_matches_html(uid, season_code, matches))

    async def daily(self, report: MatchWindowReport) -> str:
        return await self._render(build_daily_report_html(report))

    async def match_window(self, report: MatchWindowReport) -> list[str]:
        return [await self._render(html) for html in build_match_window_pages(report)]

    async def detail(self, payload: dict) -> str:
        return await self._render(build_match_detail_html(payload), render_type="detail")

    async def player(self, stats: PlayerStats) -> str:
        return await self._render(build_player_stats_html(stats))

    async def hero(self, result: HeroQueryResult) -> str:
        return await self._render(build_hero_query_html(result))

    async def player_hero_analysis(
        self,
        profile: PlayerSignatureProfile,
        hero: CareerHeroSignature,
    ) -> str:
        return await self._render(build_player_hero_analysis_html(profile, hero))

    async def player_hero_pool_analysis(self, pool) -> str:
        return await self._render(build_player_hero_pool_analysis_html(pool))

    async def help(self, help_text: str) -> str:
        return await self._render(build_help_html(help_text))

    async def meta_overview(self, overview: HeroMetaOverview) -> str:
        return await self._render(build_meta_overview_html(overview))

    async def meta_board(self, board: HeroMetaBoard) -> str:
        return await self._render(build_meta_board_html(board))

    async def meta_role_boards(self, boards) -> str:
        """Render a grouped-role board using the same semantic page shell."""
        return await self._render(build_meta_role_boards_html(boards))

    async def meta_single(self, board: HeroMetaBoard) -> str:
        return await self._render(build_meta_single_html(board))

    async def meta_segments(self, segments: HeroMetaSegments) -> str:
        return await self._render(build_meta_segments_html(segments))

    async def meta_comparison(self, comparison: HeroMetaComparison) -> str:
        return await self._render(build_meta_comparison_html(comparison))

    async def meta_trend(self, series: HeroRankSeries) -> str:
        return await self._render(build_meta_trend_html(series))

    async def meta_version_changes(self, changes: HeroMetaVersionChanges) -> str:
        return await self._render(build_meta_version_changes_html(changes))

    async def meta_insights(self, insights: HeroMetaInsights) -> str:
        return await self._render(build_meta_insights_html(insights))

    async def rank_monsters(self, board: RankMonsterBoard) -> str:
        return await self._render(build_rank_monsters_html(board))

    async def player_meta_environment(self, profile: PlayerMetaProfile) -> str:
        return await self._render(build_player_meta_environment_html(profile))

    async def player_hero_pool(self, profile: PlayerMetaProfile) -> str:
        return await self._render(build_player_hero_pool_html(profile))

    async def player_signature(self, profile: PlayerMetaProfile | PlayerSignatureProfile) -> str:
        return await self._render(build_player_signature_html(profile))

    async def player_sickness(self, profile: PlayerSignatureProfile) -> str:
        return await self._render(build_player_sickness_html(profile))


# Keep the old public name stable while callers migrate to the semantic name.
MatchImageRenderer = RivalsImageRenderer

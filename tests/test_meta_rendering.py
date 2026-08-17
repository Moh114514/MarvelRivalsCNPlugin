import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from main import MarvelRivalsPlugin
from marvel_rivals_bot.meta.models import (
    HeroMetaBoard,
    HeroMetaComparison,
    HeroMetaOverview,
    HeroMetaResult,
    HeroMetaSegment,
    HeroMetaSegments,
)
from qq_official.sender import QQOfficialCardSender
from rendering import (
    MatchImageRenderer,
    build_meta_board_html,
    build_meta_comparison_html,
    build_meta_overview_html,
    build_meta_segments_html,
    build_meta_single_html,
)


class FakeMetaEvent:
    def __init__(self, platform="aiocqhttp"):
        self.platform = platform

    def get_platform_name(self):
        return self.platform

    def plain_result(self, text):
        return ("text", text)

    def image_result(self, url):
        return ("image", url)


class FakeQQMetaEvent(FakeMetaEvent):
    def __init__(self, *, upload_error=None):
        super().__init__(platform="qq_official")
        raw_message = SimpleNamespace(
            group_openid="group-1",
            author=SimpleNamespace(user_openid="user-1"),
        )
        self.message_obj = SimpleNamespace(message_id="message-1", raw_message=raw_message)
        self.bot = SimpleNamespace(api=SimpleNamespace(
            post_group_file=AsyncMock(side_effect=upload_error, return_value={"file_info": "uploaded-image"}),
            post_group_message=AsyncMock(),
        ))


class TestMetaRendering(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.result = HeroMetaResult(
            hero_id=1020,
            hero_name="曼蒂斯",
            matches=10230,
            wins=6000,
            wr_matches=9000,
            wr_wins=5000,
            mirror_matches=10,
            bans=None,
            win_rate=55.55,
            pick_rate=2.77,
            ban_rate=None,
        )
        self.board = HeroMetaBoard(
            season_code="19",
            season_label="S9下半赛季",
            rank_key="6",
            rank_label="大师",
            sort_by="win_rate",
            heroes=[self.result],
            source="RivalsMeta",
            source_timestamp=datetime(2026, 8, 14, 7, 30, tzinfo=timezone.utc),
            fetched_at=datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc),
            stale=True,
        )
        self.overview = HeroMetaOverview(
            season_code="19",
            season_label="S9下半赛季",
            rank_key="6",
            rank_label="大师",
            win_rate=[self.result],
            pick_rate=[self.result],
            ban_rate=[self.result],
            source="RivalsMeta",
            source_timestamp=self.board.source_timestamp,
            fetched_at=self.board.fetched_at,
            stale=True,
        )
        self.segments = HeroMetaSegments(
            hero_id=self.result.hero_id,
            hero_name=self.result.hero_name,
            season_code=self.board.season_code,
            season_label=self.board.season_label,
            segments=[
                HeroMetaSegment("1", "青铜", None),
                HeroMetaSegment("5", "钻石", self.result),
            ],
            source=self.board.source,
            source_timestamp=self.board.source_timestamp,
            fetched_at=self.board.fetched_at,
            stale=True,
        )
        comparison_right = HeroMetaResult(
            hero_id=1036,
            hero_name="蜘蛛侠",
            matches=8000,
            wins=4000,
            wr_matches=8000,
            wr_wins=4000,
            mirror_matches=10,
            bans=20,
            win_rate=50.0,
            pick_rate=3.0,
            ban_rate=1.0,
        )
        self.comparison = HeroMetaComparison(
            season_code=self.board.season_code,
            season_label=self.board.season_label,
            rank_key=self.board.rank_key,
            rank_label=self.board.rank_label,
            left=self.result,
            right=comparison_right,
            source=self.board.source,
            source_timestamp=self.board.source_timestamp,
            fetched_at=self.board.fetched_at,
            stale=True,
        )

    def test_meta_pages_use_semantic_shell_and_escape_view_model_values(self):
        overview = build_meta_overview_html(self.overview)
        board = build_meta_board_html(self.board)
        single = build_meta_single_html(self.board)

        self.assertIn("CURRENT META", overview)
        self.assertIn("当前英雄环境", overview)
        for heading in ("胜率 TOP5", "选取率 TOP5", "Ban率 TOP5"):
            self.assertIn(heading, overview)
        self.assertNotIn("场次 TOP5", overview)
        self.assertIn("HERO RANKING", board)
        self.assertIn("英雄排行", board)
        self.assertIn("HERO META", single)
        self.assertIn("英雄统计", single)
        for html in (overview, board, single):
            self.assertIn('class="mr-page"', html)
            self.assertIn("RivalsMeta", html)
            self.assertIn("当前上游暂不可用", html)
            self.assertNotIn("<script>", html)
        self.assertIn("—", overview)
        self.assertIn("—", single)

        segments = build_meta_segments_html(self.segments)
        comparison = build_meta_comparison_html(self.comparison)
        for html in (segments, comparison):
            self.assertIn('class="mr-page"', html)
            self.assertIn("RivalsMeta", html)
            self.assertIn("当前上游暂不可用", html)
            self.assertNotIn("<script>", html)
        self.assertIn("HERO BREAKDOWN", segments)
        self.assertIn("青铜", segments)
        self.assertIn("暂无该段位数据", segments)
        self.assertIn('class="mr-meta-list mr-meta-list--rank-breakdown"', segments)
        self.assertIn("HERO COMPARISON", comparison)
        self.assertIn("曼蒂斯", comparison)
        self.assertIn("蜘蛛侠", comparison)
        self.assertIn('class="mr-comparison"', comparison)
        self.assertIn('class="mr-comparison__value mr-comparison__value--left"', comparison)
        self.assertIn('class="mr-comparison__label"', comparison)

    def test_meta_page_escapes_untrusted_view_model_text(self):
        escaped_result = HeroMetaResult(
            hero_id=self.result.hero_id,
            hero_name="<英雄>",
            matches=self.result.matches,
            wins=self.result.wins,
            wr_matches=self.result.wr_matches,
            wr_wins=self.result.wr_wins,
            mirror_matches=self.result.mirror_matches,
            bans=self.result.bans,
            win_rate=self.result.win_rate,
            pick_rate=self.result.pick_rate,
            ban_rate=self.result.ban_rate,
        )
        board = HeroMetaBoard(
            season_code="19",
            season_label="S9 <script>",
            rank_key="6",
            rank_label="大师 {{danger}}",
            sort_by="ban_rate",
            heroes=[escaped_result],
            source="<source>",
            source_timestamp=None,
            fetched_at=self.board.fetched_at,
        )
        html = build_meta_board_html(board)
        self.assertNotIn("<script>", html)
        self.assertNotIn("{{danger}}", html)
        self.assertIn("&lt;英雄&gt;", html)
        self.assertIn("&lt;source&gt;", html)

    async def _run_command(self, method_name, *args):
        plugin = object.__new__(MarvelRivalsPlugin)
        plugin.qq_card_sender = QQOfficialCardSender()
        plugin.image_renderer = SimpleNamespace(
            meta_overview=AsyncMock(return_value="overview.png"),
            meta_board=AsyncMock(return_value="board.png"),
            meta_single=AsyncMock(return_value="single.png"),
            meta_segments=AsyncMock(return_value="segments.png"),
            meta_comparison=AsyncMock(return_value="comparison.png"),
        )
        plugin.meta_service = SimpleNamespace(
            get_hero_meta_overview=AsyncMock(return_value=self.overview),
            get_hero_meta_board=AsyncMock(return_value=self.board),
            get_single_hero_meta_board=AsyncMock(return_value=self.board),
            get_hero_meta_segments=AsyncMock(return_value=self.segments),
            get_hero_meta_comparison=AsyncMock(return_value=self.comparison),
        )
        event = FakeMetaEvent()
        return [item async for item in getattr(plugin, method_name)(event, *args)], plugin, event

    async def test_meta_commands_send_image_on_non_qq_platform(self):
        for method_name, args, expected in (
            ("hero_meta", (), "overview.png"),
            ("hero_meta_rank", ("胜率",), "board.png"),
            ("hero_meta_stats", ("曼蒂斯",), "single.png"),
            ("hero_meta_segments", ("曼蒂斯",), "segments.png"),
            ("hero_meta_comparison", ("曼蒂斯", "蜘蛛侠", "铂金", "S9.5"), "comparison.png"),
        ):
            results, plugin, _ = await self._run_command(method_name, *args)
            self.assertEqual(results, [("image", expected)])
            getattr(plugin.image_renderer, {
                "hero_meta": "meta_overview",
                "hero_meta_rank": "meta_board",
                "hero_meta_stats": "meta_single",
                "hero_meta_segments": "meta_segments",
                "hero_meta_comparison": "meta_comparison",
            }[method_name]).assert_awaited_once()

    async def test_meta_command_render_failure_falls_back_to_text(self):
        plugin = object.__new__(MarvelRivalsPlugin)
        plugin.qq_card_sender = QQOfficialCardSender()
        plugin.image_renderer = SimpleNamespace(meta_overview=AsyncMock(side_effect=RuntimeError("render")))
        plugin.meta_service = SimpleNamespace(get_hero_meta_overview=AsyncMock(return_value=self.overview))

        results = [item async for item in plugin.hero_meta(FakeMetaEvent())]

        self.assertEqual(results[0][0], "text")
        self.assertIn("当前英雄环境", results[0][1])

    async def test_meta_command_qq_upload_failure_falls_back_to_text(self):
        plugin = object.__new__(MarvelRivalsPlugin)
        plugin.qq_card_sender = QQOfficialCardSender()
        plugin.image_renderer = SimpleNamespace(meta_board=AsyncMock(return_value="https://example.com/board.png"))
        plugin.meta_service = SimpleNamespace(get_hero_meta_board=AsyncMock(return_value=self.board))
        event = FakeQQMetaEvent(upload_error=RuntimeError("media rejected"))

        results = [item async for item in plugin.hero_meta_rank(event, "胜率")]

        self.assertEqual(results[0][0], "text")
        self.assertIn("英雄环境", results[0][1])
        event.bot.api.post_group_message.assert_not_awaited()

    async def test_new_meta_command_render_failure_falls_back_to_text(self):
        plugin = object.__new__(MarvelRivalsPlugin)
        plugin.qq_card_sender = QQOfficialCardSender()
        plugin.image_renderer = SimpleNamespace(
            meta_segments=AsyncMock(side_effect=RuntimeError("render")),
            meta_comparison=AsyncMock(side_effect=RuntimeError("render")),
        )
        plugin.meta_service = SimpleNamespace(
            get_hero_meta_segments=AsyncMock(return_value=self.segments),
            get_hero_meta_comparison=AsyncMock(return_value=self.comparison),
        )

        segment_results = [item async for item in plugin.hero_meta_segments(FakeMetaEvent(), "曼蒂斯", "S9.5")]
        comparison_results = [
            item
            async for item in plugin.hero_meta_comparison(
                FakeMetaEvent(), "曼蒂斯", "蜘蛛侠", "铂金", "S9.5"
            )
        ]
        self.assertEqual(segment_results[0][0], "text")
        self.assertIn("英雄分段", segment_results[0][1])
        self.assertEqual(comparison_results[0][0], "text")
        self.assertIn("英雄对比", comparison_results[0][1])

    async def test_new_meta_comparison_qq_upload_failure_falls_back_to_text(self):
        plugin = object.__new__(MarvelRivalsPlugin)
        plugin.qq_card_sender = QQOfficialCardSender()
        plugin.image_renderer = SimpleNamespace(meta_comparison=AsyncMock(return_value="comparison.png"))
        plugin.meta_service = SimpleNamespace(get_hero_meta_comparison=AsyncMock(return_value=self.comparison))
        event = FakeQQMetaEvent(upload_error=RuntimeError("media rejected"))

        results = [
            item
            async for item in plugin.hero_meta_comparison(
                event, "S9.5", "铂金", "曼蒂斯", "蜘蛛侠"
            )
        ]
        self.assertEqual(results[0][0], "text")
        self.assertIn("英雄对比", results[0][1])
        event.bot.api.post_group_message.assert_not_awaited()

    async def test_new_meta_segments_qq_upload_failure_falls_back_to_text(self):
        plugin = object.__new__(MarvelRivalsPlugin)
        plugin.qq_card_sender = QQOfficialCardSender()
        plugin.image_renderer = SimpleNamespace(meta_segments=AsyncMock(return_value="segments.png"))
        plugin.meta_service = SimpleNamespace(get_hero_meta_segments=AsyncMock(return_value=self.segments))
        event = FakeQQMetaEvent(upload_error=RuntimeError("media rejected"))

        results = [
            item async for item in plugin.hero_meta_segments(event, "S9.5", "曼蒂斯")
        ]
        self.assertEqual(results[0][0], "text")
        self.assertIn("英雄分段", results[0][1])
        event.bot.api.post_group_message.assert_not_awaited()


class TestMetaRenderer(unittest.IsolatedAsyncioTestCase):
    async def test_renderer_uses_png_options_for_all_meta_pages(self):
        html_render = AsyncMock(return_value="rendered.png")
        renderer = MatchImageRenderer(html_render)
        result = HeroMetaResult(1, "曼蒂斯", 10, 5, 10, 5, 0, 0, 50.0, 1.0, 0.0)
        board = HeroMetaBoard(
            "19", "S9下半赛季", "all", "全段位", "matches", [result], "RivalsMeta", None,
            datetime.now(timezone.utc),
        )
        overview = HeroMetaOverview(
            "19", "S9下半赛季", "all", "全段位", [result], [result], [result],
            "RivalsMeta", None, datetime.now(timezone.utc),
        )

        await renderer.meta_overview(overview)
        await renderer.meta_board(board)
        await renderer.meta_single(board)
        segments = HeroMetaSegments(
            1020, "曼蒂斯", "19", "S9下半赛季",
            [HeroMetaSegment("1", "青铜", result)], "RivalsMeta", None,
            datetime.now(timezone.utc),
        )
        comparison = HeroMetaComparison(
            "19", "S9下半赛季", "all", "全段位", result,
            HeroMetaResult(2, "蜘蛛侠", 10, 5, 10, 5, 0, 0, 50.0, 1.0, 0.0),
            "RivalsMeta", None, datetime.now(timezone.utc),
        )
        await renderer.meta_segments(segments)
        await renderer.meta_comparison(comparison)

        self.assertEqual(html_render.await_count, 5)
        for call in html_render.await_args_list:
            self.assertEqual(call.kwargs["options"]["type"], "png")
            self.assertTrue(call.kwargs["options"]["full_page"])


if __name__ == "__main__":
    unittest.main()

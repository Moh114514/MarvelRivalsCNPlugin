import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from marvel_rivals_bot.analytics.formatters import (
    format_player_environment,
    format_player_hero_pool,
    format_player_signature,
)
from marvel_rivals_bot.analytics.models import PlayerHeroMetaComparison, PlayerMetaProfile
from marvel_rivals_bot.meta.models import HeroMetaOverview, HeroMetaResult
from rendering import (
    MatchImageRenderer,
    build_player_hero_pool_html,
    build_player_meta_environment_html,
    build_player_signature_html,
)


def _profile():
    result = HeroMetaResult(1020, "英雄A", 100, 50, 100, 50, 0, 10, 50.0, 4.0, 1.0)
    overview = HeroMetaOverview(
        "19", "S9下半赛季", "5", "钻石", [result], [result], [result],
        "RivalsMeta", datetime(2026, 8, 17, tzinfo=timezone.utc),
        datetime(2026, 8, 17, tzinfo=timezone.utc), False,
    )
    comparison = PlayerHeroMetaComparison(
        "1020", "<英雄A>", 30, 21, 70.0, 100, 50.0, 4.0, 1.0, 20.0,
    )
    return PlayerMetaProfile(
        uid="123",
        player_name="玩家<&>",
        cn_rank_label="钻石2",
        cn_rank_level=14,
        meta_rank_code="5",
        meta_rank_label="钻石",
        season_code="19",
        season_label="S9下半赛季",
        source="RivalsMeta",
        source_timestamp=datetime(2026, 8, 17, tzinfo=timezone.utc),
        fetched_at=datetime(2026, 8, 17, tzinfo=timezone.utc),
        stale=False,
        environment=overview,
        hero_pool=(comparison,),
        signature_heroes=(comparison,),
        minimum_matches=20,
    )


class TestPlayerMetaFormatting(unittest.TestCase):
    def test_text_formatters_use_view_model_and_escape_html_only_in_pages(self):
        profile = _profile()
        self.assertIn("我的环境", format_player_environment(profile))
        self.assertIn("我的英雄池", format_player_hero_pool(profile))
        self.assertIn("我的绝活", format_player_signature(profile))

    def test_pages_use_semantic_shell_and_escape_dynamic_values(self):
        profile = _profile()
        environment = build_player_meta_environment_html(profile)
        pool = build_player_hero_pool_html(profile)
        signature = build_player_signature_html(profile)
        self.assertIn('class="mr-page"', environment)
        self.assertIn('class="mr-player-meta-list mr-player-meta-list--comparison"', pool)
        self.assertIn('class="mr-player-meta-row mr-player-meta-row--comparison mr-player-meta-row--signature"', signature)
        for html in (environment, pool, signature):
            self.assertIn("玩家&lt;&amp;&gt;", html)
            self.assertNotIn("<script>", html)


class TestPlayerMetaRenderer(unittest.IsolatedAsyncioTestCase):
    async def test_player_meta_pages_use_png_options(self):
        html_render = AsyncMock(return_value="rendered.png")
        renderer = MatchImageRenderer(html_render)
        profile = _profile()
        await renderer.player_meta_environment(profile)
        await renderer.player_hero_pool(profile)
        await renderer.player_signature(profile)
        self.assertEqual(html_render.await_count, 3)
        for call in html_render.await_args_list:
            self.assertEqual(call.kwargs["options"]["type"], "png")
            self.assertTrue(call.kwargs["options"]["full_page"])


if __name__ == "__main__":
    unittest.main()

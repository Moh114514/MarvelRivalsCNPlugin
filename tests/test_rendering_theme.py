import unittest

from rendering.pages.hero import build_hero_query_html
from rendering.pages.help import build_help_html
from rendering.pages.match_detail import build_match_detail_html
from rendering.pages.player import build_player_stats_html
from rendering.pages.recent import build_recent_matches_html
from rendering.asset_loader import APPROVED_ASSETS, LIST_FRAME_URI, PART_NEWS_BACKGROUND_URI
from rendering.theme import STYLE
from marvel_rivals_bot.models import CareerSummary, HeroQueryResult, HeroStat, PlayerProfile, PlayerStats


class TestRenderingTheme(unittest.TestCase):
    def test_approved_visual_assets_are_available_to_the_theme(self):
        self.assertEqual(len(APPROVED_ASSETS), 2)
        self.assertTrue(PART_NEWS_BACKGROUND_URI.startswith("data:image/png;base64,"))
        self.assertTrue(LIST_FRAME_URI.startswith("data:image/png;base64,"))
        self.assertIn("background-image:url(\"data:image/png;base64,", STYLE)

    def test_help_page_uses_the_shared_visual_shell(self):
        html = build_help_html("""漫威争锋国服查询 | 指令帮助

/帮助
显示完整指令帮助

/战绩 [UID] [赛季]
查询综合战绩

已绑定账号可省略 UID。""")
        for marker in (
            "COMMAND GUIDE",
            "指令帮助",
            "/帮助",
            "/战绩 [UID] [赛季]",
            'class="mr-command-list"',
            'class="mr-help-note"',
            'data-watermark="COMMAND GUIDE"',
            'class="mr-page"',
        ):
            self.assertIn(marker, html)
        self.assertNotIn("<script>", html)

    def test_shared_theme_exposes_visual_tokens_and_decorations(self):
        for token in ("--mr-yellow", "--mr-purple", "--mr-paper", "--mr-cyan", "--mr-red", "--mr-panel"):
            self.assertIn(token, STYLE)
        for feature in (
            ".mr-page__background", ".mr-page__slash", ".mr-header__nameplate",
            ".mr-hero-row__index", "grid-auto-flow:column", "grid-template-rows:repeat(5,minmax(0,auto))",
            ".mr-meta-list--rank-breakdown", ".mr-comparison__row", "data-watermark", "clip-path",
            "@media (max-width:520px)",
        ):
            self.assertIn(feature, STYLE)

    def test_player_page_uses_shared_shell_header_metrics_and_footer(self):
        html = build_player_stats_html(PlayerStats(
            profile=PlayerProfile(
                uid="123",
                name="Player*One",
                level=80,
                rank_game_season="黄金2（3774 分）",
            ),
            summary=CareerSummary(matches=10, wins=6, kills=100, deaths=20, assists=30),
            heroes=[HeroStat(hero_id="1036", hero_name="蜘蛛侠", matches=8, wins=5, kills=90)],
            season="19",
        ))
        for marker in (
            'class="mr-page"',
            'class="mr-header"',
            'class="mr-metrics"',
            'class="mr-hero-list"',
            'class="mr-header__nameplate"',
            'class="mr-header__meta-grid"',
            'class="mr-header__meta-item mr-header__meta-item--uid"',
            'class="mr-hero-row__index">01</span>',
            'class="mr-footer"',
            'data-watermark="PLAYER PROFILE"',
            "PLAYER PROFILE",
        ):
            self.assertIn(marker, html)
        self.assertIn("Player*One", html)
        self.assertIn("黄金2", html)
        self.assertIn("3774 分", html)
        self.assertNotIn("SUBJECT", html)
        self.assertNotIn("<script>", html)

    def test_recent_page_keeps_ten_stable_numbers_and_removes_platform_hint(self):
        matches = [{
            "matchUid": f"match-{index}",
            "matchMapId": 1413,
            "gameModeId": 2,
            "playModeId": 0,
            "matchPlayer": {"isWin": index % 2, "curHeroId": 1036, "k": 18, "d": 4, "a": 7},
        } for index in range(12)]
        html = build_recent_matches_html("123", "19", matches)
        self.assertEqual(html.count('class="mr-match-row"'), 10)
        self.assertIn('class="mr-match-row__index">01</div>', html)
        self.assertIn('class="mr-match-row__index">10</div>', html)
        self.assertNotIn('class="mr-match-row__index">11</div>', html)
        self.assertNotIn("点击图片下方按钮查看单局详情", html)

    def test_match_page_exposes_report_teams_and_winner_state(self):
        html = build_match_detail_html({"data": {"matches": [{
            "matchUid": "m-1",
            "matchMapId": 1413,
            "gameModeId": 2,
            "playModeId": 0,
            "matchWinnerSide": 1,
            "matchPlayers": [
                {"camp": 1, "nickName": "A", "curHeroId": 1036, "k": 10, "d": 2, "a": 3},
                {"camp": 2, "nickName": "B", "curHeroId": 1066, "k": 5, "d": 6, "a": 1},
            ],
        }]}})
        for marker in (
            "MATCH REPORT",
            "TEAM 01",
            "TEAM 02",
            "VICTORY",
            "DEFEAT",
            "阵营 1",
            'class="mr-team-list"',
        ):
            self.assertIn(marker, html)

    def test_hero_page_and_empty_fallback_use_semantic_structure(self):
        hero = build_hero_query_html(HeroQueryResult(
            uid="123",
            hero_id="9999",
            hero_name="Unknown Hero",
            season="19",
            payload={"data": {"careers": []}},
        ))
        self.assertIn("HERO DATA", hero)
        self.assertIn('class="mr-empty"', hero)
        self.assertIn("暂无该英雄的生涯数据", hero)

        recent = build_recent_matches_html("<script>{{danger}}</script>", "19", [])
        self.assertNotIn("<script>", recent)
        self.assertNotIn("{{danger}}", recent)
        self.assertIn('class="mr-empty"', recent)


if __name__ == "__main__":
    unittest.main()

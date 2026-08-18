import unittest
from datetime import datetime, timezone
from pathlib import Path

from marvel_rivals_bot.meta.commands import parse_historical_meta_command_args
from marvel_rivals_bot.meta.formatters import (
    format_hero_meta_trend,
    format_meta_insights,
    format_meta_version_changes,
    format_rank_monsters,
)
from marvel_rivals_bot.meta.models import (
    HeroMetaResult,
    HeroRankPoint,
    HeroRankSeries,
    RankMonster,
    RankMonsterBoard,
    RankSegment,
)
from marvel_rivals_bot.meta.errors import MetaDataSourceError
from marvel_rivals_bot.meta.service import MetaService
from marvel_rivals_bot.meta.sources.rivalsmeta import RivalsMetaSource
from rendering.pages.meta import (
    build_meta_insights_html,
    build_meta_trend_html,
    build_meta_version_changes_html,
    build_rank_monsters_html,
)


PLUGIN_DIR = Path(__file__).resolve().parents[1]


def _payload(season: int, *, improved: bool = False, missing_bans: bool = False) -> dict:
    first_wr = 60 if improved else 50
    second_wr = 55 if improved else 60
    return {
        "season": season,
        "timestamp": 1720000000 + season,
        "heroes": [
            {
                "rank": "3",
                "heroes": [
                    {"hero_id": 1020, "matches": 100, "wins": 80, "wr_matches": 100, "wr_wins": 80, "mirror_matches": 0},
                ],
            },
            {
                "rank": "5",
                "heroes": [
                    {"hero_id": 1020, "matches": 100, "wins": 60, "wr_matches": 100, "wr_wins": first_wr, "mirror_matches": 0},
                    {"hero_id": 1036, "matches": 120, "wins": 60, "wr_matches": 100, "wr_wins": second_wr, "mirror_matches": 0},
                ],
            }
        ],
        "bans": None if missing_bans else [
            {"rank": "5", "bans": [{"hero_id": 1020, "bans": 5}, {"hero_id": 1036, "bans": 10}]}
        ],
    }


class FakeHistoricalSource:
    SOURCE_NAME = "RivalsMeta"

    def __init__(self):
        self.parser = RivalsMetaSource(env={"MRCN_RIVALSMETA_BASE_URL": "https://example.test"})
        self.calls: list[str] = []

    async def get_hero_stats(self, season):
        season = str(season)
        self.calls.append(season)
        value = int(season)
        return self.parser.parse_payload(_payload(value, improved=value == 19))

    def parse_payload(self, value):
        return self.parser.parse_payload(value)


class TestHistoricalMetaCommands(unittest.TestCase):
    def test_history_arguments_keep_season_order_and_rank(self):
        args = parse_historical_meta_command_args("S9.5", "大师", "蜘蛛侠", "S8", require_hero=True)
        self.assertEqual(args.hero_name, "蜘蛛侠")
        self.assertEqual(args.seasons, ("S9.5", "S8"))
        self.assertEqual(args.rank, "6")

    def test_history_arguments_reject_duplicate_and_numeric_seasons(self):
        with self.assertRaisesRegex(ValueError, "不同的赛季"):
            parse_historical_meta_command_args("S9", "S9")
        with self.assertRaises(ValueError):
            parse_historical_meta_command_args("19")

    def test_version_changes_require_two_seasons(self):
        with self.assertRaisesRegex(ValueError, "至少需要指定2个"):
            parse_historical_meta_command_args("S9", min_seasons=2, max_seasons=2)


class TestHistoricalMetaService(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.source = FakeHistoricalSource()
        self.service = MetaService(
            self.source,
            cache_root=PLUGIN_DIR / "tmp-meta-historical",
            fresh_seconds=600,
            stale_seconds=3600,
        )
        self.service.cache.save = lambda *args, **kwargs: None

    async def asyncTearDown(self):
        return None

    async def test_trend_loads_each_season_once_and_keeps_missing_hero_points(self):
        series = await self.service.get_hero_meta_trend("曼蒂斯", seasons=("S9", "S9.5"), rank="钻石")
        self.assertEqual(self.source.calls, ["18", "19"])
        self.assertEqual([point.season_label for point in series.points], ["S9上半赛季", "S9下半赛季"])
        self.assertEqual(series.points[0].result.win_rate, 50.0)
        self.assertEqual(series.points[1].result.win_rate, 60.0)
        self.assertEqual(series.points[1].win_rate_delta, 10.0)

    async def test_trend_keeps_a_missing_season_when_one_history_request_fails(self):
        source = FakeHistoricalSource()
        original = source.get_hero_stats

        async def fail_one_season(season):
            if str(season) == "19":
                raise MetaDataSourceError("temporary upstream failure")
            return await original(season)

        source.get_hero_stats = fail_one_season
        service = MetaService(source, cache_root=PLUGIN_DIR / "tmp-meta-historical-partial")
        service.cache.save = lambda *args, **kwargs: None
        series = await service.get_hero_meta_trend("曼蒂斯", seasons=("S9", "S9.5"), rank="钻石")
        self.assertIsNotNone(series.points[0].result)
        self.assertIsNone(series.points[1].result)

    async def test_version_changes_aggregate_deltas_and_preserve_missing_ban(self):
        changes = await self.service.get_meta_version_changes("S9", "S9.5", rank="钻石")
        self.assertEqual(changes.win_rate_up[0].hero_name, "曼蒂斯")
        self.assertEqual(changes.win_rate_up[0].win_rate_delta, 10.0)
        self.assertEqual(changes.win_rate_down[0].hero_name, "蜘蛛侠")

        missing = FakeHistoricalSource()
        original = missing.get_hero_stats

        async def get_without_bans(season):
            result = await original(season)
            result.bans = None
            return result

        missing.get_hero_stats = get_without_bans
        service = MetaService(missing, cache_root=PLUGIN_DIR / "tmp-meta-historical-missing")
        service.cache.save = lambda *args, **kwargs: None
        changes = await service.get_meta_version_changes("S9", "S9.5", rank="钻石")
        self.assertEqual(changes.ban_rate_up, [])
        self.assertEqual(changes.ban_rate_down, [])

    async def test_version_comparisons_reject_reverse_season_order(self):
        with self.assertRaisesRegex(ValueError, "旧赛季到新赛季"):
            await self.service.get_meta_version_changes("S9.5", "S9", rank="钻石")
        with self.assertRaisesRegex(ValueError, "旧赛季到新赛季"):
            await self.service.get_meta_insights(
                "black_horse", season="S9", previous_season="S9.5", rank="钻石", minimum_matches=1
            )

    async def test_black_horse_and_distribution_insights_use_transparent_rules(self):
        black = await self.service.get_meta_insights(
            "black_horse", season="S9.5", previous_season="S9", rank="钻石", minimum_matches=1
        )
        self.assertEqual(black.items[0].result.hero_name, "曼蒂斯")
        self.assertIn("2.0pp", black.rule)

        cold = await self.service.get_meta_insights("cold_strong", season="S9.5", rank="钻石", minimum_matches=1)
        self.assertEqual(cold.items[0].result.hero_name, "曼蒂斯")
        self.assertIn("Ban率低于", cold.rule)
        hot = await self.service.get_meta_insights("hot_trap", season="S9.5", rank="钻石", minimum_matches=1)
        self.assertEqual(hot.items[0].result.hero_name, "蜘蛛侠")

    async def test_rank_monsters_group_all_qualifying_results_by_rank(self):
        board = await self.service.get_rank_monsters(season="S9.5", minimum_matches=1)
        self.assertEqual([segment.rank_label for segment in board.segments], [
            "青铜", "白银", "黄金", "铂金", "钻石", "大师", "天神", "永恒", "万物之上",
        ])
        self.assertEqual(board.segments[2].items[0].result.hero_name, "曼蒂斯")
        self.assertNotIn("1.", format_rank_monsters(board))

    async def test_cold_strong_skips_ban_for_bronze_and_silver(self):
        result = await self.service.get_meta_insights(
            "cold_strong", season="S9.5", rank="青铜", minimum_matches=1
        )
        self.assertIn("青铜/白银不纳入", result.rule)

    async def test_cold_strong_rejects_missing_ban_for_other_ranks(self):
        source = FakeHistoricalSource()
        original = source.get_hero_stats

        async def without_bans(season):
            result = await original(season)
            result.bans = None
            return result

        source.get_hero_stats = without_bans
        service = MetaService(source, cache_root=PLUGIN_DIR / "tmp-meta-historical-cold-missing")
        service.cache.save = lambda *args, **kwargs: None
        with self.assertRaisesRegex(ValueError, "Ban 数据不足"):
            await service.get_meta_insights("cold_strong", season="S9.5", rank="钻石", minimum_matches=1)


class TestHistoricalMetaPresentation(unittest.TestCase):
    def setUp(self):
        result = HeroMetaResult(1020, "曼蒂斯", 120, 60, 100, 55, 0, 10, 55.0, 3.0, 4.0)
        timestamp = datetime(2026, 8, 17, tzinfo=timezone.utc)
        self.series = HeroRankSeries(
            1020,
            "曼蒂斯",
            "5",
            "钻石",
            [HeroRankPoint("18", "S9上半赛季", result), HeroRankPoint("19", "S9下半赛季", None)],
            "RivalsMeta",
            (timestamp, timestamp),
            timestamp,
            timestamp,
            True,
        )
        self.monsters = RankMonsterBoard(
            "19", "S9下半赛季", "透明规则", [
                RankSegment("5", "钻石", [RankMonster("5", "钻石", result, 2.0)])
            ],
            "RivalsMeta", (timestamp,), timestamp, timestamp, True,
        )

    def test_text_formatters_include_rule_source_and_missing_data(self):
        trend = format_hero_meta_trend(self.series)
        monsters = format_rank_monsters(self.monsters)
        self.assertIn("RivalsMeta", trend)
        self.assertIn("暂无数据", trend)
        self.assertIn("透明规则", monsters)
        self.assertIn("+2.00pp", monsters)

    def test_history_pages_escape_and_show_stale_state(self):
        trend_html = build_meta_trend_html(self.series)
        self.assertIn('class="mr-meta-list mr-meta-list--trend"', trend_html)
        self.assertEqual(trend_html.count('class="mr-trend-metrics"'), len(self.series.points) - 1)
        for html in (trend_html, build_rank_monsters_html(self.monsters)):
            self.assertIn('class="mr-page"', html)
            self.assertIn("当前上游暂不可用", html)
            self.assertNotIn("<script>", html)


if __name__ == "__main__":
    unittest.main()

import tempfile
import unittest
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from marvel_rivals_bot.meta.models import HeroMetaBoard, HeroMetaResult
from marvel_rivals_bot.meta.service import MetaService
from marvel_rivals_bot.meta.sources.rivalsmeta import RivalsMetaSource
from marvel_rivals_bot.meta.errors import MetaCacheError, MetaDataSourceError, MetaQueryError


PLUGIN_DIR = Path(__file__).resolve().parents[1]


def payload():
    return {
        "season": 19,
        "timestamp": 1720000000,
        "heroes": [
            {
                "rank": "5",
                "heroes": [
                    {"hero_id": 1020, "matches": 100, "wins": 60, "wr_matches": 90, "wr_wins": 45, "mirror_matches": 1},
                    {"hero_id": 1036, "matches": 50, "wins": 20, "wr_matches": 50, "wr_wins": 20, "mirror_matches": 1},
                ],
            },
            {
                "rank": "6",
                "heroes": [
                    {"hero_id": 1020, "matches": 50, "wins": 30, "wr_matches": 40, "wr_wins": 20, "mirror_matches": 1},
                ],
            },
        ],
        "bans": [{"rank": "5", "bans": [{"hero_id": 1020, "bans": 10}]}],
        "maps": [],
        "teamups": [],
    }


class FakeSource:
    def __init__(self):
        self.parser = RivalsMetaSource(env={"MRCN_RIVALSMETA_BASE_URL": "https://example.test"})
        self.calls = []
        self.fail = False

    async def get_hero_stats(self, season):
        self.calls.append(season)
        if self.fail:
            from marvel_rivals_bot.meta.errors import MetaDataSourceError

            raise MetaDataSourceError("上游不可用")
        return self.parser.parse_payload(payload())

    def parse_payload(self, value):
        return self.parser.parse_payload(value)


class TestMetaService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp_parent = PLUGIN_DIR / "tmp-meta"
        self.tmp_parent.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=self.tmp_parent)
        self.source = FakeSource()
        self.service = MetaService(
            self.source,
            cache_root=Path(self.tmp.name),
            fresh_seconds=600,
            stale_seconds=3600,
            default_season="19",
        )

    def tearDown(self):
        self.tmp.cleanup()

    async def test_board_uses_api_season_code_and_view_model(self):
        board = await self.service.get_hero_meta_board(season="S9.5", rank="钻石+", sort_by="matches")
        self.assertEqual(self.source.calls, ["19"])
        self.assertEqual(board.season_code, "19")
        self.assertEqual(board.season_label, "S9下半赛季")
        self.assertEqual(board.rank_label, "钻石+")
        self.assertEqual(board.heroes[0].hero_name, "曼蒂斯")
        self.assertFalse(board.stale)

    async def test_missing_bans_remain_unavailable_through_service(self):
        original_get = self.source.get_hero_stats

        async def get_without_bans(season):
            result = await original_get(season)
            result.bans = None
            return result

        self.source.get_hero_stats = get_without_bans
        board = await self.service.get_hero_meta_board(season="S9", rank="钻石")
        self.assertIsNone(board.heroes[0].bans)
        self.assertIsNone(board.heroes[0].ban_rate)

    async def test_overview_selects_each_metric_from_one_board(self):
        overview = await self.service.get_hero_meta_overview(season="S9", rank="钻石")
        self.assertEqual(overview.season_label, "S9下半赛季")
        self.assertEqual(overview.win_rate[0].hero_id, 1020)
        self.assertEqual(overview.ban_rate[0].hero_id, 1020)

    async def test_overview_sorts_each_metric_independently(self):
        def result(hero_id, name, win_rate, pick_rate, ban_rate, matches):
            return HeroMetaResult(
                hero_id=hero_id,
                hero_name=name,
                matches=matches,
                wins=0,
                wr_matches=1,
                wr_wins=0,
                mirror_matches=0,
                bans=0,
                win_rate=win_rate,
                pick_rate=pick_rate,
                ban_rate=ban_rate,
            )

        board = HeroMetaBoard(
            season_code="19",
            season_label="S9下半赛季",
            rank_key="5",
            rank_label="钻石",
            sort_by="win_rate",
            heroes=[
                result(1020, "曼蒂斯", 60, 1, 2, 10),
                result(1036, "蜘蛛侠", 50, 9, 1, 20),
                result(1023, "火箭浣熊", 40, 3, 8, 5),
            ],
            source="RivalsMeta",
            source_timestamp=None,
            fetched_at=datetime.now(timezone.utc),
        )

        async def fake_board(**_kwargs):
            return board

        self.service.get_hero_meta_board = fake_board
        overview = await self.service.get_hero_meta_overview()
        self.assertEqual(overview.win_rate[0].hero_id, 1020)
        self.assertEqual(overview.pick_rate[0].hero_id, 1036)
        self.assertEqual(overview.ban_rate[0].hero_id, 1023)

    async def test_memory_cache_avoids_second_remote_fetch(self):
        with self.assertLogs("marvel_rivals_bot.meta.service", level=logging.INFO) as logs:
            await self.service.get_raw_hero_meta("S9")
            await self.service.get_raw_hero_meta("S9")
        self.assertEqual(self.source.calls, ["18"])
        self.assertIn("cache=memory_fresh", "\n".join(logs.output))

    async def test_stale_cache_is_used_when_remote_fails(self):
        fetched_at = datetime.now(timezone.utc) - timedelta(seconds=1200)
        cached_payload = payload()
        cached_payload["season"] = 18
        self.service.cache.save("18", cached_payload, "RivalsMeta", 1720000000, fetched_at)
        self.source.fail = True
        with self.assertLogs("marvel_rivals_bot.meta.service", level=logging.WARNING) as logs:
            result = await self.service.get_raw_hero_meta("S9")
        self.assertTrue(result.stale)
        self.assertEqual(result.source, "RivalsMeta")
        self.assertIn("cache=stale_fallback", "\n".join(logs.output))

    async def test_cache_write_failure_is_logged_but_remote_data_is_returned(self):
        from unittest.mock import patch

        with patch.object(self.service.cache, "save", side_effect=MetaCacheError("write")):
            with self.assertLogs("marvel_rivals_bot.meta.service", level=logging.WARNING) as logs:
                result = await self.service.get_raw_hero_meta("S9")
        self.assertEqual(result.season, 19)
        self.assertIn("cache=write_failure", "\n".join(logs.output))

    async def test_user_query_errors_are_not_data_source_errors(self):
        with self.assertRaises(MetaQueryError):
            await self.service.get_hero_meta_board(season="not-a-season")
        with self.assertRaises(MetaQueryError):
            await self.service.get_hero_meta_board(rank="not-a-rank")
        with self.assertRaises(MetaQueryError):
            await self.service.get_hero_meta_board(sort_by="not-a-sort")
        with self.assertRaises(MetaQueryError):
            await self.service.get_single_hero_meta("不存在的英雄")
        with self.assertRaises(MetaQueryError):
            await self.service.get_single_hero_meta("奇异博士", season="S9")
        self.assertFalse(issubclass(MetaQueryError, MetaDataSourceError))

    async def test_invalid_cached_payload_is_discarded_before_remote_fetch(self):
        self.service.cache.save("18", {"season": 18}, "RivalsMeta")
        with self.assertLogs("marvel_rivals_bot.meta.service", level=logging.WARNING) as logs:
            result = await self.service.get_raw_hero_meta("S9")
        self.assertEqual(self.source.calls, ["18"])
        self.assertFalse(result.stale)
        self.assertIn("cache=invalid_payload", "\n".join(logs.output))

    async def test_cached_payload_with_wrong_season_is_discarded(self):
        self.service.cache.save("18", payload(), "RivalsMeta")
        await self.service.get_raw_hero_meta("S9")
        self.assertEqual(self.source.calls, ["18"])

    async def test_single_hero_uses_existing_chinese_mapping(self):
        result = await self.service.get_single_hero_meta("曼蒂斯", season="S9")
        self.assertEqual(result.hero_id, 1020)
        self.assertEqual(result.matches, 150)

    async def test_segments_use_canonical_rank_order_and_one_payload(self):
        result = await self.service.get_hero_meta_segments("曼蒂斯", season="S9.5")
        self.assertEqual(self.source.calls, ["19"])
        self.assertEqual(
            [item.rank_code for item in result.segments],
            ["1", "2", "3", "4", "5", "6", "9", "7", "8"],
        )
        self.assertEqual(result.segments[4].rank_label, "钻石")
        self.assertEqual(result.segments[4].result.matches, 100)
        self.assertIsNone(result.segments[0].result)
        self.assertIsNone(result.segments[5].result.ban_rate)

    async def test_comparison_uses_same_rank_and_preserves_requested_order(self):
        result = await self.service.get_hero_meta_comparison(
            "蜘蛛侠", "曼蒂斯", season="S9.5", rank="钻石"
        )
        self.assertEqual(self.source.calls, ["19"])
        self.assertEqual(result.rank_label, "钻石")
        self.assertEqual(result.left.hero_name, "蜘蛛侠")
        self.assertEqual(result.right.hero_name, "曼蒂斯")
        self.assertEqual(result.left.matches, 50)
        self.assertEqual(result.right.matches, 100)
        self.assertEqual(result.left.ban_rate, 0.0)
        self.assertEqual(result.right.ban_rate, 200.0)

    async def test_comparison_rejects_duplicate_heroes(self):
        with self.assertRaisesRegex(MetaQueryError, "两个不同"):
            await self.service.get_hero_meta_comparison("曼蒂斯", "曼蒂斯")


if __name__ == "__main__":
    unittest.main()

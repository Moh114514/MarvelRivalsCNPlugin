import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from marvel_rivals_bot.meta.service import MetaService
from marvel_rivals_bot.meta.sources.rivalsmeta import RivalsMetaSource


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

    async def test_memory_cache_avoids_second_remote_fetch(self):
        await self.service.get_raw_hero_meta("S9")
        await self.service.get_raw_hero_meta("S9")
        self.assertEqual(self.source.calls, ["18"])

    async def test_stale_cache_is_used_when_remote_fails(self):
        fetched_at = datetime.now(timezone.utc) - timedelta(seconds=1200)
        cached_payload = payload()
        cached_payload["season"] = 18
        self.service.cache.save("18", cached_payload, "RivalsMeta", 1720000000, fetched_at)
        self.source.fail = True
        result = await self.service.get_raw_hero_meta("S9")
        self.assertTrue(result.stale)
        self.assertEqual(result.source, "RivalsMeta")

    async def test_invalid_cached_payload_is_discarded_before_remote_fetch(self):
        self.service.cache.save("18", {"season": 18}, "RivalsMeta")
        result = await self.service.get_raw_hero_meta("S9")
        self.assertEqual(self.source.calls, ["18"])
        self.assertFalse(result.stale)

    async def test_cached_payload_with_wrong_season_is_discarded(self):
        self.service.cache.save("18", payload(), "RivalsMeta")
        await self.service.get_raw_hero_meta("S9")
        self.assertEqual(self.source.calls, ["18"])

    async def test_single_hero_uses_existing_chinese_mapping(self):
        result = await self.service.get_single_hero_meta("曼蒂斯", season="S9")
        self.assertEqual(result.hero_id, 1020)
        self.assertEqual(result.matches, 150)


if __name__ == "__main__":
    unittest.main()

import unittest
from datetime import datetime, timezone

from marvel_rivals_bot.analytics.commands import parse_player_meta_args
from marvel_rivals_bot.analytics.player_meta import PlayerMetaQueryError, PlayerMetaService
from marvel_rivals_bot.meta.models import HeroMetaBoard, HeroMetaOverview, HeroMetaResult
from marvel_rivals_bot.models import HeroStat, ModeStats, PlayerHeroStats, PlayerProfile, PlayerStats


class FakeRivalsService:
    def __init__(self, stats):
        self.stats = stats
        self.calls = []

    async def get_player_stats(self, uid, season=None):
        self.calls.append((uid, season))
        return self.stats


class FakeMetaService:
    def __init__(self, board, overview):
        self.board = board
        self.overview = overview
        self.board_calls = []
        self.overview_calls = []

    async def get_hero_meta_board(self, **kwargs):
        self.board_calls.append(kwargs)
        return self.board

    async def get_hero_meta_overview(self, **kwargs):
        self.overview_calls.append(kwargs)
        return self.overview


def result(hero_id, name, win_rate, pick_rate=4.0, ban_rate=1.0, matches=100):
    return HeroMetaResult(
        hero_id=hero_id,
        hero_name=name,
        matches=matches,
        wins=round(matches * win_rate / 100),
        wr_matches=matches,
        wr_wins=round(matches * win_rate / 100),
        mirror_matches=0,
        bans=10,
        win_rate=win_rate,
        pick_rate=pick_rate,
        ban_rate=ban_rate,
    )


class TestPlayerMetaService(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.meta_results = [
            result(1020, "英雄A", 50.0, matches=100),
            result(1036, "英雄B", 45.0, matches=80),
            result(1040, "英雄C", 55.0, matches=60),
        ]
        timestamp = datetime(2026, 8, 17, tzinfo=timezone.utc)
        self.board = HeroMetaBoard(
            "19", "S9下半赛季", "5", "钻石", "matches", self.meta_results,
            "RivalsMeta", timestamp, timestamp,
        )
        self.overview = HeroMetaOverview(
            "19", "S9下半赛季", "5", "钻石",
            self.meta_results[:1], self.meta_results[1:2], self.meta_results[2:3],
            "RivalsMeta", timestamp, timestamp,
        )
        stats = PlayerStats(
            profile=PlayerProfile(
                uid="123",
                name="测试玩家",
                rank_game_season="钻石2",
                rank_level=14,
            ),
            heroes=[
                HeroStat("1020", "英雄A", matches=30, wins=21),
                HeroStat("1036", "英雄B", matches=10, wins=8),
                HeroStat("1040", "英雄C", matches=50, wins=20),
            ],
            season="19",
        )
        self.rivals = FakeRivalsService(stats)
        self.meta = FakeMetaService(self.board, self.overview)
        self.service = PlayerMetaService(self.rivals, self.meta)

    async def test_environment_maps_cn_rank_to_meta_rank_without_mixing_sources(self):
        profile = await self.service.get_player_environment("123", season="S9.5")
        self.assertEqual(profile.meta_rank_code, "5")
        self.assertEqual(profile.meta_rank_label, "钻石")
        self.assertEqual(profile.cn_rank_level, 14)
        self.assertEqual(profile.environment.win_rate[0].hero_id, 1020)
        self.assertEqual(self.rivals.calls, [("123", "S9.5")])
        self.assertEqual(self.meta.board_calls[0]["rank"], "5")
        self.assertEqual(self.meta.overview_calls[0]["rank"], "5")

    async def test_hero_pool_calculates_personal_rate_and_delta(self):
        profile = await self.service.get_player_hero_pool("123")
        self.assertEqual([item.hero_id for item in profile.hero_pool], ["1040", "1020", "1036"])
        self.assertAlmostEqual(profile.hero_pool[1].personal_win_rate, 70.0)
        self.assertAlmostEqual(profile.hero_pool[1].win_rate_delta, 20.0)
        self.assertEqual(profile.hero_pool[0].personal_matches, 50)

    async def test_signature_filters_minimum_matches_and_sorts_by_delta(self):
        profile = await self.service.get_player_signature("123", minimum_matches=1, minimum_ranked_matches=1)
        self.assertEqual([item.hero_id for item in profile.signature_heroes], ["1036", "1020"])
        self.assertEqual(profile.minimum_matches, 1)
        self.assertEqual(profile.minimum_ranked_matches, 5)
        self.assertAlmostEqual(profile.signature_heroes[0].win_rate_delta, 35.0)

    async def test_signature_accepts_five_competitive_matches(self):
        self.rivals.stats.heroes = [PlayerHeroStats(
            hero_id="1020",
            hero_name="英雄A",
            quick=ModeStats(matches=0, wins=0),
            competitive=ModeStats(matches=5, wins=4, win_rate=80.0),
        )]
        profile = await self.service.get_player_signature("123", minimum_matches=5)
        self.assertEqual([item.hero_id for item in profile.signature_heroes], ["1020"])
        self.assertEqual(profile.minimum_ranked_matches, 5)

    async def test_unknown_rank_is_user_safe(self):
        self.rivals.stats.profile.rank_level = None
        self.rivals.stats.profile.rank_game_season = "未定级"
        with self.assertRaises(PlayerMetaQueryError):
            await self.service.get_player_environment("123")

    async def test_missing_hero_details_are_not_coerced_to_zero(self):
        self.rivals.stats.heroes = [PlayerHeroStats(
            hero_id="1020",
            hero_name="英雄A",
            quick=ModeStats(matches=None),
            competitive=ModeStats(matches=None),
        )]
        with self.assertRaisesRegex(PlayerMetaQueryError, "英雄详细数据获取失败"):
            await self.service.get_player_hero_pool("123")


class TestPlayerMetaCommandArgs(unittest.TestCase):
    def test_season_and_minimum_matches_are_order_independent(self):
        args = parse_player_meta_args("S9.5", "25", allow_minimum_matches=True)
        self.assertEqual(args.season, "S9.5")
        self.assertEqual(args.minimum_matches, 25)

    def test_uid_and_season_are_order_independent(self):
        args = parse_player_meta_args("S9.5", "1287101468", allow_uid=True)
        self.assertEqual(args.season, "S9.5")
        self.assertEqual(args.uid, "1287101468")

    def test_signature_accepts_uid_and_minimum_matches(self):
        args = parse_player_meta_args(
            "1287101468", "50", allow_uid=True, allow_minimum_matches=True
        )
        self.assertEqual(args.uid, "1287101468")
        self.assertEqual(args.minimum_matches, 50)
        self.assertTrue(args.minimum_matches_provided)

    def test_environment_rejects_numeric_minimum_matches(self):
        with self.assertRaises(ValueError):
            parse_player_meta_args("25")

    def test_invalid_minimum_matches_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_player_meta_args("0", allow_minimum_matches=True)


if __name__ == "__main__":
    unittest.main()

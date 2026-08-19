import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from marvel_rivals_bot.analytics.models import PlayerSignatureProfile
from marvel_rivals_bot.analytics.formatters import format_player_signature
from marvel_rivals_bot.analytics.signature import PlayerSignatureService
from marvel_rivals_bot.meta.models import HeroMetaBoard, HeroMetaResult
from marvel_rivals_bot.models import ModeStats, PlayerHeroStats, PlayerProfile
from marvel_rivals_bot.datasource.base import GameMode


def _meta(season, rank, win_rate):
    result = HeroMetaResult(
        1026, "黑豹", 100, 50, 100, 50, 0, 10,
        win_rate, 5.0, 1.0,
    )
    return HeroMetaBoard(
        season, f"S{season}", rank, {"5": "钻石", "6": "大师", "9": "天神", "all": "全段位"}.get(rank, "全段位"),
        "matches", [result], "RivalsMeta", None, None,
    )


class FakeRivals:
    def __init__(self):
        self.batch_calls = []
        self.profile = PlayerProfile(
            uid="123", name="测试玩家", rank_history={"14": 14, "15": 16, "16": 19}
        )
        self.rows = {
            "14": (10, 6),
            "15": (30, 18),
            "16": (60, 36),
        }

    async def get_player_profile_history(self, uid):
        return self.profile

    async def get_hero_profiles_batch(self, uid, hero_ids, season, game_mode, *, batch_size=32):
        self.batch_calls.append((season, game_mode, tuple(hero_ids), batch_size))
        if season not in self.rows:
            return []
        matches, wins = self.rows[season]
        if game_mode is GameMode.QUICK:
            return [PlayerHeroStats(
                hero_id="1026", hero_name="黑豹", quick=ModeStats(matches=matches, wins=wins)
            )]
        return [PlayerHeroStats(
            hero_id="1026", hero_name="黑豹", competitive=ModeStats(matches=matches, wins=wins)
        )]


class FakeMeta:
    def __init__(self):
        self.calls = []

    async def get_hero_meta_board(self, **kwargs):
        self.calls.append(kwargs)
        rank = kwargs["rank"]
        return _meta(kwargs["season"], rank, {"5": 50.0, "6": 52.0, "9": 54.0}.get(rank, 50.0))


class FakeStaleMeta(FakeMeta):
    async def get_hero_meta_board(self, **kwargs):
        board = await super().get_hero_meta_board(**kwargs)
        board.stale = True
        board.source_timestamp = datetime(2026, 8, 1, tzinfo=timezone.utc)
        return board


class FakeSickRivals(FakeRivals):
    async def get_hero_profiles_batch(self, uid, hero_ids, season, game_mode, *, batch_size=32):
        values = await super().get_hero_profiles_batch(
            uid, hero_ids, season, game_mode, batch_size=batch_size
        )
        if season in self.rows:
            if game_mode is GameMode.QUICK:
                values.append(PlayerHeroStats(
                    hero_id="1027", hero_name="测试低胜率英雄", quick=ModeStats(matches=10, wins=2)
                ))
            else:
                values.append(PlayerHeroStats(
                    hero_id="1027", hero_name="测试低胜率英雄", competitive=ModeStats(matches=10, wins=2)
                ))
            if game_mode is GameMode.QUICK:
                values.append(PlayerHeroStats(
                    hero_id="1028", hero_name="测试高胜率英雄", quick=ModeStats(matches=10, wins=10)
                ))
            else:
                values.append(PlayerHeroStats(
                    hero_id="1028", hero_name="测试高胜率英雄", competitive=ModeStats(matches=10, wins=10)
                ))
        return values


class FakeSickMeta(FakeMeta):
    async def get_hero_meta_board(self, **kwargs):
        board = await super().get_hero_meta_board(**kwargs)
        board.heroes.append(
            HeroMetaResult(
                1027, "测试低胜率英雄", 100, 50, 100, 50, 0, 10,
                50.0, 5.0, 1.0,
            )
        )
        board.heroes.append(
            HeroMetaResult(
                1028, "测试高胜率英雄", 100, 50, 100, 50, 0, 10,
                50.0, 5.0, 1.0,
            )
        )
        return board


class TestPlayerSignatureService(unittest.IsolatedAsyncioTestCase):
    async def test_joins_each_season_to_its_historical_rank_and_weights_meta(self):
        rivals = FakeRivals()
        meta = FakeMeta()
        service = PlayerSignatureService(rivals, meta, cache_root=None)
        profile = await service.get_player_signature("123")

        self.assertIsInstance(profile, PlayerSignatureProfile)
        hero = profile.signature_heroes[0]
        # (10*50% + 30*52% + 60*54%) / 100 = 53%; the same rank-specific
        # Meta calls are made per season before aggregation.
        self.assertAlmostEqual(hero.expected_meta_win_rate, 53.0)
        self.assertAlmostEqual(hero.actual_win_rate, 60.0)
        self.assertAlmostEqual(hero.raw_delta, 7.0)
        self.assertAlmostEqual(hero.adjusted_delta, 7.0 * 100 / 120)
        self.assertEqual(hero.comparable_seasons, 3)
        self.assertEqual([call["rank"] for call in meta.calls], ["5", "6", "9"])
        self.assertEqual(len(rivals.batch_calls), 38)

    async def test_same_uid_inflight_and_result_cache(self):
        rivals = FakeRivals()
        meta = FakeMeta()
        service = PlayerSignatureService(rivals, meta, cache_root=None)
        first, second = await __import__("asyncio").gather(
            service.get_player_signature("123"), service.get_player_signature("123")
        )
        calls_after_first = len(rivals.batch_calls)
        third = await service.get_player_signature("123")
        self.assertEqual(first.uid, second.uid)
        self.assertEqual(first.uid, third.uid)
        self.assertEqual(len(rivals.batch_calls), calls_after_first)

    async def test_stale_meta_is_exposed_as_partial_profile_data(self):
        profile = await PlayerSignatureService(
            FakeRivals(), FakeStaleMeta(), cache_root=None
        ).get_player_signature("123")

        self.assertTrue(profile.partial)
        self.assertTrue(profile.meta_stale)
        self.assertEqual(profile.meta_source, "RivalsMeta")
        self.assertIsNotNone(profile.meta_source_timestamp)
        rendered = format_player_signature(profile)
        self.assertIn("Meta", rendered)
        self.assertIn(profile.meta_source_timestamp, rendered)

    async def test_sick_ranking_uses_meta_deficit_and_excludes_signature_heroes(self):
        profile = await PlayerSignatureService(
            FakeSickRivals(), FakeSickMeta(), cache_root=None
        ).get_player_signature("123")

        self.assertEqual(profile.sick_heroes[0].hero_id, "1027")
        self.assertAlmostEqual(profile.sick_heroes[0].actual_win_rate, 20.0)
        self.assertGreater(profile.sick_heroes[0].sick_score, 1.0)
        self.assertIn("1026", {item.hero_id for item in profile.signature_heroes})
        self.assertNotIn("1026", {item.hero_id for item in profile.sick_heroes})
        self.assertEqual(len(profile.sick_heroes), 1)

    async def test_no_qualified_hero_does_not_fill_sickness_ranking(self):
        profile = await PlayerSignatureService(
            FakeRivals(), FakeMeta(), cache_root=None
        ).get_player_signature("123")
        self.assertEqual(profile.sick_heroes, ())


if __name__ == "__main__":
    unittest.main()

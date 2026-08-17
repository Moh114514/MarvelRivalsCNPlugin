import unittest

from marvel_rivals_bot.hero_names import HERO_ID_MAP, format_hero_name, get_hero_id, get_hero_name
from marvel_rivals_bot.game_metadata import (
    MATCH_MAPS,
    RIVALSMETA_SEASON_MAP,
    format_game_mode,
    format_match_map,
    format_queue,
    get_map_mode,
    get_map_queue_variant,
)
from marvel_rivals_bot.models import HeroQueryResult, HeroStat, ModeStats, PlayerHeroStats, PlayerProfile, PlayerStats
from marvel_rivals_bot.services.rivals import (
    RivalsService,
    format_hero,
    format_hero_result,
    format_match_detail,
    format_matches,
    format_player,
    format_season_name,
    parse_season_name,
)


class TestFormatters(unittest.TestCase):
    def test_recent_match_uses_nested_current_player(self):
        text = format_matches([{
            "matchUid": "match-1",
            "matchTimeStamp": 1_700_000_000,
            "matchMapId": 1413,
            "matchPlayDuration": 480,
            "matchPlayer": {"isWin": 1, "curHeroId": 1036, "k": 18, "d": 1, "a": 30},
        }])
        self.assertIn("胜", text)
        self.assertIn("蜘蛛侠（1036）", text)
        self.assertIn("KDA 18/1/30", text)
        self.assertIn("matchUid=match-1", text)

    def test_recent_match_uses_hero_id_enriched_from_detail(self):
        text = format_matches([{
            "matchUid": "match-1",
            "matchPlayer": {"isWin": 1, "curHeroId": 1023, "k": 16, "d": 1, "a": 47},
        }], "19")
        self.assertIn("火箭浣熊（1023）", text)
        self.assertNotIn("未知英雄", text)

    def test_hero_uses_careers_array(self):
        text = format_hero({"data": {"careers": [{
            "heroId": 1066,
            "totalMatchCount": 10.31,
            "totalMatchWinCount": 6.79,
            "totalPlayTime": 28737.34,
            "k": 185.8,
            "d": 28.2,
            "a": 24.4,
        }]}})
        self.assertIn("英雄：红兜帽（1066）", text)
        self.assertIn("场次：10", text)
        self.assertIn("胜场：7", text)
        self.assertIn("186 / 28 / 24", text)
        self.assertIn("游玩时长：7.98 小时", text)
        self.assertNotIn("10.3", text)

    def test_structured_hero_formatter_separates_quick_and_ranked(self):
        text = format_hero_result(HeroQueryResult(
            uid="1",
            hero_id="1066",
            hero_name="红兜帽",
            season="19",
            stats=PlayerHeroStats(
                hero_id="1066",
                hero_name="红兜帽",
                total_matches=30,
                total_wins=18,
                quick=ModeStats(matches=20, wins=10, win_rate=50.0),
                ranked=ModeStats(matches=10, wins=8, win_rate=80.0, kills=100),
            ),
        ))
        self.assertIn("总计使用：30 场", text)
        self.assertIn("快速：20 场", text)
        self.assertIn("竞技：10 场", text)
        self.assertIn("竞技 K/D/A：100", text)

    def test_match_detail_uses_matches_and_match_players(self):
        text = format_match_detail({"data": {"matches": [{
            "matchUid": "match-1",
            "matchMapId": 1413,
            "matchPlayers": [{
                "playerUid": 1,
                "nickName": "Tester",
                "camp": 1,
                "isWin": 1,
                "curHeroId": 1064,
                "k": 18,
                "d": 1,
                "a": 30,
            }],
        }]}})
        self.assertIn("Tester", text)
        self.assertIn("英雄 李千欢（1064）", text)
        self.assertIn("18/1/30", text)

    def test_player_top_heroes_use_chinese_names(self):
        text = format_player(PlayerStats(
            profile=PlayerProfile(uid="1", name="Tester"),
            heroes=[HeroStat(hero_id="1066", matches=10, wins=7, kills=186, play_time_seconds=60)],
            season="18",
        ))
        self.assertIn("（S9上半赛季的数据）", text)
        self.assertIn("红兜帽（1066）", text)
        self.assertIn("总计 10 / 快速 0 / 竞技 10", text)
        self.assertNotIn("时长", text)

    def test_season_codes_map_to_half_seasons(self):
        self.assertEqual(format_season_name(1), "S0")
        self.assertEqual(format_season_name(2), "S1上半赛季")
        self.assertEqual(format_season_name(3), "S1下半赛季")
        self.assertEqual(format_season_name(18), "S9上半赛季")
        self.assertEqual(format_season_name("19"), "S9下半赛季")

    def test_user_season_names_map_to_api_codes(self):
        self.assertEqual(parse_season_name("S0"), "1")
        self.assertEqual(parse_season_name("s0"), "1")
        self.assertEqual(parse_season_name("S9上半赛季"), "18")
        self.assertEqual(parse_season_name("s9下半赛季"), "19")
        self.assertEqual(parse_season_name("S9"), "18")
        self.assertEqual(parse_season_name("s9.5"), "19")
        self.assertEqual(parse_season_name("S8.5"), "17")
        for invalid in ("S0.5", "S0上半赛季", "S0下半赛季"):
            with self.assertRaisesRegex(Exception, "S0 没有半赛季"):
                parse_season_name(invalid)
        with self.assertRaisesRegex(Exception, "S9上半赛季"):
            parse_season_name("18")

    def test_game_mode_map_and_map_names_use_separate_namespaces(self):
        self.assertEqual(format_game_mode(2), "竞技比赛（2）")
        self.assertEqual(format_queue(2, 0), "竞技比赛")
        self.assertEqual(format_queue(2, 1), "自定义比赛")
        self.assertEqual(format_queue(6, 0), "街机模式")
        self.assertEqual(format_match_map(1118), "永恒之夜帝国：至圣所（1118）")
        self.assertEqual(get_map_mode(1118), "纷争模式")
        self.assertEqual(format_match_map(1434), "底比斯（1434）")
        self.assertEqual(RIVALSMETA_SEASON_MAP[18], "S9")

    def test_match_map_ids_use_cn_names_and_keep_queue_variants(self):
        expected_ids = {
            1034, 1230, 1101, 1267, 1217, 1292, 1240, 1290, 2041, 2042,
            1411, 1421, 1032, 1231, 1148, 1245, 1201, 1291, 1286, 1311,
            1413, 1418, 1420, 1434, 1170, 1236, 1235, 1272, 1287, 1288, 1309,
            1310, 1317, 1318,
        }
        self.assertTrue(expected_ids.issubset(MATCH_MAPS))
        self.assertEqual(MATCH_MAPS[1034], ("东京2099：新涩谷区", "融合模式", "quick"))
        self.assertEqual(MATCH_MAPS[1230], ("东京2099：新涩谷区", "融合模式", "competitive"))
        self.assertEqual(format_match_map(1413), "沉思藏馆（1413）")
        self.assertEqual(format_match_map(1170), "阿斯加德：仙宫（1170）")
        self.assertEqual(get_map_mode(1287), "角逐模式")
        self.assertEqual(get_map_queue_variant(1287), "quick")
        self.assertEqual(get_map_queue_variant(1288), "competitive")
        self.assertEqual(get_map_queue_variant(1420), "quick")
        self.assertEqual(get_map_queue_variant(1434), "competitive")

    def test_match_output_formats_map_queue_and_play_mode_separately(self):
        text = format_match_detail({"data": {"matches": [{
            "matchUid": "match-1",
            "matchMapId": 1118,
            "gameModeId": 6,
            "playModeId": 7,
            "matchPlayers": [],
        }]}})
        self.assertIn("地图：永恒之夜帝国：至圣所（1118）", text)
        self.assertIn("队列：街机模式", text)
        self.assertIn("玩法：纷争模式", text)
        self.assertNotIn("模式：6/7", text)

    def test_chinese_hero_names_map_to_ids(self):
        self.assertEqual(get_hero_id("蜘蛛侠"), 1036)
        self.assertEqual(get_hero_id("潘妮帕克"), 1042)
        with self.assertRaisesRegex(ValueError, "中文名称"):
            get_hero_id("1036")

    def test_bound_command_argument_positions(self):
        from main import MarvelRivalsPlugin

        self.assertEqual(
            MarvelRivalsPlugin._uid_and_season("S9上半赛季", ""),
            ("", "S9上半赛季"),
        )
        self.assertEqual(
            MarvelRivalsPlugin._uid_and_season("1287101468", "s9下半赛季"),
            ("1287101468", "s9下半赛季"),
        )


class TestServiceTranslation(unittest.IsolatedAsyncioTestCase):
    async def test_player_cache_keeps_structured_stats_for_text_and_cards(self):
        class FakeSource:
            default_season = "19"

            def __init__(self):
                self.calls = 0

            async def get_player(self, uid, season):
                self.calls += 1
                return PlayerStats(profile=PlayerProfile(uid=uid, name="Tester"), season=season)

        source = FakeSource()
        service = RivalsService(source, cache_seconds=60)
        stats = await service.get_player_stats("1", "S9.5")
        text = await service.player_text("1", "S9.5")
        self.assertIsInstance(stats, PlayerStats)
        self.assertIn("Tester", text)
        self.assertEqual(source.calls, 1)

    async def test_s0_is_translated_to_api_season_one(self):
        class FakeSource:
            default_season = "19"

            async def get_player(self, uid, season):
                self.call = (uid, season)
                return PlayerStats(profile=PlayerProfile(uid=uid), season=season)

        source = FakeSource()
        service = RivalsService(source, cache_seconds=0)
        stats = await service.get_player_stats("1287101468", "s0")
        self.assertEqual(source.call, ("1287101468", "1"))
        self.assertEqual(format_player(stats).splitlines()[0], "漫威争锋国服个人资料（S0的数据）")

    async def test_structured_recent_hero_and_match_queries_share_cache_with_text(self):
        class FakeSource:
            default_season = "19"

            def __init__(self):
                self.calls = {"recent": 0, "hero": 0, "match": 0}

            async def get_recent_matches(self, uid, season):
                self.calls["recent"] += 1
                return [{"matchUid": "m-1"}]

            async def get_hero(self, uid, hero_id, season):
                self.calls["hero"] += 1
                return {"data": {"careers": [{"heroId": int(hero_id)}]}}

            async def get_summary_detail(self, match_uid):
                self.calls["match"] += 1
                return {"data": {"matches": [{"matchUid": match_uid}]}}

        source = FakeSource()
        service = RivalsService(source, cache_seconds=60)
        await service.get_recent_matches("123", "S9.5")
        await service.matches_text("123", "S9.5")
        await service.get_hero_stats("123", "蜘蛛侠", "S9.5")
        await service.hero_text("123", "蜘蛛侠", "S9.5")
        await service.get_match_detail("m-1")
        await service.match_detail_text("m-1")
        self.assertEqual(source.calls, {"recent": 1, "hero": 1, "match": 1})

    async def test_hero_name_and_season_are_translated_before_data_source_call(self):
        class FakeSource:
            default_season = "19"

            async def get_hero(self, uid, hero_id, season):
                self.call = (uid, hero_id, season)
                return {"data": {"careers": [{"heroId": int(hero_id)}]}}

        source = FakeSource()
        service = RivalsService(source, cache_seconds=0)
        await service.hero_text("1287101468", "蜘蛛侠", "s9上半赛季")
        self.assertEqual(source.call, ("1287101468", "1036", "18"))

    def test_hero_map_is_complete_and_unknown_ids_have_fallback(self):
        self.assertGreaterEqual(len(HERO_ID_MAP), 55)
        self.assertEqual(get_hero_name(10571), "T位死侍")
        self.assertEqual(get_hero_name(10572), "C位死侍")
        self.assertEqual(get_hero_name(10573), "奶位死侍")
        self.assertEqual(get_hero_name(1031), "冰月花雪")
        self.assertEqual(get_hero_name("1047"), "陆行鲨杰夫")
        self.assertEqual(format_hero_name(9999), "英雄 9999（9999）")


if __name__ == "__main__":
    unittest.main()

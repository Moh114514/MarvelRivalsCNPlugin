import unittest

from marvel_rivals_bot.hero_names import HERO_ID_MAP, format_hero_name, get_hero_id, get_hero_name
from marvel_rivals_bot.game_metadata import (
    RIVALSMETA_SEASON_MAP,
    format_game_mode,
    format_match_map,
    format_queue,
    get_map_mode,
)
from marvel_rivals_bot.models import HeroStat, PlayerProfile, PlayerStats
from marvel_rivals_bot.services.rivals import (
    RivalsService,
    format_hero,
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
        self.assertIn("出场 10 / 胜场 7 / 击败 186", text)
        self.assertNotIn("时长", text)

    def test_season_codes_map_to_half_seasons(self):
        self.assertEqual(format_season_name(18), "S9上半赛季")
        self.assertEqual(format_season_name("19"), "S9下半赛季")

    def test_user_season_names_map_to_api_codes(self):
        self.assertEqual(parse_season_name("S9上半赛季"), "18")
        self.assertEqual(parse_season_name("s9下半赛季"), "19")
        self.assertEqual(parse_season_name("S9"), "18")
        self.assertEqual(parse_season_name("s9.5"), "19")
        self.assertEqual(parse_season_name("S8.5"), "17")
        with self.assertRaisesRegex(Exception, "S9上半赛季"):
            parse_season_name("18")

    def test_game_mode_map_and_map_names_use_separate_namespaces(self):
        self.assertEqual(format_game_mode(2), "竞技比赛（2）")
        self.assertEqual(format_queue(2, 0), "竞技比赛")
        self.assertEqual(format_queue(2, 1), "自定义比赛")
        self.assertEqual(format_queue(6, 0), "街机模式")
        self.assertEqual(format_match_map(1118), "圣所 / Sanctum Sanctorum（1118）")
        self.assertEqual(get_map_mode(1118), "Doom Match")
        self.assertEqual(format_match_map(1434), "未知地图（ID 1434）")
        self.assertEqual(RIVALSMETA_SEASON_MAP[18], "S9")

    def test_match_output_formats_map_queue_and_play_mode_separately(self):
        text = format_match_detail({"data": {"matches": [{
            "matchUid": "match-1",
            "matchMapId": 1118,
            "gameModeId": 6,
            "playModeId": 7,
            "matchPlayers": [],
        }]}})
        self.assertIn("地图：圣所 / Sanctum Sanctorum（1118）", text)
        self.assertIn("队列：街机模式", text)
        self.assertIn("玩法：Doom Match", text)
        self.assertNotIn("模式：6/7", text)

    def test_chinese_hero_names_map_to_ids(self):
        self.assertEqual(get_hero_id("蜘蛛侠"), 1036)
        self.assertEqual(get_hero_id("潘妮帕克"), 1042)
        with self.assertRaisesRegex(ValueError, "中文名称"):
            get_hero_id("1036")

    def test_bound_command_argument_positions(self):
        from astrbot_plugin_marvel_rivals.main import MarvelRivalsPlugin

        self.assertEqual(
            MarvelRivalsPlugin._uid_and_season("S9上半赛季", ""),
            ("", "S9上半赛季"),
        )
        self.assertEqual(
            MarvelRivalsPlugin._uid_and_season("1287101468", "s9下半赛季"),
            ("1287101468", "s9下半赛季"),
        )


class TestServiceTranslation(unittest.IsolatedAsyncioTestCase):
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
        self.assertEqual(len(HERO_ID_MAP), 53)
        self.assertEqual(get_hero_name(1031), "冰月花雪")
        self.assertEqual(get_hero_name("1047"), "陆行鲨杰夫")
        self.assertEqual(format_hero_name(9999), "英雄 9999（9999）")


if __name__ == "__main__":
    unittest.main()

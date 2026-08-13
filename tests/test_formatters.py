import unittest

from marvel_rivals_bot.hero_names import HERO_ID_MAP, format_hero_name, get_hero_name
from marvel_rivals_bot.models import HeroStat, PlayerProfile, PlayerStats
from marvel_rivals_bot.services.rivals import format_hero, format_match_detail, format_matches, format_player


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

    def test_hero_uses_careers_array(self):
        text = format_hero({"data": {"careers": [{
            "heroId": 1066,
            "totalMatchCount": 10,
            "totalMatchWinCount": 7,
            "k": 186,
            "d": 28,
            "a": 24,
        }]}})
        self.assertIn("英雄：红兜帽（1066）", text)
        self.assertIn("胜率：70%", text)
        self.assertIn("186 / 28 / 24", text)

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
            heroes=[HeroStat(hero_id="1066", play_time_seconds=60)],
        ))
        self.assertIn("红兜帽（1066）", text)

    def test_hero_map_is_complete_and_unknown_ids_have_fallback(self):
        self.assertEqual(len(HERO_ID_MAP), 53)
        self.assertEqual(get_hero_name(1031), "冰月花雪")
        self.assertEqual(get_hero_name("1047"), "陆行鲨杰夫")
        self.assertEqual(format_hero_name(9999), "英雄 9999（9999）")


if __name__ == "__main__":
    unittest.main()

import unittest

from marvel_rivals_bot.analytics.models import CareerHeroSignature, HeroSeasonPerformance, PlayerSignatureProfile
from rendering.pages.player_signature import build_player_signature_html


class TestSignatureRendering(unittest.TestCase):
    def test_career_page_escapes_dynamic_text_and_uses_career_semantics(self):
        hero = CareerHeroSignature(
            hero_id="1026",
            hero_name="黑豹<&>",
            total_matches=80,
            quick_matches=20,
            competitive_matches=60,
            competitive_wins=36,
            usage_share=25.0,
            actual_win_rate=60.0,
            expected_meta_win_rate=53.0,
            raw_delta=7.0,
            adjusted_delta=5.8,
            active_seasons=3,
            competitive_seasons=3,
            comparable_seasons=3,
            effective_seasons=3,
            positive_seasons=3,
            stability=100.0,
            comparable_matches=60,
            meta_coverage=100.0,
            rank_specific_coverage=100.0,
            confidence="高",
            classification="招牌绝活",
            tags=("常青绝活", "本命英雄"),
            seasons=(HeroSeasonPerformance(
                "18", "S9上半赛季", 14, "钻石2", "5", "钻石", 20, 20, 12, 60.0,
                100, 53.0, 5.0, 1.0, 7.0, False, True,
            ),),
        )
        profile = PlayerSignatureProfile(
            uid="123",
            player_name="玩家<&>",
            first_season="S7",
            latest_season="S9.5",
            analyzed_seasons=("S7", "S9.5"),
            total_matches=100,
            competitive_matches=60,
            meta_coverage=100.0,
            signature_heroes=(hero,),
            favorite_hero=hero,
            partial=False,
            failed_seasons=(),
        )
        html = build_player_signature_html(profile)
        self.assertIn("生涯绝活 Top 5", html)
        self.assertIn("名词说明", html)
        self.assertIn("有效环境（有效赛季）", html)
        self.assertIn("绝症 Top 3", html)
        self.assertIn("招牌绝活", html)
        self.assertIn("玩家&lt;&amp;&gt;", html)
        self.assertIn("黑豹&lt;&amp;&gt;", html)
        self.assertNotIn("<script>", html)


if __name__ == "__main__":
    unittest.main()

import unittest

from marvel_rivals_bot.analytics.models import (
    AnalysisScope,
    CareerHeroSignature,
    HeroSeasonPerformance,
    PlayerSignatureProfile,
)
from rendering.pages.player_signature import build_player_signature_html
from rendering.pages.player_sickness import build_player_sickness_html


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
        self.assertIn("招牌绝活", html)
        self.assertIn("证据系数", html)
        self.assertIn("class=\"mr-signature-card__metrics\"", html)
        self.assertNotIn("<span>状态</span>", html)
        self.assertIn("玩家&lt;&amp;&gt;", html)
        self.assertIn("黑豹&lt;&amp;&gt;", html)
        self.assertNotIn("<script>", html)

    def test_sickness_page_shows_meta_relative_loss_and_glossary(self):
        hero = CareerHeroSignature(
            hero_id="1027",
            hero_name="测试英雄<&>",
            total_matches=120,
            quick_matches=20,
            competitive_matches=100,
            competitive_wins=44,
            usage_share=30.0,
            actual_win_rate=44.0,
            expected_meta_win_rate=50.0,
            raw_delta=-6.0,
            adjusted_delta=-5.0,
            active_seasons=3,
            competitive_seasons=3,
            comparable_seasons=3,
            effective_seasons=3,
            positive_seasons=0,
            stability=0.0,
            comparable_matches=100,
            meta_coverage=80.0,
            rank_specific_coverage=80.0,
            confidence="很高",
            classification="常用英雄",
            tags=(),
            seasons=(),
            sick_score=5.0,
            quick_wins=8,
            quick_win_rate=40.0,
            play_index=80.0,
            weakness_index=50.0,
            meta_disadvantage=5.0,
            personal_competitive_disadvantage=3.0,
            personal_quick_disadvantage=2.0,
        )
        profile = PlayerSignatureProfile(
            uid="123",
            player_name="玩家<&>",
            first_season="S7",
            latest_season="S9.5",
            analyzed_seasons=("S7", "S9.5"),
            total_matches=120,
            competitive_matches=100,
            meta_coverage=80.0,
            signature_heroes=(),
            favorite_hero=None,
            partial=False,
            failed_seasons=(),
            sick_heroes=(hero,),
        )
        html = build_player_sickness_html(profile)
        self.assertIn("绝症英雄排名 Top 10", html)
        self.assertIn("使用指数", html)
        self.assertIn("弱势表现", html)
        self.assertIn("5.0", html)
        self.assertIn("Meta 劣势", html)
        self.assertIn("绝症指数", html)
        self.assertIn("测试英雄&lt;&amp;&gt;", html)
        self.assertIn("判定说明", html)
        self.assertNotIn("<script>", html)

    def test_season_signature_page_omits_career_only_terms(self):
        hero = CareerHeroSignature(
            hero_id="1026",
            hero_name="黑豹",
            total_matches=30,
            quick_matches=10,
            competitive_matches=20,
            competitive_wins=14,
            usage_share=100.0,
            actual_win_rate=70.0,
            expected_meta_win_rate=55.0,
            raw_delta=15.0,
            adjusted_delta=10.0,
            active_seasons=1,
            competitive_seasons=1,
            comparable_seasons=1,
            effective_seasons=1,
            positive_seasons=1,
            stability=100.0,
            comparable_matches=20,
            meta_coverage=100.0,
            rank_specific_coverage=100.0,
            confidence="高",
            classification="赛季表现优秀",
            tags=(),
            seasons=(),
            status="赛季表现优秀",
            performance_index=30.0,
            signature_score=20.0,
        )
        profile = PlayerSignatureProfile(
            uid="123",
            player_name="玩家",
            first_season="S9.5",
            latest_season="S9.5",
            analyzed_seasons=("S9.5",),
            total_matches=30,
            competitive_matches=20,
            meta_coverage=100.0,
            signature_heroes=(hero,),
            favorite_hero=None,
            partial=False,
            failed_seasons=(),
            scope=AnalysisScope.season("19"),
        )
        html = build_player_signature_html(profile)
        self.assertIn("S9.5", html)
        self.assertIn("本赛季样本", html)
        self.assertNotIn("有效赛季", html)
        self.assertNotIn("长期稳定性", html)
        self.assertNotIn("常青绝活", html)


if __name__ == "__main__":
    unittest.main()

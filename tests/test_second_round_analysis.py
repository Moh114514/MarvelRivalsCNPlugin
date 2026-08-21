import unittest
from types import SimpleNamespace

from marvel_rivals_bot.analytics.hero_pool import build_hero_pool_analysis
from marvel_rivals_bot.analytics.models import AnalysisScope, analysis_scope_label
from marvel_rivals_bot.analytics.performance import (
    adjust_personal_delta,
    calculate_evidence_factor,
    calculate_performance_index,
    calculate_signature_score,
    calculate_sickness_score,
    classify_hero_performance,
    is_analysis_eligible,
    is_performance_sickness_candidate,
    is_signature_candidate,
)
from rendering.pages.player_hero_pool_analysis import build_player_hero_pool_analysis_html
from marvel_rivals_bot.analytics.models import HeroPoolAnalysis


class TestSecondRoundPerformance(unittest.TestCase):
    def test_personal_delta_uses_mode_specific_priors(self):
        self.assertAlmostEqual(adjust_personal_delta(10, 5, 20), 2.0)
        self.assertAlmostEqual(adjust_personal_delta(10, 10, 30), 2.5)

    def test_eligibility_is_separate_from_score(self):
        self.assertFalse(is_analysis_eligible(total_matches=9, competitive_matches=4, quick_matches=19))
        self.assertTrue(is_analysis_eligible(total_matches=10, competitive_matches=0, quick_matches=0))
        self.assertTrue(is_analysis_eligible(total_matches=0, competitive_matches=5, quick_matches=0))
        self.assertTrue(is_analysis_eligible(total_matches=0, competitive_matches=0, quick_matches=20))

        hero = SimpleNamespace(
            is_analysis_eligible=False,
            performance_index=100,
            signature_score=40,
            sickness_score=0,
        )
        self.assertFalse(is_signature_candidate(hero))
        hero.is_analysis_eligible = True
        self.assertTrue(is_signature_candidate(hero))
        hero.performance_index = 9.99
        self.assertFalse(is_signature_candidate(hero))

    def test_evidence_factor_enters_both_scores(self):
        self.assertEqual(calculate_evidence_factor("数据不足"), 0.25)
        self.assertEqual(calculate_evidence_factor("很高"), 1.0)
        self.assertAlmostEqual(calculate_signature_score(80, 50, 0.45), 18.0)
        self.assertAlmostEqual(calculate_sickness_score(80, -50, 0.45), 18.0)
        self.assertAlmostEqual(
            calculate_performance_index(
                adjusted_meta_delta=4,
                adjusted_personal_competitive_delta=4,
                adjusted_personal_quick_delta=None,
            ),
            50.0,
        )

    def test_positive_and_negative_candidates_are_mutually_exclusive(self):
        positive = SimpleNamespace(
            is_analysis_eligible=True, performance_index=10, signature_score=1, sickness_score=0
        )
        negative = SimpleNamespace(
            is_analysis_eligible=True, performance_index=-10, signature_score=0, sickness_score=1
        )
        neutral = SimpleNamespace(
            is_analysis_eligible=True, performance_index=0, signature_score=1, sickness_score=1
        )
        self.assertTrue(is_signature_candidate(positive))
        self.assertFalse(is_performance_sickness_candidate(positive))
        self.assertTrue(is_performance_sickness_candidate(negative))
        self.assertFalse(is_signature_candidate(negative))
        self.assertFalse(is_signature_candidate(neutral))
        self.assertFalse(is_performance_sickness_candidate(neutral))

    def test_classifier_is_scope_aware(self):
        career_hero = SimpleNamespace(
            performance_index=36,
            signature_score=26,
            confidence="高",
            effective_seasons=3,
            stability=60,
            is_analysis_eligible=True,
        )
        self.assertEqual(
            classify_hero_performance(career_hero, AnalysisScope.career()), "招牌绝活"
        )
        season_hero = SimpleNamespace(
            performance_index=36,
            signature_score=26,
            confidence="很高",
            effective_seasons=8,
            stability=100,
            is_analysis_eligible=True,
        )
        self.assertEqual(
            classify_hero_performance(season_hero, AnalysisScope.season("19")), "赛季强势"
        )


class TestHeroPoolAnalysis(unittest.TestCase):
    @staticmethod
    def _hero(hero_id, share, matches, performance, *, play=40, evidence=1.0, status="常用英雄"):
        return SimpleNamespace(
            hero_id=str(hero_id),
            hero_name=f"英雄{hero_id}",
            usage_share=share,
            total_matches=matches,
            competitive_matches=matches // 2,
            quick_matches=matches - matches // 2,
            performance_index=performance,
            play_index=play,
            evidence_factor=evidence,
            is_analysis_eligible=matches >= 10,
            confidence="高",
            status=status,
        )

    def test_pool_metrics_are_derived_from_usage_structure(self):
        profile = SimpleNamespace(
            uid="123",
            player_name="玩家",
            scope=AnalysisScope.season("19"),
            meta_available=False,
            meta_stale=False,
            heroes=(
                self._hero(1026, 50, 50, 20, status="赛季表现优秀"),
                self._hero(1011, 30, 30, -20, status="赛季偏弱"),
                self._hero(1020, 20, 20, 0),
            ),
        )
        pool = build_hero_pool_analysis(profile)
        self.assertEqual(pool.total_matches, 100)
        self.assertEqual(pool.active_heroes, 3)
        self.assertAlmostEqual(pool.top1_share, 50)
        self.assertAlmostEqual(pool.top3_share, 100)
        self.assertAlmostEqual(pool.effective_pool_width, 2.6315789, places=5)
        self.assertAlmostEqual(pool.duelist_share, 50)
        self.assertAlmostEqual(pool.vanguard_share, 30)
        self.assertAlmostEqual(pool.strategist_share, 20)
        self.assertAlmostEqual(pool.positive_usage_share, 50)
        self.assertAlmostEqual(pool.negative_usage_share, 30)
        self.assertEqual([item.hero_id for item in pool.core_heroes], ["1026", "1011", "1020"])
        self.assertIn("单核专精", pool.structure_tags)
        self.assertFalse(pool.meta_available)

    def test_pool_quality_shares_ignore_ineligible_small_samples(self):
        profile = SimpleNamespace(
            uid="123",
            player_name="玩家",
            scope=AnalysisScope.career(),
            meta_available=True,
            meta_stale=False,
            heroes=(
                self._hero(1026, 90, 90, 20),
                self._hero(1011, 10, 1, -20),
            ),
        )
        pool = build_hero_pool_analysis(profile)
        self.assertAlmostEqual(pool.positive_usage_share, 90.0)
        self.assertAlmostEqual(pool.negative_usage_share, 0.0)

    def test_scope_label_uses_canonical_season_name(self):
        self.assertEqual(analysis_scope_label(AnalysisScope.career()), "生涯")
        self.assertEqual(analysis_scope_label(AnalysisScope.season("19")), "S9.5")

    def test_pool_page_does_not_leak_numeric_season_code(self):
        hero = self._hero(1026, 100, 10, 0)
        pool = HeroPoolAnalysis(
            uid="123",
            player_name="玩家<&>",
            scope=AnalysisScope.season("19"),
            total_matches=10,
            active_heroes=1,
            core_heroes=(hero,),
            top1_share=100,
            top3_share=100,
            effective_pool_width=1,
            vanguard_share=0,
            duelist_share=100,
            strategist_share=0,
            weighted_performance=0,
            positive_usage_share=0,
            negative_usage_share=0,
            structure_tags=("单核专精",),
            meta_available=False,
        )
        html = build_player_hero_pool_analysis_html(pool)
        self.assertIn("S9.5", html)
        self.assertNotIn("19分析", html)
        self.assertIn("当前缺少同期 Meta", html)
        self.assertIn("玩家&lt;&amp;&gt;", html)


if __name__ == "__main__":
    unittest.main()

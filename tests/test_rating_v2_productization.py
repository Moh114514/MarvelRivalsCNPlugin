import unittest
from types import SimpleNamespace

from marvel_rivals_bot.analytics.archetypes import archetype_summary, get_archetype, product_status
from rendering.pages.player_hero_pool_analysis import build_player_hero_pool_analysis_html
from rendering.pages.player_analysis import build_player_hero_analysis_html
from rendering.pages.player_signature import _former_strong_card, _hero_card
from rendering.pages.player_sickness import _sick_card


def _rating(**overrides):
    values = {
        "hero_id": "1036",
        "classification": "常用英雄",
        "mastery": 72.0,
        "performance": 66.0,
        "specialization": None,
        "confidence": 0.60,
        "outcome": 64.0,
        "combat": 68.0,
        "consistency": 62.0,
        "experience": 75.0,
        "archetype": get_archetype(1036),
        "dimensions": {"fin": 80.0, "prs": 65.0, "sur": None, "team": 55.0, "heal": None, "front": None, "util": 40.0},
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _item(rating):
    return SimpleNamespace(
        hero_name="蜘蛛侠",
        rating=rating,
        total_matches=40,
        competitive_matches=30,
        quick_matches=10,
        usage_share=50.0,
        performance_index=20.0,
        signature_score=20.0,
        sickness_score=0.0,
        play_index=80.0,
        actual_win_rate=60.0,
        quick_win_rate=50.0,
        expected_meta_win_rate=52.0,
        adjusted_delta=8.0,
        personal_competitive_delta=4.0,
        personal_quick_delta=2.0,
        meta_coverage=100.0,
        confidence="高",
        status="常用英雄",
        weakness_index=0.0,
    )


class TestRatingV2Productization(unittest.TestCase):
    def test_archetype_labels_use_official_role_and_chinese_style(self):
        summary = archetype_summary(get_archetype(1036))
        self.assertIn("决斗家", summary)
        self.assertIn("切入", summary)
        self.assertIn("刺杀终结", summary)

    def test_product_status_splits_common_bucket_without_changing_classification(self):
        rating = _rating()
        self.assertEqual(product_status(rating), "强势英雄")
        self.assertEqual(rating.classification, "常用英雄")
        self.assertEqual(product_status(_rating(confidence=0.40, performance=50.0)), "低样本")
        self.assertEqual(product_status(_rating(performance=40.0)), "相对弱势")

    def test_v2_cards_show_product_metrics_and_archetype_without_legacy_scores(self):
        item = _item(_rating())
        signature = _hero_card(1, item, career=True, show_v2=True)
        sickness = _sick_card(1, item, show_v2=True)
        for html in (signature, sickness):
            self.assertIn("Mastery", html)
            self.assertIn("Performance", html)
            self.assertIn("Specialization", html)
            self.assertIn("Confidence", html)
            self.assertIn("Outcome", html)
            self.assertIn("Combat", html)
            self.assertIn("Consistency", html)
            self.assertIn("Experience", html)
            self.assertIn("决斗家 · 切入 · 刺杀终结", html)
            self.assertNotIn("绝活指数", html)
            self.assertNotIn("使用指数", html)

    def test_v2_missing_specialization_is_explicit(self):
        html = _hero_card(1, _item(_rating(specialization=None)), career=True, show_v2=True)
        self.assertIn("Specialization</span><strong>—</strong>", html)

    def test_hero_page_keeps_shadow_legacy_surface_and_v2_surface_separate(self):
        item = _item(_rating())
        item.status = "常用英雄"
        item.comparable_competitive_win_rate = 60.0
        item.raw_meta_delta = 5.0
        item.raw_delta = 5.0
        item.adjusted_meta_delta = 4.0
        item.adjusted_delta = 4.0
        item.evidence_factor = 1.0
        item.active_seasons = 2
        item.competitive_stats = None
        item.quick_stats = None

        v2_profile = SimpleNamespace(
            scope=SimpleNamespace(kind="career"),
            rating_version="v2",
            meta_available=True,
        )
        shadow_profile = SimpleNamespace(
            scope=SimpleNamespace(kind="career"),
            rating_version="shadow",
            meta_available=True,
        )
        v2 = build_player_hero_analysis_html(v2_profile, item)
        shadow = build_player_hero_analysis_html(shadow_profile, item)
        self.assertIn("Mastery", v2)
        self.assertIn("决斗家 · 切入 · 刺杀终结", v2)
        self.assertNotIn("绝活指数", v2)
        self.assertNotIn("竞技环境比较", v2)
        self.assertIn("绝活指数", shadow)
        self.assertIn("竞技环境比较", shadow)
        self.assertNotIn("Mastery", shadow)

    def test_v2_pool_does_not_render_legacy_quality_or_core_fields(self):
        item = _item(_rating())
        pool = SimpleNamespace(
            uid="123",
            player_name="玩家",
            scope=SimpleNamespace(kind="career"),
            total_matches=40,
            active_heroes=1,
            core_heroes=(item,),
            top1_share=100.0,
            top3_share=100.0,
            effective_pool_width=1.0,
            vanguard_share=0.0,
            duelist_share=100.0,
            strategist_share=0.0,
            weighted_performance=20.0,
            positive_usage_share=100.0,
            negative_usage_share=0.0,
            structure_tags=(),
            meta_available=True,
            style_shares={"dive": 100.0},
            tactical_tags=(),
            rating_version="v2",
            high_mastery_count=1,
            high_specialization_count=0,
            high_confidence_count=0,
            negative_specialization_usage_share=0.0,
        )
        html = build_player_hero_pool_analysis_html(pool)
        self.assertIn("V2 画像质量", html)
        self.assertIn("主要战斗风格：切入", html)
        self.assertIn("决斗家 · 切入 · 刺杀终结", html)
        self.assertNotIn("核心综合表现", html)
        self.assertNotIn("正向使用占比", html)
        self.assertNotIn("使用指数", html)
        self.assertIn("TEMPORAL RATING", html)
        season_pool = SimpleNamespace(
            **{**pool.__dict__, "scope": SimpleNamespace(kind="season", season_code="19")}
        )
        season_html = build_player_hero_pool_analysis_html(season_pool)
        self.assertNotIn("TEMPORAL RATING", season_html)

    def test_temporal_metrics_are_only_rendered_for_career_scope(self):
        rating = _rating(
            temporal_label="状态稳定",
            freshness=0.82,
            recent_performance=74.0,
            recent_mastery=76.0,
            trend=3.0,
            last_active_season="19",
        )
        item = _item(rating)
        item.active_seasons = 2
        item.competitive_stats = None
        item.quick_stats = None

        career_profile = SimpleNamespace(
            scope=SimpleNamespace(kind="career"),
            rating_version="v2",
            meta_available=True,
        )
        season_profile = SimpleNamespace(
            scope=SimpleNamespace(kind="season", season_code="19"),
            rating_version="v2",
            meta_available=True,
        )
        career_hero = build_player_hero_analysis_html(career_profile, item)
        season_hero = build_player_hero_analysis_html(season_profile, item)
        self.assertIn("Last Active Season", career_hero)
        self.assertIn("Temporal Label", career_hero)
        self.assertNotIn("Last Active Season", season_hero)
        self.assertNotIn("Temporal Label", season_hero)

        self.assertIn("Freshness", _hero_card(1, item, career=True, show_v2=True))
        self.assertNotIn("Freshness", _hero_card(1, item, career=False, show_v2=True))
        self.assertIn("Temporal", _sick_card(1, item, show_v2=True, include_temporal=True))
        self.assertNotIn("Temporal", _sick_card(1, item, show_v2=True, include_temporal=False))

    def test_former_strong_card_is_a_separate_historical_surface(self):
        rating = _rating(
            temporal_label="曾经强势",
            freshness=0.20,
            last_active_season="17",
        )
        html = _former_strong_card(1, _item(rating))
        self.assertIn("mr-signature-card--former", html)
        self.assertIn("曾经强势", html)
        self.assertIn("历史 Mastery", html)
        self.assertIn("最后活跃赛季", html)


if __name__ == "__main__":
    unittest.main()

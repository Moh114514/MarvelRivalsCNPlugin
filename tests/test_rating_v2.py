import math
import unittest

from marvel_rivals_bot.analytics.archetypes import get_archetype
from marvel_rivals_bot.analytics.models import NormalizedModeStats
from marvel_rivals_bot.analytics.rating.combat import calculate_combat
from marvel_rivals_bot.analytics.rating.confidence import calculate_confidence, shrink_performance
from marvel_rivals_bot.analytics.rating.consistency import calculate_consistency
from marvel_rivals_bot.analytics.rating.engine import HeroRatingEngine
from marvel_rivals_bot.analytics.rating.experience import calculate_experience
from marvel_rivals_bot.analytics.rating.models import RatingContext, RatingHeroSnapshot
from marvel_rivals_bot.analytics.rating.outcome import calculate_outcome
from marvel_rivals_bot.analytics.rating.transforms import robust_score, robust_z
from marvel_rivals_bot.analytics.signature import PlayerCareerAnalysisService, _profile_to_dict, _signature_from_dict
from tests.test_player_signature import FakeMeta, FakeRivals


def stats(seed: int, *, matches: int = 20) -> NormalizedModeStats:
    return NormalizedModeStats(
        matches=matches,
        wins=matches // 2,
        kills=100 + seed,
        final_hits=80 + seed,
        deaths=40 - min(seed, 20),
        assists=60 + seed,
        hero_damage=10000 + seed * 100,
        heal=5000 + seed * 50,
        damage_taken=8000 + seed * 80,
        play_time=matches * 600.0,
    )


def snapshot(hero_id: int, seed: int) -> RatingHeroSnapshot:
    return RatingHeroSnapshot(
        hero_id=str(hero_id),
        hero_name=f"Hero {hero_id}",
        archetype=get_archetype(hero_id),
        competitive_stats=stats(seed),
        quick_stats=stats(seed, matches=10),
        competitive_matches=20,
        outcome_delta=float(seed - 2),
        meta_coverage=100.0,
        comparable_seasons=2,
        active_seasons=2,
    )


class TestRatingV2(unittest.TestCase):
    def test_documented_transforms(self):
        self.assertAlmostEqual(calculate_outcome(8.0), 50 + 50 * math.tanh(1.0))
        self.assertEqual(calculate_outcome(None), None)
        self.assertAlmostEqual(robust_z(4, [1, 2, 3, 4, 5]), (4 - 3) / 1.4826)
        self.assertEqual(robust_z(3, [3, 3, 3]), 0.0)
        self.assertGreater(robust_score(5, [1, 2, 3, 4, 5]), 50)

    def test_experience_and_confidence_are_bounded(self):
        self.assertGreater(calculate_experience(20, 300, 20, 600, 3), 0)
        self.assertLessEqual(calculate_experience(10000, 100000, 10000, 100000, 20), 100)
        confidence, parts = calculate_confidence(20, 100, 95, 3)
        self.assertAlmostEqual(confidence, 0.40 * parts["sample"] + 0.25 + 0.20 * .95 + .15)
        self.assertAlmostEqual(shrink_performance(100, 0), 50)

    def test_consistency_single_season_is_neutral(self):
        season = type("Season", (), {"raw_delta": 4.0, "competitive_matches": 10, "season_code": "19"})()
        self.assertEqual(calculate_consistency((season,)), 50.0)

    def test_combat_uses_peer_group_and_missing_dimensions(self):
        heroes = tuple(snapshot(hero_id, seed) for hero_id, seed in zip((1011, 1039, 1051, 1062), (1, 2, 3, 4)))
        result = calculate_combat(RatingContext(heroes, "19"), heroes[0])
        self.assertIsNotNone(result.combat)
        self.assertIsNone(result.dimensions["util"])
        self.assertGreater(result.observable_coverage, 0)
        self.assertIsNotNone(result.baseline_group)

    def test_engine_exposes_v2_result_and_leave_one_out_specialization(self):
        heroes = tuple(snapshot(hero_id, seed) for hero_id, seed in zip((1011, 1039, 1051, 1062), (8, 2, 3, 4)))
        results = HeroRatingEngine().rate_many(RatingContext(heroes, "19"))
        self.assertEqual(set(results), {str(value) for value in (1011, 1039, 1051, 1062)})
        self.assertTrue(all(0 <= item.confidence <= 1 for item in results.values()))
        self.assertTrue(all(0 <= item.mastery <= 100 for item in results.values()))
        self.assertIsNotNone(results["1011"].specialization)
        self.assertIn(results["1011"].classification, {"招牌绝活", "强势绝活", "潜力绝活", "待验证", "常用英雄"})


class TestRatingIntegration(unittest.IsolatedAsyncioTestCase):
    async def test_v2_mode_is_switchable_and_rating_serialization_round_trips(self):
        service = PlayerCareerAnalysisService(FakeRivals(), FakeMeta(), cache_root=None, rating_version="v2")
        profile = await service.get_analysis("123")
        self.assertEqual(profile.rating_version, "v2")
        self.assertIsNotNone(profile.heroes[0].rating)
        self.assertEqual(profile.heroes[0].classification, profile.heroes[0].rating.classification)
        payload = _profile_to_dict(profile)
        cached_hero = _signature_from_dict(payload["heroes"][0])
        self.assertIsNotNone(cached_hero.rating)
        self.assertAlmostEqual(cached_hero.rating.mastery, profile.heroes[0].rating.mastery)


if __name__ == "__main__":
    unittest.main()

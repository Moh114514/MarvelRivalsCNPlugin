import math
import unittest
from pathlib import Path

from marvel_rivals_bot.analytics.archetypes import get_archetype
from marvel_rivals_bot.analytics.dynamic_features.definitions import FEATURE_DEFINITIONS
from marvel_rivals_bot.analytics.models import NormalizedModeStats
from marvel_rivals_bot.analytics.rating.combat import calculate_combat
from marvel_rivals_bot.analytics.rating.confidence import calculate_confidence, shrink_performance
from marvel_rivals_bot.analytics.rating.consistency import calculate_consistency
from marvel_rivals_bot.analytics.rating.engine import HeroRatingEngine
from marvel_rivals_bot.analytics.rating.experience import calculate_experience
from marvel_rivals_bot.analytics.rating.models import RatingContext, RatingHeroSnapshot
from marvel_rivals_bot.analytics.rating.outcome import calculate_outcome
from marvel_rivals_bot.analytics.rating.transforms import robust_score, robust_z
from marvel_rivals_bot.analytics.rating.specialization import classify_rating
from marvel_rivals_bot.analytics.rating.specialization import apply_specialization, SpecializationEvidencePolicy
from marvel_rivals_bot.analytics.rating.models import HeroRatingResult
from marvel_rivals_bot.analytics.signature import (
    AnalysisScope,
    PlayerCareerAnalysisService,
    SignatureCache,
    _NormalizedHero,
    _hero_effective_total,
    _profile_to_dict,
    _signature_from_dict,
)
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
        self.assertEqual(robust_z(3.01, [3, 3, 3]), 0.0)
        self.assertEqual(robust_score(3.01, [3, 3, 3]), 50.0)
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

    def test_effective_matches_keep_subunit_evidence_in_internal_totals(self):
        hero = _NormalizedHero(
            "1011", "Hero", 0, 0, 0, 0,
            quick_effective_matches=0.4,
            competitive_effective_matches=0.0,
        )
        self.assertAlmostEqual(_hero_effective_total(hero), 0.4)

    def test_consistency_uses_effective_competitive_matches(self):
        season = type(
            "Season",
            (),
            {"raw_delta": 4.0, "competitive_matches": 0, "competitive_effective_matches": 0.4, "season_code": "19"},
        )()
        self.assertEqual(calculate_consistency((season,)), 50.0)

    def test_combat_uses_peer_group_and_missing_dimensions(self):
        heroes = tuple(snapshot(hero_id, seed) for hero_id, seed in zip((1011, 1039, 1051, 1062), (1, 2, 3, 4)))
        result = calculate_combat(RatingContext(heroes, "19"), heroes[0])
        self.assertIsNotNone(result.combat)
        self.assertIsNone(result.dimensions["util"])
        self.assertGreater(result.observable_coverage, 0)
        self.assertIsNotNone(result.baseline_group)

    def test_combat_shrinks_raw_dimensions_by_baseline_and_peer_quality(self):
        heroes = tuple(snapshot(hero_id, seed) for hero_id, seed in zip((1011, 1039, 1051, 1062), (1, 2, 3, 4)))
        result = calculate_combat(RatingContext(heroes, "19"), heroes[0])
        self.assertEqual(result.baseline_group, "同 MetricProfile")
        self.assertEqual(result.baseline_peer_count, 3)
        self.assertEqual(result.baseline_quality, 1.0)
        self.assertAlmostEqual(result.peer_quality, 0.6)
        self.assertAlmostEqual(result.final_quality, 0.6)
        raw = result.raw_dimension_score["fin"]
        shrunk = result.shrunk_dimension_score["fin"]
        self.assertIsNotNone(raw)
        self.assertIsNotNone(shrunk)
        self.assertAlmostEqual(shrunk, 50.0 + 0.6 * (raw - 50.0))
        self.assertAlmostEqual(result.dimensions["fin"], shrunk)

    def test_combat_diagnostics_show_coarse_role_fallback_quality(self):
        heroes = tuple(snapshot(hero_id, seed) for hero_id, seed in zip((1011, 1018, 1022, 1027), (1, 2, 3, 4)))
        result = calculate_combat(RatingContext(heroes, "19"), heroes[0])
        self.assertEqual(result.baseline_group, "同 OfficialRole")
        self.assertAlmostEqual(result.baseline_quality, 0.6)
        self.assertAlmostEqual(result.peer_quality, 0.6)
        self.assertAlmostEqual(result.final_quality, 0.36)

    def test_engine_exposes_v2_result_and_leave_one_out_specialization(self):
        heroes = tuple(snapshot(hero_id, seed) for hero_id, seed in zip((1011, 1039, 1051, 1062), (8, 2, 3, 4)))
        results = HeroRatingEngine().rate_many(RatingContext(heroes, "19"))
        self.assertEqual(set(results), {str(value) for value in (1011, 1039, 1051, 1062)})
        self.assertTrue(all(0 <= item.confidence <= 1 for item in results.values()))
        self.assertTrue(all(0 <= item.mastery <= 100 for item in results.values()))
        self.assertIsNotNone(results["1011"].specialization)
        self.assertIn(results["1011"].classification, {"招牌绝活", "强势绝活", "潜力绝活", "待验证", "常用英雄"})

    def test_tactical_baseline_does_not_cross_official_roles(self):
        heroes = tuple(snapshot(hero_id, seed) for hero_id, seed in zip((1014, 1028, 10571, 1066), (1, 2, 3, 4)))
        result = calculate_combat(RatingContext(heroes, "19"), heroes[0])
        self.assertIsNone(result.baseline_group)

    def test_season_classification_is_not_a_career_label(self):
        result = HeroRatingResult(
            hero_id="1011",
            hero_name="Hero",
            archetype=get_archetype(1011),
            outcome=80,
            combat=80,
            consistency=80,
            experience=80,
            performance_raw=82,
            performance=82,
            confidence=.8,
            mastery=82,
        )
        self.assertEqual(classify_rating(result, scope="season"), "赛季表现优秀")

    def test_season_neutral_band_is_not_a_sickness_classification(self):
        base = dict(
            hero_id="1011",
            hero_name="Hero",
            archetype=get_archetype(1011),
            outcome=50,
            combat=50,
            consistency=50,
            experience=50,
            performance_raw=50,
            confidence=.8,
            mastery=50,
        )
        self.assertEqual(classify_rating(HeroRatingResult(performance=50, **base), scope="season"), "赛季中性")
        self.assertEqual(classify_rating(HeroRatingResult(performance=47, **base), scope="season"), "赛季中性")

    def test_low_confidence_negative_season_waits_for_evidence(self):
        base = dict(
            hero_id="1011", hero_name="Hero", archetype=get_archetype(1011),
            outcome=40, combat=40, consistency=40, experience=30,
            performance_raw=40, confidence=.20, mastery=40,
        )
        self.assertEqual(classify_rating(HeroRatingResult(performance=40, **base), scope="season"), "赛季待验证")

    def test_observed_1031_dynamic_fields_are_inventory_only(self):
        keys = {
            "Feature_103102:ally_hit",
            "Feature_103102:chaos_hit",
            "Feature_103102:summoner_hit",
            "Feature_103101:hero_hit",
        }
        definitions = [FEATURE_DEFINITIONS[(1031, key)] for key in keys]
        self.assertTrue(all(item.label is None for item in definitions))
        self.assertTrue(all(item.dimension == "unknown" for item in definitions))
        self.assertTrue(all(not item.rating_enabled for item in definitions))

    def test_specialization_stays_missing_without_weighted_peer_evidence(self):
        def result(hero_id):
            return HeroRatingResult(
                hero_id=str(hero_id), hero_name="Hero", archetype=get_archetype(1011),
                outcome=50, combat=50, consistency=50, experience=30,
                performance_raw=60, performance=60, confidence=0, mastery=60,
            )
        results = {str(hero_id): result(hero_id) for hero_id in (1011, 1039, 1051, 1062)}
        rated = apply_specialization(results)
        self.assertTrue(all(item.specialization is None for item in rated.values()))

    def test_specialization_evidence_gate_blocks_hero_without_rating_signal(self):
        target = HeroRatingResult(
            hero_id="1011", hero_name="Target", archetype=get_archetype(1011),
            outcome=None, combat=None, consistency=None, experience=100,
            performance_raw=50, performance=50, confidence=0, mastery=50,
        )
        peers = {
            str(hero_id): HeroRatingResult(
                hero_id=str(hero_id), hero_name="Peer", archetype=get_archetype(1011),
                outcome=60, combat=60, consistency=60, experience=30,
                performance_raw=70, performance=70, confidence=.8, mastery=70,
            )
            for hero_id in (1039, 1051, 1062)
        }
        rated = apply_specialization({"1011": target, **peers})
        self.assertIsNone(rated["1011"].specialization)

    def test_specialization_evidence_policy_is_configurable(self):
        def make(hero_id, *, confidence, experience):
            return HeroRatingResult(
                hero_id=str(hero_id), hero_name="Hero", archetype=get_archetype(1011),
                outcome=50, combat=50, consistency=50, experience=experience,
                performance_raw=60, performance=60, confidence=confidence, mastery=60,
            )
        results = {
            "1011": make(1011, confidence=.4, experience=30),
            "1039": make(1039, confidence=.8, experience=30),
            "1051": make(1051, confidence=.8, experience=30),
            "1062": make(1062, confidence=.8, experience=30),
        }
        policy = SpecializationEvidencePolicy(min_confidence=.5, min_experience=40)
        self.assertIsNone(apply_specialization(results, evidence_policy=policy)["1011"].specialization)
        policy = SpecializationEvidencePolicy(min_confidence=.5, min_experience=20)
        self.assertIsNotNone(apply_specialization(results, evidence_policy=policy)["1011"].specialization)

    def test_v2_signature_tier_precedes_specialization(self):
        from types import SimpleNamespace
        from marvel_rivals_bot.analytics.signature import _v2_signature_sort_key
        potential = SimpleNamespace(hero_id="1011", rating=SimpleNamespace(classification="潜力绝活", specialization=20, mastery=72, performance=70, confidence=.8, experience=60))
        signature = SimpleNamespace(hero_id="1039", rating=SimpleNamespace(classification="招牌绝活", specialization=16, mastery=91, performance=90, confidence=.9, experience=80))
        self.assertLess(_v2_signature_sort_key(signature), _v2_signature_sort_key(potential))

    def test_rating_cache_path_isolated_by_version_and_schema(self):
        cache = SignatureCache(None)
        cache.root = Path("analysis")
        career = AnalysisScope.career()
        shadow = cache._analysis_path("123", career, rating_version="shadow")
        v2 = cache._analysis_path("123", career, rating_version="v2")
        self.assertNotEqual(shadow, v2)
        self.assertIn("_r3", str(v2))


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

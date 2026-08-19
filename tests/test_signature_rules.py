import unittest
from types import SimpleNamespace

from marvel_rivals_bot.analytics.signature_rules import (
    adjust_delta,
    calculate_confidence,
    calculate_sick_score,
    calculate_stability,
    classify_signature,
    classification_sort_key,
    stability_counts,
)
from marvel_rivals_bot.analytics.signature import SeasonAggregationPolicy, _NormalizedHero, _NormalizedSeason, PlayerSignatureService


class TestSignatureRules(unittest.TestCase):
    def test_shrinkage_uses_prior_matches(self):
        self.assertAlmostEqual(adjust_delta(20, 20), 10.0)
        self.assertAlmostEqual(adjust_delta(20, 5), 4.0)

    def test_stability_caps_each_season_weight(self):
        seasons = [
            SimpleNamespace(competitive_matches=1, raw_delta=100),
            SimpleNamespace(competitive_matches=20, raw_delta=-1),
            SimpleNamespace(competitive_matches=20, raw_delta=1),
        ]
        self.assertAlmostEqual(calculate_stability(seasons), 21 / 41 * 100)

    def test_any_competitive_appearance_is_an_effective_season(self):
        seasons = [
            SimpleNamespace(competitive_matches=1, raw_delta=None),
            SimpleNamespace(competitive_matches=2, raw_delta=3.0),
        ]
        stability, effective, positive = stability_counts(seasons)
        self.assertEqual(effective, 2)
        self.assertEqual(positive, 1)
        self.assertAlmostEqual(stability, 100.0)

    def test_sick_score_uses_adjusted_meta_deficit_and_expected_loss(self):
        self.assertAlmostEqual(
            calculate_sick_score(44.0, 100, -5.0, 80.0, 80.0, "常用英雄"),
            5.0,
        )
        self.assertEqual(
            calculate_sick_score(56.0, 100, 5.0, 80.0, 80.0, "常用英雄"),
            0.0,
        )

    def test_sick_score_requires_coverage_volume_and_non_signature_classification(self):
        base = dict(
            actual_win_rate=44.0,
            competitive_matches=100,
            adjusted_delta=-5.0,
            meta_coverage=80.0,
            rank_specific_coverage=80.0,
            classification="常用英雄",
        )
        self.assertEqual(calculate_sick_score(**{**base, "competitive_matches": 19}), 0.0)
        self.assertEqual(calculate_sick_score(**{**base, "meta_coverage": 50.0}), 0.0)
        self.assertEqual(calculate_sick_score(**{**base, "rank_specific_coverage": 50.0}), 0.0)
        self.assertEqual(calculate_sick_score(**{**base, "classification": "强势绝活"}), 0.0)

    def test_confidence_downgrades_incomplete_coverage(self):
        self.assertEqual(calculate_confidence(100, 100, 100), "很高")
        self.assertEqual(calculate_confidence(100, 69.9, 100), "高")
        self.assertEqual(calculate_confidence(3, 100, 100), "数据不足")

    def test_classification_boundaries_are_inclusive(self):
        kwargs = dict(
            competitive_matches=50,
            effective_seasons=3,
            raw_delta=3.0,
            adjusted_delta=3.0,
            stability=65.0,
            meta_coverage=70.0,
        )
        self.assertEqual(classify_signature(**kwargs), "招牌绝活")
        kwargs["competitive_matches"] = 49
        self.assertEqual(classify_signature(**kwargs), "强势绝活")

    def test_cumulative_policy_skips_missing_intermediate_snapshot(self):
        service = PlayerSignatureService.__new__(PlayerSignatureService)
        service.season_policy = SeasonAggregationPolicy.CUMULATIVE
        hero_one = _NormalizedHero("1026", "黑豹", 0, 0, 10, 6)
        hero_three = _NormalizedHero("1026", "黑豹", 0, 0, 30, 18)
        seasons = [
            _NormalizedSeason("1", "S0", {"1026": hero_one}),
            _NormalizedSeason("2", "S1", {}),
            _NormalizedSeason("3", "S1.5", {"1026": hero_three}),
        ]
        adjusted = service._apply_policy(seasons)
        self.assertEqual(adjusted[2].heroes["1026"].competitive_matches, 20)

    def test_sort_key_keeps_zero_delta_and_stability_as_real_values(self):
        zero = SimpleNamespace(
            classification="常用英雄",
            adjusted_delta=0.0,
            comparable_matches=10,
            stability=0.0,
            total_matches=10,
        )
        missing = SimpleNamespace(
            classification="常用英雄",
            adjusted_delta=None,
            comparable_matches=10,
            stability=None,
            total_matches=10,
        )
        self.assertLess(classification_sort_key(zero), classification_sort_key(missing))


if __name__ == "__main__":
    unittest.main()

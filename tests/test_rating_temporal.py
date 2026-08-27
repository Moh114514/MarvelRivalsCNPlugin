import unittest

from marvel_rivals_bot.analytics.rating.models import (
    HeroRatingResult,
    RatingContext,
    RatingHeroSnapshot,
    SeasonRatingSnapshot,
)
from marvel_rivals_bot.analytics.rating.temporal import (
    TEMPORAL_DECLINING,
    TEMPORAL_FORMER,
    TEMPORAL_RISING,
    TEMPORAL_STABLE,
    TEMPORAL_VERIFY,
    apply_temporal_ratings,
    calculate_freshness,
    classify_temporal_state,
)
from marvel_rivals_bot.analytics.archetypes import get_archetype
from marvel_rivals_bot.analytics.models import NormalizedModeStats


def _season(code: int, matches: float, wins: float | None = None) -> SeasonRatingSnapshot:
    stats = NormalizedModeStats(
        matches=int(matches),
        wins=int(wins or 0) if wins is not None else None,
        play_time=matches * 600,
    )
    return SeasonRatingSnapshot(
        season_code=str(code),
        competitive_stats=stats,
        competitive_matches=int(matches),
        competitive_wins=wins,
        competitive_effective_matches=matches,
        competitive_effective_wins=wins,
        outcome_delta=20.0 if wins is not None else None,
        meta_win_rate=50.0 if wins is not None else None,
    )


def _rating(**changes):
    values = dict(
        hero_id="1011",
        hero_name="Hero",
        archetype=get_archetype(1011),
        outcome=70.0,
        combat=70.0,
        consistency=70.0,
        experience=70.0,
        performance_raw=70.0,
        performance=70.0,
        confidence=0.80,
        mastery=80.0,
        specialization=12.0,
        freshness=0.80,
        recent_performance=80.0,
        recent_mastery=80.0,
        recent_specialization=12.0,
        recent_confidence=0.80,
        recent_effective_matches=20.0,
    )
    values.update(changes)
    return HeroRatingResult(**values)


class TestTemporalRating(unittest.TestCase):
    def test_freshness_requires_three_effective_matches_and_decays_by_half_seasons(self):
        fresh, last, sample = calculate_freshness((_season(19, 30),), "19")
        self.assertEqual(last, "19")
        self.assertAlmostEqual(fresh, 1.0 * (0.35 + 0.65 * (1 - __import__("math").exp(-2))))
        self.assertEqual(sample, 30)

        low, low_last, low_sample = calculate_freshness((_season(19, 1),), "19")
        self.assertEqual(low_last, None)
        self.assertLess(low, 1.0)
        self.assertEqual(low_sample, 1)

    def test_temporal_labels_distinguish_rise_decline_former_and_stable(self):
        self.assertEqual(classify_temporal_state(_rating(performance=78.0)), TEMPORAL_STABLE)
        self.assertEqual(
            classify_temporal_state(_rating(performance=60.0, recent_performance=80.0, recent_mastery=80.0)),
            TEMPORAL_RISING,
        )
        self.assertEqual(
            classify_temporal_state(_rating(performance=80.0, recent_performance=65.0, recent_mastery=65.0)),
            TEMPORAL_DECLINING,
        )
        self.assertEqual(
            classify_temporal_state(_rating(freshness=0.20)),
            TEMPORAL_FORMER,
        )
        self.assertEqual(
            classify_temporal_state(_rating(freshness=0.55)),
            TEMPORAL_VERIFY,
        )

    def test_temporal_rating_is_additive_and_serializable(self):
        hero = RatingHeroSnapshot(
            hero_id="1011",
            hero_name="Hero",
            archetype=get_archetype(1011),
            competitive_stats=NormalizedModeStats(matches=20, wins=12, play_time=12000),
            quick_stats=NormalizedModeStats(),
            competitive_matches=20,
            outcome_delta=10.0,
            meta_coverage=100.0,
            season_snapshots=(_season(17, 10, 6), _season(18, 20, 14), _season(19, 1, 1)),
        )
        result = apply_temporal_ratings(
            {"1011": _rating()},
            RatingContext((hero,), "19"),
        )["1011"]
        self.assertIsNotNone(result.recent_performance)
        self.assertGreater(result.recent_effective_matches, 21.0)
        self.assertNotEqual(result.freshness, None)
        self.assertIsNotNone(result.temporal_label)
        payload = result.to_dict()
        self.assertIn("freshness", payload)
        self.assertEqual(HeroRatingResult.from_dict(payload).temporal_label, result.temporal_label)


if __name__ == "__main__":
    unittest.main()

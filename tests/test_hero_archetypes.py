import unittest

from marvel_rivals_bot.analytics.archetypes import (
    HERO_ARCHETYPES,
    METRIC_PROFILES,
    MetricProfileId,
    validate_archetypes,
    validate_metric_profiles,
)
from marvel_rivals_bot.reference.heroes import HERO_ID_MAP, HERO_ROLE_MAP


class TestHeroArchetypes(unittest.TestCase):
    def test_every_official_hero_has_one_tactical_archetype(self):
        validate_archetypes()
        self.assertEqual(set(HERO_ROLE_MAP), set(HERO_ID_MAP))
        self.assertEqual(set(HERO_ROLE_MAP), set(HERO_ARCHETYPES))
        self.assertEqual(len(HERO_ARCHETYPES), 55)

    def test_profiles_are_complete_and_normalized(self):
        validate_metric_profiles()
        self.assertEqual(set(METRIC_PROFILES), set(MetricProfileId))
        for profile in METRIC_PROFILES.values():
            self.assertAlmostEqual(profile.total_weight, 1.0)

    def test_official_roles_are_not_replaced_by_tactical_profiles(self):
        self.assertEqual(HERO_ROLE_MAP[1036], "duelist")
        self.assertEqual(HERO_ARCHETYPES[1036].metric_profile, MetricProfileId.DIVE_ASSASSIN)
        self.assertEqual(HERO_ROLE_MAP[1018], "vanguard")
        self.assertEqual(HERO_ARCHETYPES[1018].metric_profile, MetricProfileId.VANGUARD_ANCHOR)
        self.assertEqual(HERO_ROLE_MAP[1058], "strategist")
        self.assertEqual(HERO_ARCHETYPES[1058].metric_profile, MetricProfileId.AGGRESSIVE_SUPPORT)

    def test_deadpool_variants_remain_separate(self):
        self.assertEqual({10571, 10572, 10573}, set(HERO_ARCHETYPES) & {10571, 10572, 10573})
        self.assertNotEqual(HERO_ARCHETYPES[10571].metric_profile, HERO_ARCHETYPES[10572].metric_profile)
        self.assertNotEqual(HERO_ARCHETYPES[10572].metric_profile, HERO_ARCHETYPES[10573].metric_profile)


if __name__ == "__main__":
    unittest.main()


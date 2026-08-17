import unittest

from marvel_rivals_bot.meta.calculator import calculate_hero_results
from marvel_rivals_bot.meta.models import RawBanRankBucket, RawBanStat, RawHeroMetaStat, RawHeroRankBucket


def hero_bucket(rank, *rows):
    return RawHeroRankBucket(rank_code=str(rank), heroes=list(rows))


class TestMetaCalculator(unittest.TestCase):
    def test_aggregation_uses_raw_denominators_before_filtering(self):
        heroes = [
            hero_bucket(
                1,
                RawHeroMetaStat(1020, 10, 5, 8, 4, 2),
                RawHeroMetaStat(None, 20, 0, 0, 0, 0),
            ),
            hero_bucket(5, RawHeroMetaStat(1020, 20, 10, 20, 10, 3)),
        ]
        bans = [RawBanRankBucket("1", [RawBanStat(1020, 2), RawBanStat(0, 8)])]
        result = calculate_hero_results(heroes, bans, rank="1", sort_by="matches")

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].matches, 10)
        self.assertAlmostEqual(result[0].pick_rate, 200.0)  # 10 / ((10 + 20) / 6) * 100
        self.assertAlmostEqual(result[0].ban_rate, 40.0)  # 2 / ((2 + 8) / 2) * 100
        self.assertAlmostEqual(result[0].win_rate, 50.0)

    def test_composite_aggregates_counts_before_rates(self):
        heroes = [
            hero_bucket(5, RawHeroMetaStat(1020, 10, 5, 10, 5, 0)),
            hero_bucket(6, RawHeroMetaStat(1020, 30, 15, 30, 15, 0)),
        ]
        bans = [RawBanRankBucket(rank, []) for rank in ("5", "6", "9", "7", "8")]
        result = calculate_hero_results(heroes, bans, rank="diamond+", sort_by="matches")
        self.assertEqual(result[0].matches, 40)
        self.assertAlmostEqual(result[0].pick_rate, 600.0)
        self.assertEqual(result[0].bans, 0)
        self.assertEqual(result[0].ban_rate, 0.0)

    def test_partial_composite_ban_buckets_are_unavailable(self):
        heroes = [
            hero_bucket(5, RawHeroMetaStat(1020, 10, 5, 10, 5, 0)),
            hero_bucket(6, RawHeroMetaStat(1020, 30, 15, 30, 15, 0)),
        ]
        result = calculate_hero_results(
            heroes, [RawBanRankBucket("5", [RawBanStat(1020, 10)])], rank="diamond+"
        )
        self.assertIsNone(result[0].bans)
        self.assertIsNone(result[0].ban_rate)

    def test_missing_bans_is_distinct_from_empty_existing_bucket(self):
        heroes = [hero_bucket(1, RawHeroMetaStat(1020, 1, 1, 1, 1, 0))]
        missing = calculate_hero_results(heroes, None, rank="1")
        empty = calculate_hero_results(heroes, [RawBanRankBucket("1", [])], rank="1")
        self.assertIsNone(missing[0].ban_rate)
        self.assertIsNone(missing[0].bans)
        self.assertEqual(empty[0].bans, 0)
        self.assertEqual(empty[0].ban_rate, 0.0)

    def test_unavailable_ban_rates_sort_last(self):
        heroes = [
            hero_bucket(1, RawHeroMetaStat(1020, 1, 1, 1, 1, 0)),
            hero_bucket(2, RawHeroMetaStat(1021, 1, 1, 1, 1, 0)),
        ]
        result = calculate_hero_results(heroes, None, sort_by="ban_rate")
        self.assertEqual([item.hero_id for item in result], [1020, 1021])


if __name__ == "__main__":
    unittest.main()

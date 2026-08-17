import unittest

from marvel_rivals_bot.datasource.cn import RANK_LEVEL_MAP
from marvel_rivals_bot.game_metadata import RIVALSMETA_SEASON_MAP
from marvel_rivals_bot.hero_names import HERO_ID_MAP, get_hero_name
from marvel_rivals_bot.meta.ranks import RANK_LABELS as LEGACY_RANK_LABELS
from marvel_rivals_bot.reference.heroes import HERO_ID_MAP as CANONICAL_HERO_ID_MAP
from marvel_rivals_bot.reference.ranks import (
    CN_RANK_LEVEL_MAP,
    CN_RANK_LEVEL_TO_META_RANK,
    META_RANK_LABELS,
    META_RANK_ORDER,
    meta_rank_from_cn_level,
    normalize_rank,
    rank_label,
)
from marvel_rivals_bot.reference.seasons import (
    SeasonIdentity,
    format_season_name,
    get_season_identity,
    parse_season_name,
    season_identity_from_name,
)
from marvel_rivals_bot.services.rivals import parse_season_name as legacy_parse_season_name


class TestCanonicalHeroes(unittest.TestCase):
    def test_legacy_facade_uses_one_canonical_map(self):
        self.assertIs(HERO_ID_MAP, CANONICAL_HERO_ID_MAP)
        self.assertEqual(get_hero_name(10571), "T位死侍")
        self.assertEqual(get_hero_name(9999), "英雄 9999")


class TestCanonicalRanks(unittest.TestCase):
    def test_cn_levels_remain_separate_from_meta_buckets(self):
        self.assertIs(RANK_LEVEL_MAP, CN_RANK_LEVEL_MAP)
        self.assertEqual(CN_RANK_LEVEL_TO_META_RANK[1], "1")
        self.assertEqual(CN_RANK_LEVEL_TO_META_RANK[14], "5")
        self.assertEqual(CN_RANK_LEVEL_TO_META_RANK[19], "9")
        self.assertEqual(CN_RANK_LEVEL_TO_META_RANK[23], "8")
        self.assertEqual(meta_rank_from_cn_level(22), "7")

    def test_meta_labels_and_legacy_aliases_are_canonical(self):
        self.assertEqual(META_RANK_ORDER, ("1", "2", "3", "4", "5", "6", "9", "7", "8"))
        self.assertEqual(META_RANK_LABELS["4"], "白金")
        self.assertEqual(LEGACY_RANK_LABELS, META_RANK_LABELS)
        self.assertEqual(normalize_rank("铂金"), "4")
        self.assertEqual(normalize_rank("宗师"), "6")
        self.assertEqual(rank_label("至高无上"), "万物之上")


class TestCanonicalSeasons(unittest.TestCase):
    def test_identity_keeps_provider_codes_separate(self):
        identity = season_identity_from_name("S9.5")
        self.assertIsInstance(identity, SeasonIdentity)
        self.assertEqual(identity.canonical_name, "S9.5")
        self.assertEqual(identity.display_name, "S9下半赛季")
        self.assertEqual(identity.for_provider("cn"), "19")
        self.assertEqual(identity.for_provider("rivalsmeta"), "19")
        custom = SeasonIdentity("S9.5", "cn-19", "meta-9019", "S9下半赛季")
        self.assertEqual(custom.for_provider("cn"), "cn-19")
        self.assertEqual(custom.for_provider("rivalsmeta"), "meta-9019")

    def test_names_and_legacy_facade_preserve_existing_behavior(self):
        self.assertEqual(parse_season_name("S9"), "18")
        self.assertEqual(parse_season_name("S9.5"), "19")
        self.assertEqual(legacy_parse_season_name("S9上半赛季"), "18")
        self.assertEqual(format_season_name(18), "S9上半赛季")
        self.assertEqual(get_season_identity("19").canonical_name, "S9.5")
        self.assertEqual(RIVALSMETA_SEASON_MAP[18], "S9")
        self.assertEqual(RIVALSMETA_SEASON_MAP[19], "S9.5")
        with self.assertRaisesRegex(ValueError, "S9上半赛季"):
            parse_season_name("18")


if __name__ == "__main__":
    unittest.main()

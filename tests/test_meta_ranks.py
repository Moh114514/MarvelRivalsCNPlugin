import unittest

from marvel_rivals_bot.meta.ranks import RANK_GROUPS, RANK_LABELS, RANK_ORDER, normalize_rank, rank_codes, rank_label


class TestMetaRanks(unittest.TestCase):
    def test_official_labels_and_game_order(self):
        self.assertEqual(RANK_ORDER, ("1", "2", "3", "4", "5", "6", "9", "7", "8"))
        self.assertEqual(RANK_LABELS["6"], "大师")
        self.assertEqual(RANK_LABELS["8"], "万物之上")

    def test_aliases_and_composites(self):
        self.assertEqual(normalize_rank("铂金"), "4")
        self.assertEqual(normalize_rank("All Ranks"), "all")
        self.assertEqual(rank_codes("diamond+"), RANK_GROUPS["diamond+"])
        self.assertEqual(rank_codes("天神+"), ("9", "7", "8"))
        self.assertEqual(rank_label("grandmaster+"), "大师+")

    def test_rank_zero_is_not_a_business_selection(self):
        with self.assertRaises(ValueError):
            normalize_rank(0)


if __name__ == "__main__":
    unittest.main()

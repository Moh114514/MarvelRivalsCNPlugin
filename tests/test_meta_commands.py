import unittest

from marvel_rivals_bot.meta.commands import parse_meta_command_args


class TestMetaCommandArguments(unittest.TestCase):
    def test_arguments_are_order_independent(self):
        result = parse_meta_command_args("S9.5", "大师", "Ban率")
        self.assertEqual(result.season, "S9.5")
        self.assertEqual(result.rank, "6")
        self.assertEqual(result.sort_by, "ban_rate")

    def test_single_hero_argument_is_separated_from_context(self):
        result = parse_meta_command_args("曼蒂斯", "大师", "S9.5", require_hero=True)
        self.assertEqual(result.hero_name, "曼蒂斯")
        self.assertEqual(result.rank, "6")
        self.assertEqual(result.season, "S9.5")

    def test_default_and_missing_hero(self):
        result = parse_meta_command_args()
        self.assertEqual(result.rank, "all")
        self.assertEqual(result.sort_by, "win_rate")
        with self.assertRaises(ValueError):
            parse_meta_command_args("大师", require_hero=True)
        with self.assertRaises(ValueError):
            parse_meta_command_args("19")


if __name__ == "__main__":
    unittest.main()

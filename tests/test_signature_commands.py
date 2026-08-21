import unittest

from marvel_rivals_bot.analytics.commands import parse_player_analysis_args, parse_signature_args


class TestSignatureCommandArgs(unittest.TestCase):
    def test_accepts_optional_uid_only(self):
        self.assertEqual(parse_signature_args().uid, None)
        self.assertEqual(parse_signature_args("uid=1287101468").uid, "1287101468")

    def test_compatibility_parser_accepts_the_shared_scope_arguments(self):
        self.assertEqual(parse_signature_args("S9.5").season, "S9.5")
        with self.assertRaisesRegex(ValueError, "已取消最低场次参数"):
            parse_signature_args("20")

    def test_numeric_uid_is_not_confused_with_minimum_matches(self):
        self.assertEqual(parse_signature_args("1287101468").uid, "1287101468")

    def test_player_analysis_accepts_uid_and_season_in_any_order(self):
        first = parse_player_analysis_args("1287101468", "S9.5")
        second = parse_player_analysis_args("S9.5", "uid=1287101468")
        self.assertEqual((first.uid, first.season), ("1287101468", "S9.5"))
        self.assertEqual((second.uid, second.season), ("1287101468", "S9.5"))

    def test_player_analysis_rejects_duplicate_scope_arguments(self):
        with self.assertRaises(ValueError):
            parse_player_analysis_args("S9", "S9.5")
        with self.assertRaises(ValueError):
            parse_player_analysis_args("1", "1287101468")


if __name__ == "__main__":
    unittest.main()

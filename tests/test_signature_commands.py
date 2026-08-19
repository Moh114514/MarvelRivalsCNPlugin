import unittest

from marvel_rivals_bot.analytics.commands import parse_signature_args


class TestSignatureCommandArgs(unittest.TestCase):
    def test_accepts_optional_uid_only(self):
        self.assertEqual(parse_signature_args().uid, None)
        self.assertEqual(parse_signature_args("uid=1287101468").uid, "1287101468")

    def test_rejects_legacy_season_and_minimum_arguments_with_migration_help(self):
        with self.assertRaisesRegex(ValueError, "不再接受赛季参数"):
            parse_signature_args("S9.5")
        with self.assertRaisesRegex(ValueError, "已取消最低场次参数"):
            parse_signature_args("20")

    def test_numeric_uid_is_not_confused_with_minimum_matches(self):
        self.assertEqual(parse_signature_args("1287101468").uid, "1287101468")


if __name__ == "__main__":
    unittest.main()

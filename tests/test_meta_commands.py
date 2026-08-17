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

    def test_explicit_duplicate_sort_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "只能指定一种排序方式"):
            parse_meta_command_args("胜率", "胜率")

    def test_explicit_duplicate_rank_is_rejected_even_for_all(self):
        with self.assertRaisesRegex(ValueError, "只能指定一个段位"):
            parse_meta_command_args("全段位", "全段位")

    def test_explicit_duplicate_season_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "只能指定一个赛季"):
            parse_meta_command_args("S9", "S9")

    def test_command_sort_constraints(self):
        environment = parse_meta_command_args("大师", "S9", allow_sort=False)
        self.assertEqual(environment.sort_by, "win_rate")
        with self.assertRaisesRegex(ValueError, "无法识别参数"):
            parse_meta_command_args("曼蒂斯", allow_sort=False)

        ranking = parse_meta_command_args("Ban率", "天神", require_sort=True)
        self.assertEqual(ranking.sort_by, "ban_rate")

        statistics = parse_meta_command_args(
            "曼蒂斯", "大师", "S9", require_hero=True, allow_sort=False
        )
        self.assertEqual(statistics.hero_name, "曼蒂斯")

    def test_disallowed_sort_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "不接受排序指标"):
            parse_meta_command_args("胜率", allow_sort=False)

        with self.assertRaisesRegex(ValueError, "不接受排序指标"):
            parse_meta_command_args(
                "曼蒂斯", "胜率", require_hero=True, allow_sort=False
            )

    def test_required_sort_is_rejected_when_missing(self):
        with self.assertRaisesRegex(ValueError, "请提供一个排序指标"):
            parse_meta_command_args("大师", require_sort=True)

    def test_ranking_rejects_hero_name(self):
        with self.assertRaisesRegex(ValueError, "无法识别参数"):
            parse_meta_command_args("曼蒂斯", "胜率", require_sort=True)

    def test_comparison_requires_two_heroes_and_keeps_context_order_independent(self):
        result = parse_meta_command_args(
            "S9.5", "铂金", "蜘蛛侠", "黑豹", require_hero_count=2, allow_sort=False
        )
        self.assertEqual(result.hero_names, ("蜘蛛侠", "黑豹"))
        self.assertEqual(result.rank, "4")
        self.assertEqual(result.season, "S9.5")
        with self.assertRaisesRegex(ValueError, "2个"):
            parse_meta_command_args("蜘蛛侠", require_hero_count=2, allow_sort=False)

    def test_segments_reject_rank_filter(self):
        with self.assertRaisesRegex(ValueError, "不接受段位"):
            parse_meta_command_args(
                "蜘蛛侠", "大师", require_hero=True, allow_sort=False, allow_rank=False
            )


if __name__ == "__main__":
    unittest.main()

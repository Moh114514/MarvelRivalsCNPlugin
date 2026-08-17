import unittest
from datetime import datetime, timezone

from marvel_rivals_bot.meta.formatters import format_hero_meta_board, format_hero_meta_overview, format_single_hero_meta
from marvel_rivals_bot.meta.models import HeroMetaBoard, HeroMetaOverview, HeroMetaResult


class TestMetaFormatters(unittest.TestCase):
    def setUp(self):
        self.result = HeroMetaResult(
            hero_id=1020,
            hero_name="曼蒂斯",
            matches=10230,
            wins=6000,
            wr_matches=9000,
            wr_wins=5000,
            mirror_matches=10,
            bans=0,
            win_rate=55.55,
            pick_rate=2.77,
            ban_rate=None,
        )

    def test_board_contains_source_timestamp_and_stale_notice(self):
        board = HeroMetaBoard(
            season_code="19",
            season_label="S9下半赛季",
            rank_key="6",
            rank_label="大师",
            sort_by="win_rate",
            heroes=[self.result],
            source="RivalsMeta",
            source_timestamp=datetime(2026, 8, 14, 7, 30, tzinfo=timezone.utc),
            fetched_at=datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc),
            stale=True,
        )
        text = format_hero_meta_board(board)
        self.assertIn("数据来源：RivalsMeta", text)
        self.assertIn("当前上游暂不可用", text)
        self.assertIn("Ban率 —", text)
        self.assertIn("场次 10,230", text)

    def test_single_hero_formatter_keeps_unavailable_ban_as_dash(self):
        text = format_single_hero_meta(
            self.result,
            season_label="S9下半赛季",
            rank_label="大师",
            source="RivalsMeta",
            source_timestamp=1720000000,
        )
        self.assertIn("曼蒂斯 | S9下半赛季 | 大师", text)
        self.assertIn("Ban率：—", text)
        self.assertIn("更新时间：", text)

    def test_overview_formatter_has_distinct_metric_sections(self):
        overview = HeroMetaOverview(
            season_code="19",
            season_label="S9下半赛季",
            rank_key="6",
            rank_label="大师",
            win_rate=[self.result],
            pick_rate=[self.result],
            ban_rate=[self.result],
            matches=[self.result],
            source="RivalsMeta",
            source_timestamp=1720000000,
            fetched_at=datetime(2026, 8, 14, 8, 0, tzinfo=timezone.utc),
        )
        text = format_hero_meta_overview(overview)
        for heading in ("胜率 TOP5", "选取率 TOP5", "Ban率 TOP5", "场次 TOP5"):
            self.assertIn(heading, text)
        self.assertIn("当前英雄环境", text)


if __name__ == "__main__":
    unittest.main()

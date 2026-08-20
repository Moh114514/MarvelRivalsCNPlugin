import asyncio
import json
import unittest
from datetime import datetime

import httpx

from marvel_rivals_bot.commands.daily import parse_daily_command_args
from marvel_rivals_bot.reference.dates import GAME_TZ, game_date_window, parse_game_date
from marvel_rivals_bot.services.rivals import RivalsService
from marvel_rivals_bot.datasource.cn import CNDataSource
from rendering.pages.daily import build_daily_report_html


class _DailySource:
    default_season = "19"

    def __init__(self):
        self.summary_calls = []
        self.detail_calls = []

    async def get_match_summary_page(self, uid, season, **kwargs):
        self.summary_calls.append((uid, season, kwargs))
        rows = [
            {"matchUid": "m-1", "gameModeId": 1, "matchPlayDuration": 600},
            {"matchUid": "m-2", "gameModeId": 4, "matchPlayDuration": 300},
        ]
        return {"data": {"matchInfo": rows}}

    async def get_summary_details(self, match_uids):
        self.detail_calls.append(list(match_uids))
        matches = []
        for uid in match_uids:
            matches.append({
                "matchUid": uid,
                "matchPlayers": [{
                    "playerUid": "123",
                    "nickName": "Tester",
                    "curHeroId": 1036 if uid == "m-1" else 9999,
                    "isWin": 1 if uid == "m-1" else 0,
                    "k": 10 if uid == "m-1" else 4,
                    "d": 2,
                    "a": 3,
                    "totalHeroDamage": 1000,
                    **({"totalHeroHeal": 200} if uid == "m-1" else {}),
                    "totalDamageTaken": 500,
                }],
            })
        return {"data": {"matches": matches}}

    async def get_player_profile(self, uid, season):
        raise AssertionError("non-empty reports should get their name from Detail")


class TestDailyFeature(unittest.IsolatedAsyncioTestCase):
    async def test_cn_summary_page_owns_dynamic_pagination_and_time_filter(self):
        bodies = []

        def handler(request):
            bodies.append(json.loads(request.content))
            return httpx.Response(200, json={"data": {"matchInfo": []}})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test"})
            await source.get_match_summary_page(
                "123", "19", page=2, page_size=100, start_timestamp=1786723200, end_timestamp=1786809600,
            )
            await source.get_match_summary_page("123", "19", page=0, page_size=10)
        self.assertEqual(bodies[0]["page"], 2)
        self.assertEqual(bodies[0]["pageSize"], 100)
        self.assertEqual(bodies[0]["matchTimeStamp"], {"$gte": 1786723200, "$lt": 1786809600})
        self.assertNotIn("matchTimeStamp", bodies[1])

    def test_date_parser_and_beijing_window(self):
        now = datetime(2026, 8, 20, 1, 0, tzinfo=GAME_TZ)
        self.assertEqual(parse_game_date("今天", now=now).isoformat(), "2026-08-20")
        self.assertEqual(parse_game_date("昨天", now=now).isoformat(), "2026-08-19")
        self.assertEqual(parse_game_date("8月15日", now=now).isoformat(), "2026-08-15")
        self.assertEqual(parse_game_date("2026/08/15", now=now).isoformat(), "2026-08-15")
        with self.assertRaises(ValueError):
            parse_game_date("2026-08-21", now=now)
        start, end = game_date_window(parse_game_date("2026-08-15", now=now))
        self.assertEqual(end - start, 86400)

    def test_daily_args_are_order_independent(self):
        args = parse_daily_command_args("195963667", "S9.5", "2026-08-15")
        self.assertEqual((args.uid, args.season, args.target_date.isoformat()), ("195963667", "S9.5", "2026-08-15"))

    async def test_daily_report_aggregates_modes_heroes_and_cache(self):
        source = _DailySource()
        service = RivalsService(source, cache_seconds=60, daily_cache_seconds=3600)
        report = await service.get_daily_report("123", parse_game_date("2026-08-15"), "S9.5")
        again = await service.get_daily_report("123", parse_game_date("2026-08-15"), "S9.5")
        self.assertIs(report, again)
        self.assertEqual(len(source.summary_calls), 1)
        self.assertEqual(report.total.matches, 2)
        self.assertEqual((report.quick.matches, report.competitive.matches, report.other.matches), (1, 0, 1))
        self.assertEqual((report.total.wins, report.total.losses), (1, 1))
        self.assertEqual(report.total.kda, "14 / 4 / 6")
        self.assertEqual(report.total.average_healing, 200)
        self.assertEqual(report.player_name, "Tester")
        self.assertEqual([hero.hero_name for hero in report.heroes], ["蜘蛛侠", "未知英雄（9999）"])

    async def test_detail_batch_size_is_ten(self):
        source = _DailySource()
        service = RivalsService(source, cache_seconds=60)
        await service.get_summary_details([f"m-{index}" for index in range(23)])
        self.assertEqual([len(batch) for batch in source.detail_calls], [10, 10, 3])

    def test_daily_page_is_escaped_and_aggregated(self):
        source = _DailySource()
        service = RivalsService(source)
        report = asyncio.run(service.get_daily_report("123", parse_game_date("2026-08-15"), "S9.5"))
        html = build_daily_report_html(report)
        self.assertIn("DAILY REPORT", html)
        self.assertIn("今日英雄", html)
        self.assertIn("蜘蛛侠", html)
        self.assertIn("未知英雄（9999）", html)
        self.assertNotIn("matchUid", html)


if __name__ == "__main__":
    unittest.main()

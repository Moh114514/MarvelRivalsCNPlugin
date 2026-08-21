import json
import unittest
from datetime import datetime
from types import SimpleNamespace

import httpx

from marvel_rivals_bot.commands.time_window import (
    MatchWindowCommandUsageError,
    parse_match_window_command_args,
)
from marvel_rivals_bot.models import MatchPlayer, MatchRecord, MatchTimeWindow, MatchWindowReport
from marvel_rivals_bot.reference.dates import GAME_TZ
from marvel_rivals_bot.reference.time_ranges import parse_match_time_window
from marvel_rivals_bot.services.rivals import RivalsService, _build_match_window_report, format_match_window
from marvel_rivals_bot.storage.interaction_sessions import InteractionSessionStore
from marvel_rivals_bot.datasource.cn import CNDataSource
from main import CommandUsageError, MarvelRivalsPlugin
from rendering import MatchImageRenderer
from rendering.pages.match_window import build_match_window_html, build_match_window_pages


class _WindowSource:
    default_season = "19"

    def __init__(self):
        self.summary_calls = []
        self.detail_calls = []

    async def get_match_summary_page(self, uid, *, season=None, page=0, page_size=100, start_timestamp=None, end_timestamp=None, **_):
        self.summary_calls.append({
            "uid": uid, "season": season, "page": page, "page_size": page_size,
            "start": start_timestamp, "end": end_timestamp,
        })
        start = page * 100
        size = 100 if page == 0 else 3
        rows = [
            {"matchUid": f"m-{index}", "matchTimeStamp": start_timestamp, "gameModeId": 1}
            for index in range(start, start + size)
        ]
        return {"data": {"matchInfo": rows}}

    async def get_summary_details(self, match_uids):
        self.detail_calls.append(list(match_uids))
        return {"data": {"matches": [{
            "matchUid": uid,
            "matchPlayers": [{
                "playerUid": "123", "nickName": "Window Tester", "curHeroId": 1036,
                "isWin": 1, "k": 3, "d": 1, "a": 2,
            }],
        } for uid in match_uids]}}


class TestMatchWindow(unittest.IsolatedAsyncioTestCase):
    def test_time_window_forms_and_limits(self):
        now = datetime(2026, 8, 20, 16, 0, tzinfo=GAME_TZ)
        day = parse_match_time_window(("今天", "14:00-18:00"), now=now)
        self.assertEqual(day.end_at.hour, 16)
        cross_day = parse_match_time_window(
            ("2026-08-15", "20:00", "2026-08-16", "02:00"), now=now,
        )
        self.assertEqual((cross_day.start_at.hour, cross_day.end_at.hour), (20, 2))
        rolling = parse_match_time_window(("最近6小时",), now=now)
        self.assertEqual((rolling.end_timestamp - rolling.start_timestamp), 6 * 3600)
        with self.assertRaises(ValueError):
            parse_match_time_window(("今天", "20:00-22:00"), now=now)
        with self.assertRaises(ValueError):
            parse_match_time_window(("2026-08-01", "00:00", "2026-08-09", "00:00"), now=now)

    def test_date_only_range_accepts_common_separators_and_includes_end_date(self):
        now = datetime(2026, 8, 22, 16, 0, tzinfo=GAME_TZ)
        expected = parse_match_time_window(("2026-08-20",), now=now)
        hyphen = parse_match_time_window(("8月20日-8月21日",), now=now)
        separated = parse_match_time_window(("8月20日", "8月21日"), now=now)
        chinese = parse_match_time_window(("8月20日", "到", "8月21日"), now=now)
        self.assertEqual(hyphen.start_at.date().isoformat(), "2026-08-20")
        self.assertEqual(hyphen.end_at.date().isoformat(), "2026-08-22")
        self.assertEqual(hyphen.end_timestamp, separated.end_timestamp)
        self.assertEqual(hyphen.end_timestamp, chinese.end_timestamp)
        self.assertNotEqual(hyphen.end_timestamp, expected.end_timestamp)
        with self.assertRaises(ValueError):
            parse_match_time_window(("8月21日-8月20日",), now=now)

    def test_command_rejects_season_and_keeps_uid_independent(self):
        now = datetime(2026, 8, 20, 16, 0, tzinfo=GAME_TZ)
        args = parse_match_window_command_args("123", "今天", "14:00-18:00", now=now)
        self.assertEqual(args.uid, "123")
        with self.assertRaises(MatchWindowCommandUsageError):
            parse_match_window_command_args("今天", "S9.5", now=now)

    async def test_service_filters_before_paging_and_batches_details(self):
        source = _WindowSource()
        service = RivalsService(source, cache_seconds=60, daily_cache_seconds=3600)
        window = parse_match_time_window(("2026-08-15",), now=datetime(2026, 8, 20, tzinfo=GAME_TZ))
        report = await service.get_match_window_report("123", window)
        self.assertEqual(len(report.matches), 103)
        self.assertEqual(source.summary_calls[0]["season"], None)
        self.assertEqual((source.summary_calls[0]["page_size"], len(source.summary_calls)), (100, 2))
        self.assertEqual([len(batch) for batch in source.detail_calls], [10] * 10 + [3])
        self.assertEqual(report.total.matches, 103)
        self.assertEqual(report.heroes[0].matches, 103)
        again = await service.get_match_window_report("123", window)
        self.assertIs(report, again)
        self.assertEqual(len(source.summary_calls), 2)

    def test_generic_session_overwrites_recent_and_expires(self):
        now = [100.0]
        store = InteractionSessionStore(ttl_seconds=600, clock=lambda: now[0])
        store.set_recent("u", "g", ["recent-1"])
        window = store.set_window("u", "g", [f"window-{i}" for i in range(23)], "2026年8月15日")
        self.assertEqual(window.source, "window")
        self.assertEqual(len(store.get("u", "g").match_uids), 23)
        now[0] = 700
        self.assertIsNone(store.get("u", "g"))

    def test_main_selection_uses_the_full_current_window(self):
        plugin = object.__new__(MarvelRivalsPlugin)
        store = InteractionSessionStore()
        store.set_window("u", "g", [f"window-{i}" for i in range(23)], "测试窗口")
        plugin.interaction_sessions = store
        plugin._qq_id = lambda _event: "u"
        plugin._group_id = lambda _event: "g"
        event = SimpleNamespace()
        self.assertEqual(plugin._resolve_match_selection(event, "17"), "window-16")
        with self.assertRaises(CommandUsageError):
            plugin._resolve_match_selection(event, "24")

    def test_recent_session_accepts_typed_match_records(self):
        plugin = object.__new__(MarvelRivalsPlugin)
        matches = [MatchRecord(match_uid="typed-1"), MatchRecord(match_uid="typed-2")]
        self.assertEqual(
            [plugin._selection_match_uid(item) for item in matches],
            ["typed-1", "typed-2"],
        )
        self.assertEqual(plugin._selection_match_uid({"matchUid": "legacy-1"}), "legacy-1")

    def test_long_window_renders_multiple_pages(self):
        window = MatchTimeWindow(
            1, 2, datetime(2026, 8, 15, tzinfo=GAME_TZ), datetime(2026, 8, 15, 0, 0, 1, tzinfo=GAME_TZ),
            label="测试窗口",
        )
        matches = [MatchRecord(
            match_uid=f"m-{index}",
            timestamp=1,
            game_mode_id=1,
            player=MatchPlayer("123", hero_id="1036", is_win=True, kills=1, deaths=0, assists=2),
        ) for index in range(44)]
        report = MatchWindowReport("123", "Tester", window, matches=matches)
        pages = build_match_window_pages(report)
        self.assertEqual(len(pages), 2)
        self.assertIn("对局 1-25", pages[0])
        self.assertIn("对局 26-44", pages[1])

    def test_role_stats_use_role_specific_denominators_and_group_heroes(self):
        window = MatchTimeWindow(
            1, 2, datetime(2026, 8, 15, tzinfo=GAME_TZ),
            datetime(2026, 8, 15, 0, 0, 1, tzinfo=GAME_TZ), label="测试窗口",
        )
        matches = [
            MatchRecord(
                match_uid="v-1", timestamp=1, game_mode_id=1,
                player=MatchPlayer("123", hero_id="1018", is_win=True, kills=2, deaths=1, assists=3,
                                    hero_damage=100, healing=10, damage_taken=200),
            ),
            MatchRecord(
                match_uid="v-2", timestamp=1, game_mode_id=1,
                player=MatchPlayer("123", hero_id="1018", is_win=False, kills=4, deaths=2, assists=1,
                                    hero_damage=300, healing=30, damage_taken=400),
            ),
            MatchRecord(
                match_uid="s-1", timestamp=1, game_mode_id=2,
                player=MatchPlayer("123", hero_id="1016", is_win=True, kills=1, deaths=0, assists=5,
                                    hero_damage=500, healing=60000, damage_taken=700),
            ),
        ]
        report = _build_match_window_report(
            uid="123", player_name="Tester", window=window, season="", matches=matches,
        )
        self.assertEqual(set(report.roles), {"vanguard", "duelist", "strategist"})
        self.assertEqual(report.roles["vanguard"].matches, 2)
        self.assertEqual(report.roles["vanguard"].average_hero_damage, 200)
        self.assertEqual(report.roles["strategist"].average_healing, 60000)
        self.assertEqual(report.roles["duelist"].matches, 0)
        self.assertEqual(report.heroes_by_role["vanguard"][0].hero_name, "奇异博士")
        self.assertEqual(report.heroes_by_role["strategist"][0].hero_name, "洛基")
        text = format_match_window(report)
        self.assertIn("策略家：1 场", text)
        self.assertIn("场均治疗 60000", text)
        html = build_match_window_html(report)
        self.assertIn("ROLE BREAKDOWN", html)
        self.assertIn("策略家", html)
        self.assertNotIn("总治疗", html)

    async def test_cn_time_query_omits_season_but_keeps_it_when_explicit(self):
        bodies = []

        def handler(request):
            bodies.append(json.loads(request.content))
            return httpx.Response(200, json={"data": {"matchInfo": []}})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            source = CNDataSource(client=client, env={"MRCN_API_BASE_URL": "https://example.test"})
            await source.get_match_summary_page("123", start_timestamp=1, end_timestamp=2)
            await source.get_match_summary_page("123", season="19", start_timestamp=1, end_timestamp=2)
        self.assertNotIn("matchSeason", bodies[0])
        self.assertEqual(bodies[1]["matchSeason"], {"$eq": "19"})


if __name__ == "__main__":
    unittest.main()

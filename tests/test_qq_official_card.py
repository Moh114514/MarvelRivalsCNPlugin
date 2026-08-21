import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from main import MarvelRivalsPlugin
from qq_official.cards import build_capability_test_card, build_match_window_card, build_recent_card
from qq_official.sender import QQOfficialCardSender
from rendering import (
    MatchImageRenderer, build_hero_query_html, build_match_detail_html,
    build_player_stats_html, build_recent_matches_html,
)
from marvel_rivals_bot.models import CareerSummary, HeroQueryResult, HeroStat, MatchRecord, PlayerProfile, PlayerStats


class FakeEvent:
    def __init__(self, platform="qq_official", *, group=True):
        self._platform = platform
        raw_message = SimpleNamespace(
            group_openid="group-1" if group else None,
            author=SimpleNamespace(user_openid="user-1"),
            channel_id=None,
            guild_id=None,
        )
        self.message_obj = SimpleNamespace(message_id="message-1", raw_message=raw_message)
        self.bot = SimpleNamespace(api=SimpleNamespace(
            post_group_file=AsyncMock(return_value={"file_info": "uploaded-image", "ttl": 60}),
            post_group_message=AsyncMock(),
            post_c2c_file=AsyncMock(return_value={"file_info": "uploaded-image", "ttl": 60}),
        ))
        self.post_c2c_message = AsyncMock()
        self.send = AsyncMock()

    def get_platform_name(self):
        return self._platform

    def plain_result(self, text):
        return ("text", text)

    def image_result(self, url):
        return ("image", url)


class TestQQOfficialCard(unittest.IsolatedAsyncioTestCase):
    def test_recent_card_has_match_detail_buttons_within_qq_limit(self):
        matches = [{
            "matchUid": f"match-{index}",
            "matchMapId": 1413,
            "gameModeId": 2,
            "playModeId": 0,
            "matchPlayer": {"isWin": index % 2, "curHeroId": 1036, "k": 18, "d": 4, "a": 7},
        } for index in range(12)]
        card = build_recent_card("123", "19", matches)
        self.assertEqual(len(card.rows), 5)
        self.assertEqual(sum(len(row) for row in card.rows), 10)
        self.assertEqual(card.rows[0][0].data, "/对局详情 match-0")

        card = build_recent_card("123", "19", [{"matchUid": None, "matchUID": "m-1"}, {"matchUID": "m-2"}])
        self.assertEqual(
            [button.data for row in card.rows for button in row],
            ["/对局详情 m-1", "/对局详情 m-2"],
        )

    def test_window_card_reuses_detail_buttons_and_exposes_window_ttl(self):
        matches = [MatchRecord(match_uid=f"window-{index}") for index in range(23)]
        card = build_match_window_card("2026年8月20日", matches, 10)
        self.assertEqual(sum(len(row) for row in card.rows), 23)
        self.assertLessEqual(len(card.rows), 5)
        self.assertEqual(card.rows[0][0].data, "/对局详情 window-0")
        self.assertEqual(card.rows[-1][-1].data, "/对局详情 window-22")
        self.assertIn("有效 10 分钟", card.markdown)

    async def test_window_query_sends_images_then_selectable_detail_card(self):
        report = SimpleNamespace(
            window=SimpleNamespace(label="2026年8月20日"),
            matches=[MatchRecord(match_uid="window-1"), MatchRecord(match_uid="window-2")],
        )

        plugin = object.__new__(MarvelRivalsPlugin)
        plugin.match_history = SimpleNamespace(
            build_match_window_report=AsyncMock(return_value=report),
        )
        plugin.service = SimpleNamespace()
        plugin.image_renderer = SimpleNamespace(
            match_window=AsyncMock(return_value=["https://example.com/window.png"]),
        )
        plugin.qq_card_sender = QQOfficialCardSender()
        plugin.interaction_sessions = SimpleNamespace(ttl_seconds=600, set_window= lambda *args: None)
        plugin._qq_id = lambda _event: "user-1"
        plugin._group_id = lambda _event: "group-1"
        event = FakeEvent()

        results = [item async for item in plugin._match_window_results(
            event, SimpleNamespace(uid="123", window=SimpleNamespace()), "战绩回顾",
        )]
        self.assertEqual(results, [])
        self.assertEqual(event.bot.api.post_group_file.await_count, 1)
        self.assertEqual(event.bot.api.post_group_message.await_count, 2)
        card_payload = event.bot.api.post_group_message.await_args_list[-1].kwargs
        self.assertIn("选择要查看的对局", card_payload["markdown"]["content"])
        self.assertEqual(card_payload["keyboard"]["content"]["rows"][0]["buttons"][0]["action"]["data"], "/对局详情 window-1")

    async def test_image_renderer_builds_recent_and_detail_cards(self):
        html_render = AsyncMock(return_value="rendered.png")
        renderer = MatchImageRenderer(html_render)
        matches = [{"matchUid": "m-1", "matchMapId": 1413, "matchPlayer": {"isWin": 1, "curHeroId": 1036}}]
        self.assertEqual(await renderer.recent("123", "19", matches), "rendered.png")
        recent_html = html_render.await_args.args[0]
        self.assertIn("最近 10 场对局", recent_html)
        self.assertIn("蜘蛛侠", recent_html)
        self.assertIn("S9下半赛季", recent_html)

        payload = {"data": {"matches": [{"matchUid": "m-1", "matchPlayers": [{"camp": 1, "nickName": "A&lt;", "curHeroId": 1036, "k": 10}]}]}}
        self.assertEqual(await renderer.detail(payload), "rendered.png")
        detail_html = html_render.await_args.args[0]
        self.assertIn("阵营 1", detail_html)
        self.assertIn("A&amp;lt;", detail_html)

        stats = PlayerStats(profile=PlayerProfile(uid="123", name="Tester"), season="19")
        self.assertEqual(await renderer.player(stats), "rendered.png")
        self.assertIn("Tester", html_render.await_args.args[0])

        hero = HeroQueryResult(
            uid="123", hero_id="1036", hero_name="蜘蛛侠", season="19",
            payload={"data": {"careers": [{"totalMatchCount": 3}]}},
        )
        self.assertEqual(await renderer.hero(hero), "rendered.png")
        self.assertIn("蜘蛛侠", html_render.await_args.args[0])
        self.assertEqual(await renderer.help(MarvelRivalsPlugin.HELP_TEXT), "rendered.png")
        self.assertIn("COMMAND GUIDE", html_render.await_args.args[0])
        for call in html_render.await_args_list:
            self.assertTrue(call.kwargs["options"]["full_page"])

    async def test_help_sends_themed_image_on_qq_official(self):
        plugin = object.__new__(MarvelRivalsPlugin)
        plugin.image_renderer = SimpleNamespace(help=AsyncMock(return_value="https://example.com/help.png"))
        plugin.qq_card_sender = QQOfficialCardSender()
        event = FakeEvent()

        results = [item async for item in plugin.help(event)]

        self.assertEqual(results, [])
        event.bot.api.post_group_file.assert_awaited_once_with(
            group_openid="group-1", file_type=1,
            url="https://example.com/help.png", srv_send_msg=False,
        )

    def test_player_html_fills_viewport_and_computes_missing_win_rate(self):
        stats = PlayerStats(
            profile=PlayerProfile(uid="123", name="Tester", level=80),
            summary=CareerSummary(matches=27, wins=14, kills=386, deaths=117, assists=284),
            heroes=[HeroStat(hero_id=str(index), hero_name=f"英雄{index}", matches=index) for index in range(1, 11)],
            season="19",
        )
        html = build_player_stats_html(stats)
        self.assertIn("width:100vw", html)
        self.assertNotIn("width:1040px", html)
        self.assertNotIn("路", html)
        self.assertIn('class="mr-page"', html)
        self.assertIn('class="mr-page__background"', html)
        self.assertIn('class="mr-metric__value">51.9%', html)
        self.assertIn('class="mr-metric__value">386/117/284', html)
        self.assertIn('class="mr-hero-row__index">10</span>', html)
        self.assertIn("英雄10", html)

    def test_image_html_escapes_untrusted_values(self):
        html = build_recent_matches_html("<script>{{danger}}</script>", "19", [])
        self.assertNotIn("<script>", html)
        self.assertNotIn("{{danger}}", html)
        detail = build_match_detail_html({"data": {"matches": [{"matchPlayers": []}]}})
        self.assertIn("暂无玩家明细", detail)

    async def test_recent_query_sends_image_then_markdown_buttons(self):
        matches = [{"matchUid": "m-1", "matchPlayer": {"isWin": 1}}]

        class FakeService:
            def season_code(self, season):
                return "19"

            async def get_recent_matches(self, uid, season):
                return matches

        plugin = object.__new__(MarvelRivalsPlugin)
        plugin.service = FakeService()
        plugin.bindings = SimpleNamespace(get=lambda _qq: None)
        plugin.qq_card_sender = QQOfficialCardSender()
        plugin.image_renderer = SimpleNamespace(recent=AsyncMock(return_value="https://example.com/recent.png"))
        event = FakeEvent()
        event.get_sender_id = lambda: "qq-1"

        results = [item async for item in plugin.recent(event, "123", "S9.5")]
        self.assertEqual(results, [])
        event.send.assert_not_awaited()
        event.bot.api.post_group_file.assert_awaited_once_with(
            group_openid="group-1", file_type=1,
            url="https://example.com/recent.png", srv_send_msg=False,
        )
        self.assertEqual(event.bot.api.post_group_message.await_count, 2)
        markdown_payload, media_payload = [call.kwargs for call in event.bot.api.post_group_message.await_args_list]
        self.assertEqual(markdown_payload["msg_type"], 2)
        self.assertTrue(markdown_payload["markdown"]["content"].startswith("<@user-1>\n\n"))
        self.assertIn("选择要查看的对局", markdown_payload["markdown"]["content"])
        self.assertIn("keyboard", markdown_payload)
        self.assertEqual(markdown_payload["msg_seq"], 1)
        button_action = markdown_payload["keyboard"]["content"]["rows"][0]["buttons"][0]["action"]
        self.assertEqual(button_action["data"], "/对局详情 m-1")
        self.assertIn("unsupport_tips", button_action)
        self.assertEqual(media_payload["msg_type"], 7)
        self.assertEqual(media_payload["media"]["file_info"], "uploaded-image")
        self.assertNotIn("content", media_payload)
        self.assertNotIn("keyboard", media_payload)
        self.assertEqual(media_payload["msg_seq"], 2)

    def test_c2c_markdown_does_not_add_group_mention(self):
        payload = QQOfficialCardSender.build_payload(FakeEvent(group=False), build_capability_test_card())
        self.assertFalse(payload["markdown"]["content"].startswith("<@"))

    async def test_recent_query_qq_card_failure_falls_back_to_text(self):
        matches = [{"matchUid": "m-1", "matchPlayer": {"isWin": 1}}]

        class FakeService:
            def season_code(self, season):
                return "19"

            async def get_recent_matches(self, uid, season):
                return matches

        plugin = object.__new__(MarvelRivalsPlugin)
        plugin.service = FakeService()
        plugin.bindings = SimpleNamespace(get=lambda _qq: None)
        plugin.qq_card_sender = QQOfficialCardSender()
        plugin.image_renderer = SimpleNamespace(recent=AsyncMock(return_value="recent.png"))
        event = FakeEvent()
        event.get_sender_id = lambda: "qq-1"
        event.bot.api.post_group_file.side_effect = RuntimeError("media rejected")

        results = [item async for item in plugin.recent(event, "123", "S9.5")]
        self.assertEqual(results[0][0], "text")
        self.assertIn("最近比赛", results[0][1])
        event.bot.api.post_group_message.assert_not_awaited()

    async def test_match_query_image_failure_falls_back_to_same_payload(self):
        payload = {"data": {"matches": [{"matchUid": "m-1", "matchPlayers": []}]}}

        class FakeService:
            async def get_match_detail(self, match_uid):
                return payload

        plugin = object.__new__(MarvelRivalsPlugin)
        plugin.service = FakeService()
        plugin.qq_card_sender = QQOfficialCardSender()
        plugin.image_renderer = SimpleNamespace(detail=AsyncMock(side_effect=RuntimeError("render failed")))
        event = FakeEvent()
        results = [item async for item in plugin.match_detail(event, "m-1")]
        self.assertEqual(results[0][0], "text")
        self.assertIn("matchUid：m-1", results[0][1])
        event.bot.api.post_group_message.assert_not_awaited()

    async def test_match_query_sends_image_without_buttons(self):
        payload = {"data": {"matches": [{"matchUid": "m-1", "matchPlayers": []}]}}

        class FakeService:
            async def get_match_detail(self, match_uid):
                return payload

        plugin = object.__new__(MarvelRivalsPlugin)
        plugin.service = FakeService()
        plugin.qq_card_sender = QQOfficialCardSender()
        plugin.image_renderer = SimpleNamespace(detail=AsyncMock(return_value="https://example.com/detail.png"))
        event = FakeEvent()

        results = [item async for item in plugin.match_detail(event, "m-1")]
        self.assertEqual(results, [])
        event.bot.api.post_group_file.assert_awaited_once()
        event.bot.api.post_group_message.assert_awaited_once()
        media_payload = event.bot.api.post_group_message.await_args.kwargs
        self.assertEqual(media_payload["msg_type"], 7)
        self.assertEqual(media_payload["msg_seq"], 1)
        self.assertNotIn("keyboard", media_payload)
        self.assertNotIn("content", media_payload)

    def test_payload_contains_markdown_command_and_url_buttons(self):
        payload = QQOfficialCardSender.build_payload(FakeEvent(), build_capability_test_card())
        self.assertEqual(payload["msg_type"], 2)
        self.assertIn("漫威争锋查询", payload["markdown"]["content"])
        buttons = payload["keyboard"]["content"]["rows"][0]["buttons"]
        self.assertEqual(buttons[0]["action"]["type"], 2)
        self.assertTrue(buttons[0]["action"]["enter"])
        self.assertEqual(buttons[0]["action"]["data"], "/战绩 1287101468")
        self.assertEqual(buttons[1]["action"]["type"], 0)
        self.assertTrue(buttons[1]["action"]["data"].startswith("https://"))

    async def test_group_sender_calls_qq_official_api(self):
        event = FakeEvent()
        await QQOfficialCardSender().send(event, build_capability_test_card())
        event.bot.api.post_group_message.assert_awaited_once()
        kwargs = event.bot.api.post_group_message.await_args.kwargs
        self.assertEqual(kwargs["group_openid"], "group-1")
        self.assertTrue(kwargs["markdown"]["content"].startswith("<@user-1>\n\n"))
        self.assertIn("keyboard", kwargs)

    async def test_group_sender_uploads_image_then_sends_markdown_with_keyboard(self):
        event = FakeEvent()
        card = build_capability_test_card()
        card = type(card)(card.markdown, card.rows, "https://example.com/result.png")
        await QQOfficialCardSender().send(event, card)
        event.bot.api.post_group_file.assert_awaited_once()
        self.assertEqual(event.bot.api.post_group_message.await_count, 2)
        markdown_payload, media_payload = [call.kwargs for call in event.bot.api.post_group_message.await_args_list]
        self.assertEqual(media_payload["msg_type"], 7)
        self.assertEqual(media_payload["media"]["file_info"], "uploaded-image")
        self.assertNotIn("keyboard", media_payload)
        self.assertEqual(markdown_payload["msg_type"], 2)
        self.assertIn("keyboard", markdown_payload)

    async def test_c2c_sender_uses_event_protocol_method(self):
        event = FakeEvent(group=False)
        await QQOfficialCardSender().send(event, build_capability_test_card())
        event.post_c2c_message.assert_awaited_once()
        kwargs = event.post_c2c_message.await_args.kwargs
        self.assertEqual(kwargs["openid"], "user-1")
        self.assertIn("keyboard", kwargs)

    async def test_send_image_uses_direct_c2c_media_message(self):
        event = FakeEvent(group=False)
        await QQOfficialCardSender().send_image(event, "https://example.com/result.png")
        event.bot.api.post_c2c_file.assert_awaited_once_with(
            openid="user-1", file_type=1,
            url="https://example.com/result.png", srv_send_msg=False,
        )
        event.post_c2c_message.assert_awaited_once()
        kwargs = event.post_c2c_message.await_args.kwargs
        self.assertEqual(kwargs["openid"], "user-1")
        self.assertEqual(kwargs["msg_type"], 7)
        self.assertEqual(kwargs["msg_seq"], 1)
        self.assertNotIn("markdown", kwargs)
        self.assertNotIn("keyboard", kwargs)

    async def test_card_test_falls_back_on_non_qq_platform(self):
        plugin = object.__new__(MarvelRivalsPlugin)
        plugin.qq_card_sender = QQOfficialCardSender()
        event = FakeEvent("aiocqhttp")
        results = [item async for item in plugin.card_test(event)]
        self.assertEqual(results[0][0], "text")
        self.assertIn("已回退普通文本", results[0][1])
        event.bot.api.post_group_message.assert_not_awaited()

    async def test_card_test_sends_directly_without_duplicate_result(self):
        plugin = object.__new__(MarvelRivalsPlugin)
        plugin.qq_card_sender = QQOfficialCardSender()
        event = FakeEvent()
        results = [item async for item in plugin.card_test(event)]
        self.assertEqual(results, [])
        event.bot.api.post_group_message.assert_awaited_once()

    async def test_card_test_falls_back_when_qq_api_rejects_payload(self):
        plugin = object.__new__(MarvelRivalsPlugin)
        plugin.qq_card_sender = QQOfficialCardSender()
        event = FakeEvent()
        event.bot.api.post_group_message.side_effect = RuntimeError("keyboard not allowed")
        results = [item async for item in plugin.card_test(event)]
        self.assertEqual(results[0][0], "text")
        self.assertIn("Markdown 与消息按钮权限", results[0][1])

    async def test_player_query_sends_image_and_api_failure_falls_back_same_data(self):
        stats = PlayerStats(profile=PlayerProfile(uid="123", name="Tester"), season="19")

        class FakeService:
            calls = 0

            async def get_player_stats(self, uid, season):
                self.calls += 1
                return stats

        plugin = object.__new__(MarvelRivalsPlugin)
        plugin.service = FakeService()
        plugin.qq_card_sender = QQOfficialCardSender()
        plugin.image_renderer = SimpleNamespace(player=AsyncMock(return_value="https://example.com/player.png"))
        event = FakeEvent()
        results = [item async for item in plugin._query(event, "123", "S9.5")]
        self.assertEqual(results, [])
        self.assertEqual(plugin.service.calls, 1)
        event.send.assert_not_awaited()
        event.bot.api.post_group_file.assert_awaited_once()
        self.assertEqual(event.bot.api.post_group_message.await_count, 1)
        media_payload = event.bot.api.post_group_message.await_args.kwargs
        self.assertEqual(media_payload["msg_type"], 7)
        self.assertEqual(media_payload["media"]["file_info"], "uploaded-image")
        self.assertEqual(media_payload["msg_seq"], 1)
        self.assertNotIn("content", media_payload)
        self.assertNotIn("keyboard", media_payload)

        event = FakeEvent()
        event.bot.api.post_group_file = AsyncMock(side_effect=RuntimeError("rejected"))
        results = [item async for item in plugin._query(event, "123", "S9.5")]
        self.assertEqual(results[0][0], "text")
        self.assertIn("Tester", results[0][1])
        self.assertEqual(plugin.service.calls, 2)

    async def test_hero_query_sends_image_without_navigation_card(self):
        result = HeroQueryResult(
            uid="123", hero_id="1036", hero_name="蜘蛛侠", season="19",
            payload={"data": {"careers": [{"totalMatchCount": 1}]}},
        )

        class FakeService:
            async def get_hero_stats(self, uid, hero_name, season):
                return result

        plugin = object.__new__(MarvelRivalsPlugin)
        plugin.service = FakeService()
        plugin.bindings = SimpleNamespace(get=lambda _qq: None)
        plugin.qq_card_sender = QQOfficialCardSender()
        plugin.image_renderer = SimpleNamespace(hero=AsyncMock(return_value="https://example.com/hero.png"))
        event = FakeEvent()

        results = [item async for item in plugin.hero(event, "蜘蛛侠", "123", "S9.5")]
        self.assertEqual(results, [])
        event.bot.api.post_group_file.assert_awaited_once()
        media_payload = event.bot.api.post_group_message.await_args.kwargs
        self.assertEqual(media_payload["msg_type"], 7)
        self.assertEqual(media_payload["msg_seq"], 1)
        self.assertNotIn("markdown", media_payload)
        self.assertNotIn("keyboard", media_payload)

if __name__ == "__main__":
    unittest.main()

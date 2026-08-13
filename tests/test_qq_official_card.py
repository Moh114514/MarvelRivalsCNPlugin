import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from main import MarvelRivalsPlugin
from qq_official.cards import (
    build_capability_test_card, build_hero_card, build_match_card,
    build_player_card, build_recent_card,
)
from qq_official.sender import QQOfficialCardSender
from rendering import (
    MatchImageRenderer, build_hero_query_html, build_match_detail_html,
    build_player_stats_html, build_recent_matches_html,
)
from marvel_rivals_bot.models import CareerSummary, HeroQueryResult, HeroStat, PlayerProfile, PlayerStats


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
    def test_player_card_contains_navigation_and_hero_commands(self):
        card = build_player_card(PlayerStats(
            profile=PlayerProfile(uid="123", name="Player*One", level=80, rank_game_season="钻石2（4411 分）"),
            summary=CareerSummary(matches=43, wins=22, kills=787, deaths=297, assists=427, win_rate=51.2),
            heroes=[HeroStat(hero_id="1036", hero_name="蜘蛛侠", matches=37, wins=21, kills=492)],
            season="19",
        ))
        self.assertEqual(card.markdown, "")
        commands = [button.data for row in card.rows for button in row]
        self.assertIn("/最近对局 123 S9.5", commands)
        self.assertIn("/英雄数据 蜘蛛侠 123 S9.5", commands)

        unknown = build_player_card(PlayerStats(
            profile=PlayerProfile(uid="123", name="Tester"),
            heroes=[HeroStat(hero_id=None, hero_name="Unknown Hero")],
            season="19",
        ))
        self.assertFalse(any(button.data.startswith("/英雄 ") for row in unknown.rows for button in row))

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

    def test_hero_and_match_cards_include_navigation_and_teams(self):
        hero = build_hero_card(HeroQueryResult(
            uid="123", hero_id="1036", hero_name="蜘蛛侠", season="19",
            payload={"data": {"careers": [{"heroId": 1036, "totalMatchCount": 37, "totalMatchWinCount": 21, "k": 492}]}},
        ))
        self.assertIn("蜘蛛侠", hero.markdown)
        self.assertEqual(hero.rows[0][0].data, "/英雄数据 蜘蛛侠 123 S9.5")

        match = build_match_card({"data": {"matches": [{
            "matchUid": "m-1", "matchMapId": 1413, "gameModeId": 2, "playModeId": 0,
            "matchWinnerSide": 1, "matchPlayers": [
                {"camp": 1, "isWin": 1, "nickName": "A", "curHeroId": 1036, "k": 10, "d": 2, "a": 3},
                {"camp": 2, "isWin": 0, "nickName": "B", "curHeroId": 1066, "k": 5, "d": 6, "a": 1},
            ],
        }]}})
        self.assertEqual(match.markdown, "")
        self.assertEqual(match.rows[0][0].data, "/对局详情 m-1")

        mixed_camps = build_match_card({"data": {"matches": [{
            "matchUid": None,
            "matchPlayers": [{"camp": 1}, {"camp": "2"}],
        }]}})
        self.assertEqual(mixed_camps.rows, [])

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
        for call in html_render.await_args_list:
            self.assertTrue(call.kwargs["options"]["full_page"])

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
        self.assertIn("胜率</span><b>51.9%", html)
        self.assertIn("K / D / A</span><b>386/117/284", html)
        self.assertIn("10. 英雄10", html)

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

    def test_player_card_builder_has_no_markdown_text(self):
        card = build_player_card(PlayerStats(
            profile=PlayerProfile(uid="123", name="Tester"),
            heroes=[HeroStat(hero_id="1036", hero_name="蜘蛛侠")],
            season="19",
        ))
        self.assertEqual(card.markdown, "")
        self.assertTrue(card.rows)

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

    async def test_match_query_sends_image_only_without_buttons(self):
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

    async def test_player_query_sends_card_and_api_failure_falls_back_same_data(self):
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

        with patch(
            "main.build_player_card",
            side_effect=ValueError("unexpected response shape"),
        ):
            results = [item async for item in plugin._query(FakeEvent(), "123", "S9.5")]
        self.assertEqual(results[0][0], "text")
        self.assertIn("Tester", results[0][1])
        self.assertEqual(plugin.service.calls, 3)


if __name__ == "__main__":
    unittest.main()

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from astrbot_plugin_marvel_rivals.main import MarvelRivalsPlugin
from astrbot_plugin_marvel_rivals.qq_official.cards import build_capability_test_card
from astrbot_plugin_marvel_rivals.qq_official.sender import QQOfficialCardSender


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
        self.bot = SimpleNamespace(api=SimpleNamespace(post_group_message=AsyncMock()))
        self.post_c2c_message = AsyncMock()

    def get_platform_name(self):
        return self._platform

    def plain_result(self, text):
        return ("text", text)


class TestQQOfficialCard(unittest.IsolatedAsyncioTestCase):
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
        self.assertIn("keyboard", kwargs)

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


if __name__ == "__main__":
    unittest.main()

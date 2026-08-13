import unittest
from unittest.mock import AsyncMock

import httpx

from astrbot_plugin_marvel_rivals.main import MarvelRivalsPlugin
from astrbot_plugin_marvel_rivals.qq_official.menu import DEFAULT_MENU, QQMenuClient, QQMenuError, validate_menu


class FakeEvent:
    def plain_result(self, text):
        return ("text", text)


class TestQQMenu(unittest.IsolatedAsyncioTestCase):
    def test_default_menu_matches_plugin_commands_and_limits(self):
        validate_menu(DEFAULT_MENU)
        items = DEFAULT_MENU["menu"]["items"]
        self.assertEqual([item["name"] for item in items], ["战绩", "最近", "英雄", "账号", "更多"])
        commands = []
        for item in items:
            if item["type"] == "send_message":
                commands.append(item["send_message"])
            commands.extend(child["send_message"] for child in item.get("sub_menu_items", []) if child["type"] == "send_message")
        for command in ("/战绩", "/最近", "/英雄 ", "/绑定漫威 ", "/解绑漫威", "/对局 ", "/漫威帮助", "/卡片测试"):
            self.assertIn(command, commands)

    def test_menu_validation_rejects_invalid_link_and_nested_menu(self):
        with self.assertRaisesRegex(QQMenuError, "https"):
            validate_menu({"menu": {"items": [{"name": "官网", "type": "link", "link": "http://example.com"}]}})
        with self.assertRaisesRegex(QQMenuError, "不支持"):
            validate_menu({"menu": {"items": [{"name": "更多", "type": "menu", "sub_menu_items": [{"name": "嵌套", "type": "menu"}]}]}})

    async def test_client_gets_token_and_puts_complete_menu(self):
        requests = []

        def handler(request: httpx.Request):
            requests.append(request)
            if request.url.path == "/app/getAppAccessToken":
                return httpx.Response(200, json={"access_token": "secret-token", "expires_in": "7200"})
            self.assertEqual(request.headers["Authorization"], "QQBot secret-token")
            self.assertEqual(request.method, "PUT")
            return httpx.Response(200, json={"version": 7})

        client = QQMenuClient("app-id", "client-secret", transport=httpx.MockTransport(handler))
        self.assertEqual((await client.put_menu())["version"], 7)
        self.assertEqual(len(requests), 2)
        self.assertNotIn("secret-token", str(DEFAULT_MENU))

    async def test_client_reuses_token_and_exposes_safe_error(self):
        token_calls = 0

        def handler(request: httpx.Request):
            nonlocal token_calls
            if request.url.path == "/app/getAppAccessToken":
                token_calls += 1
                return httpx.Response(200, json={"access_token": "token", "expires_in": 7200})
            return httpx.Response(400, json={"err_code": 40030013, "message": "超出数量限制", "trace_id": "trace-1"})

        client = QQMenuClient("app-id", "secret", transport=httpx.MockTransport(handler))
        with self.assertRaisesRegex(QQMenuError, "40030013.*trace-1"):
            await client.get_menu()
        with self.assertRaises(QQMenuError):
            await client.get_menu()
        self.assertEqual(token_calls, 1)

    async def test_client_wraps_network_errors_without_exposing_secret(self):
        def handler(request: httpx.Request):
            raise httpx.ConnectError("connection failed with client-secret", request=request)

        client = QQMenuClient("app-id", "client-secret", transport=httpx.MockTransport(handler))
        with self.assertRaises(QQMenuError) as caught:
            await client.get_menu()
        self.assertIn("网络请求异常", str(caught.exception))
        self.assertNotIn("client-secret", str(caught.exception))

    async def test_admin_commands_sync_and_show_menu(self):
        plugin = object.__new__(MarvelRivalsPlugin)
        plugin.qq_menu_client = type("Menu", (), {
            "put_menu": AsyncMock(return_value={"version": 9}),
            "get_menu": AsyncMock(return_value={"version": 9, "menu": {"items": [{"name": "战绩"}, {"name": "最近"}]}}),
        })()
        synced = [item async for item in plugin.sync_qq_menu(FakeEvent())]
        shown = [item async for item in plugin.show_qq_menu(FakeEvent())]
        self.assertIn("版本：9", synced[0][1])
        self.assertIn("战绩、最近", shown[0][1])


if __name__ == "__main__":
    unittest.main()

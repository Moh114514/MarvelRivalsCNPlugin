from __future__ import annotations

import time
from typing import Any

import httpx


class QQMenuError(RuntimeError):
    pass


DEFAULT_MENU: dict[str, Any] = {
    "menu": {
        "items": [
            {"type": "send_message", "name": "战绩", "send_message": "/战绩"},
            {"type": "send_message", "name": "最近", "send_message": "/最近对局"},
            {"type": "send_message", "name": "英雄", "send_message": "/英雄 "},
            {
                "type": "menu",
                "name": "账号",
                "sub_menu_items": [
                    {"type": "send_message", "name": "绑定账号", "send_message": "/绑定漫威 "},
                    {"type": "send_message", "name": "解除绑定", "send_message": "/解绑漫威"},
                ],
            },
            {
                "type": "menu",
                "name": "更多",
                "sub_menu_items": [
                    {"type": "send_message", "name": "对局详情", "send_message": "/对局 "},
                    {"type": "send_message", "name": "使用帮助", "send_message": "/帮助"},
                    {"type": "send_message", "name": "卡片测试", "send_message": "/卡片测试"},
                ],
            },
        ]
    }
}


def _weighted_length(value: str) -> int:
    return sum(1 if ord(char) < 128 else 2 for char in value)


def validate_menu(payload: dict[str, Any]) -> None:
    menu = payload.get("menu")
    items = menu.get("items") if isinstance(menu, dict) else None
    if not isinstance(items, list):
        raise QQMenuError("菜单配置缺少 menu.items")
    if len(items) > 10:
        raise QQMenuError("QQ 一级菜单最多 10 项")
    for item in items:
        _validate_item(item, submenu=False)


def _validate_item(item: Any, *, submenu: bool) -> None:
    if not isinstance(item, dict):
        raise QQMenuError("菜单项必须是对象")
    name = item.get("name")
    limit = 14 if submenu else 10
    if not isinstance(name, str) or not name or _weighted_length(name) > limit:
        raise QQMenuError(f"菜单名称为空或超过 {limit} 个字符单位：{name!r}")
    item_type = item.get("type")
    allowed = {"send_message", "link"} if submenu else {"switch", "send_message", "link", "menu"}
    if item_type not in allowed:
        raise QQMenuError(f"不支持的菜单类型：{item_type}")
    if item_type == "send_message" and not isinstance(item.get("send_message"), str):
        raise QQMenuError(f"菜单“{name}”缺少 send_message")
    if item_type == "link":
        link = item.get("link")
        if not isinstance(link, str) or not link.startswith("https://"):
            raise QQMenuError(f"菜单“{name}”的链接必须以 https:// 开头")
    if item_type == "switch":
        switch = item.get("switch")
        if not isinstance(switch, dict) or not isinstance(switch.get("switch_id"), str) or not isinstance(switch.get("default"), bool):
            raise QQMenuError(f"菜单“{name}”的开关配置无效")
    if item_type == "menu":
        children = item.get("sub_menu_items")
        if not isinstance(children, list) or not children or len(children) > 5:
            raise QQMenuError(f"折叠菜单“{name}”必须包含 1 至 5 个子菜单")
        for child in children:
            _validate_item(child, submenu=True)


class QQMenuClient:
    TOKEN_URL = "https://api.bot.qq.com/app/getAppAccessToken"
    API_BASE_URL = "https://api.bot.qq.com"

    def __init__(
        self,
        app_id: str,
        client_secret: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 10,
    ):
        self.app_id = str(app_id).strip()
        self.client_secret = str(client_secret).strip()
        self.transport = transport
        self.timeout = timeout
        self._access_token = ""
        self._expires_at = 0.0

    def _require_credentials(self) -> None:
        if not self.app_id or not self.client_secret:
            raise QQMenuError("请先在插件配置中填写 QQ_BOT_APP_ID 和 QQ_BOT_CLIENT_SECRET")

    async def _token(self) -> str:
        self._require_credentials()
        if self._access_token and time.monotonic() < self._expires_at:
            return self._access_token
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout) as client:
                response = await client.post(self.TOKEN_URL, json={"appId": self.app_id, "clientSecret": self.client_secret})
        except httpx.RequestError as exc:
            raise QQMenuError(f"获取 QQ 访问凭证失败：网络请求异常（{type(exc).__name__}）") from exc
        data = self._response_json(response, "获取 QQ 访问凭证")
        token = data.get("access_token")
        if not isinstance(token, str) or not token:
            raise QQMenuError("QQ 凭证响应缺少 access_token")
        try:
            expires_in = max(60, int(data.get("expires_in", 7200)))
        except (TypeError, ValueError):
            expires_in = 7200
        self._access_token = token
        self._expires_at = time.monotonic() + max(1, expires_in - 60)
        return token

    async def get_menu(self) -> dict[str, Any]:
        return await self._request("GET")

    async def put_menu(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        menu = payload or DEFAULT_MENU
        validate_menu(menu)
        return await self._request("PUT", menu)

    async def _request(self, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        token = await self._token()
        request_kwargs: dict[str, Any] = {
            "headers": {"Authorization": f"QQBot {token}"},
        }
        if payload is not None:
            request_kwargs["json"] = payload
        try:
            async with httpx.AsyncClient(transport=self.transport, timeout=self.timeout) as client:
                response = await client.request(method, f"{self.API_BASE_URL}/v2/menu", **request_kwargs)
        except httpx.RequestError as exc:
            operation = "查询 QQ 菜单" if method == "GET" else "同步 QQ 菜单"
            raise QQMenuError(f"{operation}失败：网络请求异常（{type(exc).__name__}）") from exc
        return self._response_json(response, "查询 QQ 菜单" if method == "GET" else "同步 QQ 菜单")

    @staticmethod
    def _response_json(response: httpx.Response, operation: str) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError as exc:
            raise QQMenuError(f"{operation}失败：HTTP {response.status_code}，响应不是 JSON") from exc
        if response.is_error or (isinstance(data, dict) and data.get("err_code") not in (None, 0)):
            code = data.get("err_code", response.status_code) if isinstance(data, dict) else response.status_code
            message = data.get("message", "未知错误") if isinstance(data, dict) else "未知错误"
            trace_id = data.get("trace_id") if isinstance(data, dict) else None
            trace = f"，trace_id={trace_id}" if trace_id else ""
            raise QQMenuError(f"{operation}失败：错误码 {code}，{message}{trace}")
        if not isinstance(data, dict):
            raise QQMenuError(f"{operation}失败：响应结构无效")
        return data

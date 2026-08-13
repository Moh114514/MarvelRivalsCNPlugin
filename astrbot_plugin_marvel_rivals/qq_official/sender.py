from __future__ import annotations

import random
from typing import Any
from urllib.parse import quote, urlsplit

from .models import CardButton, InteractiveCard


class UnsupportedQQOfficialEvent(RuntimeError):
    pass


class QQOfficialCardSender:
    PLATFORM_NAMES = {"qq_official", "qq_official_webhook"}

    @classmethod
    def supports(cls, event: Any) -> bool:
        try:
            return event.get_platform_name() in cls.PLATFORM_NAMES
        except (AttributeError, TypeError):
            return False

    @staticmethod
    def _button_payload(button: CardButton, button_id: str) -> dict[str, Any]:
        return {
            "id": button_id,
            "render_data": {
                "label": button.label,
                "visited_label": button.label,
                "style": 1 if button.style == "blue" else 0,
            },
            "action": {
                "type": 2 if button.action == "command" else 0,
                "permission": {
                    "type": 2,
                    "specify_role_ids": [],
                    "specify_user_ids": [],
                },
                "data": button.data,
                "enter": button.action == "command",
                "reply": False,
                "at_bot_show_channel_list": False,
            },
        }

    @classmethod
    def build_payload(cls, event: Any, card: InteractiveCard) -> dict[str, Any]:
        rows = []
        for row_index, row in enumerate(card.rows[:5]):
            rows.append({
                "buttons": [
                    cls._button_payload(button, f"mrcn-{row_index}-{button_index}")
                    for button_index, button in enumerate(row[:5])
                ]
            })
        message_obj = getattr(event, "message_obj", None)
        markdown = card.markdown
        if card.image_url:
            if not isinstance(card.image_url, str):
                raise ValueError("图片 URL 必须是字符串")
            image_url = card.image_url.strip()
            parsed = urlsplit(image_url)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("图片 URL 必须是可访问的 HTTP(S) 地址")
            image_url = quote(image_url, safe=":/?#@!$&'*+,;=%")
            markdown = f"![查询结果]({image_url})\n\n{markdown}"
        payload = {
            "markdown": {"content": markdown},
            "keyboard": {"content": {"rows": rows}},
            "msg_type": 2,
            "msg_id": getattr(message_obj, "message_id", None),
            "msg_seq": random.randint(1, 10000),
        }
        if payload["msg_id"] is None:
            payload.pop("msg_id")
        return payload

    async def send(self, event: Any, card: InteractiveCard) -> None:
        if not self.supports(event):
            raise UnsupportedQQOfficialEvent("当前平台不是 QQ Official")
        payload = self.build_payload(event, card)
        source = getattr(getattr(event, "message_obj", None), "raw_message", None)
        bot = getattr(event, "bot", None)
        api = getattr(bot, "api", None)
        if source is None or bot is None:
            raise UnsupportedQQOfficialEvent("无法取得 QQ Official 事件上下文")

        group_openid = getattr(source, "group_openid", None)
        if group_openid and api and hasattr(api, "post_group_message"):
            await api.post_group_message(group_openid=group_openid, **payload)
            return

        author = getattr(source, "author", None)
        user_openid = getattr(author, "user_openid", None)
        if user_openid and hasattr(event, "post_c2c_message"):
            await event.post_c2c_message(openid=user_openid, **payload)
            return

        channel_id = getattr(source, "channel_id", None)
        if channel_id and api and hasattr(api, "post_message"):
            payload.pop("msg_type", None)
            payload.pop("msg_seq", None)
            await api.post_message(channel_id=channel_id, **payload)
            return

        guild_id = getattr(source, "guild_id", None)
        if guild_id and api and hasattr(api, "post_dms"):
            payload.pop("msg_type", None)
            payload.pop("msg_seq", None)
            await api.post_dms(guild_id=guild_id, **payload)
            return

        raise UnsupportedQQOfficialEvent("当前 QQ Official 会话类型暂不支持富消息")

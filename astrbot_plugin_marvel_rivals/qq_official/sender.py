from __future__ import annotations

import random
from typing import Any
from urllib.parse import urlsplit

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
                "unsupport_tips": "当前 QQ 版本不支持此操作，请更新 QQ 后重试。",
            },
        }

    @classmethod
    def _keyboard(cls, card: InteractiveCard) -> dict[str, Any]:
        rows = []
        for row_index, row in enumerate(card.rows[:5]):
            rows.append({
                "buttons": [
                    cls._button_payload(button, f"mrcn-{row_index}-{button_index}")
                    for button_index, button in enumerate(row[:5])
                ]
            })
        return {"content": {"rows": rows}}

    @classmethod
    def build_payload(cls, event: Any, card: InteractiveCard) -> dict[str, Any]:
        message_obj = getattr(event, "message_obj", None)
        payload = {
            "markdown": {"content": card.markdown},
            "keyboard": cls._keyboard(card),
            "msg_type": 2,
            "msg_id": getattr(message_obj, "message_id", None),
            "msg_seq": random.randint(1, 10000),
        }
        if payload["msg_id"] is None:
            payload.pop("msg_id")
        return payload

    @staticmethod
    def _validate_image_url(image_url: str) -> str:
        if not isinstance(image_url, str):
            raise ValueError("图片 URL 必须是字符串")
        image_url = image_url.strip()
        parsed = urlsplit(image_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("图片 URL 必须是可访问的 HTTP(S) 地址")
        return image_url

    @staticmethod
    def _media_payload(media: Any) -> Any:
        if isinstance(media, dict):
            return media
        if hasattr(media, "to_dict"):
            return media.to_dict()
        if hasattr(media, "__dict__"):
            return dict(media.__dict__)
        fields = {name: getattr(media, name) for name in ("file_uuid", "file_info", "ttl") if hasattr(media, name)}
        if fields:
            return fields
        return media

    async def _send_media(self, event: Any, card: InteractiveCard, source: Any, bot: Any, api: Any) -> bool:
        image_url = self._validate_image_url(card.image_url or "")
        message_obj = getattr(event, "message_obj", None)
        raw_message = getattr(message_obj, "raw_message", None)
        group_openid = getattr(raw_message, "group_openid", None)
        author = getattr(raw_message, "author", None)
        user_openid = getattr(author, "user_openid", None)
        reply_id = getattr(message_obj, "message_id", None)
        media_reply_fields = {"msg_id": reply_id, "msg_seq": 2} if reply_id else {}
        markdown_payload = self.build_payload(event, card)
        if reply_id:
            # 群/C2C 的被动回复需要为同一 msg_id 使用递增的序号。
            # 先发 Markdown 可让 QQ 自动附加的 @ 信息显示在结果最前面。
            markdown_payload["msg_seq"] = 1
        if group_openid and api and hasattr(api, "post_group_file") and hasattr(api, "post_group_message"):
            media = await api.post_group_file(
                group_openid=group_openid, file_type=1, url=image_url, srv_send_msg=False
            )
            await api.post_group_message(group_openid=group_openid, **markdown_payload)
            await api.post_group_message(
                group_openid=group_openid,
                msg_type=7,
                media=self._media_payload(media),
                **media_reply_fields,
            )
            return True
        if user_openid and api and hasattr(api, "post_c2c_file") and hasattr(event, "post_c2c_message"):
            media = await api.post_c2c_file(
                openid=user_openid, file_type=1, url=image_url, srv_send_msg=False
            )
            await event.post_c2c_message(openid=user_openid, **markdown_payload)
            await event.post_c2c_message(
                openid=user_openid,
                msg_type=7,
                media=self._media_payload(media),
                **media_reply_fields,
            )
            return True
        raise UnsupportedQQOfficialEvent("当前 QQ Official 会话不支持图片与按钮合并发送")

    async def send(self, event: Any, card: InteractiveCard) -> None:
        if not self.supports(event):
            raise UnsupportedQQOfficialEvent("当前平台不是 QQ Official")
        source = getattr(getattr(event, "message_obj", None), "raw_message", None)
        bot = getattr(event, "bot", None)
        api = getattr(bot, "api", None)
        if source is None or bot is None:
            raise UnsupportedQQOfficialEvent("无法取得 QQ Official 事件上下文")

        if card.image_url:
            await self._send_media(event, card, source, bot, api)
            return

        payload = self.build_payload(event, card)

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

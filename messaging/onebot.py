"""Conservative OneBot adapter using AstrBot message-chain capabilities."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class OneBotSender:
    PLATFORM_NAMES = {"aiocqhttp", "onebot", "onebot11", "onebot_v11", "onebot12"}

    @classmethod
    def supports(cls, event: Any) -> bool:
        try:
            name = str(event.get_platform_name()).lower()
        except (AttributeError, TypeError):
            return False
        return name in cls.PLATFORM_NAMES or "onebot" in name or name == "aiocqhttp"

    @staticmethod
    def _sender_id(event: Any) -> str:
        getter = getattr(event, "get_sender_id", None)
        if callable(getter):
            try:
                return str(getter())
            except Exception:
                pass
        return ""

    @staticmethod
    def _group_id(event: Any) -> str:
        getter = getattr(event, "get_group_id", None)
        if callable(getter):
            try:
                value = getter()
                if value not in (None, ""):
                    return str(value)
            except Exception:
                pass
        message_obj = getattr(event, "message_obj", None)
        raw = getattr(message_obj, "raw_message", None)
        for source in (raw, message_obj, event):
            for name in ("group_id", "group_openid", "groupId"):
                value = source.get(name) if isinstance(source, Mapping) else getattr(source, name, None)
                if value not in (None, ""):
                    return str(value)
        return ""

    @classmethod
    def is_group(cls, event: Any) -> bool:
        return bool(cls._group_id(event))

    @staticmethod
    def _component(component_name: str, **kwargs: Any) -> Any:
        try:
            from astrbot.api import message_components

            component_type = getattr(message_components, component_name)
            if component_name == "Image" and hasattr(component_type, "fromURL"):
                return component_type.fromURL(kwargs["url"])
            try:
                return component_type(**kwargs)
            except TypeError:
                return component_type(kwargs.get("qq") or kwargs.get("url"))
        except (ImportError, AttributeError, TypeError):
            return {"type": component_name.lower(), **kwargs}

    @classmethod
    def build_chain(cls, event: Any, image_url: str, *, mention: bool = True) -> list[Any]:
        chain: list[Any] = []
        if mention and cls.is_group(event):
            chain.append(cls._component("At", qq=cls._sender_id(event)))
        chain.append(cls._component("Image", url=image_url))
        return chain

    @classmethod
    def send_image(cls, event: Any, image_url: str, *, mention: bool = False) -> Any:
        chain = cls.build_chain(event, image_url, mention=mention)
        for method_name in ("chain_result", "message_chain_result"):
            method = getattr(event, method_name, None)
            if callable(method):
                return method(chain)
        # AstrBot adapters that do not expose chain_result still have the
        # stable image_result API; preserving it is preferable to guessing a
        # private OneBot action or keyboard protocol.
        return event.image_result(image_url)

    @classmethod
    def send_image_with_mention(cls, event: Any, image_url: str) -> Any:
        return cls.send_image(event, image_url, mention=True)

    @classmethod
    def image_result(cls, event: Any, image_url: str, *, mention: bool = True) -> Any:
        return cls.send_image(event, image_url, mention=mention)


__all__ = ["OneBotSender"]

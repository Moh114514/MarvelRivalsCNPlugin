"""Platform-neutral result sending interfaces."""

from __future__ import annotations

from typing import Any, Protocol


class MessageSender(Protocol):
    def supports(self, event: Any) -> bool: ...

    def send_image(self, event: Any, image_url: str, *, mention: bool = False) -> Any: ...

    def send_image_with_mention(self, event: Any, image_url: str) -> Any: ...

    def image_result(self, event: Any, image_url: str, *, mention: bool = True) -> Any: ...


class GenericSender:
    """Use AstrBot's normal image result for adapters without special needs."""

    @classmethod
    def supports(cls, event: Any) -> bool:
        return True

    @staticmethod
    def send_image(event: Any, image_url: str, *, mention: bool = False) -> Any:
        return event.image_result(image_url)

    @staticmethod
    def send_image_with_mention(event: Any, image_url: str) -> Any:
        return GenericSender.send_image(event, image_url, mention=True)

    @staticmethod
    def image_result(event: Any, image_url: str, *, mention: bool = True) -> Any:
        return GenericSender.send_image(
            event, image_url, mention=mention
        )


class SenderRouter:
    def __init__(self, *senders: MessageSender):
        self.senders = tuple(senders)

    def for_event(self, event: Any) -> MessageSender:
        for sender in self.senders:
            if sender.supports(event):
                return sender
        return GenericSender()

    def send_image(self, event: Any, image_url: str, *, mention: bool = False) -> Any:
        sender = self.for_event(event)
        return sender.send_image(event, image_url, mention=mention)

    def send_image_with_mention(self, event: Any, image_url: str) -> Any:
        sender = self.for_event(event)
        return sender.send_image_with_mention(event, image_url)

    def image_result(self, event: Any, image_url: str, *, mention: bool = True) -> Any:
        if mention:
            return self.send_image_with_mention(event, image_url)
        return self.send_image(event, image_url, mention=False)


__all__ = ["GenericSender", "MessageSender", "SenderRouter"]

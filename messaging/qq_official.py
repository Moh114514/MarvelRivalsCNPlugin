"""Adapter facade for the existing QQ Official implementation."""

from __future__ import annotations

from typing import Any

try:
    from ..qq_official.sender import QQOfficialCardSender
except ImportError:
    from qq_official.sender import QQOfficialCardSender


class QQOfficialSender(QQOfficialCardSender):
    """Semantic name retained while the tested QQ API implementation stays put."""

    async def send_image_with_mention(self, event: Any, image_url: str) -> Any:
        return await self.send_image(event, image_url)

    def image_result(self, event: Any, image_url: str, *, mention: bool = True) -> Any:
        return self.send_image(event, image_url)


__all__ = ["QQOfficialSender"]

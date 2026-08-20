"""Short-lived user interaction state, kept separate from data caches."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class RecentSelectionSession:
    user_id: str
    group_id: str
    match_uids: tuple[str, ...]
    created_at: float


class InteractionSessionStore:
    def __init__(self, ttl_seconds: float = 300, *, clock: Callable[[], float] | None = None):
        self.ttl_seconds = max(1.0, float(ttl_seconds))
        self._clock = clock or time.monotonic
        self._recent: dict[tuple[str, str], RecentSelectionSession] = {}

    @staticmethod
    def key(user_id: str, group_id: str | None = None) -> tuple[str, str]:
        return str(user_id), str(group_id or "")

    def set_recent(
        self,
        user_id: str,
        group_id: str | None,
        match_uids: list[str] | tuple[str, ...],
    ) -> RecentSelectionSession:
        self.cleanup()
        session = RecentSelectionSession(
            user_id=str(user_id),
            group_id=str(group_id or ""),
            match_uids=tuple(str(value) for value in match_uids if str(value).strip()),
            created_at=self._clock(),
        )
        self._recent[self.key(user_id, group_id)] = session
        return session

    def get_recent(self, user_id: str, group_id: str | None = None) -> RecentSelectionSession | None:
        key = self.key(user_id, group_id)
        session = self._recent.get(key)
        if session is None:
            return None
        if self._clock() - session.created_at >= self.ttl_seconds:
            self._recent.pop(key, None)
            return None
        return session

    def cleanup(self) -> int:
        now = self._clock()
        expired = [key for key, item in self._recent.items() if now - item.created_at >= self.ttl_seconds]
        for key in expired:
            self._recent.pop(key, None)
        return len(expired)


__all__ = ["InteractionSessionStore", "RecentSelectionSession"]

"""Short-lived user interaction state, kept separate from data caches."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class MatchSelectionSession:
    user_id: str
    group_id: str
    match_uids: tuple[str, ...]
    created_at: float
    source: str = "recent"
    label: str = "最近对局"


class InteractionSessionStore:
    def __init__(self, ttl_seconds: float = 600, *, clock: Callable[[], float] | None = None):
        self.ttl_seconds = max(1.0, float(ttl_seconds))
        self._clock = clock or time.monotonic
        self._sessions: dict[tuple[str, str], MatchSelectionSession] = {}
        self._recent = self._sessions

    @staticmethod
    def key(user_id: str, group_id: str | None = None) -> tuple[str, str]:
        return str(user_id), str(group_id or "")

    def set(
        self,
        user_id: str,
        group_id: str | None,
        match_uids: list[str] | tuple[str, ...],
        *,
        source: str,
        label: str,
    ) -> MatchSelectionSession:
        self.cleanup()
        session = MatchSelectionSession(
            user_id=str(user_id),
            group_id=str(group_id or ""),
            source=str(source),
            label=str(label),
            match_uids=tuple(str(value) for value in match_uids if str(value).strip()),
            created_at=self._clock(),
        )
        self._sessions[self.key(user_id, group_id)] = session
        return session

    def set_recent(
        self,
        user_id: str,
        group_id: str | None,
        match_uids: list[str] | tuple[str, ...],
    ) -> MatchSelectionSession:
        return self.set(
            user_id,
            group_id,
            match_uids,
            source="recent",
            label="最近对局",
        )

    def set_window(
        self,
        user_id: str,
        group_id: str | None,
        match_uids: list[str] | tuple[str, ...],
        label: str,
    ) -> MatchSelectionSession:
        return self.set(user_id, group_id, match_uids, source="window", label=label)

    def get(self, user_id: str, group_id: str | None = None) -> MatchSelectionSession | None:
        key = self.key(user_id, group_id)
        session = self._sessions.get(key)
        if session is None:
            return None
        if self._clock() - session.created_at >= self.ttl_seconds:
            self._sessions.pop(key, None)
            return None
        return session

    def get_recent(self, user_id: str, group_id: str | None = None) -> MatchSelectionSession | None:
        return self.get(user_id, group_id)

    def cleanup(self) -> int:
        now = self._clock()
        expired = [key for key, item in self._sessions.items() if now - item.created_at >= self.ttl_seconds]
        for key in expired:
            self._sessions.pop(key, None)
        return len(expired)


RecentSelectionSession = MatchSelectionSession


__all__ = ["InteractionSessionStore", "MatchSelectionSession", "RecentSelectionSession"]

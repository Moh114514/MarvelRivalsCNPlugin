"""Command argument parsing for generic match-window queries."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from ..models import MatchTimeWindow
from ..reference.time_ranges import parse_match_time_window


class MatchWindowCommandUsageError(ValueError):
    """Raised when a window command cannot classify its arguments."""


_UID_RE = re.compile(r"^\d+$")
_SEASON_RE = re.compile(r"^[sS]\d+(?:\.5|上半赛季|下半赛季)?$")


@dataclass(frozen=True, slots=True)
class MatchWindowCommandArgs:
    window: MatchTimeWindow
    uid: str = ""


def parse_match_window_command_args(
    *values: str,
    now: datetime | None = None,
) -> MatchWindowCommandArgs:
    """Parse UID independently from the explicit window token sequence."""

    uid = ""
    window_values: list[str] = []
    for raw in values:
        token = str(raw or "").strip()
        if not token:
            continue
        if _UID_RE.fullmatch(token):
            if uid:
                raise MatchWindowCommandUsageError("只能指定一个 UID")
            uid = token
            continue
        if _SEASON_RE.fullmatch(token):
            raise MatchWindowCommandUsageError("战绩回顾按时间查询，无需指定赛季")
        window_values.append(token)
    try:
        window = parse_match_time_window(window_values, now=now)
    except ValueError as exc:
        raise MatchWindowCommandUsageError(str(exc)) from exc
    return MatchWindowCommandArgs(window=window, uid=uid)


parse_window_args = parse_match_window_command_args


__all__ = [
    "MatchWindowCommandArgs",
    "MatchWindowCommandUsageError",
    "parse_match_window_command_args",
    "parse_window_args",
]

"""Argument parsing for the daily-report commands."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

from ..reference.dates import parse_game_date
from ..reference.seasons import parse_season_name


class DailyCommandUsageError(ValueError):
    """Raised when a daily-report token is neither date, UID, nor season."""


_UID_RE = re.compile(r"^\d+$")
_SEASON_RE = re.compile(r"^[sS]\d+(?:\.5|上半赛季|下半赛季)?$")


@dataclass(frozen=True, slots=True)
class DailyCommandArgs:
    target_date: date
    uid: str = ""
    season: str = ""


def parse_daily_command_args(
    *values: str,
    now: datetime | None = None,
) -> DailyCommandArgs:
    """Classify up to three AstrBot positional arguments independent of order."""

    target_date = parse_game_date(None, now=now)
    date_seen = False
    uid = ""
    season = ""
    for raw in values:
        token = str(raw or "").strip()
        if not token:
            continue
        if _UID_RE.fullmatch(token):
            if uid:
                raise DailyCommandUsageError("只能指定一个 UID")
            uid = token
            continue
        if _SEASON_RE.fullmatch(token):
            if season:
                raise DailyCommandUsageError("只能指定一个赛季")
            try:
                parse_season_name(token)
            except ValueError as exc:
                raise DailyCommandUsageError(str(exc)) from exc
            season = token
            continue
        try:
            parsed_date = parse_game_date(token, now=now)
        except ValueError as exc:
            raise DailyCommandUsageError(str(exc)) from exc
        if date_seen:
            raise DailyCommandUsageError("只能指定一个日期")
        target_date = parsed_date
        date_seen = True
    return DailyCommandArgs(target_date=target_date, uid=uid, season=season)


parse_daily_args = parse_daily_command_args


__all__ = ["DailyCommandArgs", "DailyCommandUsageError", "parse_daily_args", "parse_daily_command_args"]

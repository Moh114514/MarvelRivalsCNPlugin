"""Explicit Beijing-time parsing for match history windows."""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date, datetime, time, timedelta

from ..models import MatchTimeWindow
from .dates import GAME_TZ, now_in_game_timezone, parse_game_date


MAX_WINDOW_SECONDS = 7 * 24 * 60 * 60
_TIME_RE = re.compile(r"^(?P<hour>\d{1,2}):(?P<minute>\d{2})(?::(?P<second>\d{2}))?$")
_TIME_RANGE_RE = re.compile(
    r"^(?P<start>\d{1,2}:\d{2}(?::\d{2})?)[-~至–—](?P<end>\d{1,2}:\d{2}(?::\d{2})?)$"
)
_RECENT_RE = re.compile(r"^最近(?P<hours>\d{1,2})小时$")
_SEASON_RE = re.compile(r"^[sS]\d+(?:\.5|上半赛季|下半赛季)?$")


def _current(now: datetime | None) -> datetime:
    value = now or now_in_game_timezone()
    if value.tzinfo is None:
        return value.replace(tzinfo=GAME_TZ)
    return value.astimezone(GAME_TZ)


def _date_or_none(value: str, now: datetime) -> date | None:
    try:
        return parse_game_date(value, now=now)
    except ValueError:
        return None


def _parse_clock(value: str) -> time:
    match = _TIME_RE.fullmatch(value.strip())
    if not match:
        raise ValueError("时间格式错误，请使用 HH:MM 或 HH:MM:SS")
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    second = int(match.group("second") or 0)
    try:
        return time(hour, minute, second)
    except ValueError as exc:
        raise ValueError("时间格式错误，请使用有效的时分秒") from exc


def _parse_range(value: str) -> tuple[time, time] | None:
    match = _TIME_RANGE_RE.fullmatch(value.strip())
    if not match:
        return None
    return _parse_clock(match.group("start")), _parse_clock(match.group("end"))


def _label(start: datetime, end: datetime, *, rolling_hours: int | None = None) -> str:
    if rolling_hours is not None:
        return f"最近 {rolling_hours} 小时"
    if start.date() == end.date() - timedelta(days=1) and start.time() == time(0) and end.time() == time(0):
        return f"{start.year}年{start.month}月{start.day}日"
    if start.date() == end.date():
        return f"{start.year}年{start.month}月{start.day}日 {start:%H:%M}–{end:%H:%M}"
    return f"{start:%Y-%m-%d %H:%M}–{end:%Y-%m-%d %H:%M}"


def _make_window(start: datetime, end: datetime, *, now: datetime, label: str | None = None) -> MatchTimeWindow:
    start = start.astimezone(GAME_TZ)
    end = end.astimezone(GAME_TZ)
    if start >= end:
        raise ValueError("时间范围的开始时间必须早于结束时间")
    if end - start > timedelta(seconds=MAX_WINDOW_SECONDS):
        raise ValueError("单次战绩回顾最多查询 7 天")
    if start > now:
        raise ValueError("该时间范围尚未开始")
    clamped_to_now = end > now
    if clamped_to_now:
        end = now
    if start >= end:
        raise ValueError("该时间范围尚未开始")
    return MatchTimeWindow(
        start_timestamp=int(start.timestamp()),
        end_timestamp=int(end.timestamp()),
        start_at=start,
        end_at=end,
        timezone="Asia/Shanghai",
        label=label or (
            f"{start.year}年{start.month}月{start.day}日 {start:%H:%M}–现在"
            if clamped_to_now else _label(start, end)
        ),
    )


def parse_match_time_window(
    args: Sequence[str] | str | None = None,
    *,
    now: datetime | None = None,
) -> MatchTimeWindow:
    """Parse the deliberately small public time-window grammar.

    Supported forms include a calendar date, ``date HH:MM-HH:MM``, two
    explicit date/time endpoints, ``最近N小时`` and ``本周``.  All output is
    a Beijing-time half-open interval and the end is clamped to ``now``.
    """

    current = _current(now)
    if isinstance(args, str):
        tokens = [item for item in args.split() if item]
    else:
        tokens = [str(item).strip() for item in (args or ()) if str(item).strip()]
    if any(_SEASON_RE.fullmatch(token) for token in tokens):
        raise ValueError("战绩回顾按时间查询，无需指定赛季")

    if not tokens:
        start = datetime.combine(current.date(), time.min, tzinfo=GAME_TZ)
        return _make_window(start, current, now=current, label=f"{current.year}年{current.month}月{current.day}日")

    if len(tokens) == 1:
        recent = _RECENT_RE.fullmatch(tokens[0])
        if recent:
            hours = int(recent.group("hours"))
            if hours not in {1, 3, 6, 12, 24}:
                raise ValueError("目前支持最近 1、3、6、12 或 24 小时")
            return _make_window(
                current - timedelta(hours=hours), current, now=current,
                label=f"最近 {hours} 小时",
            )
        if tokens[0] == "本周":
            start_date = current.date() - timedelta(days=current.weekday())
            start = datetime.combine(start_date, time.min, tzinfo=GAME_TZ)
            return _make_window(start, current, now=current, label="本周")
        target = _date_or_none(tokens[0], current)
        if target is None:
            raise ValueError("时间范围格式错误，请使用日期、日期时间段或最近N小时")
        start = datetime.combine(target, time.min, tzinfo=GAME_TZ)
        end = start + timedelta(days=1)
        return _make_window(start, end, now=current, label=f"{target.year}年{target.month}月{target.day}日")

    if len(tokens) == 2:
        target = _date_or_none(tokens[0], current)
        if target is None:
            raise ValueError("时间范围格式错误，请使用 日期 HH:MM-HH:MM")
        clocks = _parse_range(tokens[1])
        if clocks is None:
            raise ValueError("时间范围格式错误，请使用 HH:MM-HH:MM")
        start_clock, end_clock = clocks
        start = datetime.combine(target, start_clock, tzinfo=GAME_TZ)
        end = datetime.combine(target, end_clock, tzinfo=GAME_TZ)
        return _make_window(start, end, now=current)

    if len(tokens) == 4:
        start_date = _date_or_none(tokens[0], current)
        end_date = _date_or_none(tokens[2], current)
        if start_date is None or end_date is None:
            raise ValueError("跨日范围格式应为 日期 HH:MM 日期 HH:MM")
        start = datetime.combine(start_date, _parse_clock(tokens[1]), tzinfo=GAME_TZ)
        end = datetime.combine(end_date, _parse_clock(tokens[3]), tzinfo=GAME_TZ)
        return _make_window(start, end, now=current)

    raise ValueError("时间范围参数格式错误，请检查日期和时间是否成对")


# Small aliases keep imports readable for callers that used the earlier daily
# terminology while the public model remains time-window based.
parse_time_window = parse_match_time_window
parse_match_time_range = parse_match_time_window


__all__ = [
    "MAX_WINDOW_SECONDS",
    "parse_match_time_range",
    "parse_match_time_window",
    "parse_time_window",
]

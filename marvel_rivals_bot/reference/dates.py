"""Beijing-time date parsing for time-windowed game queries."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo


try:
    GAME_TZ = ZoneInfo("Asia/Shanghai")
except Exception:  # Windows installations may not ship the IANA tz database.
    GAME_TZ = timezone(timedelta(hours=8), name="Asia/Shanghai")
DATE_ERROR = "日期格式错误，请使用今天、昨天、YYYY-MM-DD、MM-DD 或 M月D日"

_FULL_DATE_RE = re.compile(r"^(?P<year>\d{4})[-/](?P<month>\d{1,2})[-/](?P<day>\d{1,2})$")
_SHORT_DATE_RE = re.compile(r"^(?P<month>\d{1,2})-(?P<day>\d{1,2})$")
_CN_DATE_RE = re.compile(r"^(?P<month>\d{1,2})月(?P<day>\d{1,2})日?$")


def now_in_game_timezone() -> datetime:
    return datetime.now(GAME_TZ)


def parse_game_date(value: str | None = None, *, now: datetime | None = None) -> date:
    """Parse the intentionally small, explicit daily-command date grammar."""

    current = now or now_in_game_timezone()
    current = current.replace(tzinfo=GAME_TZ) if current.tzinfo is None else current.astimezone(GAME_TZ)
    text = str(value or "").strip()
    if not text or text in {"今天", "今日"}:
        result = current.date()
    elif text in {"昨天", "昨日"}:
        result = (current - timedelta(days=1)).date()
    else:
        match = _FULL_DATE_RE.fullmatch(text)
        if match:
            year = int(match.group("year"))
            month = int(match.group("month"))
            day = int(match.group("day"))
        else:
            match = _SHORT_DATE_RE.fullmatch(text) or _CN_DATE_RE.fullmatch(text)
            if not match:
                raise ValueError(DATE_ERROR)
            year = current.year
            month = int(match.group("month"))
            day = int(match.group("day"))
        try:
            result = date(year, month, day)
        except ValueError as exc:
            raise ValueError(DATE_ERROR) from exc

    if result > current.date():
        raise ValueError("不能查询未来日期的战绩")
    return result


def game_date_window(target_date: date) -> tuple[int, int]:
    """Return the UTC epoch bounds for a Beijing calendar day."""

    start = datetime(
        target_date.year,
        target_date.month,
        target_date.day,
        tzinfo=GAME_TZ,
    )
    end = start + timedelta(days=1)
    return int(start.timestamp()), int(end.timestamp())


def format_game_date(target_date: date, separator: str = ".") -> str:
    return f"{target_date.year:04d}{separator}{target_date.month:02d}{separator}{target_date.day:02d}"


parse_daily_date = parse_game_date
build_daily_time_window = game_date_window


__all__ = [
    "DATE_ERROR",
    "GAME_TZ",
    "build_daily_time_window",
    "format_game_date",
    "game_date_window",
    "now_in_game_timezone",
    "parse_daily_date",
    "parse_game_date",
]

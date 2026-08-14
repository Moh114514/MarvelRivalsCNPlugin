"""Formatting and response-shape helpers used by rendering pages."""

from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any


def escape_text(value: Any, fallback: str = "-") -> str:
    """Escape dynamic text for HTML while preserving the old fallbacks."""

    text = escape(fallback if value in (None, "") else str(value))
    return text.replace("{", "&#123;").replace("}", "&#125;")


def format_number(data: dict, *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, (int, float)):
            if abs(value) >= 1000:
                return f"{value / 1000:.1f}K"
            if isinstance(value, float) and not value.is_integer():
                return f"{value:.1f}"
            return str(int(value))
    return "-"


def format_duration(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "-"
    minutes, seconds = divmod(int(value), 60)
    return f"{minutes}:{seconds:02d}"


def format_timestamp(value: Any) -> str:
    try:
        return datetime.fromtimestamp(int(value)).strftime("%m-%d %H:%M")
    except (TypeError, ValueError, OSError):
        return "未知时间"


def extract_first_match(payload: dict) -> dict:
    data = payload.get("data", payload)
    matches = data.get("matches", []) if isinstance(data, dict) else []
    return matches[0] if isinstance(matches, list) and matches and isinstance(matches[0], dict) else {}


def extract_career(result: Any) -> dict:
    payload = result.payload
    data = payload.get("data", payload)
    careers = data.get("careers", []) if isinstance(data, dict) else []
    return careers[0] if isinstance(careers, list) and careers and isinstance(careers[0], dict) else {}

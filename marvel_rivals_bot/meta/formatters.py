"""Simplified-Chinese text formatters for Meta ViewModels."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import HeroMetaBoard, HeroMetaOverview, HeroMetaResult


def _percent(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}%"


def _timestamp(value: Any) -> str:
    if value is None:
        return "未知"
    if isinstance(value, datetime):
        return value.astimezone().strftime("%Y-%m-%d %H:%M")
    try:
        number = float(value)
        if number > 100_000_000_000:
            number /= 1000
        return datetime.fromtimestamp(number).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError, OSError, OverflowError):
        return str(value)


def _hero_line(index: int, result: HeroMetaResult) -> str:
    return (
        f"{index}. {result.hero_name}  "
        f"胜率 {_percent(result.win_rate)} | "
        f"选取率 {_percent(result.pick_rate)} | "
        f"Ban率 {_percent(result.ban_rate)} | "
        f"场次 {result.matches:,}"
    )


def format_hero_meta_board(board: HeroMetaBoard) -> str:
    """Format a board without reading provider-specific raw payload fields."""

    lines = [f"英雄环境 | {board.season_label} | {board.rank_label}"]
    lines.append(f"数据来源：{board.source}")
    lines.append(f"更新时间：{_timestamp(board.source_timestamp)}")
    if board.stale:
        lines.append("当前上游暂不可用，展示最近缓存数据")
    if not board.heroes:
        lines.append("没有可用的英雄环境数据。")
        return "\n".join(lines)
    lines.append("")
    lines.extend(_hero_line(index, result) for index, result in enumerate(board.heroes, 1))
    return "\n".join(lines)


def format_hero_meta_overview(overview: HeroMetaOverview) -> str:
    """Format the multi-metric environment overview."""

    lines = [f"当前英雄环境 | {overview.season_label} | {overview.rank_label}"]
    lines.append(f"数据来源：{overview.source}")
    lines.append(f"更新时间：{_timestamp(overview.source_timestamp)}")
    if overview.stale:
        lines.append("当前上游暂不可用，展示最近缓存数据")

    sections = (
        ("胜率 TOP5", overview.win_rate, "胜率", "win_rate"),
        ("选取率 TOP5", overview.pick_rate, "选取率", "pick_rate"),
        ("Ban率 TOP5", overview.ban_rate, "Ban率", "ban_rate"),
    )
    if not any(items for _, items, _, _ in sections):
        lines.append("没有可用的英雄环境数据。")
        return "\n".join(lines)
    for title, items, label, metric in sections:
        lines.extend(("", title))
        for index, result in enumerate(items, 1):
            value = result.matches if metric == "matches" else _percent(getattr(result, metric))
            if metric == "matches":
                value = f"{value:,}"
            lines.append(f"{index}. {result.hero_name}  {label} {value}")
    return "\n".join(lines)


def format_single_hero_meta(result: HeroMetaResult, *, season_label: str, rank_label: str, source: str, source_timestamp: Any, stale: bool = False) -> str:
    lines = [f"{result.hero_name} | {season_label} | {rank_label}"]
    lines.extend(
        [
            f"胜率：{_percent(result.win_rate)}",
            f"选取率：{_percent(result.pick_rate)}",
            f"Ban率：{_percent(result.ban_rate)}",
            f"样本场次：{result.matches:,}",
            f"来源：{source}",
            f"更新时间：{_timestamp(source_timestamp)}",
        ]
    )
    if stale:
        lines.append("当前上游暂不可用，展示最近缓存数据")
    return "\n".join(lines)

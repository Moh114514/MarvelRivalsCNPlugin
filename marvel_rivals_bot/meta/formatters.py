"""Simplified-Chinese text formatters for Meta ViewModels."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import HeroMetaBoard, HeroMetaResult


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

"""Simplified-Chinese text formatters for Meta ViewModels."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import (
    HeroMetaBoard,
    HeroMetaComparison,
    HeroMetaInsights,
    HeroMetaOverview,
    HeroMetaResult,
    HeroMetaRoleBoards,
    HeroMetaSegments,
    HeroMetaVersionChanges,
    HeroRankSeries,
    RankMonsterBoard,
)


def format_command_error(reason: str, usage: str) -> str:
    """Format user input errors without disguising upstream failures."""

    return (
        "Mrrrrrrr！（杰夫不知道你在说什么，请检查命令是否正确）\n\n"
        f"原因：{reason}\n"
        f"用法：{usage}"
    )


def _percent(value: float | None) -> str:
    return "—" if value is None else f"{value:.2f}%"


def _delta(value: float | None) -> str:
    return "—" if value is None else f"{value:+.2f}pp"


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
    if board.group_by_role and board.role_boards:
        for role_board in board.role_boards:
            lines.extend(("", role_board.role_label))
            if not role_board.heroes:
                lines.append("暂无可用数据。")
            else:
                start = role_board.range_start or 1
                lines.extend(
                    _hero_line(start + offset, result)
                    for offset, result in enumerate(role_board.heroes)
                )
        return "\n".join(lines)
    if not board.heroes:
        lines.append("没有可用的英雄环境数据。")
        return "\n".join(lines)
    lines.append("")
    start = board.range_start or 1
    lines.extend(_hero_line(start + offset, result) for offset, result in enumerate(board.heroes))
    return "\n".join(lines)


def format_hero_meta_role_boards(boards: HeroMetaRoleBoards) -> str:
    lines = [f"英雄排行 | {boards.season_label} | {boards.rank_label}"]
    lines.append(f"数据来源：{boards.source}")
    lines.append(f"更新时间：{_timestamp(boards.source_timestamp)}")
    if boards.stale:
        lines.append("当前上游暂不可用，展示最近缓存数据")
    for role_board in boards.roles:
        lines.extend(("", role_board.role_label))
        if not role_board.heroes:
            lines.append("暂无可用数据。")
        else:
            start = role_board.range_start or 1
            lines.extend(
                _hero_line(start + offset, result)
                for offset, result in enumerate(role_board.heroes)
            )
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


def format_hero_meta_segments(segments: HeroMetaSegments) -> str:
    """Format a hero's metrics in canonical rank order."""

    lines = [f"英雄分段 | {segments.hero_name} | {segments.season_label}"]
    lines.append(f"数据来源：{segments.source}")
    lines.append(f"更新时间：{_timestamp(segments.source_timestamp)}")
    if segments.stale:
        lines.append("当前上游暂不可用，展示最近缓存数据")
    lines.extend(("", "段位        胜率       选取率      Ban率       场次"))
    for segment in segments.segments:
        result = segment.result
        if result is None:
            lines.append(f"{segment.rank_label:<8} 暂无数据")
            continue
        lines.append(
            f"{segment.rank_label:<8} "
            f"{_percent(result.win_rate):>8} "
            f"{_percent(result.pick_rate):>10} "
            f"{_percent(result.ban_rate):>10} "
            f"{result.matches:,}"
        )
    return "\n".join(lines)


def format_hero_meta_comparison(comparison: HeroMetaComparison) -> str:
    """Format two heroes without recomputing any metric in presentation."""

    left, right = comparison.left, comparison.right
    lines = [f"英雄对比 | {comparison.season_label} | {comparison.rank_label}"]
    lines.append(f"数据来源：{comparison.source}")
    lines.append(f"更新时间：{_timestamp(comparison.source_timestamp)}")
    if comparison.stale:
        lines.append("当前上游暂不可用，展示最近缓存数据")
    lines.extend(("", f"{left.hero_name}  VS  {right.hero_name}", ""))
    lines.extend(
        (
            f"胜率：{_percent(left.win_rate)}  VS  {_percent(right.win_rate)}",
            f"选取率：{_percent(left.pick_rate)}  VS  {_percent(right.pick_rate)}",
            f"Ban率：{_percent(left.ban_rate)}  VS  {_percent(right.ban_rate)}",
            f"场次：{left.matches:,}  VS  {right.matches:,}",
        )
    )
    return "\n".join(lines)


def _history_source_lines(model: Any) -> list[str]:
    lines = [f"数据来源：{model.source}", f"最近上游时间：{_timestamp(model.source_timestamp)}"]
    if model.stale:
        lines.append("当前上游暂不可用，展示最近缓存数据")
    return lines


def format_hero_meta_trend(series: HeroRankSeries) -> str:
    """Format a cross-season hero series without recomputing metrics."""

    lines = [f"英雄趋势 | {series.hero_name} | {series.rank_label}", *_history_source_lines(series)]
    lines.extend(("", "趋势指标（括号内为较上一赛季变化）"))
    for point in series.points:
        result = point.result
        if result is None:
            lines.append(f"{point.season_label:<14} 暂无数据")
            continue
        def trend(metric: str, delta: float | None) -> str:
            value = _percent(getattr(result, metric))
            change = "基准" if delta is None else _trend_delta(delta)
            return f"{value}（{change}）"

        lines.append(
            f"{point.season_label}  胜率 {trend('win_rate', point.win_rate_delta)} | "
            f"选取率 {trend('pick_rate', point.pick_rate_delta)} | "
            f"Ban率 {trend('ban_rate', point.ban_rate_delta)} | 样本 {result.matches:,}"
        )
    return "\n".join(lines)


def _trend_delta(value: float) -> str:
    if value > 0:
        return f"▲ {value:+.2f}pp"
    if value < 0:
        return f"▼ {value:+.2f}pp"
    return "→ 0.00pp"


def _delta_line(index: int, item: Any, metric: str) -> str:
    return (
        f"{index}. {item.hero_name}  {_delta(getattr(item, metric))} "
        f"（{_percent(getattr(item.current, metric.removesuffix('_delta')))}，场次 {item.current.matches:,}）"
    )


def format_meta_version_changes(changes: HeroMetaVersionChanges) -> str:
    """Format season-to-season changes as transparent metric deltas."""

    lines = [
        f"版本变化（按赛季快照） | {changes.previous_season_label} → {changes.current_season_label} | {changes.rank_label}",
        *_history_source_lines(changes),
    ]
    sections = (
        ("胜率上升最多", "win_rate_delta", changes.win_rate_up),
        ("胜率下降最多", "win_rate_delta", changes.win_rate_down),
        ("选取率上升最多", "pick_rate_delta", changes.pick_rate_up),
        ("选取率下降最多", "pick_rate_delta", changes.pick_rate_down),
        ("Ban率上升最多", "ban_rate_delta", changes.ban_rate_up),
        ("Ban率下降最多", "ban_rate_delta", changes.ban_rate_down),
    )
    for title, metric, items in sections:
        lines.extend(("", title))
        if not items:
            lines.append("暂无可比较数据")
            continue
        lines.extend(_delta_line(index, item, metric) for index, item in enumerate(items, 1))
    return "\n".join(lines)


def _insight_title(insights: HeroMetaInsights) -> str:
    return {
        "black_horse": "版本黑马",
        "cold_strong": "冷门强者",
        "hot_trap": "热门低胜率英雄",
    }.get(insights.insight_type, "历史洞察")


def format_meta_insights(insights: HeroMetaInsights) -> str:
    """Format a rule-bearing insight board."""

    context = insights.season_label
    if insights.previous_season_label:
        context = f"{insights.previous_season_label} → {context}"
    lines = [f"{_insight_title(insights)} | {context} | {insights.rank_label}", *_history_source_lines(insights)]
    lines.extend(("", f"规则：{insights.rule}"))
    if not insights.items:
        lines.append("暂无满足条件的英雄。")
        return "\n".join(lines)
    lines.extend(("", "结果"))
    for item in insights.items:
        result = item.result
        details = [
            f"胜率 {_percent(result.win_rate)}",
            f"选取率 {_percent(result.pick_rate)}",
            f"Ban率 {_percent(result.ban_rate)}",
            f"场次 {result.matches:,}",
        ]
        if item.win_rate_delta is not None:
            details.append(f"胜率变化 {_delta(item.win_rate_delta)}")
        if item.pick_rate_delta is not None:
            details.append(f"选取率变化 {_delta(item.pick_rate_delta)}")
        lines.append(f"{result.hero_name}  " + " · ".join(details))
    return "\n".join(lines)


def format_rank_monsters(board: RankMonsterBoard) -> str:
    lines = [f"分段怪物 | {board.season_label}", *_history_source_lines(board), "", f"规则：{board.rule}"]
    if not board.segments or not board.items:
        lines.append("暂无满足条件的分段数据。")
        return "\n".join(lines)
    lines.extend(("", "按游戏段位顺序展示"))
    for segment in board.segments:
        lines.extend(("", f"【{segment.rank_label}】"))
        if not segment.items:
            lines.append("暂无符合条件的英雄")
            continue
        for item in segment.items:
            result = item.result
            lines.append(
                f"{result.hero_name}  胜率 {_percent(result.win_rate)} · "
                f"相对全段 {_delta(item.win_rate_delta)} · 场次 {result.matches:,}"
            )
    return "\n".join(lines)


# Friendly aliases for callers that use the ViewModel-oriented names.
format_hero_meta_version_changes = format_meta_version_changes
format_hero_meta_insights = format_meta_insights

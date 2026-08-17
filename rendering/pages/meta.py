"""Meta ViewModel pages."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

try:
    from ...marvel_rivals_bot.meta.models import HeroMetaBoard, HeroMetaOverview, HeroMetaResult
except ImportError:
    from marvel_rivals_bot.meta.models import HeroMetaBoard, HeroMetaOverview, HeroMetaResult

from ..components import empty_state, metric_grid, page_header, page_shell, section_title
from ..formatters import escape_text


def _value(value: Any, fallback: str = "—") -> str:
    return escape_text(fallback if value is None else value)


def _percent(value: float | None) -> str:
    return "—" if value is None else escape_text(f"{value:.1f}%")


def _count(value: int | None) -> str:
    return "—" if value is None else escape_text(f"{value:,}")


def _source_line(model: Any) -> str:
    timestamp = model.source_timestamp
    if isinstance(timestamp, datetime):
        timestamp = timestamp.astimezone().strftime("%Y-%m-%d %H:%M")
    elif timestamp is None:
        timestamp = "—"
    stale = "是" if model.stale else "否"
    stale_notice = '<span>当前上游暂不可用，展示最近缓存数据</span>' if model.stale else ''
    return (
        '<div class="mr-meta-source">'
        f'<span>数据来源：{_value(model.source)}</span>'
        f'<span>上游时间：{_value(timestamp)}</span>'
        f'<span>Stale：{_value(stale)}</span>'
        f'{stale_notice}'
        '</div>'
    )


def _hero_row(index: int, result: HeroMetaResult, metric: str) -> str:
    if metric == "win_rate":
        value = _percent(result.win_rate)
        detail = f"场次 {_count(result.matches)} · 胜场 {_count(result.wins)}"
    elif metric == "pick_rate":
        value = _percent(result.pick_rate)
        detail = f"场次 {_count(result.matches)}"
    elif metric == "ban_rate":
        value = _percent(result.ban_rate)
        detail = f"Ban {_count(result.bans)}"
    else:
        value = _count(result.matches)
        detail = f"胜率 {_percent(result.win_rate)} · Ban率 {_percent(result.ban_rate)}"
    return (
        '<article class="mr-meta-row">'
        f'<span class="mr-meta-row__index">{_value(f"{index:02d}")}</span>'
        '<div class="mr-meta-row__body">'
        f'<strong class="mr-meta-row__title">{_value(result.hero_name)}</strong>'
        f'<span class="mr-meta-row__detail">{escape_text(detail)}</span>'
        '</div>'
        f'<strong class="mr-meta-row__value">{value}</strong>'
        '</article>'
    )


def _sort_label(metric: str) -> str:
    return {
        "win_rate": "胜率",
        "pick_rate": "选取率",
        "ban_rate": "Ban率",
        "matches": "场次",
    }.get(metric, metric)


def _metric_section(title: str, metric: str, results: Iterable[HeroMetaResult], kicker: str = "TOP 5") -> str:
    rows = [_hero_row(index, result, metric) for index, result in enumerate(results, 1)]
    body = ''.join(rows) if rows else empty_state("暂无该指标数据")
    return (
        '<section class="mr-section mr-meta-section">'
        + section_title(title, kicker)
        + f'<div class="mr-meta-list">{body}</div>'
        + '</section>'
    )


def _header_meta(model: Any) -> list[tuple[str, str]]:
    return [("段位", model.rank_label), ("来源", model.source)]


def build_meta_overview_html(overview: HeroMetaOverview) -> str:
    content = (
        page_header(
            "CURRENT META",
            "全局英雄环境总览",
            overview.season_label,
            title_cn="当前英雄环境",
            eyebrow="MR // META",
            meta_items=_header_meta(overview),
        )
        + _source_line(overview)
        + _metric_section("胜率 TOP5", "win_rate", overview.win_rate)
        + _metric_section("选取率 TOP5", "pick_rate", overview.pick_rate)
        + _metric_section("Ban率 TOP5", "ban_rate", overview.ban_rate)
        + _metric_section("场次 TOP5", "matches", overview.matches)
    )
    return page_shell(content, watermark="CURRENT META")


def build_meta_board_html(board: HeroMetaBoard) -> str:
    content = (
        page_header(
            "HERO RANKING",
            "英雄排行",
            board.season_label,
            title_cn="英雄排行",
            eyebrow="MR // META",
            meta_items=[("段位", board.rank_label), ("指标", _sort_label(board.sort_by))],
        )
        + _source_line(board)
        + _metric_section(f"英雄排行 · {_sort_label(board.sort_by)}", board.sort_by, board.heroes, "RANKING")
    )
    return page_shell(content, watermark="HERO RANKING")


def build_meta_single_html(board: HeroMetaBoard) -> str:
    result = board.heroes[0] if board.heroes else None
    title = result.hero_name if result else "英雄统计"
    metrics = (
        metric_grid((
            ("胜率", _percent(result.win_rate)),
            ("选取率", _percent(result.pick_rate)),
            ("Ban率", _percent(result.ban_rate)),
            ("样本场次", _count(result.matches)),
        ))
        if result
        else empty_state("暂无该英雄环境数据")
    )
    sample = (
        '<section class="mr-section mr-meta-section">'
        + section_title("样本明细", "SAMPLE DETAIL")
        + f'<div class="mr-meta-source"><span>胜场：{_count(result.wins)}</span>'
        f'<span>胜率样本：{_count(result.wr_matches)}</span>'
        f'<span>Ban 次数：{_count(result.bans)}</span></div>'
        + '</section>'
        if result
        else ""
    )
    content = (
        page_header(
            "HERO META",
            "英雄统计",
            board.season_label,
            title_cn=title,
            eyebrow="MR // META",
            meta_items=[("段位", board.rank_label), ("来源", board.source)],
        )
        + _source_line(board)
        + '<section class="mr-section mr-meta-section">'
        + section_title("英雄统计", "HERO META")
        + metrics
        + '</section>'
        + sample
    )
    return page_shell(content, watermark="HERO META")

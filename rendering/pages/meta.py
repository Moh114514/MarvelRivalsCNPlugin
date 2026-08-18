"""Meta ViewModel pages."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

try:
    from ...marvel_rivals_bot.meta.models import (
        HeroMetaBoard,
        HeroMetaComparison,
        HeroMetaOverview,
        HeroMetaResult,
        HeroMetaSegments,
        HeroMetaInsights,
        HeroMetaVersionChanges,
        HeroRankSeries,
        RankMonsterBoard,
    )
except ImportError:
    from marvel_rivals_bot.meta.models import (
        HeroMetaBoard,
        HeroMetaComparison,
        HeroMetaOverview,
        HeroMetaResult,
        HeroMetaSegments,
        HeroMetaInsights,
        HeroMetaVersionChanges,
        HeroRankSeries,
        RankMonsterBoard,
    )

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
        + f'<div class="mr-meta-list mr-meta-list--ranked">{body}</div>'
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


def _segment_row(index: int, segment: Any) -> str:
    result = segment.result
    if result is None:
        return (
            '<article class="mr-meta-row mr-meta-row--empty">'
            f'<span class="mr-meta-row__index">{_value(f"{index:02d}")}</span>'
            '<div class="mr-meta-row__body">'
            f'<strong class="mr-meta-row__title">{_value(segment.rank_label)}</strong>'
            '<span class="mr-meta-row__detail">暂无该段位数据</span>'
            '</div><strong class="mr-meta-row__value">—</strong></article>'
        )
    detail = (
        f'胜率 {_percent(result.win_rate)} · '
        f'选取率 {_percent(result.pick_rate)} · '
        f'Ban率 {_percent(result.ban_rate)}'
    )
    return (
        '<article class="mr-meta-row">'
        f'<span class="mr-meta-row__index">{_value(f"{index:02d}")}</span>'
        '<div class="mr-meta-row__body">'
        f'<strong class="mr-meta-row__title">{_value(segment.rank_label)}</strong>'
        f'<span class="mr-meta-row__detail">{escape_text(detail)} · 场次 {_count(result.matches)}</span>'
        '</div>'
        f'<strong class="mr-meta-row__value">{_percent(result.win_rate)}</strong>'
        '</article>'
    )


def build_meta_segments_html(segments: HeroMetaSegments) -> str:
    rows = ''.join(
        _segment_row(index, segment)
        for index, segment in enumerate(segments.segments, 1)
    ) or empty_state("暂无该英雄分段数据")
    content = (
        page_header(
            "HERO BREAKDOWN",
            "英雄分段",
            segments.season_label,
            title_cn=segments.hero_name,
            eyebrow="MR // META",
            meta_items=[("范围", "九段位"), ("来源", segments.source)],
        )
        + _source_line(segments)
        + '<section class="mr-section mr-meta-section">'
        + section_title("段位环境", "RANK BREAKDOWN")
        + f'<div class="mr-meta-list mr-meta-list--rank-breakdown">{rows}</div>'
        + '</section>'
    )
    return page_shell(content, watermark="HERO BREAKDOWN")


def _comparison_metric(label: str, left: str, right: str) -> str:
    return (
        '<div class="mr-comparison__row">'
        f'<strong class="mr-comparison__value mr-comparison__value--left">{_value(left)}</strong>'
        f'<span class="mr-comparison__label">{_value(label)}</span>'
        f'<strong class="mr-comparison__value mr-comparison__value--right">{_value(right)}</strong>'
        '</div>'
    )


def build_meta_comparison_html(comparison: HeroMetaComparison) -> str:
    left, right = comparison.left, comparison.right
    body = (
        '<div class="mr-comparison">'
        '<div class="mr-comparison__heads">'
        '<div class="mr-comparison__hero mr-comparison__hero--left">'
        '<span class="mr-comparison__tag">A</span>'
        f'<strong>{_value(left.hero_name)}</strong>'
        '</div>'
        '<div class="mr-comparison__vs">VS</div>'
        '<div class="mr-comparison__hero mr-comparison__hero--right">'
        '<span class="mr-comparison__tag">B</span>'
        f'<strong>{_value(right.hero_name)}</strong>'
        '</div>'
        '</div>'
        '<div class="mr-comparison__metrics">'
        + _comparison_metric("胜率", _percent(left.win_rate), _percent(right.win_rate))
        + _comparison_metric("选取率", _percent(left.pick_rate), _percent(right.pick_rate))
        + _comparison_metric("Ban率", _percent(left.ban_rate), _percent(right.ban_rate))
        + _comparison_metric("场次", _count(left.matches), _count(right.matches))
        + '</div></div>'
    )
    content = (
        page_header(
            "HERO COMPARISON",
            "英雄对比",
            comparison.season_label,
            title_cn=f"{left.hero_name} VS {right.hero_name}",
            eyebrow="MR // META",
            meta_items=[("段位", comparison.rank_label), ("来源", comparison.source)],
        )
        + _source_line(comparison)
        + '<section class="mr-section mr-meta-section">'
        + section_title("数据对比", "COMPARISON")
        + body
        + '</section>'
    )
    return page_shell(content, watermark="HERO COMPARISON")


def _delta(value: float | None) -> str:
    return "—" if value is None else f"{value:+.2f}pp"


def _trend_delta(value: float | None) -> str:
    if value is None:
        return "基准"
    if value > 0:
        return f"▲ {value:+.2f}pp"
    if value < 0:
        return f"▼ {value:+.2f}pp"
    return "→ 0.00pp"


def build_meta_trend_html(series: HeroRankSeries) -> str:
    rows = []
    for point in series.points:
        result = point.result
        if result is None:
            rows.append(
                '<article class="mr-meta-row mr-meta-row--trend mr-meta-row--empty">'
                '<div class="mr-meta-row__body">'
                f'<strong class="mr-meta-row__title">{_value(point.season_label)}</strong>'
                '<span class="mr-meta-row__detail">暂无该赛季数据</span>'
                '</div></article>'
            )
            continue
        def metric(label: str, value: str, delta: float | None) -> str:
            return (
                '<div class="mr-trend-metric">'
                f'<span class="mr-trend-metric__label">{_value(label)}</span>'
                f'<strong class="mr-trend-metric__value">{_value(value)}</strong>'
                f'<span class="mr-trend-metric__delta">{_value(_trend_delta(delta))}</span>'
                '</div>'
            )

        rows.append(
            '<article class="mr-meta-row mr-meta-row--trend">'
            '<div class="mr-meta-row__body">'
            f'<strong class="mr-meta-row__title">{_value(point.season_label)}</strong>'
            '<span class="mr-meta-row__detail">相对上一赛季的指标变化</span>'
            '</div>'
            '<div class="mr-trend-metrics">'
            + metric("胜率", _percent(result.win_rate), point.win_rate_delta)
            + metric("选取率", _percent(result.pick_rate), point.pick_rate_delta)
            + metric("Ban率", _percent(result.ban_rate), point.ban_rate_delta)
            + metric("样本场次", _count(result.matches), None)
            + '</div></article>'
        )
    content = (
        page_header(
            "HERO TREND",
            "英雄趋势",
            " · ".join(point.season_label for point in series.points),
            title_cn=series.hero_name,
            eyebrow="MR // HISTORY",
            meta_items=[("段位", series.rank_label), ("来源", series.source)],
        )
        + _source_line(series)
        + '<section class="mr-section mr-meta-section">'
        + section_title("赛季变化", "SEASON SERIES")
        + f'<div class="mr-meta-list mr-meta-list--trend">{"".join(rows) or empty_state("暂无历史趋势数据")}</div>'
        + '</section>'
    )
    return page_shell(content, watermark="HERO TREND")


def _delta_row(index: int, item: Any, metric: str) -> str:
    delta = getattr(item, metric)
    current_metric = metric.removesuffix("_delta")
    detail = f"当前 {_percent(getattr(item.current, current_metric))} · 场次 {_count(item.current.matches)}"
    return (
        '<article class="mr-meta-row">'
        f'<span class="mr-meta-row__index">{_value(f"{index:02d}")}</span>'
        '<div class="mr-meta-row__body">'
        f'<strong class="mr-meta-row__title">{_value(item.hero_name)}</strong>'
        f'<span class="mr-meta-row__detail">{escape_text(detail)}</span>'
        '</div>'
        f'<strong class="mr-meta-row__value">{_value(_delta(delta))}</strong>'
        '</article>'
    )


def build_meta_version_changes_html(changes: HeroMetaVersionChanges) -> str:
    sections = (
        ("胜率上升最多", "win_rate_delta", changes.win_rate_up),
        ("胜率下降最多", "win_rate_delta", changes.win_rate_down),
        ("选取率上升最多", "pick_rate_delta", changes.pick_rate_up),
        ("选取率下降最多", "pick_rate_delta", changes.pick_rate_down),
        ("Ban率上升最多", "ban_rate_delta", changes.ban_rate_up),
        ("Ban率下降最多", "ban_rate_delta", changes.ban_rate_down),
    )
    body = []
    for title, metric, items in sections:
        rows = ''.join(_delta_row(index, item, metric) for index, item in enumerate(items, 1))
        body.append(
            '<section class="mr-section mr-meta-section">'
            + section_title(title, "SEASON DELTA")
            + f'<div class="mr-meta-list mr-meta-list--ranked">{rows or empty_state("暂无可比较数据")}</div>'
            + '</section>'
        )
    content = (
        page_header(
            "SEASON DELTA",
            "版本变化",
            f"{changes.previous_season_label} → {changes.current_season_label}",
            title_cn="按赛季快照比较",
            eyebrow="MR // HISTORY",
            meta_items=[("段位", changes.rank_label), ("来源", changes.source)],
        )
        + _source_line(changes)
        + ''.join(body)
    )
    return page_shell(content, watermark="SEASON DELTA")


def build_meta_insights_html(insights: HeroMetaInsights) -> str:
    title = {
        "black_horse": "版本黑马",
        "cold_strong": "冷门强者",
        "hot_trap": "热门低胜率英雄",
    }.get(insights.insight_type, "历史洞察")
    rows = []
    for item in insights.items:
        result = item.result
        details = f"胜率 {_percent(result.win_rate)} · 选取率 {_percent(result.pick_rate)} · 场次 {_count(result.matches)}"
        if insights.insight_type == "cold_strong":
            details += f" · Ban率 {_percent(result.ban_rate)}"
        if item.win_rate_delta is not None:
            details += f" · 胜率变化 {_delta(item.win_rate_delta)}"
        rows.append(
            '<article class="mr-meta-row mr-meta-row--unranked">'
            '<div class="mr-meta-row__body">'
            f'<strong class="mr-meta-row__title">{_value(result.hero_name)}</strong>'
            f'<span class="mr-meta-row__detail">{escape_text(details)}</span>'
            '</div>'
            f'<strong class="mr-meta-row__value">{_value(_delta(item.win_rate_delta) if item.win_rate_delta is not None else _percent(result.win_rate))}</strong>'
            '</article>'
        )
    context = insights.season_label
    if insights.previous_season_label:
        context = f"{insights.previous_season_label} → {context}"
    content = (
        page_header(
            "META INSIGHT",
            title,
            context,
            title_cn=title,
            eyebrow="MR // HISTORY",
            meta_items=[("段位", insights.rank_label), ("来源", insights.source)],
        )
        + _source_line(insights)
        + '<section class="mr-section mr-meta-section">'
        + section_title("筛选结果", "TRANSPARENT RULE")
        + f'<div class="mr-help-note">{escape_text(insights.rule)}</div>'
        + f'<div class="mr-meta-list mr-meta-list--unranked">{"".join(rows) or empty_state("暂无满足条件的英雄")}</div>'
        + '</section>'
    )
    return page_shell(content, watermark="META INSIGHT")


def build_rank_monsters_html(board: RankMonsterBoard) -> str:
    sections = []
    for segment in board.segments:
        rows = []
        for item in segment.items:
            result = item.result
            rows.append(
                '<article class="mr-meta-row mr-meta-row--unranked">'
                '<div class="mr-meta-row__body">'
                f'<strong class="mr-meta-row__title">{_value(result.hero_name)}</strong>'
                f'<span class="mr-meta-row__detail">胜率 {_percent(result.win_rate)} · 场次 {_count(result.matches)}</span>'
                '</div>'
                f'<strong class="mr-meta-row__value">{_value(_delta(item.win_rate_delta))}</strong>'
                '</article>'
            )
        sections.append(
            '<section class="mr-rank-segment">'
            f'<h3 class="mr-rank-segment__title">{_value(segment.rank_label)}</h3>'
            f'<div class="mr-meta-list mr-meta-list--unranked">{"".join(rows) or empty_state("暂无符合条件的英雄")}</div>'
            '</section>'
        )
    content = (
        page_header(
            "RANK SPECIALIST",
            "分段怪物",
            board.season_label,
            title_cn="分段专项表现",
            eyebrow="MR // HISTORY",
            meta_items=[("范围", "九段位"), ("来源", board.source)],
        )
        + _source_line(board)
        + '<section class="mr-section mr-meta-section">'
        + section_title("分段专项表现", "RANK SPECIALIST")
        + f'<div class="mr-help-note">{escape_text(board.rule)}</div>'
        + f'<div class="mr-rank-segments">{"".join(sections) or empty_state("暂无满足条件的分段数据")}</div>'
        + '</section>'
    )
    return page_shell(content, watermark="RANK SPECIALIST")

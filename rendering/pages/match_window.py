"""Image pages for generic time-window match reports."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

try:
    from ...marvel_rivals_bot.game_metadata import format_match_map, format_queue
    from ...marvel_rivals_bot.models import MatchRecord, MatchWindowReport, WindowStats
    from ...marvel_rivals_bot.reference.dates import GAME_TZ
    from ...marvel_rivals_bot.reference.heroes import get_hero_name
except ImportError:
    from marvel_rivals_bot.game_metadata import format_match_map, format_queue
    from marvel_rivals_bot.models import MatchRecord, MatchWindowReport, WindowStats
    from marvel_rivals_bot.reference.dates import GAME_TZ
    from marvel_rivals_bot.reference.heroes import get_hero_name

from ..components import empty_state, match_row, metric_grid, page_header, page_shell, section_title
from ..formatters import escape_text


MAX_MATCHES_PER_IMAGE = 25


def _number(value, fallback: str = "—") -> str:
    if value is None:
        return fallback
    if isinstance(value, float) and not value.is_integer():
        return f"{value:,.1f}"
    try:
        return f"{int(value):,}"
    except (TypeError, ValueError):
        return escape_text(value, fallback)


def _percent(value: float | None) -> str:
    return f"{value:.1f}%" if value is not None else "—"


def _duration(seconds: float | int | None) -> str:
    if seconds is None:
        return "—"
    minutes, remain = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes:02d}m" if hours else f"{minutes}m {remain:02d}s"


def _timestamp(value: int | None) -> str:
    if value is None:
        return "未知时间"
    try:
        return datetime.fromtimestamp(int(value), GAME_TZ).strftime("%m-%d %H:%M")
    except (TypeError, ValueError, OSError, OverflowError):
        return "未知时间"


def _mode_row(title: str, stats: WindowStats) -> str:
    return (
        '<article class="mr-window-mode-row">'
        f'<div class="mr-window-mode-row__title">{escape_text(title)}</div>'
        f'<div class="mr-window-mode-row__value">{_number(stats.matches)} 场</div>'
        f'<div class="mr-window-mode-row__detail">{_number(stats.wins)} 胜 · '
        f'{_number(stats.losses)} 负 · {_percent(stats.win_rate)}</div>'
        '</article>'
    )


def _hero_name(hero_id: str | None) -> str:
    if not hero_id:
        return "未知英雄"
    name = get_hero_name(hero_id)
    return f"未知英雄（{hero_id}）" if name == f"英雄 {hero_id}" else name


def _match_rows(matches: Iterable[MatchRecord], start_index: int = 1) -> str:
    rows = []
    for index, match in enumerate(matches, start_index):
        player = match.player
        result, result_class = (
            ("胜利", "win") if player.is_win is True
            else ("失败", "loss") if player.is_win is False
            else ("未知", "unknown")
        )
        rows.append(match_row(
            index=index,
            result=result,
            result_class=result_class,
            hero=_hero_name(player.hero_id),
            timestamp=_timestamp(match.timestamp),
            map_name=format_match_map(match.map_id),
            queue=format_queue(match.game_mode_id, match.play_mode_id),
            duration=_duration(match.duration_seconds),
            kda="/".join(_number(value) for value in (player.kills, player.deaths, player.assists)),
        ))
    return "".join(rows)


def _overview(report: MatchWindowReport) -> str:
    total = report.total
    metrics = metric_grid((
        ("总场次", f"{total.matches} 场"),
        ("战绩", f"{total.wins} 胜 {total.losses} 负"),
        ("胜率", _percent(total.win_rate)),
        ("游戏时间", _duration(total.play_time_seconds)),
        ("K / D / A", total.kda),
        ("场均击败", _number(total.average_kills)),
        ("场均死亡", _number(total.average_deaths)),
        ("场均助攻", _number(total.average_assists)),
        ("总伤害", _number(total.hero_damage, "数据不完整")),
        ("总治疗", _number(total.healing, "数据不完整")),
        ("总承伤", _number(total.damage_taken, "数据不完整")),
        ("场均伤害", _number(total.average_hero_damage, "数据不完整")),
        ("场均治疗", _number(total.average_healing, "数据不完整")),
        ("场均承伤", _number(total.average_damage_taken, "数据不完整")),
    ))
    modes = (
        '<section class="mr-section">'
        + section_title("模式表现", "MODE BREAKDOWN")
        + '<div class="mr-window-mode-list">'
        + _mode_row("快速比赛", report.quick)
        + _mode_row("竞技比赛", report.competitive)
        + _mode_row("其他模式", report.other)
        + '</div></section>'
    )
    incomplete = total.incomplete_metrics
    note = (
        '<p class="mr-window-note">部分对局缺少'
        + escape_text("、".join(incomplete))
        + '统计，相关场均值按已返回对局计算。</p>'
        if incomplete else ""
    )
    heroes = []
    for index, hero in enumerate(report.heroes[:5], 1):
        usage = hero.matches * 100 / report.total.matches if report.total.matches else None
        heroes.append(
            '<article class="mr-window-hero-row">'
            f'<span class="mr-window-hero-row__index">{index:02d}</span>'
            '<div class="mr-window-hero-row__body">'
            f'<div class="mr-window-hero-row__title">{escape_text(hero.hero_name)}</div>'
            f'<div class="mr-window-hero-row__meta">{_number(hero.matches)} 场 · '
            f'{_number(hero.wins)} 胜 · 胜率 {_percent(hero.win_rate)} · 使用 {_percent(usage)}</div>'
            f'<div class="mr-window-hero-row__meta">KDA {escape_text(hero.kda)} · '
            f'游玩 {_duration(hero.play_time_seconds)}</div>'
            '</div></article>'
        )
    hero_body = "".join(heroes) if heroes else empty_state("暂无英雄记录")
    hero_section = (
        '<section class="mr-section">'
        + section_title("英雄表现", "HERO BREAKDOWN")
        + f'<div class="mr-window-hero-list">{hero_body}</div></section>'
    )
    return metrics + modes + note + hero_section


def build_match_window_html(
    report: MatchWindowReport,
    *,
    matches: Iterable[MatchRecord] | None = None,
    start_index: int = 1,
    page_number: int = 1,
    total_pages: int = 1,
) -> str:
    """Build one page; later pages omit repeated aggregate sections."""

    selected = list(matches if matches is not None else report.matches)
    title = f"{report.window.label} · 对局 {start_index}-{start_index + len(selected) - 1}" if selected else report.window.label
    header = page_header(
        "MATCH REVIEW",
        f"UID {report.uid} · {report.window.label}",
        "TIME WINDOW",
        title_cn=report.player_name,
        meta_items=(("UID", report.uid), ("范围", report.window.label)),
    )
    content = header
    if page_number == 1:
        content += _overview(report)
    content += (
        '<section class="mr-section">'
        + section_title(title, f"MATCH LIST {page_number}/{total_pages}")
        + f'<div class="mr-match-list">{_match_rows(selected, start_index) if selected else empty_state("暂无对局记录")}</div>'
        + '</section>'
    )
    return page_shell(content, watermark="MATCH REVIEW")


def build_match_window_pages(
    report: MatchWindowReport,
    *,
    max_matches_per_image: int = MAX_MATCHES_PER_IMAGE,
) -> list[str]:
    page_size = max(1, int(max_matches_per_image))
    if not report.matches:
        return [build_match_window_html(report, matches=[])]
    chunks = [
        report.matches[index:index + page_size]
        for index in range(0, len(report.matches), page_size)
    ]
    return [
        build_match_window_html(
            report,
            matches=chunk,
            start_index=index * page_size + 1,
            page_number=index + 1,
            total_pages=len(chunks),
        )
        for index, chunk in enumerate(chunks)
    ]


__all__ = ["MAX_MATCHES_PER_IMAGE", "build_match_window_html", "build_match_window_pages"]

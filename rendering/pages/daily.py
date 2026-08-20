"""Daily aggregated match report page."""

from __future__ import annotations

from typing import Any

try:
    from ...marvel_rivals_bot.models import DailyModeStats, DailyReport
    from ...marvel_rivals_bot.reference.seasons import format_season_name
except ImportError:
    from marvel_rivals_bot.models import DailyModeStats, DailyReport
    from marvel_rivals_bot.reference.seasons import format_season_name

from ..components import empty_state, metric_grid, page_header, page_shell, section_title
from ..formatters import escape_text


def _number(value: Any, fallback: str = "—") -> str:
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


def _mode_row(title: str, stats: DailyModeStats) -> str:
    return (
        '<article class="mr-daily-mode-row">'
        f'<div class="mr-daily-mode-row__title">{escape_text(title)}</div>'
        f'<div class="mr-daily-mode-row__value">{_number(stats.matches)} 场</div>'
        f'<div class="mr-daily-mode-row__detail">{_number(stats.wins)} 胜 · {_number(stats.losses)} 负 · {_percent(stats.win_rate)}</div>'
        '</article>'
    )


def _hero_row(index: int, hero, total_matches: int) -> str:
    usage = hero.matches * 100 / total_matches if total_matches else None
    summary = (
        f"{_number(hero.matches)} 场 · {_number(hero.wins)} 胜 {_number(hero.losses)} 负 · "
        f"胜率 {_percent(hero.win_rate)} · 使用 {_percent(usage)}"
    )
    return (
        '<article class="mr-daily-hero-row">'
        f'<span class="mr-daily-hero-row__index">{index:02d}</span>'
        '<div class="mr-daily-hero-row__body">'
        f'<div class="mr-daily-hero-row__title">{escape_text(hero.hero_name)}</div>'
        f'<div class="mr-daily-hero-row__meta">{escape_text(summary)}</div>'
        f'<div class="mr-daily-hero-row__meta">游玩 {_duration(hero.play_time_seconds)}</div>'
        '</div>'
        '</article>'
    )


def build_daily_report_html(report: DailyReport) -> str:
    """Build a report from the stable DailyReport view model only."""

    season_name = format_season_name(report.season) if str(report.season).isdigit() else str(report.season)
    date_text = f"{report.date.year:04d}.{report.date.month:02d}.{report.date.day:02d}"
    header = page_header(
        "DAILY REPORT",
        f"UID {report.uid}",
        season_name,
        title_cn=report.player_name,
        meta_items=(("UID", report.uid), ("日期", date_text)),
    )
    metrics = metric_grid((
        ("总场次", f"{report.total.matches} 场"),
        ("战绩", f"{report.total.wins} 胜 {report.total.losses} 负"),
        ("胜率", _percent(report.total.win_rate)),
        ("游戏时间", _duration(report.total.play_time_seconds)),
    ))

    mode_rows = [_mode_row("快速比赛", report.quick), _mode_row("竞技比赛", report.competitive)]
    if report.other.matches:
        mode_rows.append(_mode_row("其他模式", report.other))
    modes = (
        '<section class="mr-section">'
        + section_title("模式表现", "MODE BREAKDOWN")
        + '<div class="mr-daily-mode-list">'
        + "".join(mode_rows)
        + "</div></section>"
    )

    total = report.total
    combat = metric_grid((
        ("K / D / A", total.kda),
        ("场均击败", _number(total.average_kills)),
        ("场均死亡", _number(total.average_deaths)),
        ("场均助攻", _number(total.average_assists)),
        ("场均英雄伤害", _number(total.average_hero_damage, "数据不完整")),
        ("场均治疗", _number(total.average_healing, "数据不完整")),
        ("场均承伤", _number(total.average_damage_taken, "数据不完整")),
    ))
    incomplete = total.incomplete_metrics
    note = (
        '<p class="mr-daily-note">部分对局缺少' + escape_text("、".join(incomplete)) + '统计，相关场均值按已返回对局计算。</p>'
        if incomplete else ""
    )
    combat_section = (
        '<section class="mr-section">'
        + section_title("战斗表现", "COMBAT")
        + combat
        + note
        + '</section>'
    )

    hero_content = (
        "".join(_hero_row(index, hero, total.matches) for index, hero in enumerate(report.heroes[:5], 1))
        if report.heroes else empty_state("当日暂无英雄记录")
    )
    hero_section = (
        '<section class="mr-section">'
        + section_title("今日英雄", "TOP 5 HEROES")
        + '<div class="mr-daily-hero-list">'
        + hero_content
        + '</div></section>'
    )
    empty = empty_state("当日暂无对局") if not report.matches else ""
    return page_shell(header + metrics + empty + modes + combat_section + hero_section, watermark="DAILY REPORT")


__all__ = ["build_daily_report_html"]

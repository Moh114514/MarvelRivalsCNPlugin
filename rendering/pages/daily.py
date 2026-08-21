"""Daily aggregated match report page."""

from __future__ import annotations

from typing import Any

try:
    from ...marvel_rivals_bot.models import MatchWindowReport, RoleWindowStats, WindowStats, ROLE_ORDER
    from ...marvel_rivals_bot.reference.seasons import format_season_name
    from ...marvel_rivals_bot.reference.heroes import HERO_ROLE_LABELS
except ImportError:
    from marvel_rivals_bot.models import MatchWindowReport, RoleWindowStats, WindowStats, ROLE_ORDER
    from marvel_rivals_bot.reference.seasons import format_season_name
    from marvel_rivals_bot.reference.heroes import HERO_ROLE_LABELS

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


def _mode_row(title: str, stats: WindowStats) -> str:
    return (
        '<article class="mr-daily-mode-row">'
        f'<div class="mr-daily-mode-row__title">{escape_text(title)}</div>'
        f'<div class="mr-daily-mode-row__value">{_number(stats.matches)} 场</div>'
        f'<div class="mr-daily-mode-row__detail">{_number(stats.wins)} 胜 · {_number(stats.losses)} 负 · {_percent(stats.win_rate)}</div>'
        '</article>'
    )


def _role_row(label: str, stats: RoleWindowStats) -> str:
    if not stats.matches:
        return (
            '<article class="mr-window-role-row mr-window-role-row--empty">'
            f'<div class="mr-window-role-row__title">{escape_text(label)}</div>'
            '<div class="mr-window-role-row__empty">0 场 · 暂无该职责对局</div>'
            '</article>'
        )
    if stats.per10_available:
        metrics = metric_grid((
            ("K / D / A", stats.kda),
            ("每10分钟击败", _number(stats.per10_kills)),
            ("每10分钟死亡", _number(stats.per10_deaths)),
            ("每10分钟助攻", _number(stats.per10_assists)),
            ("每10分钟伤害", _number(stats.per10_hero_damage, "数据不完整")),
            ("每10分钟治疗", _number(stats.per10_healing, "数据不完整")),
            ("每10分钟承伤", _number(stats.per10_damage_taken, "数据不完整")),
            ("游戏时间", _duration(stats.play_time_seconds)),
        ))
    else:
        metrics = metric_grid((
            ("K / D / A", stats.kda),
            ("场均击败", _number(stats.average_kills)),
            ("场均死亡", _number(stats.average_deaths)),
            ("场均助攻", _number(stats.average_assists)),
            ("场均伤害", _number(stats.average_hero_damage, "数据不完整")),
            ("场均治疗", _number(stats.average_healing, "数据不完整")),
            ("场均承伤", _number(stats.average_damage_taken, "数据不完整")),
            ("游戏时间", "未知"),
        ))
    return (
        '<article class="mr-window-role-row">'
        f'<div class="mr-window-role-row__heading"><div class="mr-window-role-row__title">{escape_text(label)}</div>'
        f'<div class="mr-window-role-row__summary">{_number(stats.matches)} 场 · {_number(stats.wins)} 胜 '
        f'{_number(stats.losses)} 负 · {_percent(stats.win_rate)}</div></div>'
        f'<div class="mr-window-role-row__metrics">{metrics}</div>'
        '</article>'
    )


def _hero_row(index: int, hero, total_matches: int) -> str:
    hero_metric = (
        f'游玩 {_duration(hero.play_time_seconds)} · 每10分钟击败 {_number(hero.per10_kills, "数据不足")} · '
        f'每10分钟伤害 {_number(hero.per10_hero_damage, "数据不足")}'
        if hero.per10_available else
        f'游玩 {_duration(hero.play_time_seconds)} · 场均击败 {_number(hero.average_kills)} · '
        f'场均伤害 {_number(hero.average_hero_damage, "数据不完整")}'
    )
    summary = (
        f"{_number(hero.matches)} 场 · {_number(hero.wins)} 胜 {_number(hero.losses)} 负 · "
        f"胜率 {_percent(hero.win_rate)} · 全局使用 {_percent(hero.usage_rate)} · 职责内使用 {_percent(hero.role_usage_rate)}"
    )
    return (
        '<article class="mr-daily-hero-row">'
        f'<span class="mr-daily-hero-row__index">{index:02d}</span>'
        '<div class="mr-daily-hero-row__body">'
        f'<div class="mr-daily-hero-row__title">{escape_text(hero.hero_name)}</div>'
        f'<div class="mr-daily-hero-row__meta">{escape_text(summary)}</div>'
        f'<div class="mr-daily-hero-row__meta">{hero_metric}</div>'
        '</div>'
        '</article>'
    )


def build_daily_report_html(report: MatchWindowReport) -> str:
    """Compatibility page for a full-day MatchWindowReport."""

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
    incomplete = total.incomplete_metrics
    note = (
        '<p class="mr-daily-note">当前接口未返回完整的玩家 playTime，相关指标按兼容场均口径展示。</p>'
        if report.total.matches and not report.total.per10_available else
        '<p class="mr-daily-note">部分对局缺少' + escape_text("、".join(incomplete)) + '统计，职责每10分钟指标按各职责已返回数据样本和实际使用时长计算。</p>'
        if incomplete else ""
    )
    role_section = (
        '<section class="mr-section">'
        + section_title("职责表现", "ROLE BREAKDOWN")
        + '<div class="mr-window-role-list">'
        + "".join(
            _role_row(HERO_ROLE_LABELS.get(role, role), report.roles.get(role, RoleWindowStats(role=role)))
            for role in ROLE_ORDER
        )
        + '</div>'
        + note
        + '</section>'
    )

    hero_groups = []
    for role in (*ROLE_ORDER, "unknown"):
        heroes = report.heroes_by_role.get(role, [])
        if not heroes:
            continue
        label = HERO_ROLE_LABELS.get(role, "未识别职责")
        hero_groups.append(
            f'<div class="mr-window-hero-group"><h3 class="mr-window-hero-group__title">{escape_text(label)}</h3>'
            + "".join(_hero_row(index, hero, report.roles.get(role, total).matches) for index, hero in enumerate(heroes, 1))
            + '</div>'
        )
    hero_content = "".join(hero_groups) if hero_groups else empty_state("当日暂无英雄记录")
    hero_section = (
        '<section class="mr-section">'
        + section_title("英雄表现（今日英雄）", "HERO PERFORMANCE")
        + '<div class="mr-window-hero-groups">'
        + hero_content
        + '</div></section>'
    )
    empty = empty_state("当日暂无对局") if not report.matches else ""
    return page_shell(header + metrics + empty + modes + role_section + hero_section, watermark="DAILY REPORT")


__all__ = ["build_daily_report_html"]

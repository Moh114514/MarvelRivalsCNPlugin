"""Image pages for generic time-window match reports."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

try:
    from ...marvel_rivals_bot.game_metadata import format_match_map, format_queue
    from ...marvel_rivals_bot.models import MatchRecord, MatchWindowReport, RoleWindowStats, WindowStats, ROLE_ORDER
    from ...marvel_rivals_bot.reference.dates import GAME_TZ
    from ...marvel_rivals_bot.reference.heroes import HERO_ROLE_LABELS, get_hero_name
except ImportError:
    from marvel_rivals_bot.game_metadata import format_match_map, format_queue
    from marvel_rivals_bot.models import MatchRecord, MatchWindowReport, RoleWindowStats, WindowStats, ROLE_ORDER
    from marvel_rivals_bot.reference.dates import GAME_TZ
    from marvel_rivals_bot.reference.heroes import HERO_ROLE_LABELS, get_hero_name

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


def _role_row(label: str, stats: RoleWindowStats) -> str:
    if not stats.matches:
        return (
            '<article class="mr-window-role-row mr-window-role-row--empty">'
            f'<div class="mr-window-role-row__title">{escape_text(label)}</div>'
            '<div class="mr-window-role-row__empty">0 场 · 暂无该职责对局</div>'
            '</article>'
        )
    incomplete = stats.incomplete_metrics
    note = (
        '<div class="mr-window-role-row__note">部分对局缺少'
        + escape_text("、".join(incomplete))
        + '，每10分钟指标按该职责已返回数据样本和实际使用时长计算。</div>'
        if incomplete else ""
    )
    if stats.per10_available:
        metrics = (
            ("K / D / A", stats.kda),
            ("每10分钟击败", _number(stats.per10_kills)),
            ("每10分钟死亡", _number(stats.per10_deaths)),
            ("每10分钟助攻", _number(stats.per10_assists)),
            ("每10分钟伤害", _number(stats.per10_hero_damage, "数据不完整")),
            ("每10分钟治疗", _number(stats.per10_healing, "数据不完整")),
            ("每10分钟承伤", _number(stats.per10_damage_taken, "数据不完整")),
            ("游戏时间", _duration(stats.play_time_seconds)),
        )
    else:
        # Old adapters may not expose player playTime; retain a truthful
        # per-match fallback until the upstream field is available.
        metrics = (
            ("K / D / A", stats.kda),
            ("场均击败", _number(stats.average_kills)),
            ("场均死亡", _number(stats.average_deaths)),
            ("场均助攻", _number(stats.average_assists)),
            ("场均伤害", _number(stats.average_hero_damage, "数据不完整")),
            ("场均治疗", _number(stats.average_healing, "数据不完整")),
            ("场均承伤", _number(stats.average_damage_taken, "数据不完整")),
            ("游戏时间", "未知"),
        )
    metric_rows = "".join(
        f'<div class="mr-window-role-row__metric"><span>{escape_text(title)}</span><strong>{escape_text(value)}</strong></div>'
        for title, value in metrics
    )
    return (
        '<article class="mr-window-role-row">'
        f'<div class="mr-window-role-row__heading"><div class="mr-window-role-row__title">{escape_text(label)}</div>'
        f'<div class="mr-window-role-row__summary">{_number(stats.matches)} 场 · {_number(stats.wins)} 胜 '
        f'{_number(stats.losses)} 负 · {_percent(stats.win_rate)}</div></div>'
        f'<div class="mr-window-role-row__metrics">{metric_rows}</div>'
        f'{note}'
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
        if player.play_time_seconds and player.play_time_seconds > 0:
            kda_values = (player.per10_kills, player.per10_deaths, player.per10_assists)
            kda = "每10分钟 " + "/".join(_number(value) for value in kda_values)
        else:
            kda = "/".join(_number(value) for value in (player.kills, player.deaths, player.assists))
        rows.append(match_row(
            index=index,
            result=result,
            result_class=result_class,
            hero=_hero_name(player.main_hero.hero_id if player.main_hero else player.hero_id)
            + (f"（另使用 {player.hero_switch_count} 名英雄）" if player.hero_switch_count else ""),
            timestamp=_timestamp(match.timestamp),
            map_name=format_match_map(match.map_id),
            queue=format_queue(match.game_mode_id, match.play_mode_id),
            duration=_duration(match.duration_seconds),
            kda=kda,
        ))
    return "".join(rows)


def _overview(report: MatchWindowReport) -> str:
    total = report.total
    if total.per10_available:
        normalized_metrics = (
            ("每10分钟击败", _number(total.per10_kills)),
            ("每10分钟伤害", _number(total.per10_hero_damage, "数据不足")),
            ("每10分钟治疗", _number(total.per10_healing, "数据不足")),
            ("每10分钟承伤", _number(total.per10_damage_taken, "数据不足")),
        )
    else:
        normalized_metrics = (
            ("场均击败", _number(total.average_kills)),
            ("场均伤害", _number(total.average_hero_damage, "数据不完整")),
            ("场均治疗", _number(total.average_healing, "数据不完整")),
            ("场均承伤", _number(total.average_damage_taken, "数据不完整")),
        )
    overview_kda = (
        "/".join(_number(value) for value in (total.per10_kills, total.per10_deaths, total.per10_assists))
        if total.per10_available else total.kda
    )
    metrics = metric_grid((
        ("总场次", f"{total.matches} 场"),
        ("战绩", f"{total.wins} 胜 {total.losses} 负"),
        ("胜率", _percent(total.win_rate)),
        ("游戏时间", _duration(total.play_time_seconds)),
        ("每10分钟 K / D / A" if total.per10_available else "总 K / D / A", overview_kda),
        ("总击败", _number(total.kills)),
        ("总死亡", _number(total.deaths)),
        ("总助攻", _number(total.assists)),
        *normalized_metrics,
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
        '<p class="mr-window-note">当前接口未返回完整的玩家 playTime，相关指标按兼容场均口径展示。</p>'
        if total.matches and not total.per10_available else
        '<p class="mr-window-note">部分对局缺少'
        + escape_text("、".join(incomplete))
        + '统计，职责每10分钟指标按各职责已返回数据样本和实际使用时长计算。</p>'
        if incomplete else ""
    )
    role_rows = "".join(
        _role_row(HERO_ROLE_LABELS.get(role, role), report.roles.get(role, RoleWindowStats(role=role)))
        for role in ROLE_ORDER
    )
    role_section = (
        '<section class="mr-section">'
        + section_title("职责表现", "ROLE BREAKDOWN")
        + f'<div class="mr-window-role-list">{role_rows}</div></section>'
    )

    hero_groups = []
    for role in (*ROLE_ORDER, "unknown"):
        heroes = report.heroes_by_role.get(role, [])
        if not heroes:
            continue
        label = HERO_ROLE_LABELS.get(role, "未识别职责")
        rows = []
        for index, hero in enumerate(heroes, 1):
            hero_metric = (
                f'游玩 {_duration(hero.play_time_seconds)} · 每10分钟击败 {_number(hero.per10_kills, "数据不足")} · '
                f'每10分钟伤害 {_number(hero.per10_hero_damage, "数据不完整")}'
                if hero.per10_available else
                f'游玩 {_duration(hero.play_time_seconds)} · 场均击败 {_number(hero.average_kills)} · '
                f'场均伤害 {_number(hero.average_hero_damage, "数据不完整")}'
            )
            rows.append(
                '<article class="mr-window-hero-row">'
                f'<span class="mr-window-hero-row__index">{index:02d}</span>'
                '<div class="mr-window-hero-row__body">'
                f'<div class="mr-window-hero-row__title">{escape_text(hero.hero_name)}</div>'
                f'<div class="mr-window-hero-row__meta">{_number(hero.matches)} 场 · '
                f'{_number(hero.wins)} 胜 · 胜率 {_percent(hero.win_rate)} · 全局使用 {_percent(hero.usage_rate)} · '
                f'职责内使用 {_percent(hero.role_usage_rate)}</div>'
                f'<div class="mr-window-hero-row__meta">KDA {escape_text(hero.kda)} · '
                f'{hero_metric}</div>'
                '</div></article>'
            )
        hero_groups.append(
            f'<div class="mr-window-hero-group"><h3 class="mr-window-hero-group__title">{escape_text(label)}</h3>'
            f'<div class="mr-window-hero-list">{"".join(rows)}</div></div>'
        )
    hero_body = "".join(hero_groups) if hero_groups else empty_state("暂无英雄记录")
    hero_section = (
        '<section class="mr-section">'
        + section_title("英雄表现", "HERO PERFORMANCE")
        + f'<div class="mr-window-hero-groups">{hero_body}</div></section>'
    )
    return metrics + modes + note + role_section + hero_section


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

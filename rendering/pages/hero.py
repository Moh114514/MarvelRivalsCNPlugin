"""Hero statistics page."""

from __future__ import annotations

try:
    from ...marvel_rivals_bot.models import HeroQueryResult
    from ...marvel_rivals_bot.reference.heroes import format_hero_name
    from ...marvel_rivals_bot.reference.seasons import format_season_name
except ImportError:
    from marvel_rivals_bot.models import HeroQueryResult
    from marvel_rivals_bot.reference.heroes import format_hero_name
    from marvel_rivals_bot.reference.seasons import format_season_name

from ..components import empty_state, metric_grid, page_header, page_shell, section_title
from ..formatters import extract_career, format_duration, format_number


def _percent(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}%"


def _average(total: int | float | None, matches: int | None) -> float | None:
    if total is None or matches is None or matches <= 0:
        return None
    return total / matches


def _stat_value(value: int | float | None) -> str:
    return format_number({"value": value}, "value")


def _mode_grid(mode, *, prefix: str) -> str:
    matches = mode.matches
    if getattr(mode, "play_time_seconds", None) and mode.play_time_seconds > 0:
        count_metrics = (
            ("每10分钟击败", mode.per10_kills),
            ("每10分钟最后一击", mode.per10_final_hits),
            ("每10分钟死亡", mode.per10_deaths),
            ("每10分钟助攻", mode.per10_assists),
        )
        damage_label, damage = "每10分钟伤害", mode.per10_hero_damage
        heal_label, healing = "每10分钟治疗", mode.per10_heal
        taken_label, taken = "每10分钟承伤", mode.per10_damage_taken
    else:
        count_metrics = (
            ("击败", mode.kills),
            ("最后一击", mode.final_hits),
            ("死亡", mode.deaths),
            ("助攻", mode.assists),
        )
        damage_label, damage = "场均伤害", _average(mode.hero_damage, matches)
        heal_label, healing = "场均治疗", _average(mode.heal, matches)
        taken_label, taken = "场均承伤", _average(mode.damage_taken, matches)
    return metric_grid((
        (f"{prefix}场次", _stat_value(matches)),
        (f"{prefix}胜率", _percent(mode.win_rate)),
        *tuple((label, _stat_value(value)) for label, value in count_metrics),
        (damage_label, _stat_value(damage)),
        (heal_label, _stat_value(healing)),
        (taken_label, _stat_value(taken)),
    ))


def build_hero_query_html(result: HeroQueryResult) -> str:
    hero = extract_career(result)
    role = getattr(result, "role_label", "") or ""
    stats = result.stats if result.stats is not None and hasattr(result.stats, "ranked") else None
    if stats is not None:
        total_matches = stats.total_matches
        total_wins = stats.total_wins
        total_rate = stats.total_win_rate
        if total_rate is None and total_matches and total_wins is not None:
            total_rate = total_wins * 100 / total_matches
        ranked = stats.competitive
        quick = stats.quick
        role = getattr(result, "role_label", "") or getattr(stats, "role_label", "") or ""
        overview = metric_grid((
            ("总计场次", format_number({"value": total_matches}, "value")),
            ("总胜场", _stat_value(total_wins)),
            ("总胜率", _percent(total_rate)),
            ("总时长", format_duration(stats.total.play_time_seconds)),
        ))
        ranked_details = metric_grid((
            ("MVP / SVP", f"{format_number({'value': ranked.mvp}, 'value')}/{format_number({'value': ranked.svp}, 'value')}"),
        ))
        details = (
            '<section class="mr-section">'
            + section_title("竞技", "RANKED DETAILS")
            + ranked_details
            + _mode_grid(ranked, prefix="竞技")
            + '<section class="mr-section__totals">'
            + metric_grid((
                ("总伤害", _stat_value(ranked.hero_damage)),
                ("总治疗", _stat_value(ranked.heal)),
                ("总承伤", _stat_value(ranked.damage_taken)),
            ))
            + '</section>'
            + section_title("快速", "QUICK SUMMARY")
            + _mode_grid(quick, prefix="快速")
            + '</section>'
        )
    else:
        total_matches = hero.get("totalMatchCount")
        total_wins = hero.get("totalMatchWinCount")
        total_rate = total_wins * 100 / total_matches if isinstance(total_matches, (int, float)) and total_matches and isinstance(total_wins, (int, float)) else None
        overview = metric_grid((
            ("比赛", format_number({"value": total_matches}, "value")),
            ("胜场", format_number({"value": total_wins}, "value")),
            ("胜率", _percent(total_rate)),
            ("K / D / A", "/".join(format_number(hero, key) for key in ("k", "d", "a"))),
        ))
        details = (
            '<section class="mr-section">'
            + section_title("核心表现", "CAREER METRICS")
            + metric_grid((
                ("英雄伤害", format_number(hero, "totalHeroDamage")),
                ("治疗", format_number(hero, "totalHeroHeal")),
                ("承受伤害", format_number(hero, "totalDamageTaken")),
                ("MVP / SVP", f"{format_number(hero, 'totalMvpTimes')}/{format_number(hero, 'totalSvpTimes')}"),
            ))
            + '</section>'
        ) if hero else empty_state("暂无该英雄的生涯数据")
    title = format_hero_name(result.hero_id, result.hero_name)
    content = (
        page_header(
            "HERO DATA",
            f"UID {result.uid} · {role or '英雄数据'}",
            format_season_name(result.season),
            title_cn=title,
            meta_items=(("UID", result.uid), ("职责", role or "未知职责")),
        )
        + overview
        + details
    )
    return page_shell(content, watermark="HERO DATA")

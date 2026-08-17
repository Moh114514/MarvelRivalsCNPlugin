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


def build_hero_query_html(result: HeroQueryResult) -> str:
    hero = extract_career(result)
    stats = result.stats if result.stats is not None and hasattr(result.stats, "ranked") else None
    if stats is not None:
        total_matches = stats.total_matches
        total_wins = stats.total_wins
        total_rate = stats.total_win_rate
        if total_rate is None and total_matches and total_wins is not None:
            total_rate = total_wins * 100 / total_matches
        ranked = stats.ranked
        quick = stats.quick
        overview = metric_grid((
            ("总计场次", format_number({"value": total_matches}, "value")),
            ("快速场次", format_number({"value": quick.matches}, "value")),
            ("竞技场次", format_number({"value": ranked.matches}, "value")),
            ("总计胜率", _percent(total_rate)),
        ))
        ranked_details = metric_grid((
            ("竞技胜率", _percent(ranked.win_rate)),
            ("竞技 K / D / A", "/".join(format_number({
                "k": ranked.kills, "d": ranked.deaths, "a": ranked.assists,
            }, key) for key in ("k", "d", "a"))),
            ("英雄伤害", format_number({"value": ranked.hero_damage}, "value")),
            ("治疗 / 承受", f"{format_number({'value': ranked.heal}, 'value')} / {format_number({'value': ranked.damage_taken}, 'value')}"),
            ("MVP / SVP", f"{format_number({'value': ranked.mvp}, 'value')}/{format_number({'value': ranked.svp}, 'value')}"),
            ("竞技时长", format_duration(ranked.play_time_seconds)),
        ))
        quick_details = metric_grid((
            ("快速胜率", _percent(quick.win_rate)),
            ("快速 K / D / A", f"{format_number({'value': quick.kills}, 'value')} / {format_number({'value': quick.deaths}, 'value')} / {format_number({'value': quick.assists}, 'value')}"),
            ("快速时长", format_duration(quick.play_time_seconds)),
        ))
        details = (
            '<section class="mr-section">'
            + section_title("竞技详细数据", "RANKED DETAILS")
            + ranked_details
            + section_title("快速模式摘要", "QUICK SUMMARY")
            + quick_details
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
            f"UID {result.uid} · 英雄 ID {result.hero_id}",
            format_season_name(result.season),
            title_cn=title,
        )
        + overview
        + details
    )
    return page_shell(content, watermark="HERO DATA")

"""Player statistics page."""

from __future__ import annotations

try:
    from ...marvel_rivals_bot.reference.heroes import format_hero_name
    from ...marvel_rivals_bot.models import PlayerStats
    from ...marvel_rivals_bot.reference.seasons import format_season_name
except ImportError:
    from marvel_rivals_bot.reference.heroes import format_hero_name
    from marvel_rivals_bot.models import PlayerStats
    from marvel_rivals_bot.reference.seasons import format_season_name

from ..components import empty_state, hero_row, metric_grid, page_header, page_shell, section_title
from ..formatters import format_duration, format_number


def _percent(value: float | None) -> str:
    return "-" if value is None else f"{value:.1f}%"


def build_player_stats_html(stats: PlayerStats) -> str:
    profile, summary = stats.profile, stats.summary
    ranked_matches = summary.ranked.matches if summary.ranked.matches is not None else summary.matches
    quick_matches = summary.quick.matches
    ranked_rate = summary.ranked.win_rate
    if ranked_rate is None and ranked_matches:
        ranked_wins = summary.ranked.wins if summary.ranked.wins is not None else summary.wins
        if ranked_wins is not None:
            ranked_rate = ranked_wins * 100 / ranked_matches
    ranked_kills = summary.ranked.kills if summary.ranked.kills is not None else summary.kills
    ranked_deaths = summary.ranked.deaths if summary.ranked.deaths is not None else summary.deaths
    ranked_assists = summary.ranked.assists if summary.ranked.assists is not None else summary.assists
    overview = metric_grid((
        ("竞技场次", format_number({"value": ranked_matches}, "value")),
        ("快速场次", format_number({"value": quick_matches}, "value")),
        ("总场次", format_number({"value": summary.matches}, "value")),
        ("竞技胜率", _percent(ranked_rate)),
        ("竞技 K / D / A", f"{format_number({'value': ranked_kills}, 'value')}/{format_number({'value': ranked_deaths}, 'value')}/{format_number({'value': ranked_assists}, 'value')}"),
    ))
    heroes = []
    for index, hero in enumerate(stats.heroes[:10], 1):
        total_matches = getattr(hero, "total_matches", getattr(hero, "matches", None))
        quick = getattr(getattr(hero, "quick", None), "matches", None)
        ranked_scope = getattr(hero, "ranked", None)
        ranked = getattr(ranked_scope, "matches", None)
        ranked_rate = getattr(ranked_scope, "win_rate", None)
        if ranked_scope is None:
            ranked = total_matches
            ranked_rate = getattr(hero, "win_rate", None)
            if ranked_rate is None and ranked and getattr(hero, "wins", None) is not None:
                ranked_rate = hero.wins * 100 / ranked
        heroes.append(hero_row(
            index=index,
            title=format_hero_name(hero.hero_id, hero.hero_name),
            summary=(
                f"总计 {format_number({'value': total_matches}, 'value')} · "
                f"快速 {format_number({'value': quick}, 'value')} · "
                f"竞技 {format_number({'value': ranked}, 'value')}"
            ),
            duration=(
                f"竞技胜率 {_percent(ranked_rate)} · "
                f"总时长 {format_duration(getattr(hero, 'total_play_time_seconds', getattr(hero, 'play_time_seconds', None)))}"
            ),
        ))
    body = f'<div class="mr-hero-list">{"".join(heroes)}</div>' if heroes else empty_state("暂无常用英雄数据")
    rank = profile.rank_game_season or "暂无段位"
    rank_name, rank_score = rank, ""
    if "（" in rank:
        rank_name, rank_score = rank.split("（", 1)
        rank_score = rank_score.rstrip("）")
    meta_items = [("段位", rank_name)]
    if rank_score:
        meta_items.append(("积分", rank_score))
    meta_items.extend((("等级", f"LV.{profile.level}"), ("UID", profile.uid)))
    content = (
        page_header(
            "PLAYER PROFILE",
            "",
            format_season_name(stats.season),
            title_cn=profile.name,
            meta_items=meta_items,
        )
        + overview
        + '<section class="mr-section">'
        + section_title("常用英雄", "TOP HEROES")
        + body
        + '</section>'
    )
    return page_shell(content, watermark="PLAYER PROFILE")

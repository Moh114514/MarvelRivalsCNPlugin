"""Player statistics page."""

from __future__ import annotations

try:
    from ...marvel_rivals_bot.hero_names import format_hero_name
    from ...marvel_rivals_bot.models import PlayerStats
    from ...marvel_rivals_bot.services.rivals import format_season_name
except ImportError:
    from marvel_rivals_bot.hero_names import format_hero_name
    from marvel_rivals_bot.models import PlayerStats
    from marvel_rivals_bot.services.rivals import format_season_name

from ..components import empty_state, hero_row, metric_grid, page_header, page_shell, section_title
from ..formatters import format_duration, format_number


def build_player_stats_html(stats: PlayerStats) -> str:
    profile, summary = stats.profile, stats.summary
    win_rate = summary.win_rate
    if win_rate is None and summary.matches and summary.wins is not None:
        win_rate = summary.wins * 100 / summary.matches
    overview = metric_grid((
        ("场次", format_number({"value": summary.matches}, "value")),
        ("胜场", format_number({"value": summary.wins}, "value")),
        ("胜率", f"{format_number({'value': win_rate}, 'value')}%"),
        ("K / D / A", "/".join(format_number({"value": value}, "value") for value in (summary.kills, summary.deaths, summary.assists))),
    ))
    heroes = []
    for index, hero in enumerate(stats.heroes[:10], 1):
        heroes.append(hero_row(
            index=index,
            title=format_hero_name(hero.hero_id, hero.hero_name),
            summary=(
                f"出场 {format_number({'value': hero.matches}, 'value')} · "
                f"胜场 {format_number({'value': hero.wins}, 'value')} · "
                f"击败 {format_number({'value': hero.kills}, 'value')}"
            ),
            duration=(
                f"胜率 {format_number({'value': hero.win_rate}, 'value')}% · "
                f"时长 {format_duration(hero.play_time_seconds)}"
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

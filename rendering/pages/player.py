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
from ..formatters import escape_text, format_duration, format_number


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
            title=escape_text(format_hero_name(hero.hero_id, hero.hero_name)),
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
    body = f'<section class="hero-list">{"".join(heroes)}</section>' if heroes else empty_state("暂无常用英雄数据")
    rank = profile.rank_game_season or "暂无段位"
    content = page_header(
        escape_text(profile.name),
        f"UID {escape_text(profile.uid)} · 等级 {escape_text(profile.level)} · {escape_text(rank)}",
        escape_text(format_season_name(stats.season)),
    ) + overview + section_title("常用英雄") + body
    return page_shell(content)

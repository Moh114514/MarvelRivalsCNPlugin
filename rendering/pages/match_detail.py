"""Match detail page."""

from __future__ import annotations

try:
    from ...marvel_rivals_bot.game_metadata import format_match_map, format_play_mode, format_queue, get_map_mode
    from ...marvel_rivals_bot.hero_names import format_hero_name
except ImportError:
    from marvel_rivals_bot.game_metadata import format_match_map, format_play_mode, format_queue, get_map_mode
    from marvel_rivals_bot.hero_names import format_hero_name

from ..components import empty_state, metric_grid, page_header, page_shell, player_row, team_panel
from ..formatters import escape_text, extract_first_match, format_duration, format_number, format_timestamp


def build_match_detail_html(payload: dict) -> str:
    match = extract_first_match(payload)
    if not match:
        title, overview, body = "对局详情", "", empty_state("暂无对局数据")
    else:
        title = format_match_map(match.get("matchMapId"))
        mode = get_map_mode(match.get("matchMapId")) or format_play_mode(match.get("playModeId"))
        overview = metric_grid((
            ("队列", format_queue(match.get("gameModeId"), match.get("playModeId"))),
            ("玩法", mode),
            ("时长", format_duration(match.get("matchPlayDuration"))),
            ("胜方阵营", match.get("matchWinnerSide", "-")),
        ))
        players = match.get("matchPlayers", [])
        camps = sorted(
            {player.get("camp") for player in players if isinstance(player, dict) and player.get("camp") is not None},
            key=lambda value: str(value),
        ) if isinstance(players, list) else []
        teams = []
        for camp in camps:
            members = []
            for player in players:
                if not isinstance(player, dict) or player.get("camp") != camp:
                    continue
                members.append(player_row(
                    name=escape_text(player.get("nickName", player.get("playerUid", "-"))),
                    hero=escape_text(format_hero_name(player.get("curHeroId"))),
                    stats="/".join(format_number(player, key) for key in ("k", "d", "a")),
                    extra=(
                        f"伤害 {format_number(player, 'totalHeroDamage')} · "
                        f"治疗 {format_number(player, 'totalHeroHeal')} · "
                        f"承伤 {format_number(player, 'totalDamageTaken')}"
                    ),
                ))
            teams.append(team_panel(escape_text(camp), "".join(members)))
        body = f'<section class="teams">{"".join(teams)}</section>' if teams else empty_state("暂无玩家明细")
    match_uid = match.get("matchUid", "-") if match else "-"
    content = page_header(
        escape_text(title),
        f'{escape_text(format_timestamp(match.get("matchTimeStamp")) if match else "")} · matchUid {escape_text(match_uid)}',
        "对局详情",
    ) + f"{overview}{body}"
    return page_shell(content)

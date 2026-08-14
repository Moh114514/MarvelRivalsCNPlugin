"""Match detail page."""

from __future__ import annotations

try:
    from ...marvel_rivals_bot.game_metadata import format_match_map, format_play_mode, format_queue, get_map_mode
    from ...marvel_rivals_bot.hero_names import format_hero_name
except ImportError:
    from marvel_rivals_bot.game_metadata import format_match_map, format_play_mode, format_queue, get_map_mode
    from marvel_rivals_bot.hero_names import format_hero_name

from ..components import empty_state, metric_grid, page_header, page_shell, player_row, section_title, team_panel
from ..formatters import extract_first_match, format_duration, format_number, format_timestamp


def build_match_detail_html(payload: dict) -> str:
    match = extract_first_match(payload)
    if not match:
        title_cn, overview, body = "暂无对局数据", "", empty_state("暂无对局数据")
    else:
        title_cn = format_match_map(match.get("matchMapId"))
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
        winner_side = match.get("matchWinnerSide")
        teams = []
        for camp in camps:
            members = []
            for player in players:
                if not isinstance(player, dict) or player.get("camp") != camp:
                    continue
                members.append(player_row(
                    name=player.get("nickName", player.get("playerUid", "-")),
                    hero=format_hero_name(player.get("curHeroId")),
                    stats="/".join(format_number(player, key) for key in ("k", "d", "a")),
                    extra=(
                        f"伤害 {format_number(player, 'totalHeroDamage')} · "
                        f"治疗 {format_number(player, 'totalHeroHeal')} · "
                        f"承伤 {format_number(player, 'totalDamageTaken')}"
                    ),
                ))
            teams.append(team_panel(camp, "".join(members), winner_side=winner_side))
        body = (
            '<section class="mr-section">'
            + section_title("对局阵容", "TEAM REPORT")
            + f'<div class="mr-team-list">{"".join(teams)}</div></section>'
        ) if teams else empty_state("暂无玩家明细")
    match_uid = match.get("matchUid", "-") if match else "-"
    subtitle = f'{format_timestamp(match.get("matchTimeStamp")) if match else ""} · matchUid {match_uid}'
    content = page_header("MATCH REPORT", subtitle, "对局详情", title_cn=title_cn) + overview + body
    return page_shell(content, watermark="MATCH REPORT")

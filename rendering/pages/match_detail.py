"""Match detail page."""

from __future__ import annotations

try:
    from ...marvel_rivals_bot.game_metadata import format_match_map, format_play_mode, format_queue, get_map_mode
    from ...marvel_rivals_bot.reference.heroes import format_hero_name
except ImportError:
    from marvel_rivals_bot.game_metadata import format_match_map, format_play_mode, format_queue, get_map_mode
    from marvel_rivals_bot.reference.heroes import format_hero_name

from ..components import empty_state, metric_grid, page_header, page_shell, player_row, section_title, team_panel
from ..formatters import extract_first_match, format_duration, format_number, format_timestamp


def _number_value(value):
    try:
        return float(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _per10(player: dict, *keys: str) -> str:
    play_time = _number_value(player.get("playTime", player.get("playerPlayTime")))
    value = next((_number_value(player.get(key)) for key in keys if _number_value(player.get(key)) is not None), None)
    if value is None or play_time is None or play_time <= 0:
        return "数据不足"
    return f"{value * 600 / play_time:,.1f}"


def _per10_stat(player: dict, key: str) -> str:
    value = _number_value(player.get(key))
    play_time = _number_value(player.get("playTime", player.get("playerPlayTime")))
    if value is None or play_time is None or play_time <= 0:
        return format_number(player, key)
    return f"{value * 600 / play_time:,.1f}"


def _main_hero(player: dict) -> tuple[object, int]:
    rows = player.get("playerHeroes")
    if not isinstance(rows, list):
        return player.get("curHeroId"), 0
    valid = [
        row for row in rows
        if isinstance(row, dict) and row.get("heroId", row.get("curHeroId")) is not None
    ]
    if not valid:
        return player.get("curHeroId"), 0
    main = max(valid, key=lambda row: _number_value(row.get("playTime", row.get("play_time"))) or 0)
    ids = {
        str(row.get("heroId", row.get("curHeroId")))
        for row in valid
    }
    return main.get("heroId", main.get("curHeroId")), max(0, len(ids) - 1)


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
                hero_id, switch_count = _main_hero(player)
                hero_name = format_hero_name(hero_id) if hero_id is not None else "未知英雄"
                if switch_count:
                    hero_name += f"（另使用 {switch_count} 名英雄）"
                members.append(player_row(
                    name=player.get("nickName", player.get("playerUid", "-")),
                    hero=hero_name,
                    stats=(
                        "每10分钟 " + "/".join(_per10_stat(player, key) for key in ("k", "d", "a"))
                        if _number_value(player.get("playTime", player.get("playerPlayTime"))) else
                        "/".join(format_number(player, key) for key in ("k", "d", "a"))
                    ),
                    extra=(
                        f"伤害 {format_number(player, 'totalHeroDamage')}（每10分钟 {_per10(player, 'totalHeroDamage', 'heroDamage')}） · "
                        f"治疗 {format_number(player, 'totalHeroHeal')}（每10分钟 {_per10(player, 'totalHeroHeal', 'totalHeal', 'heal')}） · "
                        f"承伤 {format_number(player, 'totalDamageTaken')}（每10分钟 {_per10(player, 'totalDamageTaken', 'damageTaken')}）"
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

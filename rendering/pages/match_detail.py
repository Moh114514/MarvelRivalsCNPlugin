"""Match detail page."""

from __future__ import annotations

try:
    from ...marvel_rivals_bot.game_metadata import format_match_map, format_play_mode, format_queue, get_map_mode
    from ...marvel_rivals_bot.reference.heroes import format_hero_name
except ImportError:
    from marvel_rivals_bot.game_metadata import format_match_map, format_play_mode, format_queue, get_map_mode
    from marvel_rivals_bot.reference.heroes import format_hero_name

from ..components import empty_state, metric_grid, page_header, page_shell, section_title, team_panel
from ..formatters import escape_text, extract_first_match, format_duration, format_number, format_timestamp


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
        return "数据不足"
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


def _scoreboard_metric(label: str, value: str, per10: str) -> str:
    return (
        '<div class="mr-scoreboard-player__metric">'
        f'<span>{label}</span>'
        f'<strong>{value}</strong>'
        f'<small>/10分钟 {per10}</small>'
        '</div>'
    )


def _scoreboard_player(player: dict) -> str:
    hero_id, switch_count = _main_hero(player)
    hero_name = format_hero_name(hero_id) if hero_id is not None else "未知英雄"
    play_time = _number_value(player.get("playTime", player.get("playerPlayTime")))
    total_kda = "/".join(format_number(player, key) for key in ("k", "d", "a"))
    per10_kda = "/".join(_per10_stat(player, key) for key in ("k", "d", "a"))
    name = player.get("nickName", player.get("playerUid", "-"))
    switch_note = f"切换 {switch_count} 名英雄" if switch_count else ""
    switch_html = (
        f'<small class="mr-scoreboard-player__switch">{escape_text(switch_note)}</small>'
        if switch_note else ""
    )
    return (
        '<div class="mr-scoreboard-player">'
        '<div class="mr-scoreboard-player__identity">'
        f'<strong class="mr-scoreboard-player__name">{escape_text(name)}</strong>'
        f'<span class="mr-scoreboard-player__hero">{escape_text(hero_name)}</span>'
        f'{switch_html}'
        '</div>'
        '<div class="mr-scoreboard-player__metric mr-scoreboard-player__kda">'
        '<span>K / D / A</span>'
        f'<strong>{escape_text(total_kda)}</strong>'
        f'<small>/10分钟 {escape_text(per10_kda if play_time and play_time > 0 else "数据不足")}</small>'
        '</div>'
        + _scoreboard_metric("伤害", format_number(player, "totalHeroDamage"), _per10(player, "totalHeroDamage", "heroDamage"))
        + _scoreboard_metric("治疗", format_number(player, "totalHeroHeal"), _per10(player, "totalHeroHeal", "totalHeal", "heal"))
        + _scoreboard_metric("承伤", format_number(player, "totalDamageTaken"), _per10(player, "totalDamageTaken", "damageTaken"))
        + '</div>'
    )


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
            members = [
                '<div class="mr-scoreboard-head">'
                '<span>玩家 / 英雄</span><span>K / D / A</span><span>伤害</span><span>治疗</span><span>承伤</span>'
                '</div>'
            ]
            for player in players:
                if not isinstance(player, dict) or player.get("camp") != camp:
                    continue
                members.append(_scoreboard_player(player))
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

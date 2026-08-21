"""Recent matches page."""

from __future__ import annotations

try:
    from ...marvel_rivals_bot.game_metadata import format_match_map, format_queue
    from ...marvel_rivals_bot.reference.heroes import format_hero_name
    from ...marvel_rivals_bot.reference.seasons import format_season_name
except ImportError:
    from marvel_rivals_bot.game_metadata import format_match_map, format_queue
    from marvel_rivals_bot.reference.heroes import format_hero_name
    from marvel_rivals_bot.reference.seasons import format_season_name

from ..components import empty_state, match_row, page_header, page_shell, section_title
from ..formatters import format_duration, format_number, format_timestamp


def _play_time(row: dict) -> float:
    try:
        return float(row.get("playTime", row.get("play_time", 0)) or 0)
    except (TypeError, ValueError):
        return 0


def _per10_value(player: dict, key: str):
    play_time = _play_time(player)
    try:
        value = float(player.get(key))
    except (TypeError, ValueError):
        return None
    return value * 600 / play_time if play_time > 0 else None


def build_recent_matches_html(uid: str, season_code: str, matches: list[dict]) -> str:
    rows = []
    for index, item in enumerate(matches[:10], 1):
        player = item.get("matchPlayer", {}) if isinstance(item.get("matchPlayer"), dict) else {}
        win = player.get("isWin")
        result, result_class = ("胜利", "win") if win == 1 else ("失败", "loss") if win == 0 else ("未知", "unknown")
        hero_rows = player.get("playerHeroes")
        main_hero = None
        if isinstance(hero_rows, list):
            valid_heroes = [
                row for row in hero_rows
                if isinstance(row, dict) and row.get("heroId", row.get("curHeroId")) is not None
            ]
            if valid_heroes:
                main_hero = max(
                    valid_heroes,
                    key=_play_time,
                )
        hero_id = (main_hero or {}).get("heroId", (main_hero or {}).get("curHeroId"))
        if hero_id is None:
            hero_id = player.get("curHeroId")
        hero = format_hero_name(hero_id) if hero_id is not None else "未知英雄"
        used_hero_ids = {
            str(row.get("heroId", row.get("curHeroId")))
            for row in hero_rows
            if isinstance(row, dict) and row.get("heroId", row.get("curHeroId")) is not None
        } if isinstance(hero_rows, list) else set()
        if len(used_hero_ids) > 1:
            hero += f"（另使用 {len(used_hero_ids) - 1} 名英雄）"
        kda = "/".join(
            format_number({"value": _per10_value(player, key)}, "value")
            if _per10_value(player, key) is not None else format_number(player, key)
            for key in ("k", "d", "a")
        )
        if _play_time(player) > 0:
            kda = f"每10分钟 {kda}"
        rows.append(match_row(
            index=index,
            result=result,
            result_class=result_class,
            hero=hero,
            timestamp=format_timestamp(item.get("matchTimeStamp")),
            map_name=format_match_map(item.get("matchMapId")),
            queue=format_queue(item.get("gameModeId"), item.get("playModeId")),
            duration=format_duration(item.get("matchPlayDuration")),
            kda=kda,
        ))
    body = "".join(rows) if rows else empty_state("暂无可用比赛记录")
    content = (
        page_header(
            "RECENT MATCHES",
            f"UID {uid}",
            format_season_name(season_code),
            title_cn="最近 10 场对局",
        )
        + '<section class="mr-section">'
        + section_title("最近 10 场对局", "MATCH HISTORY")
        + f'<div class="mr-match-list">{body}</div></section>'
    )
    return page_shell(content, watermark="RECENT MATCHES")

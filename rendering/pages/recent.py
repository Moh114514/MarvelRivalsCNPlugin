"""Recent matches page."""

from __future__ import annotations

try:
    from ...marvel_rivals_bot.game_metadata import format_match_map, format_queue
    from ...marvel_rivals_bot.hero_names import format_hero_name
    from ...marvel_rivals_bot.services.rivals import format_season_name
except ImportError:
    from marvel_rivals_bot.game_metadata import format_match_map, format_queue
    from marvel_rivals_bot.hero_names import format_hero_name
    from marvel_rivals_bot.services.rivals import format_season_name

from ..components import empty_state, match_row, page_header, page_shell, section_title
from ..formatters import format_duration, format_number, format_timestamp


def build_recent_matches_html(uid: str, season_code: str, matches: list[dict]) -> str:
    rows = []
    for index, item in enumerate(matches[:10], 1):
        player = item.get("matchPlayer", {}) if isinstance(item.get("matchPlayer"), dict) else {}
        win = player.get("isWin")
        result, result_class = ("胜利", "win") if win == 1 else ("失败", "loss") if win == 0 else ("未知", "unknown")
        hero = format_hero_name(player.get("curHeroId")) if player.get("curHeroId") is not None else "未知英雄"
        rows.append(match_row(
            index=index,
            result=result,
            result_class=result_class,
            hero=hero,
            timestamp=format_timestamp(item.get("matchTimeStamp")),
            map_name=format_match_map(item.get("matchMapId")),
            queue=format_queue(item.get("gameModeId"), item.get("playModeId")),
            duration=format_duration(item.get("matchPlayDuration")),
            kda="/".join(format_number(player, key) for key in ("k", "d", "a")),
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

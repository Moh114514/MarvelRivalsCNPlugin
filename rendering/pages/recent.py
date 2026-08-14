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

from ..components import empty_state, match_row, page_header, page_shell
from ..formatters import escape_text, format_duration, format_number, format_timestamp


def build_recent_matches_html(uid: str, season_code: str, matches: list[dict]) -> str:
    rows = []
    for index, item in enumerate(matches[:10], 1):
        player = item.get("matchPlayer", {}) if isinstance(item.get("matchPlayer"), dict) else {}
        win = player.get("isWin")
        result, result_class = ("胜利", "win") if win == 1 else ("失败", "loss") if win == 0 else ("未知", "unknown")
        hero = format_hero_name(player.get("curHeroId")) if player.get("curHeroId") is not None else "未知英雄"
        rows.append(match_row(
            index=index,
            result=escape_text(result),
            result_class=result_class,
            hero=escape_text(hero),
            timestamp=escape_text(format_timestamp(item.get("matchTimeStamp"))),
            map_name=escape_text(format_match_map(item.get("matchMapId"))),
            queue=escape_text(format_queue(item.get("gameModeId"), item.get("playModeId"))),
            duration=escape_text(format_duration(item.get("matchPlayDuration"))),
            kda="/".join(format_number(player, key) for key in ("k", "d", "a")),
        ))
    body = "".join(rows) if rows else empty_state("暂无可用比赛记录")
    content = page_header(
        "最近 10 场对局",
        f"UID {escape_text(uid)} · 点击图片下方按钮查看单局详情",
        escape_text(format_season_name(season_code)),
    ) + f'<section class="matches">{body}</section>'
    return page_shell(content)

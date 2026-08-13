from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any, Awaitable, Callable

try:
    from ..marvel_rivals_bot.game_metadata import format_match_map, format_play_mode, format_queue, get_map_mode
    from ..marvel_rivals_bot.hero_names import format_hero_name
    from ..marvel_rivals_bot.services.rivals import format_season_name
except ImportError:
    from marvel_rivals_bot.game_metadata import format_match_map, format_play_mode, format_queue, get_map_mode
    from marvel_rivals_bot.hero_names import format_hero_name
    from marvel_rivals_bot.services.rivals import format_season_name


_STYLE = """
<style>
*{box-sizing:border-box}body{margin:0;background:#0b1020;color:#f5f7ff;font-family:"Microsoft YaHei","Noto Sans SC",sans-serif}
.card{width:1040px;padding:42px;background:radial-gradient(circle at 90% 0,#263b72 0,transparent 32%),linear-gradient(145deg,#151d38,#090d19)}
.head{display:flex;justify-content:space-between;align-items:flex-end;margin-bottom:26px}.title{font-size:42px;font-weight:800}.sub{color:#aebbd9;font-size:20px;margin-top:8px}.badge{padding:9px 18px;border-radius:20px;background:#2e61ff;font-size:20px;font-weight:700}
.matches{display:grid;grid-template-columns:1fr 1fr;gap:14px}.match,.team{background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.12);border-radius:18px;padding:20px}.match{display:grid;grid-template-columns:54px 1fr auto;gap:16px;align-items:center}.index{font-size:28px;color:#8494bb}.main{font-size:23px;font-weight:700}.meta{font-size:17px;color:#aebbd9;margin-top:8px}.kda{font-size:24px;font-weight:800;text-align:right}.win{color:#70e1a1}.loss{color:#ff7188}.unknown{color:#b9c1d5}
.overview{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px}.metric{background:rgba(255,255,255,.07);border-radius:15px;padding:16px}.metric b{display:block;font-size:21px;margin-top:5px}.metric span{color:#9eaccd;font-size:15px}.teams{display:grid;grid-template-columns:1fr 1fr;gap:16px}.team-title{font-size:25px;font-weight:800;margin-bottom:13px}.player{display:grid;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr) auto;gap:10px;padding:12px 0;border-top:1px solid rgba(255,255,255,.09)}.player:first-of-type{border-top:0}.name{font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.hero,.stats{color:#b7c2df}.extra{grid-column:1/-1;color:#8f9cbd;font-size:14px}.empty{padding:36px;text-align:center;color:#aebbd9;background:rgba(255,255,255,.06);border-radius:18px}
</style>
"""


def _text(value: Any, fallback: str = "-") -> str:
    text = escape(fallback if value in (None, "") else str(value))
    return text.replace("{", "&#123;").replace("}", "&#125;")


def _number(data: dict, *keys: str) -> str:
    for key in keys:
        value = data.get(key)
        if isinstance(value, (int, float)):
            return f"{value / 1000:.1f}K" if abs(value) >= 1000 else str(round(value))
    return "-"


def _duration(value: Any) -> str:
    if not isinstance(value, (int, float)):
        return "-"
    minutes, seconds = divmod(int(value), 60)
    return f"{minutes}:{seconds:02d}"


def _time(value: Any) -> str:
    try:
        return datetime.fromtimestamp(int(value)).strftime("%m-%d %H:%M")
    except (TypeError, ValueError, OSError):
        return "未知时间"


def _match(payload: dict) -> dict:
    data = payload.get("data", payload)
    matches = data.get("matches", []) if isinstance(data, dict) else []
    return matches[0] if isinstance(matches, list) and matches and isinstance(matches[0], dict) else {}


def build_recent_matches_html(uid: str, season_code: str, matches: list[dict]) -> str:
    rows = []
    for index, item in enumerate(matches[:10], 1):
        player = item.get("matchPlayer", {}) if isinstance(item.get("matchPlayer"), dict) else {}
        win = player.get("isWin")
        result, css = ("胜利", "win") if win == 1 else ("失败", "loss") if win == 0 else ("未知", "unknown")
        hero = format_hero_name(player.get("curHeroId")) if player.get("curHeroId") is not None else "未知英雄"
        rows.append(
            f'<div class="match"><div class="index">{index:02d}</div><div><div class="main"><span class="{css}">{result}</span> · {_text(hero)}</div>'
            f'<div class="meta">{_text(_time(item.get("matchTimeStamp")))} · {_text(format_match_map(item.get("matchMapId")))} · {_text(format_queue(item.get("gameModeId"), item.get("playModeId")))} · {_duration(item.get("matchPlayDuration"))}</div>'
            f'</div><div class="kda">{_number(player,"k")}/{_number(player,"d")}/{_number(player,"a")}</div></div>'
        )
    body = "".join(rows) if rows else '<div class="empty">暂无可用比赛记录</div>'
    return f'<!doctype html><html><head><meta charset="utf-8">{_STYLE}</head><body><main class="card"><header class="head"><div><div class="title">最近 10 场对局</div><div class="sub">UID {_text(uid)} · 点击图片下方按钮查看单局详情</div></div><div class="badge">{_text(format_season_name(season_code))}</div></header><section class="matches">{body}</section></main></body></html>'


def build_match_detail_html(payload: dict) -> str:
    match = _match(payload)
    if not match:
        title, overview, body = "对局详情", "", '<div class="empty">暂无对局数据</div>'
    else:
        title = format_match_map(match.get("matchMapId"))
        mode = get_map_mode(match.get("matchMapId")) or format_play_mode(match.get("playModeId"))
        metrics = (("队列", format_queue(match.get("gameModeId"), match.get("playModeId"))), ("玩法", mode), ("时长", _duration(match.get("matchPlayDuration"))), ("胜方阵营", match.get("matchWinnerSide", "-")))
        overview = '<section class="overview">' + "".join(f'<div class="metric"><span>{_text(label)}</span><b>{_text(value)}</b></div>' for label, value in metrics) + "</section>"
        players = match.get("matchPlayers", [])
        camps = sorted({p.get("camp") for p in players if isinstance(p, dict) and p.get("camp") is not None}, key=lambda value: str(value)) if isinstance(players, list) else []
        teams = []
        for camp in camps:
            members = []
            for player in players:
                if not isinstance(player, dict) or player.get("camp") != camp:
                    continue
                members.append(f'<div class="player"><div class="name">{_text(player.get("nickName", player.get("playerUid", "-")))}</div><div class="hero">{_text(format_hero_name(player.get("curHeroId")))}</div><div class="stats">{_number(player,"k")}/{_number(player,"d")}/{_number(player,"a")}</div><div class="extra">伤害 {_number(player,"totalHeroDamage")} · 治疗 {_number(player,"totalHeroHeal")} · 承伤 {_number(player,"totalDamageTaken")}</div></div>')
            teams.append(f'<section class="team"><div class="team-title">阵营 {_text(camp)}</div>{"".join(members)}</section>')
        body = '<section class="teams">' + "".join(teams) + "</section>" if teams else '<div class="empty">暂无玩家明细</div>'
    match_uid = match.get("matchUid", "-") if match else "-"
    return f'<!doctype html><html><head><meta charset="utf-8">{_STYLE}</head><body><main class="card"><header class="head"><div><div class="title">{_text(title)}</div><div class="sub">{_text(_time(match.get("matchTimeStamp")) if match else "")} · matchUid {_text(match_uid)}</div></div><div class="badge">对局详情</div></header>{overview}{body}</main></body></html>'


class MatchImageRenderer:
    def __init__(self, html_render: Callable[..., Awaitable[str]]):
        self._html_render = html_render

    async def recent(self, uid: str, season_code: str, matches: list[dict]) -> str:
        return await self._html_render(build_recent_matches_html(uid, season_code, matches), {}, options={"type": "png"})

    async def detail(self, payload: dict) -> str:
        return await self._html_render(build_match_detail_html(payload), {}, options={"type": "png"})

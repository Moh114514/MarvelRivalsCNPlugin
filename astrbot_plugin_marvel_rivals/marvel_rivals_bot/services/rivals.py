from __future__ import annotations

import time
from datetime import datetime

from ..datasource.base import RivalsDataSource
from ..hero_names import format_hero_name
from ..models import PlayerStats


class RivalsService:
    def __init__(self, source: RivalsDataSource, cache_seconds: float = 60):
        self.source = source
        self.cache_seconds = max(0, cache_seconds)
        self._player_cache: dict[str, tuple[float, str]] = {}
        self._matches_cache: dict[str, tuple[float, str]] = {}

    async def player_text(self, uid: str) -> str:
        cached = self._cached(self._player_cache, uid)
        if cached is not None:
            return cached
        result = format_player(await self.source.get_player(uid))
        self._player_cache[uid] = (time.monotonic(), result)
        return result

    async def matches_text(self, uid: str) -> str:
        cached = self._cached(self._matches_cache, uid)
        if cached is not None:
            return cached
        result = format_matches(await self.source.get_recent_matches(uid))
        self._matches_cache[uid] = (time.monotonic(), result)
        return result

    async def hero_text(self, uid: str, hero_id: str) -> str:
        return format_hero(await self.source.get_hero(uid, hero_id))

    async def match_detail_text(self, match_uid: str) -> str:
        return format_match_detail(await self.source.get_summary_detail(match_uid))

    def _cached(self, cache: dict[str, tuple[float, str]], uid: str) -> str | None:
        if self.cache_seconds <= 0:
            return None
        item = cache.get(uid)
        if item and time.monotonic() - item[0] < self.cache_seconds:
            return item[1]
        cache.pop(uid, None)
        return None


def _fmt(value: int | float | None, fallback: str = "-") -> str:
    if value is None:
        return fallback
    return f"{value:.1f}" if isinstance(value, float) and not value.is_integer() else str(int(value))


def _duration(seconds: int | float | None) -> str:
    if not isinstance(seconds, (int, float)):
        return "-"
    minutes, remain = divmod(int(seconds), 60)
    return f"{minutes}:{remain:02d}"


def _time(timestamp: Any) -> str:
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime("%m-%d %H:%M")
    except (TypeError, ValueError, OSError):
        return "未知时间"


def format_player(stats: PlayerStats) -> str:
    p, s = stats.profile, stats.summary
    lines = ["漫威争锋国服战绩", f"玩家：{p.name}", f"UID：{p.uid}"]
    if p.level is not None:
        lines.append(f"等级：{p.level}")
    if p.rank_game_season:
        lines.append(f"当前段位：{p.rank_game_season}")
    lines += ["", "综合数据", f"场次：{_fmt(s.matches)}    胜场：{_fmt(s.wins)}    胜率：{_fmt(s.win_rate)}%", f"K/D/A：{_fmt(s.kills)} / {_fmt(s.deaths)} / {_fmt(s.assists)}"]
    if s.damage is not None:
        lines.append(f"总伤害：{_fmt(s.damage)}")
    if stats.heroes:
        lines += ["", "常用英雄"]
        for index, hero in enumerate(stats.heroes[:5], 1):
            lines.append(
                f"{index}. {format_hero_name(hero.hero_id, hero.hero_name)}  "
                f"时长 {_duration(hero.play_time_seconds)}"
            )
    return "\n".join(lines)


def format_matches(matches: list[dict]) -> str:
    if not matches:
        return "最近比赛接口尚未配置或没有可用记录。"
    lines = ["最近比赛"]
    for item in matches[:10]:
        match_uid = str(item.get("matchUid", item.get("matchUID", item.get("id", ""))))
        player = item.get("matchPlayer", {})
        result = "胜" if player.get("isWin") == 1 else "负" if player.get("isWin") == 0 else "?"
        kda = f"{player.get('k', '-')}/{player.get('d', '-')}/{player.get('a', '-')}"
        hero = format_hero_name(player.get("curHeroId")) if player.get("curHeroId") is not None else "未知英雄"
        lines.append(
            f"{result}  {_time(item.get('matchTimeStamp'))}  {hero}  KDA {kda}  "
            f"地图 {item.get('matchMapId', '-')}  {_duration(item.get('matchPlayDuration'))}\n"
            f"matchUid={match_uid}"
        )
    return "\n".join(lines)


def format_detail(title: str, payload: dict) -> str:
    data = payload.get("data", payload)
    if not isinstance(data, dict):
        return title + "\n接口返回了数据，但暂时没有可展示字段。"
    lines = [title]
    preferred = ("heroName", "name", "heroId", "totalMatchCount", "totalMatchWinCount", "winRate", "k", "d", "a", "totalDamage", "totalHeroDamage", "totalHeal", "totalHeroHeal")
    for key in preferred:
        if key in data and data[key] not in (None, ""):
            lines.append(f"{key}: {data[key]}")
    if len(lines) == 1:
        lines.append("接口返回了数据，但字段名还需要根据完整抓包响应映射。")
    return "\n".join(lines)


def format_hero(payload: dict) -> str:
    data = payload.get("data", payload)
    careers = data.get("careers", []) if isinstance(data, dict) else []
    if not isinstance(careers, list) or not careers:
        return "英雄数据\n没有返回该英雄的生涯数据。"
    hero = careers[0]
    matches = hero.get("totalMatchCount")
    wins = hero.get("totalMatchWinCount")
    win_rate = wins * 100 / matches if isinstance(matches, (int, float)) and matches and isinstance(wins, (int, float)) else None
    hit_rate = hero.get("sessionMaxHitRate")
    lines = [
        f"英雄：{format_hero_name(hero.get('heroId'))}",
        f"场次：{_fmt(matches)}    胜场：{_fmt(wins)}    胜率：{_fmt(win_rate)}%",
        f"K/D/A：{_fmt(hero.get('k'))} / {_fmt(hero.get('d'))} / {_fmt(hero.get('a'))}",
        f"游玩时长：{_duration(hero.get('totalPlayTime'))}",
        f"英雄伤害：{_fmt(hero.get('totalHeroDamage'))}    治疗：{_fmt(hero.get('totalHeroHeal'))}",
        f"承受伤害：{_fmt(hero.get('totalDamageTaken'))}",
        f"最高命中率：{_fmt(hit_rate * 100 if isinstance(hit_rate, (int, float)) else None)}%",
        f"MVP：{_fmt(hero.get('totalMvpTimes'))}    SVP：{_fmt(hero.get('totalSvpTimes'))}",
    ]
    return "\n".join(lines)


def format_match_detail(payload: dict) -> str:
    data = payload.get("data", payload)
    matches = data.get("matches", []) if isinstance(data, dict) else []
    if not isinstance(matches, list) or not matches:
        return "对局详情\n没有返回对局数据。"
    match = matches[0]
    lines = [
        "对局详情",
        f"时间：{_time(match.get('matchTimeStamp'))}",
        f"地图：{match.get('matchMapId', '-')}    模式：{match.get('gameModeId', '-')}/{match.get('playModeId', '-')}",
        f"时长：{_duration(match.get('matchPlayDuration'))}    胜方阵营：{match.get('matchWinnerSide', '-')}",
        f"matchUid：{match.get('matchUid', '-')}",
    ]
    players = match.get("matchPlayers", [])
    if isinstance(players, list):
        for camp in sorted({p.get("camp") for p in players if isinstance(p, dict) and p.get("camp") is not None}):
            lines.append("")
            lines.append(f"阵营 {camp}")
            for player in players:
                if not isinstance(player, dict) or player.get("camp") != camp:
                    continue
                lines.append(
                    f"{'胜' if player.get('isWin') == 1 else '负'} {player.get('nickName', player.get('playerUid', '-'))} "
                    f"英雄 {format_hero_name(player.get('curHeroId'))}  {player.get('k', '-')}/{player.get('d', '-')}/{player.get('a', '-')}  "
                    f"伤害 {_fmt(player.get('totalHeroDamage'))} 治疗 {_fmt(player.get('totalHeroHeal'))} 承伤 {_fmt(player.get('totalDamageTaken'))}"
                )
    return "\n".join(lines)

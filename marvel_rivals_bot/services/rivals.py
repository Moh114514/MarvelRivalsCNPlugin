from __future__ import annotations

import time

from ..datasource.base import RivalsDataSource
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
        return format_detail("英雄数据", await self.source.get_hero(uid, hero_id))

    async def match_detail_text(self, match_uid: str) -> str:
        return format_detail("对局详情", await self.source.get_summary_detail(match_uid))

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
            lines.append(f"{index}. {hero.hero_name}  {_fmt(hero.matches)}场  {_fmt(hero.win_rate)}%")
    return "\n".join(lines)


def format_matches(matches: list[dict]) -> str:
    if not matches:
        return "最近比赛接口尚未配置或没有可用记录。"
    lines = ["最近比赛"]
    for item in matches[:10]:
        match_uid = str(item.get("matchUid", item.get("matchUID", item.get("id", ""))))
        result = str(item.get("result", item.get("win", "?")))
        hero = str(item.get("heroName", item.get("hero", "未知英雄")))
        kda = f"{item.get('kills', item.get('k', '-'))}/{item.get('deaths', item.get('d', '-'))}/{item.get('assists', item.get('a', '-'))}"
        lines.append(f"{result} {hero} {kda}  matchUid={match_uid}")
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

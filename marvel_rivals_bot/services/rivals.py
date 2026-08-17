from __future__ import annotations

import time
from datetime import datetime
from typing import TypeVar

from ..datasource.base import DataSourceError, RivalsDataSource
from ..game_metadata import format_match_map, format_play_mode, format_queue, get_map_mode
from ..reference.heroes import format_hero_name, get_hero_id
from ..models import HeroQueryResult, ModeStats, PlayerStats
from ..reference.seasons import format_season_name as _format_season_name
from ..reference.seasons import parse_season_name as _parse_season_name
from ..reference.seasons import season_identity_from_cn_code, season_identity_from_name


CacheValue = TypeVar("CacheValue")


def format_season_name(code: str | int) -> str:
    return _format_season_name(code)


def parse_season_name(value: str) -> str:
    try:
        return _parse_season_name(value)
    except ValueError as exc:
        # Keep the legacy façade's DataSourceError contract while the
        # canonical reference module stays independent of data sources.
        raise DataSourceError(str(exc)) from exc


class RivalsService:
    def __init__(self, source: RivalsDataSource, cache_seconds: float = 60):
        self.source = source
        self.cache_seconds = max(0, cache_seconds)
        self._player_cache: dict[str, tuple[float, PlayerStats]] = {}
        self._matches_cache: dict[str, tuple[float, list[dict]]] = {}
        self._hero_cache: dict[str, tuple[float, HeroQueryResult]] = {}
        self._match_detail_cache: dict[str, tuple[float, dict]] = {}

    async def get_player_stats(self, uid: str, season: str | None = None) -> PlayerStats:
        season_code = self._season_code(season)
        cache_key = f"{uid}:{season_code}"
        cached = self._cached(self._player_cache, cache_key)
        if cached is not None:
            return cached
        stats = await self.source.get_player(uid, season_code)
        self._player_cache[cache_key] = (time.monotonic(), stats)
        return stats

    async def player_text(self, uid: str, season: str | None = None) -> str:
        return format_player(await self.get_player_stats(uid, season))

    async def get_recent_matches(self, uid: str, season: str | None = None) -> list[dict]:
        season_code = self._season_code(season)
        cache_key = f"{uid}:{season_code}"
        cached = self._cached(self._matches_cache, cache_key)
        if cached is not None:
            return cached
        matches = await self.source.get_recent_matches(uid, season_code)
        self._matches_cache[cache_key] = (time.monotonic(), matches)
        return matches

    async def matches_text(self, uid: str, season: str | None = None) -> str:
        season_code = self._season_code(season)
        return format_matches(await self.get_recent_matches(uid, season), season_code)

    async def get_hero_stats(self, uid: str, hero_name: str, season: str | None = None) -> HeroQueryResult:
        season_code = self._season_code(season)
        try:
            hero_id = str(get_hero_id(hero_name))
        except ValueError as exc:
            raise DataSourceError(str(exc)) from exc
        cache_key = f"{uid}:{hero_id}:{season_code}"
        cached = self._cached(self._hero_cache, cache_key)
        if cached is not None:
            return cached
        profile_loader = getattr(self.source, "get_hero_profile", None)
        if callable(profile_loader):
            profile = await profile_loader(uid, hero_id, season_code)
            result = HeroQueryResult(
                uid=uid,
                hero_id=hero_id,
                hero_name=profile.hero_name or hero_name,
                season=season_code,
                payload={"data": {"careers": [profile.raw]}},
                stats=profile,
            )
        else:
            result = HeroQueryResult(
                uid=uid,
                hero_id=hero_id,
                hero_name=hero_name,
                season=season_code,
                payload=await self.source.get_hero(uid, hero_id, season_code),
            )
        self._hero_cache[cache_key] = (time.monotonic(), result)
        return result

    async def hero_text(self, uid: str, hero_name: str, season: str | None = None) -> str:
        result = await self.get_hero_stats(uid, hero_name, season)
        return format_hero_result(result)

    async def get_match_detail(self, match_uid: str) -> dict:
        cache_key = str(match_uid).strip()
        cached = self._cached(self._match_detail_cache, cache_key)
        if cached is not None:
            return cached
        payload = await self.source.get_summary_detail(match_uid)
        self._match_detail_cache[cache_key] = (time.monotonic(), payload)
        return payload

    async def match_detail_text(self, match_uid: str) -> str:
        return format_match_detail(await self.get_match_detail(match_uid))

    def _season_code(self, season: str | None) -> str:
        if season is None or not str(season).strip():
            default_season = getattr(self.source, "default_season", "19")
            try:
                return season_identity_from_cn_code(default_season).for_provider("cn")
            except ValueError as exc:
                raise DataSourceError(str(exc)) from exc
        try:
            return season_identity_from_name(season).for_provider("cn")
        except ValueError as exc:
            raise DataSourceError(str(exc)) from exc

    def season_code(self, season: str | None = None) -> str:
        return self._season_code(season)

    def _cached(self, cache: dict[str, tuple[float, CacheValue]], key: str) -> CacheValue | None:
        if self.cache_seconds <= 0:
            return None
        item = cache.get(key)
        if item and time.monotonic() - item[0] < self.cache_seconds:
            return item[1]
        cache.pop(key, None)
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


def _hours(seconds: int | float | None) -> str:
    if not isinstance(seconds, (int, float)):
        return "-"
    return f"{seconds / 3600:.2f} 小时"


def _count(value: int | float | None, fallback: str = "-") -> str:
    if not isinstance(value, (int, float)):
        return fallback
    return str(round(value))


def _time(timestamp: Any) -> str:
    try:
        return datetime.fromtimestamp(int(timestamp)).strftime("%m-%d %H:%M")
    except (TypeError, ValueError, OSError):
        return "未知时间"


def _mode_matches(mode: ModeStats, fallback: int | float | None = None) -> str:
    value = mode.matches if mode.matches is not None else fallback
    return _count(value)


def _mode_rate(mode: ModeStats, fallback: float | None = None) -> str:
    value = mode.win_rate if mode.win_rate is not None else fallback
    return _fmt(value) + "%" if value is not None else "-"


def format_player(stats: PlayerStats) -> str:
    p, s = stats.profile, stats.summary
    lines = [f"漫威争锋国服个人资料（{format_season_name(stats.season)}的数据）", f"玩家：{p.name}", f"UID：{p.uid}"]
    if p.level is not None:
        lines.append(f"等级：{p.level}")
    if p.rank_game_season:
        lines.append(f"段位：{p.rank_game_season}")
    lines += [
        "",
        "本赛季游戏",
        f"竞技：{_mode_matches(s.ranked)} 场 · 胜率 {_mode_rate(s.ranked)}",
        f"快速：{_mode_matches(s.quick)} 场 · 胜率 {_mode_rate(s.quick)}",
        f"总计：{_count(s.matches)} 场 · 胜场 {_count(s.wins)} · 胜率 {_mode_rate(ModeStats(win_rate=s.win_rate))}",
        f"竞技 K/D/A：{_count(s.ranked.kills, _count(s.kills))} / {_count(s.ranked.deaths, _count(s.deaths))} / {_count(s.ranked.assists, _count(s.assists))}",
    ]
    if s.damage is not None:
        lines.append(f"总伤害：{_fmt(s.damage)}")
    if stats.heroes:
        lines += ["", "常用英雄（快速 + 竞技总场次）"]
        for index, hero in enumerate(stats.heroes[:5], 1):
            total_matches = getattr(hero, "total_matches", getattr(hero, "matches", None))
            quick = getattr(getattr(hero, "quick", None), "matches", 0) or 0
            ranked_scope = getattr(hero, "ranked", None)
            ranked = getattr(ranked_scope, "matches", None)
            ranked_rate = getattr(ranked_scope, "win_rate", None)
            if ranked_scope is None:
                # Older adapters exposed one aggregate HeroStat.  Keep that
                # data visible while the CN adapter supplies explicit scopes.
                ranked = total_matches
                ranked_rate = getattr(hero, "win_rate", None)
                if ranked_rate is None and ranked and getattr(hero, "wins", None) is not None:
                    ranked_rate = hero.wins * 100 / ranked
            lines.append(
                f"{index}. {format_hero_name(hero.hero_id, hero.hero_name)}  "
                f"总计 {_fmt(total_matches)} / 快速 {_fmt(quick)} / 竞技 {_fmt(ranked)} / 竞技胜率 {_mode_rate(ModeStats(win_rate=ranked_rate))}"
            )
    return "\n".join(lines)


def format_matches(matches: list[dict], season: str | None = None) -> str:
    title = "最近比赛" + (f"（{format_season_name(season)}的数据）" if season else "")
    if not matches:
        return title + "\n没有可用记录。"
    lines = [title]
    for item in matches[:10]:
        match_uid = str(item.get("matchUid", item.get("matchUID", item.get("id", ""))))
        player = item.get("matchPlayer", {})
        result = "胜" if player.get("isWin") == 1 else "负" if player.get("isWin") == 0 else "?"
        kda = f"{_count(player.get('k'))}/{_count(player.get('d'))}/{_count(player.get('a'))}"
        hero = format_hero_name(player.get("curHeroId")) if player.get("curHeroId") is not None else "未知英雄"
        map_name = format_match_map(item.get("matchMapId"))
        queue = format_queue(item.get("gameModeId"), item.get("playModeId"))
        map_mode = get_map_mode(item.get("matchMapId"))
        mode_text = f"{queue} / {map_mode}" if map_mode else queue
        lines.append(
            f"{result}  {_time(item.get('matchTimeStamp'))}  {hero}  KDA {kda}  "
            f"{_duration(item.get('matchPlayDuration'))}\n"
            f"地图 {map_name}  {mode_text}\n"
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


def format_hero(payload: dict, season: str | None = None) -> str:
    data = payload.get("data", payload)
    careers = data.get("careers", []) if isinstance(data, dict) else []
    if not isinstance(careers, list) or not careers:
        title = "英雄数据" + (f"（{format_season_name(season)}的数据）" if season else "")
        return title + "\n没有返回该英雄的生涯数据。"
    hero = careers[0]
    matches = hero.get("totalMatchCount")
    wins = hero.get("totalMatchWinCount")
    win_rate = wins * 100 / matches if isinstance(matches, (int, float)) and matches and isinstance(wins, (int, float)) else None
    hit_rate = hero.get("sessionMaxHitRate")
    lines = [
        f"英雄：{format_hero_name(hero.get('heroId'))}",
        *([f"（{format_season_name(season)}的数据）"] if season else []),
        f"场次：{_count(matches)}    胜场：{_count(wins)}    胜率：{_fmt(win_rate)}%",
        f"K/D/A：{_count(hero.get('k'))} / {_count(hero.get('d'))} / {_count(hero.get('a'))}",
        f"游玩时长：{_hours(hero.get('totalPlayTime'))}",
        f"英雄伤害：{_fmt(hero.get('totalHeroDamage'))}    治疗：{_fmt(hero.get('totalHeroHeal'))}",
        f"承受伤害：{_fmt(hero.get('totalDamageTaken'))}",
        f"最高命中率：{_fmt(hit_rate * 100 if isinstance(hit_rate, (int, float)) else None)}%",
        f"MVP：{_count(hero.get('totalMvpTimes'))}    SVP：{_count(hero.get('totalSvpTimes'))}",
    ]
    return "\n".join(lines)


def format_hero_result(result: HeroQueryResult) -> str:
    """Format the explicit total/quick/ranked hero model when available.

    The payload-only formatter remains public for CLI and older integrations;
    structured queries use this path so text and image output share scopes.
    """

    stats = result.stats
    if stats is None or not hasattr(stats, "ranked"):
        return format_hero(result.payload, result.season)

    total_matches = getattr(stats, "total_matches", None)
    total_wins = getattr(stats, "total_wins", None)
    total_rate = getattr(stats, "total_win_rate", None)
    quick = stats.quick
    ranked = stats.ranked
    if total_rate is None and total_matches and total_wins is not None:
        total_rate = total_wins * 100 / total_matches
    hero_name = format_hero_name(result.hero_id, result.hero_name)
    lines = [
        f"英雄：{hero_name}",
        *((f"（{format_season_name(result.season)}的数据）",) if result.season else ()),
        f"总计使用：{_count(total_matches)} 场    快速：{_count(quick.matches)} 场    竞技：{_count(ranked.matches)} 场",
        f"总计胜率：{_mode_rate(ModeStats(win_rate=total_rate))}    总胜场：{_count(total_wins)}",
        f"竞技：{_count(ranked.matches)} 场    胜场：{_count(ranked.wins)}    胜率：{_mode_rate(ranked)}",
        f"快速：{_count(quick.matches)} 场    胜场：{_count(quick.wins)}    胜率：{_mode_rate(quick)}",
        f"竞技 K/D/A：{_count(ranked.kills)} / {_count(ranked.deaths)} / {_count(ranked.assists)}",
        f"竞技英雄伤害：{_fmt(ranked.hero_damage)}    治疗：{_fmt(ranked.heal)}",
        f"竞技承受伤害：{_fmt(ranked.damage_taken)}",
        f"竞技游戏时长：{_hours(ranked.play_time_seconds)}",
        f"竞技 MVP：{_count(ranked.mvp)}    SVP：{_count(ranked.svp)}",
    ]
    return "\n".join(lines)


def format_match_detail(payload: dict) -> str:
    data = payload.get("data", payload)
    matches = data.get("matches", []) if isinstance(data, dict) else []
    if not isinstance(matches, list) or not matches:
        return "对局详情\n没有返回对局数据。"
    match = matches[0]
    map_mode = get_map_mode(match.get("matchMapId"))
    lines = [
        "对局详情",
        f"时间：{_time(match.get('matchTimeStamp'))}",
        f"地图：{format_match_map(match.get('matchMapId'))}",
        f"队列：{format_queue(match.get('gameModeId'), match.get('playModeId'))}",
        f"玩法：{map_mode or format_play_mode(match.get('playModeId'))}",
        f"时长：{_duration(match.get('matchPlayDuration'))}    胜方阵营：{match.get('matchWinnerSide', '-')}",
        f"matchUid：{match.get('matchUid', '-')}",
    ]
    players = match.get("matchPlayers", [])
    if isinstance(players, list):
        camps = {p.get("camp") for p in players if isinstance(p, dict) and p.get("camp") is not None}
        for camp in sorted(camps, key=lambda value: (0, str(value).zfill(12)) if isinstance(value, (int, float)) else (1, str(value))):
            lines.append("")
            lines.append(f"阵营 {camp}")
            for player in players:
                if not isinstance(player, dict) or player.get("camp") != camp:
                    continue
                lines.append(
                    f"{'胜' if player.get('isWin') == 1 else '负'} {player.get('nickName', player.get('playerUid', '-'))} "
                    f"英雄 {format_hero_name(player.get('curHeroId'))}  {_count(player.get('k'))}/{_count(player.get('d'))}/{_count(player.get('a'))}  "
                    f"伤害 {_fmt(player.get('totalHeroDamage'))} 治疗 {_fmt(player.get('totalHeroHeal'))} 承伤 {_fmt(player.get('totalDamageTaken'))}"
                )
    return "\n".join(lines)

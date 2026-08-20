"""Argument parsing helpers for the text Meta commands."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .models import RankingRange
from ..reference.ranks import normalize_rank
from ..reference.seasons import season_identity_from_name


class MetaCommandError(ValueError):
    """A user-safe Meta command argument error."""


class CommandUsageError(MetaCommandError):
    """A malformed command argument that can be shown in Jeff style."""


SORT_ALIASES = {
    "胜率": "win_rate",
    "winrate": "win_rate",
    "win_rate": "win_rate",
    "选取率": "pick_rate",
    "选取": "pick_rate",
    "pick": "pick_rate",
    "pickrate": "pick_rate",
    "pick_rate": "pick_rate",
    "ban": "ban_rate",
    "ban率": "ban_rate",
    "ban率": "ban_rate",
    "banrate": "ban_rate",
    "ban_rate": "ban_rate",
    "场次": "matches",
    "matches": "matches",
}

ROLE_ALIASES = {
    "先锋": "vanguard",
    "捍卫": "vanguard",
    "捍卫者": "vanguard",
    "t": "vanguard",
    "t位": "vanguard",
    "坦克": "vanguard",
    "vanguard": "vanguard",
    "决斗": "duelist",
    "决斗家": "duelist",
    "c": "duelist",
    "c位": "duelist",
    "输出": "duelist",
    "dps": "duelist",
    "duelist": "duelist",
    "战略": "strategist",
    "战略家": "strategist",
    "策略": "strategist",
    "策略家": "strategist",
    "奶": "strategist",
    "奶位": "strategist",
    "辅助": "strategist",
    "support": "strategist",
    "strategist": "strategist",
    "n": "strategist",
}

_GROUP_BY_ROLE_ALIASES = {"分职责", "分职能", "按职责", "职责排行"}
_RANGE_RE = re.compile(r"^(?P<start>\d+)[-~～](?P<end>\d+)$")
_TOP_RE = re.compile(r"^(?:前|top)(?P<count>\d+)$", re.IGNORECASE)
_TAIL_RE = re.compile(r"^(?:后|最后|倒数)(?P<count>\d+)$")


@dataclass(slots=True)
class MetaCommandArgs:
    hero_name: str | None = None
    hero_names: tuple[str, ...] = ()
    season: str | None = None
    rank: str = "all"
    sort_by: str = "win_rate"
    role: str | None = None
    group_by_role: bool = False
    ranking_range: RankingRange | None = None


@dataclass(slots=True)
class HistoricalMetaCommandArgs:
    hero_name: str | None = None
    seasons: tuple[str, ...] = ()
    rank: str = "all"


_SEASON_RE = re.compile(r"^[sS](?:0|[1-9]\d*(?:\.5|上半赛季|下半赛季)?)$")


def parse_meta_command_args(
    *parts: str,
    require_hero: bool = False,
    require_hero_count: int | None = None,
    allow_sort: bool = True,
    require_sort: bool = False,
    allow_rank: bool = True,
) -> MetaCommandArgs:
    tokens: list[str] = []
    for part in parts:
        if part and str(part).strip():
            tokens.extend(str(part).split())

    result = MetaCommandArgs()
    remaining: list[str] = []
    season_seen = False
    rank_seen = False
    sort_seen = False
    role_seen = False
    range_seen = False
    for token in tokens:
        token = token.strip()
        range_value = _parse_ranking_range(token)
        if range_value is not None:
            if range_seen:
                raise CommandUsageError("只能指定一个排名范围")
            range_seen = True
            result.ranking_range = range_value
            continue
        if token in _GROUP_BY_ROLE_ALIASES:
            if result.group_by_role or role_seen:
                raise CommandUsageError("只能指定一种职责筛选方式")
            result.group_by_role = True
            continue
        role_key = ROLE_ALIASES.get(token.lower(), ROLE_ALIASES.get(token))
        if role_key is not None:
            if role_seen or result.group_by_role:
                raise CommandUsageError("只能指定一个职责")
            role_seen = True
            result.role = role_key
            continue
        if _SEASON_RE.fullmatch(token):
            if season_seen:
                raise CommandUsageError("只能指定一个赛季")
            season_seen = True
            result.season = token
            continue
        sort_key = SORT_ALIASES.get(token.strip().lower(), SORT_ALIASES.get(token.strip()))
        if sort_key is not None:
            if not allow_sort:
                raise CommandUsageError("该命令不接受排序指标")
            if sort_seen:
                raise CommandUsageError("只能指定一种排序方式")
            sort_seen = True
            result.sort_by = sort_key
            continue
        try:
            rank_key = normalize_rank(token)
        except ValueError:
            remaining.append(token)
        else:
            if not allow_rank:
                raise CommandUsageError("该命令不接受段位筛选")
            if rank_seen:
                raise CommandUsageError("只能指定一个段位")
            rank_seen = True
            result.rank = rank_key

    if require_hero_count is not None:
        if require_hero_count < 1:
            raise CommandUsageError("英雄数量配置无效")
        if len(remaining) != require_hero_count:
            raise CommandUsageError(f"请提供{require_hero_count}个不同的英雄中文名称")
        result.hero_names = tuple(remaining)
        if require_hero_count == 1:
            result.hero_name = remaining[0]
    elif remaining:
        if not require_hero:
            raise CommandUsageError(f"无法识别参数：{' '.join(remaining)}")
        result.hero_name = " ".join(remaining)
        result.hero_names = (result.hero_name,)
    if require_hero and not result.hero_name:
        raise CommandUsageError("请提供英雄中文名称，例如：曼蒂斯")
    if require_sort and not sort_seen:
        raise CommandUsageError("请提供一个排序指标，例如：胜率、选取率、Ban率或场次")
    if result.ranking_range is None and require_sort:
        result.ranking_range = RankingRange(1, 10)
    return result


def _parse_ranking_range(token: str) -> RankingRange | None:
    try:
        match = _TOP_RE.fullmatch(token)
        if match:
            count = int(match.group("count"))
            return RankingRange(1, count)
        match = _TAIL_RE.fullmatch(token)
        if match:
            count = int(match.group("count"))
            return RankingRange(from_tail=count)
        match = _RANGE_RE.fullmatch(token)
        if match:
            return RankingRange(int(match.group("start")), int(match.group("end")))
    except ValueError as exc:
        raise CommandUsageError(str(exc)) from exc
    if token in {"前", "top", "TOP", "后", "最后", "倒数"}:
        raise CommandUsageError("排名范围必须包含正整数，例如：前10或11-20")
    return None


def parse_historical_meta_command_args(
    *parts: str,
    require_hero: bool = False,
    allow_rank: bool = True,
    min_seasons: int = 0,
    max_seasons: int | None = None,
) -> HistoricalMetaCommandArgs:
    """Parse history commands without making season order positional."""

    tokens: list[str] = []
    for part in parts:
        if part and str(part).strip():
            tokens.extend(str(part).split())

    seasons: list[str] = []
    rank = "all"
    rank_seen = False
    remaining: list[str] = []
    for token in tokens:
        if _SEASON_RE.fullmatch(token):
            try:
                canonical = season_identity_from_name(token).canonical_name
            except ValueError as exc:
                raise MetaCommandError(str(exc)) from exc
            if canonical in seasons:
                raise MetaCommandError("只能指定不同的赛季")
            seasons.append(canonical)
            continue
        try:
            rank_key = normalize_rank(token)
        except ValueError:
            remaining.append(token)
        else:
            if not allow_rank:
                raise MetaCommandError("该命令不接受段位筛选")
            if rank_seen:
                raise MetaCommandError("只能指定一个段位")
            rank = rank_key
            rank_seen = True

    if require_hero:
        if not remaining:
            raise MetaCommandError("请提供英雄中文名称，例如：曼蒂斯")
        hero_name = " ".join(remaining)
    elif remaining:
        raise MetaCommandError(f"无法识别参数：{' '.join(remaining)}")
    else:
        hero_name = None

    if len(seasons) < max(0, int(min_seasons)):
        raise MetaCommandError(f"至少需要指定{int(min_seasons)}个不同的赛季")
    if max_seasons is not None and len(seasons) > int(max_seasons):
        raise MetaCommandError(f"最多只能指定{int(max_seasons)}个赛季")
    return HistoricalMetaCommandArgs(hero_name=hero_name, seasons=tuple(seasons), rank=rank)


__all__ = [
    "CommandUsageError",
    "HistoricalMetaCommandArgs",
    "MetaCommandArgs",
    "MetaCommandError",
    "ROLE_ALIASES",
    "RankingRange",
    "parse_historical_meta_command_args",
    "parse_meta_command_args",
]

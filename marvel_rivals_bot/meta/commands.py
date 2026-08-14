"""Argument parsing helpers for the text Meta commands."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .ranks import normalize_rank


class MetaCommandError(ValueError):
    """A user-safe Meta command argument error."""


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


@dataclass(slots=True)
class MetaCommandArgs:
    hero_name: str | None = None
    season: str | None = None
    rank: str = "all"
    sort_by: str = "win_rate"


_SEASON_RE = re.compile(r"^[sS](?:0|[1-9]\d*(?:\.5|上半赛季|下半赛季)?)$")


def parse_meta_command_args(*parts: str, require_hero: bool = False) -> MetaCommandArgs:
    tokens: list[str] = []
    for part in parts:
        if part and str(part).strip():
            tokens.extend(str(part).split())

    result = MetaCommandArgs()
    remaining: list[str] = []
    for token in tokens:
        if _SEASON_RE.fullmatch(token):
            if result.season is not None:
                raise MetaCommandError("只能指定一个赛季")
            result.season = token
            continue
        sort_key = SORT_ALIASES.get(token.strip().lower(), SORT_ALIASES.get(token.strip()))
        if sort_key is not None:
            if result.sort_by != "win_rate":
                raise MetaCommandError("只能指定一种排序方式")
            result.sort_by = sort_key
            continue
        try:
            rank_key = normalize_rank(token)
        except ValueError:
            remaining.append(token)
        else:
            if result.rank != "all":
                raise MetaCommandError("只能指定一个段位")
            result.rank = rank_key

    if remaining:
        if not require_hero:
            raise MetaCommandError(f"无法识别参数：{' '.join(remaining)}")
        result.hero_name = " ".join(remaining)
    if require_hero and not result.hero_name:
        raise MetaCommandError("请提供英雄中文名称，例如：曼蒂斯")
    return result

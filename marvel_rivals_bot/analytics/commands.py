"""Argument parsing for Player × Meta commands."""

from __future__ import annotations

from dataclasses import dataclass

from ..reference.seasons import parse_season_name
from .player_meta import DEFAULT_SIGNATURE_MIN_MATCHES


@dataclass(slots=True)
class PlayerMetaCommandArgs:
    season: str | None = None
    minimum_matches: int = DEFAULT_SIGNATURE_MIN_MATCHES


def parse_player_meta_args(*parts: str, allow_minimum_matches: bool = False) -> PlayerMetaCommandArgs:
    tokens: list[str] = []
    for part in parts:
        if part and str(part).strip():
            tokens.extend(str(part).split())
    season: str | None = None
    minimum_matches = DEFAULT_SIGNATURE_MIN_MATCHES
    minimum_seen = False
    for token in tokens:
        try:
            parse_season_name(token)
        except ValueError:
            if allow_minimum_matches and token.isdigit() and not minimum_seen:
                minimum_matches = int(token)
                minimum_seen = True
                continue
            raise ValueError("参数只支持赛季名称；/我的绝活还可指定最低场次")
        if season is not None:
            raise ValueError("只能指定一个赛季")
        season = token
    if minimum_matches < 1:
        raise ValueError("最低场次必须是正整数")
    return PlayerMetaCommandArgs(season=season, minimum_matches=minimum_matches)


__all__ = ["PlayerMetaCommandArgs", "parse_player_meta_args"]

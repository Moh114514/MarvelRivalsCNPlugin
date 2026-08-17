"""Argument parsing for Player × Meta commands."""

from __future__ import annotations

from dataclasses import dataclass

from ..reference.seasons import parse_season_name
from .player_meta import DEFAULT_SIGNATURE_MIN_MATCHES


@dataclass(slots=True)
class PlayerMetaCommandArgs:
    season: str | None = None
    minimum_matches: int = DEFAULT_SIGNATURE_MIN_MATCHES
    uid: str | None = None
    minimum_matches_provided: bool = False


def parse_player_meta_args(
    *parts: str,
    allow_minimum_matches: bool = False,
    allow_uid: bool = False,
) -> PlayerMetaCommandArgs:
    tokens: list[str] = []
    for part in parts:
        if part and str(part).strip():
            tokens.extend(str(part).split())
    season: str | None = None
    minimum_matches = DEFAULT_SIGNATURE_MIN_MATCHES
    minimum_seen = False
    uid: str | None = None
    for token in tokens:
        normalized = token.strip()
        lowered = normalized.lower()
        explicit_uid = None
        for prefix in ("uid:", "uid=", "playeruid:", "playeruid="):
            if lowered.startswith(prefix):
                explicit_uid = normalized[len(prefix):].strip()
                if not explicit_uid.isdigit():
                    raise ValueError("UID 必须是数字")
                break
        if explicit_uid is not None:
            if not allow_uid:
                raise ValueError("当前命令不支持 UID 参数")
            if uid is not None:
                raise ValueError("只能指定一个 UID")
            uid = explicit_uid
            continue
        try:
            parse_season_name(normalized)
        except ValueError:
            if allow_uid and normalized.isdigit() and (
                not allow_minimum_matches or len(normalized) >= 6
            ):
                if uid is not None:
                    raise ValueError("只能指定一个 UID")
                uid = normalized
                continue
            if allow_minimum_matches and normalized.isdigit() and not minimum_seen:
                minimum_matches = int(normalized)
                minimum_seen = True
                continue
            raise ValueError("参数只支持赛季名称")
        if season is not None:
            raise ValueError("只能指定一个赛季")
        season = normalized
    if minimum_matches < 1:
        raise ValueError("最低场次必须是正整数")
    return PlayerMetaCommandArgs(
        season=season,
        minimum_matches=minimum_matches,
        uid=uid,
        minimum_matches_provided=minimum_seen,
    )


__all__ = ["PlayerMetaCommandArgs", "parse_player_meta_args"]

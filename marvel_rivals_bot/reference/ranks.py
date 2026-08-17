"""Canonical CN and RivalsMeta rank namespaces."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


CN_RANK_LEVEL_MAP: dict[int, str] = {
    1: "青铜3",
    2: "青铜2",
    3: "青铜1",
    4: "白银3",
    5: "白银2",
    6: "白银1",
    7: "黄金3",
    8: "黄金2",
    9: "黄金1",
    10: "铂金3",
    11: "铂金2",
    12: "铂金1",
    13: "钻石3",
    14: "钻石2",
    15: "钻石1",
    16: "大师3",
    17: "大师2",
    18: "大师1",
    19: "天神3",
    20: "天神2",
    21: "天神1",
    22: "永恒",
    23: "万物之上",
}

CN_RANK_LEVEL_TO_META_RANK: dict[int, str] = {
    **{level: "1" for level in range(1, 4)},
    **{level: "2" for level in range(4, 7)},
    **{level: "3" for level in range(7, 10)},
    **{level: "4" for level in range(10, 13)},
    **{level: "5" for level in range(13, 16)},
    **{level: "6" for level in range(16, 19)},
    **{level: "9" for level in range(19, 22)},
    22: "7",
    23: "8",
}


META_RANK_LABELS: dict[str, str] = {
    "1": "青铜",
    "2": "白银",
    "3": "黄金",
    "4": "白金",
    "5": "钻石",
    "6": "大师",
    "9": "天神",
    "7": "永恒",
    "8": "万物之上",
}

META_RANK_ORDER: tuple[str, ...] = ("1", "2", "3", "4", "5", "6", "9", "7", "8")

_META_RANK_ALIASES: dict[str, str] = {
    "all": "all",
    "allranks": "all",
    "allrank": "all",
    "全部": "all",
    "全段位": "all",
    "全段": "all",
    "所有段位": "all",
    "bronze": "1",
    "青铜": "1",
    "silver": "2",
    "白银": "2",
    "gold": "3",
    "黄金": "3",
    "platinum": "4",
    "plat": "4",
    "白金": "4",
    "铂金": "4",
    "diamond": "5",
    "钻石": "5",
    "grandmaster": "6",
    "grand master": "6",
    "大师": "6",
    "宗师": "6",
    "celestial": "9",
    "天神": "9",
    "eternity": "7",
    "永恒": "7",
    "oneaboveall": "8",
    "one above all": "8",
    "万物之上": "8",
    "至高无上": "8",
    "diamond+": "diamond+",
    "钻石+": "diamond+",
    "grandmaster+": "grandmaster+",
    "grand master+": "grandmaster+",
    "大师+": "grandmaster+",
    "宗师+": "grandmaster+",
    "celestial+": "celestial+",
    "天神+": "celestial+",
    "eternity+": "eternity+",
    "永恒+": "eternity+",
}

META_RANK_ALIASES = _META_RANK_ALIASES

META_RANK_GROUPS: dict[str, tuple[str, ...]] = {
    "diamond+": ("5", "6", "9", "7", "8"),
    "grandmaster+": ("6", "9", "7", "8"),
    "celestial+": ("9", "7", "8"),
    "eternity+": ("7", "8"),
}


@dataclass(frozen=True, slots=True)
class RankIdentity:
    """Canonical broad-rank identity with its CN detailed levels."""

    canonical_name: str
    meta_code: str
    cn_levels: tuple[int, ...] = ()
    aliases: tuple[str, ...] = ()

    @classmethod
    def from_meta(cls, value: str | int = "all") -> "RankIdentity":
        return rank_identity(value)

    @classmethod
    def from_cn_level(cls, level: Any) -> "RankIdentity":
        identity = rank_identity_from_cn_level(level)
        if identity is None:
            raise ValueError(f"未知国服段位等级：{level}")
        return identity

    def for_provider(self, provider: str) -> str | tuple[int, ...]:
        if provider in {"rivalsmeta", "meta"}:
            return self.meta_code
        if provider == "cn":
            return self.cn_levels
        raise ValueError(f"未知段位数据源：{provider}")

# Compatibility names retained for the old Meta module API.
RANK_LABELS = META_RANK_LABELS
RANK_ORDER = META_RANK_ORDER
RANK_GROUPS = META_RANK_GROUPS
ALL_RANKS_KEY = "all"


def _normalize(value: str) -> str:
    return re.sub(r"[\s_-]+", "", str(value).strip().lower())


def meta_rank_from_cn_level(level: Any) -> str | None:
    """Map a CN API rank level to its canonical Meta rank code."""

    try:
        normalized = int(level)
    except (TypeError, ValueError):
        return None
    return CN_RANK_LEVEL_TO_META_RANK.get(normalized)


meta_rank_code_from_cn_level = meta_rank_from_cn_level
cn_level_to_meta_rank = meta_rank_from_cn_level
cn_rank_level_to_meta_rank = meta_rank_from_cn_level
CN_TO_META_RANK = CN_RANK_LEVEL_TO_META_RANK


def cn_rank_label(level: Any, fallback: str | None = None) -> str:
    try:
        normalized = int(level)
    except (TypeError, ValueError):
        return fallback or "未知段位"
    return CN_RANK_LEVEL_MAP.get(normalized, fallback or f"等级 {normalized}")


def rank_identity(value: str | int = ALL_RANKS_KEY) -> RankIdentity:
    key = normalize_rank(value)
    if key == ALL_RANKS_KEY or key in META_RANK_GROUPS:
        return RankIdentity(rank_label(key), key, aliases=())
    levels = tuple(level for level, code in CN_RANK_LEVEL_TO_META_RANK.items() if code == key)
    return RankIdentity(
        canonical_name=META_RANK_LABELS[key],
        meta_code=key,
        cn_levels=levels,
        aliases=tuple(alias for alias, alias_code in _META_RANK_ALIASES.items() if alias_code == key),
    )


def rank_identity_from_cn_level(level: Any) -> RankIdentity | None:
    code = meta_rank_from_cn_level(level)
    return rank_identity(code) if code is not None else None


def normalize_rank(value: str | int) -> str:
    """Return a canonical Meta rank key, rejecting diagnostic rank ``0``."""

    text = _normalize(value)
    if text == "0":
        raise ValueError("rank=0 仅保留在原始数据中，不能作为有效段位查询")
    if text in RANK_LABELS:
        return text
    alias = _META_RANK_ALIASES.get(text)
    if alias is not None:
        return alias
    raise ValueError(f"未知段位：{value}")


def rank_codes(value: str | int = "all") -> tuple[str, ...]:
    """Resolve a user rank selection to valid API rank codes in game order."""

    key = normalize_rank(value)
    if key == ALL_RANKS_KEY:
        return RANK_ORDER
    if key in RANK_GROUPS:
        return RANK_GROUPS[key]
    return (key,)


def rank_label(value: str | int = ALL_RANKS_KEY) -> str:
    key = normalize_rank(value)
    if key == ALL_RANKS_KEY:
        return "全段位"
    if key in RANK_GROUPS:
        return {
            "diamond+": "钻石+",
            "grandmaster+": "大师+",
            "celestial+": "天神+",
            "eternity+": "永恒+",
        }[key]
    return RANK_LABELS[key]


resolve_rank_codes = rank_codes
get_rank_label = rank_label


__all__ = [
    "ALL_RANKS_KEY",
    "CN_RANK_LEVEL_MAP",
    "CN_RANK_LEVEL_TO_META_RANK",
    "CN_TO_META_RANK",
    "cn_level_to_meta_rank",
    "cn_rank_level_to_meta_rank",
    "cn_rank_label",
    "META_RANK_ALIASES",
    "META_RANK_GROUPS",
    "META_RANK_LABELS",
    "META_RANK_ORDER",
    "RankIdentity",
    "RANK_GROUPS",
    "RANK_LABELS",
    "RANK_ORDER",
    "get_rank_label",
    "meta_rank_code_from_cn_level",
    "meta_rank_from_cn_level",
    "normalize_rank",
    "rank_codes",
    "rank_identity",
    "rank_identity_from_cn_level",
    "rank_label",
    "resolve_rank_codes",
]

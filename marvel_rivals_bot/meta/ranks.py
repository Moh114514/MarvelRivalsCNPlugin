from __future__ import annotations

import re


RANK_LABELS: dict[str, str] = {
    "1": "青铜",
    "2": "白银",
    "3": "黄金",
    "4": "铂金",
    "5": "钻石",
    "6": "大师",
    "9": "天神",
    "7": "永恒",
    "8": "万物之上",
}

RANK_ORDER: tuple[str, ...] = ("1", "2", "3", "4", "5", "6", "9", "7", "8")

_ALIASES: dict[str, str] = {
    "all": "all",
    "allranks": "all",
    "allrank": "all",
    "allranks": "all",
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
    "铂金": "4",
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

_COMPOSITES: dict[str, tuple[str, ...]] = {
    "diamond+": ("5", "6", "9", "7", "8"),
    "grandmaster+": ("6", "9", "7", "8"),
    "celestial+": ("9", "7", "8"),
    "eternity+": ("7", "8"),
}

# Public names used by MetaService and tests. Rank 0 is deliberately absent.
RANK_GROUPS = _COMPOSITES
ALL_RANKS_KEY = "all"


def _normalize(value: str) -> str:
    return re.sub(r"[\s_-]+", "", str(value).strip().lower())


def normalize_rank(value: str | int) -> str:
    """Return a canonical rank key, rejecting diagnostic rank ``0``."""

    text = _normalize(value)
    if text == "0":
        raise ValueError("rank=0 仅保留在原始数据中，不能作为有效段位查询")
    if text in RANK_LABELS:
        return text
    alias = _ALIASES.get(text)
    if alias is not None:
        return alias
    if text.endswith("+"):
        alias = _ALIASES.get(text)
        if alias is not None:
            return alias
    raise ValueError(f"未知段位：{value}")


def rank_codes(value: str | int = "all") -> tuple[str, ...]:
    """Resolve a user rank selection to valid API rank codes in game order."""

    key = normalize_rank(value)
    if key == "all":
        return RANK_ORDER
    if key in _COMPOSITES:
        return _COMPOSITES[key]
    return (key,)


def rank_label(value: str | int = "all") -> str:
    key = normalize_rank(value)
    if key == "all":
        return "全段位"
    if key in _COMPOSITES:
        return {
            "diamond+": "钻石+",
            "grandmaster+": "大师+",
            "celestial+": "天神+",
            "eternity+": "永恒+",
        }[key]
    return RANK_LABELS[key]


# Names that make the public interface convenient for MetaService.
resolve_rank_codes = rank_codes
get_rank_label = rank_label

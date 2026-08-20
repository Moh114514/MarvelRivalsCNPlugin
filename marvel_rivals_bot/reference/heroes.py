"""Canonical hero identities and compatibility-friendly name helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import unicodedata


@dataclass(frozen=True, slots=True)
class HeroIdentity:
    hero_id: int | None
    name: str
    role: str | None = None
    aliases: tuple[str, ...] = ()

    @classmethod
    def from_id(cls, hero_id: Any, fallback: str | None = None) -> "HeroIdentity":
        return get_hero_identity(hero_id, fallback)

    @property
    def canonical_name(self) -> str:
        return self.name

    @property
    def display_name(self) -> str:
        return self.name


HERO_ID_MAP: dict[int, str] = {
    1011: "浩克",
    1014: "惩罚者",
    1015: "暴风女",
    1016: "洛基",
    1017: "霹雳火",
    1018: "奇异博士",
    1020: "曼蒂斯",
    1021: "鹰眼",
    1022: "美国队长",
    1023: "火箭浣熊",
    1024: "海拉",
    1025: "斗篷与匕首",
    1026: "黑豹",
    1027: "格鲁特",
    1028: "奥创",
    1029: "魔剑客",
    1030: "月光骑士",
    1031: "冰月花雪",
    1032: "松鼠女",
    1033: "黑寡妇",
    1034: "钢铁侠",
    1035: "毒液",
    1036: "蜘蛛侠",
    1037: "万磁王",
    1038: "猩红女巫",
    1039: "索尔",
    1040: "神奇先生",
    1041: "冬兵",
    1042: "潘妮·帕克",
    1043: "星爵",
    1044: "刀锋战士",
    1045: "纳摩",
    1046: "亚当术士",
    1047: "陆行鲨杰夫",
    1048: "灵蝶",
    1049: "金刚狼",
    1050: "隐形女",
    1051: "石头人",
    1052: "铁拳",
    1053: "艾玛·弗斯特",
    1054: "凤凰女",
    1055: "夜魔侠",
    1056: "安吉拉",
    10571: "T位死侍",
    10572: "C位死侍",
    10573: "奶位死侍",
    1058: "牌皇",
    1059: "艾尔莎·血石",
    1060: "白狐",
    1061: "黑猫",
    1062: "恶魔恐龙",
    1063: "镭射眼",
    1064: "李千欢",
    1065: "小淘气",
    1066: "红兜帽",
}


HERO_ROLE_MAP: dict[int, str] = {
    1011: "vanguard",
    1014: "duelist",
    1015: "duelist",
    1016: "strategist",
    1017: "duelist",
    1018: "vanguard",
    1020: "strategist",
    1021: "duelist",
    1022: "vanguard",
    1023: "strategist",
    1024: "duelist",
    1025: "strategist",
    1026: "duelist",
    1027: "vanguard",
    1028: "strategist",
    1029: "duelist",
    1030: "duelist",
    1031: "strategist",
    1032: "duelist",
    1033: "duelist",
    1034: "duelist",
    1035: "vanguard",
    1036: "duelist",
    1037: "vanguard",
    1038: "duelist",
    1039: "vanguard",
    1040: "duelist",
    1041: "duelist",
    1042: "vanguard",
    1043: "duelist",
    1044: "duelist",
    1045: "duelist",
    1046: "strategist",
    1047: "strategist",
    1048: "duelist",
    1049: "duelist",
    1050: "strategist",
    1051: "vanguard",
    1052: "duelist",
    1053: "vanguard",
    1054: "duelist",
    1055: "duelist",
    1056: "vanguard",
    10571: "vanguard",
    10572: "duelist",
    10573: "strategist",
    1058: "strategist",
    1059: "duelist",
    1060: "strategist",
    1061: "duelist",
    1062: "vanguard",
    1063: "duelist",
    1064: "strategist",
    1065: "vanguard",
    1066: "vanguard",
}


HERO_ROLE_LABELS: dict[str, str] = {
    "vanguard": "捍卫者",
    "duelist": "决斗家",
    "strategist": "策略家",
}


# These are intentionally input-only spellings.  ``get_hero_name`` and the
# canonical identity continue to use ``HERO_ID_MAP`` for display.
HERO_ALIASES: dict[int, tuple[str, ...]] = {
    1011: ("绿巨人","捣蛋猪"),
    1014: ("罚叔","惩罚"),
    1015: ("风暴女", "风暴","风女"),
    1017: ("火人","火男"),
    1018: ("奇异", "奇博","博士"),
    1020: ("螳螂","虫女"),
    1022: ("美队",),
    1023: ("火箭","浣熊"),
    1025: ("斗篷", "匕首","斗匕"),
    1026: ("豹",),
    1027: ("格鲁特", "树人"),
    1029: ("魔剑", "魔剑客"),
    1030: ("月骑",),
    1031: ("冰月","冰女"),
    1033: ("黑寡",),
    1034: ("铁人", "托尼","钢铁侠"),
    1037: ("铁桶僵尸", "万磁王","老万"),
    1038: ("红女巫", "女巫","绯红女巫"),
    1039: ("雷神", "托尔"),
    1040: ("神奇","哈哈男"),
    1041: ("冬日战士",),
    1042: ("潘妮", "P妮","蜘蛛女"),
    1044: ("刀锋","刀哥"),
    1045: ("海王","章鱼哥"),
    1046: ("亚当","亚亚"),
    1047: ("杰夫", "陆行鲨", "鲨鱼", "鲨狗","Jeff","jeff"),
    1049: ("狼叔",),
    1050: ("苏珊","你臀","臀臀"),
    1051: ("本","本叔叔"),
    1052: ("林烈", "铁拳"),
    1053: ("艾玛","白皇后","白皇"),
    1054: ("琴", "琴格雷", "凤凰"),
    1055: ("超胆侠", "夜魔","马律师"),
    1056: ("安吉拉", "天使","鸟人"),
    10571: ("T死侍", "坦克死侍", "死侍T", "死侍T位","T侍"),
    10572: ("C死侍", "输出死侍", "输出位死侍", "死侍C", "死侍C位", "C侍", "c4"),
    10573: ("奶死侍", "辅助死侍", "辅助位死侍", "死侍奶", "死侍奶位", "奶侍"),
    1059: ("艾尔莎", "艾莎", "血石"),
    1060: ("狐狸",),
    1061: ("菲丽西亚",),
    1062: ("恐龙",),
    1063: ("镭射","雷光眼"),
    1065: ("罗刹女",),
}


HERO_AMBIGUOUS_ALIASES: dict[str, tuple[int, ...]] = {
    "死侍": (10571, 10572, 10573),
}


def _normalize_hero_name(name: str) -> str:
    text = unicodedata.normalize("NFKC", str(name)).strip().lower()
    return "".join(character for character in text if character.isalnum())


_HERO_NAME_CANDIDATES: dict[str, set[int]] = {}
for _hero_id, _name in HERO_ID_MAP.items():
    _HERO_NAME_CANDIDATES.setdefault(_normalize_hero_name(_name), set()).add(_hero_id)
for _hero_id, _aliases in HERO_ALIASES.items():
    if not isinstance(_aliases, tuple):
        raise TypeError(f"HERO_ALIASES[{_hero_id}] 必须是 tuple[str, ...]")
    for _alias in _aliases:
        _HERO_NAME_CANDIDATES.setdefault(_normalize_hero_name(_alias), set()).add(_hero_id)

HERO_ALIAS_CONFLICTS: dict[str, tuple[int, ...]] = {
    _name: tuple(sorted(_hero_ids))
    for _name, _hero_ids in _HERO_NAME_CANDIDATES.items()
    if len(_hero_ids) > 1
}
if HERO_ALIAS_CONFLICTS:
    raise ValueError(f"英雄名称或别称存在冲突: {HERO_ALIAS_CONFLICTS}")

HERO_NAME_ID_MAP: dict[str, int] = {
    _name: next(iter(_hero_ids))
    for _name, _hero_ids in _HERO_NAME_CANDIDATES.items()
}

_HERO_AMBIGUOUS_NAME_MAP = {
    _normalize_hero_name(name): hero_ids
    for name, hero_ids in HERO_AMBIGUOUS_ALIASES.items()
}


class HeroNameAmbiguityError(ValueError):
    """Raised when an input name maps to more than one hero identity."""


def get_hero_id(hero_name: str) -> int:
    value = str(hero_name).strip()
    if not value or value.isdigit():
        raise ValueError("请直接输入英雄的中文名称，例如：蜘蛛侠")
    normalized = _normalize_hero_name(value)
    ambiguous = _HERO_AMBIGUOUS_NAME_MAP.get(normalized)
    if ambiguous is not None:
        names = "、".join(get_hero_name(hero_id) for hero_id in ambiguous)
        raise HeroNameAmbiguityError(
            f"英雄名称“{value}”存在歧义，请指定职责（{names}）"
        )
    hero_id = HERO_NAME_ID_MAP.get(normalized)
    if hero_id is None:
        raise ValueError(f"未找到英雄“{value}”，请检查并输入完整中文名称")
    return hero_id


def get_hero_name(hero_id: Any, fallback: str | None = None) -> str:
    try:
        normalized = int(hero_id)
    except (TypeError, ValueError):
        return fallback or "未知英雄"
    return HERO_ID_MAP.get(normalized, fallback or f"英雄 {normalized}")


def get_hero_identity(hero_id: Any, fallback: str | None = None) -> HeroIdentity:
    if isinstance(hero_id, str) and not hero_id.strip().isdigit():
        try:
            hero_id = get_hero_id(hero_id)
        except HeroNameAmbiguityError:
            raise
        except ValueError:
            return HeroIdentity(hero_id=None, name=fallback or "未知英雄")
    try:
        normalized = int(hero_id)
    except (TypeError, ValueError):
        return HeroIdentity(hero_id=None, name=fallback or "未知英雄")
    return HeroIdentity(
        hero_id=normalized,
        name=get_hero_name(normalized, fallback),
        role=HERO_ROLE_MAP.get(normalized),
        aliases=HERO_ALIASES.get(normalized, ()),
    )


def format_hero_name(hero_id: Any, fallback: str | None = None) -> str:
    name = get_hero_name(hero_id, fallback)
    try:
        normalized = int(hero_id)
    except (TypeError, ValueError):
        return name
    return f"{name}（{normalized}）"


__all__ = [
    "HERO_ID_MAP",
    "HERO_ROLE_MAP",
    "HERO_ROLE_LABELS",
    "HERO_ALIASES",
    "HERO_ALIAS_CONFLICTS",
    "HERO_AMBIGUOUS_ALIASES",
    "HERO_NAME_ID_MAP",
    "HeroIdentity",
    "HeroNameAmbiguityError",
    "format_hero_name",
    "get_hero_id",
    "get_hero_identity",
    "get_hero_name",
]

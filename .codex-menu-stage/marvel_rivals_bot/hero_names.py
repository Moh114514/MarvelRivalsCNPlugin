from __future__ import annotations

from typing import Any


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


def _normalize_hero_name(name: str) -> str:
    return "".join(str(name).strip().lower().replace("＆", "&").split()).replace("·", "").replace(".", "")


HERO_NAME_ID_MAP: dict[str, int] = {
    _normalize_hero_name(name): hero_id for hero_id, name in HERO_ID_MAP.items()
}


def get_hero_id(hero_name: str) -> int:
    value = str(hero_name).strip()
    if not value or value.isdigit():
        raise ValueError("请直接输入英雄的中文名称，例如：蜘蛛侠")
    hero_id = HERO_NAME_ID_MAP.get(_normalize_hero_name(value))
    if hero_id is None:
        raise ValueError(f"未找到英雄“{value}”，请检查并输入完整中文名称")
    return hero_id


def get_hero_name(hero_id: Any, fallback: str | None = None) -> str:
    try:
        normalized = int(hero_id)
    except (TypeError, ValueError):
        return fallback or "未知英雄"
    return HERO_ID_MAP.get(normalized, fallback or f"英雄 {normalized}")


def format_hero_name(hero_id: Any, fallback: str | None = None) -> str:
    name = get_hero_name(hero_id, fallback)
    try:
        normalized = int(hero_id)
    except (TypeError, ValueError):
        return name
    return f"{name}（{normalized}）"

"""Stable, presentation-only labels for the Rating V2 product surface.

The helpers in this module deliberately do not participate in rating,
classification, sorting, or cache decisions.  They turn the already computed
archetype and rating fields into user-facing labels.
"""

from __future__ import annotations

from ...reference.heroes import HERO_ROLE_MAP


ROLE_LABELS = {
    "vanguard": "捍卫者",
    "duelist": "决斗家",
    "strategist": "策略家",
}

STYLE_LABELS = {
    "dive": "切入",
    "brawl": "缠斗",
    "poke": "消耗",
}

FUNCTION_LABELS = {
    "assassin": "刺杀终结",
    "skirmisher": "游击",
    "pick": "抓单",
    "pressure": "持续压制",
    "bruiser": "斗士",
    "tank_buster": "坦克克制",
    "anchor": "锚定防守",
    "zone": "区域控制",
    "initiator": "开团切入",
    "utility": "功能支援",
    "support": "后排支援",
}


def archetype_labels(archetype) -> tuple[str, str, str]:
    """Return ``(official_role, combat_style, tactical_function)`` labels."""

    if archetype is None:
        return "未知职责", "未知风格", "未知战术职责"
    try:
        role_key = HERO_ROLE_MAP.get(int(archetype.hero_id))
    except (AttributeError, TypeError, ValueError):
        role_key = None
    role = ROLE_LABELS.get(role_key, "未知职责")
    style = STYLE_LABELS.get(getattr(archetype.primary_style, "value", ""), "未知风格")
    function = FUNCTION_LABELS.get(getattr(archetype.function, "value", ""), "未知战术职责")
    return role, style, function


def archetype_summary(archetype) -> str:
    role, style, function = archetype_labels(archetype)
    return f"{role} · {style} · {function}"


def product_status(rating) -> str:
    """Return a display label without changing the computed classification.

    Signature/sickness and season classifications remain authoritative.  The
    remaining common-hero bucket is only split for presentation clarity.
    """

    classification = str(getattr(rating, "classification", "常用英雄") or "常用英雄")
    if (
        classification in {"招牌绝活", "强势绝活", "潜力绝活", "绝症候选", "待验证"}
        or classification.startswith("赛季")
    ):
        return classification
    try:
        confidence = float(getattr(rating, "confidence", 0.0) or 0.0)
        performance = float(getattr(rating, "performance", 50.0) or 50.0)
        mastery = float(getattr(rating, "mastery", 50.0) or 50.0)
    except (TypeError, ValueError):
        return classification
    if confidence < 0.55:
        return "低样本"
    if performance <= 45.0:
        return "相对弱势"
    if performance >= 65.0:
        return "强势英雄"
    if mastery >= 68.0:
        return "高熟练英雄"
    return "常用英雄"


__all__ = [
    "FUNCTION_LABELS",
    "ROLE_LABELS",
    "STYLE_LABELS",
    "archetype_labels",
    "archetype_summary",
    "product_status",
]

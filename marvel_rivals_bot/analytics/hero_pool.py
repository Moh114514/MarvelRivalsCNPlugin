"""Hero-pool structure derived from one cached PlayerCareerAnalysis."""

from __future__ import annotations

from collections.abc import Iterable

from ..reference.heroes import HERO_ROLE_MAP
from .archetypes import get_archetype
from .models import CareerHeroSignature, HeroPoolAnalysis, PlayerCareerAnalysis


def _usage_sorted(heroes: Iterable[CareerHeroSignature]) -> list[CareerHeroSignature]:
    return sorted(
        heroes,
        key=lambda item: (
            -float(item.usage_share or 0.0),
            -float(item.play_index or 0.0),
            -int(item.total_matches or 0),
            str(item.hero_id),
        ),
    )


def _share(value: int, total: int) -> float:
    return value * 100 / total if total else 0.0


def _structure_tags(
    *,
    ordered: list[CareerHeroSignature],
    top1: float,
    top3: float,
    width: float,
    roles: dict[str, float],
    positive: float,
    negative: float,
) -> tuple[str, ...]:
    tags: list[str] = []
    top2 = sum(item.usage_share for item in ordered[:2])
    if top1 >= 45:
        tags.append("单核专精")
    elif top2 >= 65:
        tags.append("双核体系")
    if top3 >= 75:
        tags.append("集中型英雄池")
    if width >= 4 and top3 < 70:
        tags.append("多核英雄池")
    role_names = {
        "vanguard": "捍卫者",
        "duelist": "决斗家",
        "strategist": "策略家",
    }
    dominant = max(roles, key=roles.get, default=None)
    if dominant is not None and roles[dominant] >= 70:
        tags.append(f"职责偏科：{role_names[dominant]}")
    if roles and all(value >= 20 for value in roles.values()):
        tags.append("职责覆盖均衡")
    if negative >= 25:
        tags.append("高使用量短板较多")
    if positive >= 60:
        tags.append("核心英雄质量较高")
    return tuple(tags)


def build_hero_pool_analysis(profile: PlayerCareerAnalysis) -> HeroPoolAnalysis:
    heroes = [item for item in profile.heroes if int(item.total_matches or 0) > 0]
    ordered = _usage_sorted(heroes)
    total_matches = sum(max(0, int(item.total_matches or 0)) for item in heroes)
    top1_share = ordered[0].usage_share if ordered else 0.0
    top3_share = sum(item.usage_share for item in ordered[:3])
    proportions = [item.usage_share / 100 for item in heroes if item.usage_share > 0]
    effective_width = 1 / sum(value * value for value in proportions) if proportions else 0.0

    role_matches = {role: 0 for role in ("vanguard", "duelist", "strategist")}
    for item in heroes:
        try:
            role = HERO_ROLE_MAP.get(int(item.hero_id))
        except (TypeError, ValueError):
            role = None
        if role in role_matches:
            role_matches[role] += int(item.total_matches or 0)
    role_shares = {role: _share(matches, total_matches) for role, matches in role_matches.items()}
    style_matches: dict[str, int] = {}
    profile_matches: dict[str, int] = {}
    for item in heroes:
        archetype = get_archetype(item.hero_id)
        if archetype is None:
            continue
        style = archetype.primary_style.value
        profile_id = archetype.metric_profile.value
        matches = int(item.total_matches or 0)
        style_matches[style] = style_matches.get(style, 0) + matches
        profile_matches[profile_id] = profile_matches.get(profile_id, 0) + matches
    style_shares = {key: _share(value, total_matches) for key, value in style_matches.items()}
    profile_shares = {key: _share(value, total_matches) for key, value in profile_matches.items()}
    tactical_tags: list[str] = []
    if style_shares:
        dominant_style, dominant_share = max(style_shares.items(), key=lambda pair: pair[1])
        style_labels = {"dive": "突袭", "brawl": "近战", "poke": "远程压制"}
        if dominant_share >= 55:
            tactical_tags.append(f"{style_labels.get(dominant_style, dominant_style)}体系偏重")
    if len([value for value in profile_shares.values() if value >= 15]) == 1:
        tactical_tags.append("单一战术体系")
    elif len([value for value in profile_shares.values() if value >= 15]) >= 4:
        tactical_tags.append("多战术体系")

    weighted_numerator = 0.0
    weighted_denominator = 0.0
    positive_usage = 0.0
    negative_usage = 0.0
    for item in heroes:
        if getattr(item, "is_analysis_eligible", False) and item.performance_index >= 10:
            positive_usage += float(item.usage_share or 0.0)
        if getattr(item, "is_analysis_eligible", False) and item.performance_index <= -10:
            negative_usage += float(item.usage_share or 0.0)
        weight = (item.usage_share / 100) * float(item.evidence_factor or 0.0)
        weighted_numerator += float(item.performance_index or 0.0) * weight
        weighted_denominator += weight

    core = tuple(
        item for item in ordered
        if item.usage_share >= 5 or item.play_index >= 30
    )[:10]
    positive_share = positive_usage
    negative_share = negative_usage
    tags = _structure_tags(
        ordered=ordered,
        top1=top1_share,
        top3=top3_share,
        width=effective_width,
        roles=role_shares,
        positive=positive_share,
        negative=negative_share,
    )
    return HeroPoolAnalysis(
        uid=profile.uid,
        player_name=profile.player_name,
        scope=profile.scope,
        total_matches=total_matches,
        active_heroes=len(heroes),
        core_heroes=core,
        top1_share=top1_share,
        top3_share=top3_share,
        effective_pool_width=effective_width,
        vanguard_share=role_shares["vanguard"],
        duelist_share=role_shares["duelist"],
        strategist_share=role_shares["strategist"],
        weighted_performance=(weighted_numerator / weighted_denominator if weighted_denominator else None),
        positive_usage_share=positive_share,
        negative_usage_share=negative_share,
        structure_tags=tags,
        meta_available=profile.meta_available,
        meta_stale=profile.meta_stale,
        style_shares=style_shares,
        profile_shares=profile_shares,
        tactical_tags=tuple(tactical_tags),
    )


__all__ = ["build_hero_pool_analysis"]

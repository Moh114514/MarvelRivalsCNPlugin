"""Leave-one-out specialization and V2 classifications."""

from __future__ import annotations

from dataclasses import replace

from .models import HeroRatingResult


def apply_specialization(results: dict[str, HeroRatingResult]) -> dict[str, HeroRatingResult]:
    output: dict[str, HeroRatingResult] = {}
    for hero_id, result in results.items():
        peers = [item for key, item in results.items() if key != hero_id and item.performance is not None and item.experience >= 20]
        if len(peers) < 3:
            output[hero_id] = result
            continue
        weighted = [(item.performance, item.confidence * max(0.01, item.experience / 100.0)) for item in peers]
        denominator = sum(weight for _value, weight in weighted)
        baseline = sum(value * weight for value, weight in weighted) / denominator if denominator else 50.0
        output[hero_id] = replace(result, specialization=result.performance - baseline)
    return output


def classify_rating(result: HeroRatingResult, *, scope: str = "career") -> str:
    if scope == "season":
        if result.performance >= 85 and result.confidence >= 0.85:
            return "赛季强势"
        if result.performance >= 78 and result.confidence >= 0.70:
            return "赛季表现优秀"
        if result.performance >= 65 and result.confidence < 0.55:
            return "赛季待验证"
        if result.performance <= 35 and result.confidence >= 0.70:
            return "赛季偏弱"
        if result.performance >= 55:
            return "赛季中性"
        return "赛季偏弱"
    spec = result.specialization
    if result.performance <= 35 and spec is not None and spec <= -10 and result.experience >= 20 and result.confidence >= 0.70:
        return "绝症候选"
    if spec is not None and result.mastery >= 85 and spec >= 15 and result.confidence >= 0.85:
        return "招牌绝活"
    if spec is not None and result.mastery >= 78 and spec >= 10 and result.confidence >= 0.70:
        return "强势绝活"
    if spec is not None and result.mastery >= 70 and spec >= 8 and result.confidence >= 0.55:
        return "潜力绝活"
    if result.mastery >= 70 and result.confidence < 0.55:
        return "待验证"
    return "常用英雄"

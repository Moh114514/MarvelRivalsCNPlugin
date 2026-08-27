"""Leave-one-out specialization and V2 classifications."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace

from .models import HeroRatingResult


@dataclass(frozen=True, slots=True)
class SpecializationEvidencePolicy:
    """Configurable evidence gate for leave-one-out specialization."""

    min_confidence: float = 0.55
    min_experience: float = 20.0


@dataclass(frozen=True, slots=True)
class CareerClassificationThresholds:
    """Centralized Career Scope classification thresholds."""

    sickness_performance_max: float = 35.0
    sickness_specialization_max: float = -10.0
    sickness_experience_min: float = 20.0
    sickness_confidence_min: float = 0.70
    signature_mastery_min: float = 85.0
    signature_specialization_min: float = 15.0
    signature_confidence_min: float = 0.85
    strong_mastery_min: float = 78.0
    strong_specialization_min: float = 10.0
    strong_confidence_min: float = 0.70
    potential_mastery_min: float = 68.0
    potential_specialization_min: float = 8.0
    potential_confidence_min: float = 0.55
    unverified_mastery_min: float = 70.0
    unverified_confidence_max: float = 0.55


CAREER_CLASSIFICATION_THRESHOLDS = CareerClassificationThresholds()


def _has_rating_signal(result: HeroRatingResult) -> bool:
    return any(value is not None for value in (result.outcome, result.combat, result.consistency))


def _passes_evidence_gate(result: HeroRatingResult, policy: SpecializationEvidencePolicy) -> bool:
    if not _has_rating_signal(result):
        return False
    return result.confidence >= policy.min_confidence or result.experience >= policy.min_experience


def apply_specialization(
    results: dict[str, HeroRatingResult],
    *,
    evidence_policy: SpecializationEvidencePolicy | None = None,
) -> dict[str, HeroRatingResult]:
    policy = evidence_policy or SpecializationEvidencePolicy()
    output: dict[str, HeroRatingResult] = {}
    for hero_id, result in results.items():
        if not _passes_evidence_gate(result, policy):
            output[hero_id] = replace(result, specialization=None)
            continue
        peers = [item for key, item in results.items() if key != hero_id and item.performance is not None and item.experience >= 20]
        if len(peers) < 3:
            output[hero_id] = result
            continue
        weighted = [(item.performance, item.confidence * max(0.01, item.experience / 100.0)) for item in peers]
        denominator = sum(weight for _value, weight in weighted)
        if denominator <= 1e-9:
            output[hero_id] = replace(result, specialization=None)
            continue
        baseline = sum(value * weight for value, weight in weighted) / denominator
        output[hero_id] = replace(result, specialization=result.performance - baseline)
    return output


def classify_rating(result: HeroRatingResult, *, scope: str = "career") -> str:
    if scope == "season":
        if result.performance >= 85 and result.confidence >= 0.85:
            return "赛季强势"
        if result.performance >= 78 and result.confidence >= 0.70:
            return "赛季表现优秀"
        if 45 <= result.performance <= 55:
            return "赛季中性"
        if result.performance >= 65 and result.confidence < 0.55:
            return "赛季待验证"
        if result.performance < 45 and result.confidence < 0.55:
            return "赛季待验证"
        if result.performance < 45:
            return "赛季偏弱"
        if result.performance > 55:
            return "赛季中性"
        return "赛季偏弱"
    spec = result.specialization
    thresholds = CAREER_CLASSIFICATION_THRESHOLDS
    if (
        result.performance <= thresholds.sickness_performance_max
        and spec is not None
        and spec <= thresholds.sickness_specialization_max
        and result.experience >= thresholds.sickness_experience_min
        and result.confidence >= thresholds.sickness_confidence_min
    ):
        return "绝症候选"
    if (
        spec is not None
        and result.mastery >= thresholds.signature_mastery_min
        and spec >= thresholds.signature_specialization_min
        and result.confidence >= thresholds.signature_confidence_min
    ):
        return "招牌绝活"
    if (
        spec is not None
        and result.mastery >= thresholds.strong_mastery_min
        and spec >= thresholds.strong_specialization_min
        and result.confidence >= thresholds.strong_confidence_min
    ):
        return "强势绝活"
    if (
        spec is not None
        and result.mastery >= thresholds.potential_mastery_min
        and spec >= thresholds.potential_specialization_min
        and result.confidence >= thresholds.potential_confidence_min
    ):
        return "潜力绝活"
    if result.mastery >= thresholds.unverified_mastery_min and result.confidence < thresholds.unverified_confidence_max:
        return "待验证"
    return "常用英雄"

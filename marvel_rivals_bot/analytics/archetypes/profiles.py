"""Cold-start metric profiles shared by heroes with the same tactical job."""

from __future__ import annotations

from .models import MetricDimension, MetricProfile, MetricProfileId


def _profile(
    profile_id: MetricProfileId,
    **weights: int,
) -> MetricProfile:
    return MetricProfile(
        profile_id=profile_id,
        weights=tuple(
            (MetricDimension[name], value / 100)
            for name, value in weights.items()
        ),
    )


METRIC_PROFILES: dict[MetricProfileId, MetricProfile] = {
    MetricProfileId.DIVE_ASSASSIN: _profile(
        MetricProfileId.DIVE_ASSASSIN, FIN=45, PRS=10, SUR=25, TEAM=15, UTIL=5
    ),
    MetricProfileId.MOBILE_SKIRMISHER: _profile(
        MetricProfileId.MOBILE_SKIRMISHER, FIN=25, PRS=25, SUR=25, TEAM=20, UTIL=5
    ),
    MetricProfileId.POKE_PICK: _profile(
        MetricProfileId.POKE_PICK, FIN=35, PRS=30, SUR=20, TEAM=10, UTIL=5
    ),
    MetricProfileId.POKE_PRESSURE: _profile(
        MetricProfileId.POKE_PRESSURE, FIN=15, PRS=45, SUR=15, TEAM=20, UTIL=5
    ),
    MetricProfileId.BRAWL_BRUISER: _profile(
        MetricProfileId.BRAWL_BRUISER, FIN=20, PRS=30, SUR=25, TEAM=20, UTIL=5
    ),
    MetricProfileId.TANK_BUSTER: _profile(
        MetricProfileId.TANK_BUSTER, FIN=15, PRS=45, SUR=20, TEAM=15, UTIL=5
    ),
    MetricProfileId.VANGUARD_ANCHOR: _profile(
        MetricProfileId.VANGUARD_ANCHOR, FIN=5, PRS=10, SUR=25, TEAM=20, FRONT=25, UTIL=15
    ),
    MetricProfileId.VANGUARD_ZONE: _profile(
        MetricProfileId.VANGUARD_ZONE, FIN=5, PRS=20, SUR=20, TEAM=20, FRONT=15, UTIL=20
    ),
    MetricProfileId.VANGUARD_BRAWL: _profile(
        MetricProfileId.VANGUARD_BRAWL, FIN=15, PRS=25, SUR=20, TEAM=15, FRONT=20, UTIL=5
    ),
    MetricProfileId.VANGUARD_DIVE: _profile(
        MetricProfileId.VANGUARD_DIVE, FIN=10, PRS=15, SUR=25, TEAM=20, FRONT=25, UTIL=5
    ),
    MetricProfileId.VANGUARD_PRESSURE: _profile(
        MetricProfileId.VANGUARD_PRESSURE, FIN=10, PRS=30, SUR=20, TEAM=20, FRONT=15, UTIL=5
    ),
    MetricProfileId.BACKLINE_SUPPORT: _profile(
        MetricProfileId.BACKLINE_SUPPORT, FIN=5, PRS=5, SUR=25, TEAM=20, HEAL=35, UTIL=10
    ),
    MetricProfileId.AGGRESSIVE_SUPPORT: _profile(
        MetricProfileId.AGGRESSIVE_SUPPORT, FIN=10, PRS=15, SUR=20, TEAM=20, HEAL=25, UTIL=10
    ),
    MetricProfileId.MOBILE_SUPPORT: _profile(
        MetricProfileId.MOBILE_SUPPORT, FIN=5, PRS=10, SUR=25, TEAM=20, HEAL=30, UTIL=10
    ),
    MetricProfileId.UTILITY_SUPPORT: _profile(
        MetricProfileId.UTILITY_SUPPORT, FIN=5, PRS=10, SUR=20, TEAM=20, HEAL=25, UTIL=20
    ),
}


def validate_metric_profiles() -> None:
    expected = set(MetricProfileId)
    if set(METRIC_PROFILES) != expected:
        raise ValueError("METRIC_PROFILES 必须覆盖全部 MetricProfileId")
    for profile_id, profile in METRIC_PROFILES.items():
        if abs(profile.total_weight - 1.0) > 1e-9:
            raise ValueError(f"{profile_id.value} 的权重总和必须为 1")
        if any(weight < 0 for _dimension, weight in profile.weights):
            raise ValueError(f"{profile_id.value} 不能包含负权重")


validate_metric_profiles()


__all__ = ["METRIC_PROFILES", "validate_metric_profiles"]

"""Experience component based on observable play volume."""

from __future__ import annotations

from .transforms import clamp, saturating


def calculate_experience(
    competitive_matches: int | None,
    competitive_minutes: float | None,
    quick_matches: int | None,
    quick_minutes: float | None,
    active_seasons: int | None,
) -> float:
    total_comp_minutes = max(0.0, float(competitive_minutes or 0.0))
    total_quick_minutes = max(0.0, float(quick_minutes or 0.0))
    score = 100.0 * (
        0.45 * saturating(total_comp_minutes, 300.0)
        + 0.25 * saturating(competitive_matches, 20.0)
        + 0.20 * saturating(total_quick_minutes, 600.0)
        + 0.10 * saturating(active_seasons, 3.0)
    )
    return clamp(score)

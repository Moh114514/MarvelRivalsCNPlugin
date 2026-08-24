"""Season-decay consistency component."""

from __future__ import annotations

from statistics import median

from .transforms import clamp


def calculate_consistency(seasons, *, latest_season_code: str | None = None) -> float | None:
    def effective_matches(item) -> float:
        value = getattr(item, "competitive_effective_matches", None)
        return max(0.0, float(value if value is not None else (getattr(item, "competitive_matches", 0) or 0)))

    rows = [item for item in seasons if getattr(item, "raw_delta", None) is not None and effective_matches(item) > 0]
    if not rows:
        return None
    if len(rows) == 1:
        return 50.0
    latest = int(latest_season_code) if latest_season_code and str(latest_season_code).isdigit() else max(int(getattr(item, "season_code", 0) or 0) for item in rows)
    weighted: list[tuple[float, float]] = []
    for item in rows:
        code = int(getattr(item, "season_code", latest) or latest)
        age = max(0, latest - code)
        weight = min(effective_matches(item), 20.0) * (2 ** (-age / 2))
        weighted.append((float(item.raw_delta), weight))
    denominator = sum(weight for _value, weight in weighted)
    if denominator <= 0:
        return 50.0
    positive_rate = sum(weight for value, weight in weighted if value > 0) / denominator
    center = median([value for value, _weight in weighted])
    mad = median([abs(value - center) for value, _weight in weighted])
    stability = clamp(100.0 - min(100.0, mad * 10.0))
    return clamp(100.0 * (0.7 * positive_rate + 0.3 * stability / 100.0))

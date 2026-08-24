"""Provider feature containers kept separate from the rating dimensions."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FeatureDefinition:
    hero_id: int
    key: str
    label: str | None
    dimension: str
    rating_enabled: bool = False


__all__ = ["FeatureDefinition"]


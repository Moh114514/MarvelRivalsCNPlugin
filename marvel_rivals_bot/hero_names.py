"""Compatibility façade for the canonical hero reference data."""

from .reference.heroes import (
    HERO_ID_MAP,
    HERO_NAME_ID_MAP,
    HeroIdentity,
    format_hero_name,
    get_hero_id,
    get_hero_identity,
    get_hero_name,
)

__all__ = [
    "HERO_ID_MAP",
    "HERO_NAME_ID_MAP",
    "HeroIdentity",
    "format_hero_name",
    "get_hero_id",
    "get_hero_identity",
    "get_hero_name",
]

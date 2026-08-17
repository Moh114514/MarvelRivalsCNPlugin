"""Compatibility façade for canonical Meta rank reference data."""

from ..reference.ranks import (
    ALL_RANKS_KEY,
    META_RANK_GROUPS,
    META_RANK_LABELS,
    META_RANK_ORDER,
    RANK_GROUPS,
    RANK_LABELS,
    RANK_ORDER,
    get_rank_label,
    normalize_rank,
    rank_codes,
    rank_label,
    resolve_rank_codes,
)

__all__ = [
    "ALL_RANKS_KEY",
    "META_RANK_GROUPS",
    "META_RANK_LABELS",
    "META_RANK_ORDER",
    "RANK_GROUPS",
    "RANK_LABELS",
    "RANK_ORDER",
    "get_rank_label",
    "normalize_rank",
    "rank_codes",
    "rank_label",
    "resolve_rank_codes",
]

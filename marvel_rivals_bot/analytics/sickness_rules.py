"""Compatibility facade for the shared negative-performance rules."""

from __future__ import annotations

from .performance import calculate_sickness_score, is_performance_sickness_candidate
from .signature_rules import sickness_severity

__all__ = [
    "calculate_sickness_score",
    "is_performance_sickness_candidate",
    "sickness_severity",
]

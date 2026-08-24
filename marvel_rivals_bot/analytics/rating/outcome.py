"""Outcome component: Meta-relative competitive win-rate delta."""

from __future__ import annotations

import math


def calculate_outcome(delta: float | None, *, scale: float = 8.0) -> float | None:
    if delta is None:
        return None
    adjusted = float(delta)
    return 50.0 + 50.0 * math.tanh(adjusted / scale)

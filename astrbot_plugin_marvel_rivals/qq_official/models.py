from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


@dataclass(frozen=True, slots=True)
class CardButton:
    label: str
    action: Literal["command", "url"]
    data: str
    style: Literal["gray", "blue"] = "gray"


@dataclass(frozen=True, slots=True)
class InteractiveCard:
    markdown: str
    rows: list[list[CardButton]] = field(default_factory=list)

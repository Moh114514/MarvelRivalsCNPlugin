"""Canonical season identities and provider-specific season namespaces."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


SeasonProvider = Literal["cn", "rivalsmeta"]
SEASON_FORMAT_ERROR = "赛季格式错误，请使用 S0、S9、S9.5、S9上半赛季 或 S9下半赛季格式；S0 没有半赛季"

# These are provider translations, not a generic numeric season map.  The
# values currently coincide for the confirmed seasons, but keeping the two
# tables separate prevents a future upstream renumbering from leaking into
# the other provider's request boundary.
CN_SEASON_CODES: dict[str, str] = {
    "S0": "1",
    "S1": "2",
    "S1.5": "3",
    "S2": "4",
    "S2.5": "5",
    "S3": "6",
    "S3.5": "7",
    "S4": "8",
    "S4.5": "9",
    "S5": "10",
    "S5.5": "11",
    "S6": "12",
    "S6.5": "13",
    "S7": "14",
    "S7.5": "15",
    "S8": "16",
    "S8.5": "17",
    "S9": "18",
    "S9.5": "19",
}

RIVALSMETA_SEASON_CODES: dict[str, str] = {
    "S0": "1",
    "S1": "2",
    "S1.5": "3",
    "S2": "4",
    "S2.5": "5",
    "S3": "6",
    "S3.5": "7",
    "S4": "8",
    "S4.5": "9",
    "S5": "10",
    "S5.5": "11",
    "S6": "12",
    "S6.5": "13",
    "S7": "14",
    "S7.5": "15",
    "S8": "16",
    "S8.5": "17",
    "S9": "18",
    "S9.5": "19",
}


@dataclass(frozen=True, slots=True)
class SeasonIdentity:
    canonical_name: str
    cn_code: str
    rivalsmeta_code: str
    display_name: str = ""

    @classmethod
    def from_code(cls, code: str | int, provider: SeasonProvider = "cn") -> "SeasonIdentity":
        return season_identity_from_code(code, provider)

    @classmethod
    def from_name(cls, value: str) -> "SeasonIdentity":
        return season_identity_from_name(value)

    @property
    def label(self) -> str:
        return self.display_name or self.canonical_name

    @property
    def code(self) -> str:
        """Backward-friendly default code; provider code is preferred."""

        return self.cn_code

    def for_provider(self, provider: SeasonProvider) -> str:
        if provider == "cn":
            return self.cn_code
        if provider == "rivalsmeta":
            return self.rivalsmeta_code
        raise ValueError(f"未知赛季数据源：{provider}")


def _display_name(canonical_name: str) -> str:
    if canonical_name == "S0":
        return "S0"
    if canonical_name.endswith(".5"):
        return f"{canonical_name[:-2]}下半赛季"
    return f"{canonical_name}上半赛季"


def _identity_for_canonical(canonical_name: str) -> SeasonIdentity:
    # Unknown future season names retain the established arithmetic fallback;
    # confirmed seasons still use the explicit provider tables above.
    match = re.fullmatch(r"S(0|[1-9]\d*)(?:\.5)?", canonical_name)
    if not match:
        raise ValueError(SEASON_FORMAT_ERROR)
    season = int(match.group(1))
    if canonical_name == "S0":
        derived_code = "1"
    else:
        derived_code = str(season * 2 + (1 if canonical_name.endswith(".5") else 0))
    cn_code = CN_SEASON_CODES.get(canonical_name, derived_code)
    rivalsmeta_code = RIVALSMETA_SEASON_CODES.get(canonical_name, derived_code)
    return SeasonIdentity(canonical_name, cn_code, rivalsmeta_code, _display_name(canonical_name))


def _canonical_from_code(code: str, provider: SeasonProvider) -> str | None:
    table = CN_SEASON_CODES if provider == "cn" else RIVALSMETA_SEASON_CODES
    return next((name for name, provider_code in table.items() if provider_code == code), None)


def season_identity_from_code(code: str | int, provider: SeasonProvider = "cn") -> SeasonIdentity:
    """Resolve an internal numeric code, with its source namespace explicit."""

    value = int(code)
    if value < 1:
        raise ValueError(SEASON_FORMAT_ERROR)
    text = str(value)
    canonical = _canonical_from_code(text, provider)
    if canonical is None:
        # Preserve the old support for future arithmetic season codes while
        # keeping the provider argument explicit at this boundary.
        season = value // 2
        canonical = f"S{season}{'.5' if value % 2 else ''}"
    return _identity_for_canonical(canonical)


def season_identity_from_cn_code(code: str | int) -> SeasonIdentity:
    return season_identity_from_code(code, "cn")


def season_identity_from_rivalsmeta_code(code: str | int) -> SeasonIdentity:
    return season_identity_from_code(code, "rivalsmeta")


def parse_season_name(value: str) -> str:
    """Convert a user-facing season name to the CN API code.

    Raw numeric values intentionally belong to provider-specific internal
    boundaries and are rejected here for command/API compatibility.
    """

    text = str(value).strip()
    if re.fullmatch(r"[sS]0", text):
        return CN_SEASON_CODES["S0"]
    half_match = re.fullmatch(r"[sS]([1-9]\d*)(上|下)半赛季", text)
    if half_match:
        season = int(half_match.group(1))
        canonical = f"S{season}{'.5' if half_match.group(2) == '下' else ''}"
        return _identity_for_canonical(canonical).for_provider("cn")
    short_match = re.fullmatch(r"[sS]([1-9]\d*)(?:\.(5))?", text)
    if short_match:
        season = int(short_match.group(1))
        canonical = f"S{season}{'.5' if short_match.group(2) else ''}"
        return _identity_for_canonical(canonical).for_provider("cn")
    raise ValueError(SEASON_FORMAT_ERROR)


def season_identity_from_name(value: str) -> SeasonIdentity:
    return season_identity_from_code(parse_season_name(value), "cn")


def get_season_identity(value: str | int, provider: SeasonProvider = "cn") -> SeasonIdentity:
    """Resolve a user-facing name or a provider-specific internal code."""

    text = str(value).strip()
    if text.isdigit():
        return season_identity_from_code(text, provider)
    return season_identity_from_name(text)


def format_season_name(code: str | int, provider: SeasonProvider = "cn") -> str:
    """Format a provider-specific numeric code using established labels."""

    value = int(code)
    if 1 <= value:
        return season_identity_from_code(value, provider).label
    # Preserve the legacy arithmetic behavior for invalid/out-of-range codes.
    season = value // 2
    half = "上半赛季" if value % 2 == 0 else "下半赛季"
    return f"S{season}{half}"


RIVALSMETA_SEASON_MAP: dict[int, str] = {
    int(code): canonical for canonical, code in RIVALSMETA_SEASON_CODES.items()
}


__all__ = [
    "CN_SEASON_CODES",
    "RIVALSMETA_SEASON_CODES",
    "RIVALSMETA_SEASON_MAP",
    "SEASON_FORMAT_ERROR",
    "SeasonIdentity",
    "format_season_name",
    "get_season_identity",
    "parse_season_name",
    "season_identity_from_cn_code",
    "season_identity_from_code",
    "season_identity_from_name",
    "season_identity_from_rivalsmeta_code",
]

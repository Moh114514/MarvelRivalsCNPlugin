"""Load the approved Marvel Rivals visual assets as self-contained data URIs."""

from __future__ import annotations

from base64 import b64encode
from pathlib import Path


ASSET_ROOT = Path(__file__).with_name("assets")
PART_NEWS_BACKGROUND = "part-news-bg_ac16ec22.png"
LIST_FRAME = "list-l_8a1441f6.png"
APPROVED_ASSETS = (PART_NEWS_BACKGROUND, LIST_FRAME)


def asset_data_uri(filename: str) -> str:
    """Return a PNG data URI, or an empty string when the optional asset is absent."""

    if filename not in APPROVED_ASSETS:
        return ""
    try:
        payload = (ASSET_ROOT / filename).read_bytes()
    except OSError:
        return ""
    return "data:image/png;base64," + b64encode(payload).decode("ascii")


PART_NEWS_BACKGROUND_URI = asset_data_uri(PART_NEWS_BACKGROUND)
LIST_FRAME_URI = asset_data_uri(LIST_FRAME)

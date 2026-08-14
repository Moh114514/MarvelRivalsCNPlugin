"""HTML page builders for the four image-rendered views."""

from .help import build_help_html
from .hero import build_hero_query_html
from .match_detail import build_match_detail_html
from .player import build_player_stats_html
from .recent import build_recent_matches_html

__all__ = [
    "build_help_html",
    "build_hero_query_html",
    "build_match_detail_html",
    "build_player_stats_html",
    "build_recent_matches_html",
]

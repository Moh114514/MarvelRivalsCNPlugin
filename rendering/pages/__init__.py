"""HTML page builders for the four image-rendered views."""

from .help import build_help_html
from .hero import build_hero_query_html
from .match_detail import build_match_detail_html
from .meta import (
    build_meta_board_html,
    build_meta_comparison_html,
    build_meta_insights_html,
    build_meta_overview_html,
    build_meta_segments_html,
    build_meta_single_html,
    build_meta_trend_html,
    build_meta_version_changes_html,
    build_rank_monsters_html,
)
from .player_meta import (
    build_player_hero_pool_html,
    build_player_meta_environment_html,
)
from .player import build_player_stats_html
from .recent import build_recent_matches_html
from .player_signature import build_player_signature_html

__all__ = [
    "build_help_html",
    "build_hero_query_html",
    "build_match_detail_html",
    "build_meta_board_html",
    "build_meta_comparison_html",
    "build_meta_insights_html",
    "build_meta_overview_html",
    "build_meta_segments_html",
    "build_meta_single_html",
    "build_meta_trend_html",
    "build_meta_version_changes_html",
    "build_rank_monsters_html",
    "build_player_hero_pool_html",
    "build_player_meta_environment_html",
    "build_player_signature_html",
    "build_player_stats_html",
    "build_recent_matches_html",
]

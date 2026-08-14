"""Backward-compatible imports for the pre-PR1 rendering module.

The implementation now lives in focused modules under ``rendering``.  This
shim keeps direct imports from older integrations working during the split.
"""

try:
    from ..marvel_rivals_bot.game_metadata import format_match_map, format_play_mode, format_queue, get_map_mode
    from ..marvel_rivals_bot.hero_names import format_hero_name
    from ..marvel_rivals_bot.models import HeroQueryResult, PlayerStats
    from ..marvel_rivals_bot.services.rivals import format_season_name
except ImportError:
    from marvel_rivals_bot.game_metadata import format_match_map, format_play_mode, format_queue, get_map_mode
    from marvel_rivals_bot.hero_names import format_hero_name
    from marvel_rivals_bot.models import HeroQueryResult, PlayerStats
    from marvel_rivals_bot.services.rivals import format_season_name

from .components import metric_grid
from .formatters import (
    escape_text as _text,
    extract_career as _career,
    extract_first_match as _match,
    format_duration as _duration,
    format_number as _number,
    format_timestamp as _time,
)
from .pages import (
    build_help_html,
    build_hero_query_html,
    build_match_detail_html,
    build_player_stats_html,
    build_recent_matches_html,
)
from .renderer import MatchImageRenderer, RivalsImageRenderer, PNG_OPTIONS
from .theme import STYLE

_STYLE = STYLE
_PNG_OPTIONS = PNG_OPTIONS
_metrics = metric_grid

__all__ = [
    "build_help_html",
    "MatchImageRenderer",
    "RivalsImageRenderer",
    "build_hero_query_html",
    "build_match_detail_html",
    "build_player_stats_html",
    "build_recent_matches_html",
]

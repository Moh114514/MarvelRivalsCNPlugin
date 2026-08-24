"""Pure Player Rating V2 calculations.

The package deliberately has no transport, cache, AstrBot, or rendering
dependencies.  ``signature.py`` adapts its normalized ViewModels into this
engine and keeps the existing public result fields compatible.
"""

from .engine import HeroRatingEngine
from .models import HeroRatingResult, RatingContext, RatingHeroSnapshot

__all__ = ["HeroRatingEngine", "HeroRatingResult", "RatingContext", "RatingHeroSnapshot"]

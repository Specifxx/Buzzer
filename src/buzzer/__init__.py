"""Buzzer: iconic basketball moments as original minimalist data-art posters.

Hard legal constraint, everywhere in this project: rendered output may
contain ONLY factual data (scores, dates, times, city names, distances,
coordinates) — never photos, logos, team marks, player names or likenesses.
See ``buzzer.models`` for how that is enforced at the type level.
"""

from buzzer.detect import detect_moments, scan_season
from buzzer.models import Moment, MomentFacts

__version__ = "0.1.0"

__all__ = ["Moment", "MomentFacts", "detect_moments", "scan_season", "__version__"]

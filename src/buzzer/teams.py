"""City lookup for team tricodes.

Uses nba_api's bundled static team data (no network call). We deliberately
expose ONLY the city: city names are plain geographic facts and are allowed
on posters; team nicknames and full names are trademarks and are not.
"""

from __future__ import annotations

import logging
from functools import cache

logger = logging.getLogger(__name__)

# nba_api's "city" field is sometimes a marketing region, not a city.
# "Golden State" is half a trade name; "Utah"/"Indiana"/"Minnesota" are
# states. Posters may only carry true geographic city names.
CITY_OVERRIDES = {
    "GSW": "San Francisco",
    "UTA": "Salt Lake City",
    "IND": "Indianapolis",
    "MIN": "Minneapolis",
}


@cache
def city_for_tricode(tricode: str) -> str | None:
    """Return the city for a team abbreviation, e.g. ``"POR" -> "Portland"``.

    Returns ``None`` for unknown/historic tricodes rather than guessing.
    """
    if tricode in CITY_OVERRIDES:
        return CITY_OVERRIDES[tricode]
    try:
        from nba_api.stats.static import teams as static_teams
    except ImportError:  # pragma: no cover - nba_api is a hard dependency
        logger.warning("nba_api static team data unavailable; no city for %s", tricode)
        return None

    team = static_teams.find_team_by_abbreviation(tricode)
    if team is None:
        logger.debug("no static team entry for tricode %s", tricode)
        return None
    city = team.get("city")
    return str(city) if city else None

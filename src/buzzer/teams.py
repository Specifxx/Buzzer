"""City lookup for team tricodes.

Uses nba_api's bundled static team data (no network call). We deliberately
expose ONLY the city: city names are plain geographic facts and are allowed
on posters; team nicknames and full names are trademarks and are not.
"""

from __future__ import annotations

import logging
from functools import cache

logger = logging.getLogger(__name__)


@cache
def city_for_tricode(tricode: str) -> str | None:
    """Return the city for a team abbreviation, e.g. ``"POR" -> "Portland"``.

    Returns ``None`` for unknown/historic tricodes rather than guessing.
    """
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

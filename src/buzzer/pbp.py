"""Parse raw PlayByPlayV2 rows into typed events with a running score.

Conventions of the stats.nba.com payload this relies on:
  * ``SCORE`` is the string ``"<away> - <home>"`` and is only populated on
    scoring plays; we carry the last seen value forward.
  * ``PCTIMESTRING`` is ``"MM:SS"`` remaining in the period.
  * ``EVENTMSGTYPE`` 1 is a made field goal.
"""

from __future__ import annotations

import logging
from typing import Any

from buzzer.models import PlayEvent, Side

logger = logging.getLogger(__name__)

EVENT_MADE_FG = 1

# Regulation periods are 12 minutes, overtime periods 5.
REGULATION_PERIODS = 4
PERIOD_SECONDS = 12 * 60
OT_SECONDS = 5 * 60


def parse_clock(pctimestring: str) -> float:
    """``"11:42" -> 702.0`` seconds remaining in the period."""
    minutes, _, seconds = pctimestring.partition(":")
    return int(minutes) * 60 + float(seconds)


def _parse_score(score: str | None) -> tuple[int, int] | None:
    """``"98 - 100" -> (98, 100)`` as (away, home), or None when blank."""
    if not score:
        return None
    away, _, home = score.partition("-")
    try:
        return int(away.strip()), int(home.strip())
    except ValueError:
        logger.warning("unparseable SCORE value: %r", score)
        return None


def parse_play_by_play(rows: list[dict[str, Any]]) -> list[PlayEvent]:
    """Convert raw rows to ``PlayEvent``s, carrying the score forward."""
    events: list[PlayEvent] = []
    away_score = 0
    home_score = 0
    for row in rows:
        parsed = _parse_score(row.get("SCORE"))
        prev_away, prev_home = away_score, home_score
        if parsed is not None:
            away_score, home_score = parsed

        scoring_side: Side | None = None
        points = 0
        if home_score > prev_home:
            scoring_side, points = "home", home_score - prev_home
        elif away_score > prev_away:
            scoring_side, points = "away", away_score - prev_away

        description = " ".join(
            str(row[key]).strip()
            for key in ("HOMEDESCRIPTION", "NEUTRALDESCRIPTION", "VISITORDESCRIPTION")
            if row.get(key)
        )
        events.append(
            PlayEvent(
                event_num=int(row["EVENTNUM"]),
                event_type=int(row["EVENTMSGTYPE"]),
                period=int(row["PERIOD"]),
                clock=str(row["PCTIMESTRING"]),
                seconds_remaining=parse_clock(str(row["PCTIMESTRING"])),
                away_score=away_score,
                home_score=home_score,
                scoring_side=scoring_side,
                points=points,
                is_made_fg=int(row["EVENTMSGTYPE"]) == EVENT_MADE_FG,
                description=description,
                team_tricode=(
                    str(row["PLAYER1_TEAM_ABBREVIATION"])
                    if row.get("PLAYER1_TEAM_ABBREVIATION")
                    else None
                ),
            )
        )
    logger.debug("parsed %d play-by-play events", len(events))
    return events

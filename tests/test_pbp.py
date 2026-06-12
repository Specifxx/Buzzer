from typing import Any

from buzzer.pbp import parse_clock, parse_play_by_play


def _row(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "EVENTNUM": 1,
        "EVENTMSGTYPE": 12,
        "PERIOD": 1,
        "PCTIMESTRING": "12:00",
        "HOMEDESCRIPTION": None,
        "NEUTRALDESCRIPTION": None,
        "VISITORDESCRIPTION": None,
        "SCORE": None,
        "SCOREMARGIN": None,
        "PLAYER1_TEAM_ABBREVIATION": None,
    }
    base.update(overrides)
    return base


def test_parse_clock() -> None:
    assert parse_clock("12:00") == 720.0
    assert parse_clock("0:33") == 33.0
    assert parse_clock("0:00") == 0.0


def test_running_score_and_scoring_side() -> None:
    rows = [
        _row(EVENTNUM=1, EVENTMSGTYPE=12),
        _row(
            EVENTNUM=2,
            EVENTMSGTYPE=1,
            PCTIMESTRING="11:30",
            SCORE="0 - 2",
            HOMEDESCRIPTION="X Dunk",
            PLAYER1_TEAM_ABBREVIATION="AAA",
        ),
        _row(
            EVENTNUM=3, EVENTMSGTYPE=2, PCTIMESTRING="11:00", VISITORDESCRIPTION="MISS Y Jump Shot"
        ),
        _row(
            EVENTNUM=4,
            EVENTMSGTYPE=3,
            PCTIMESTRING="10:40",
            SCORE="1 - 2",
            VISITORDESCRIPTION="Y Free Throw",
        ),
        _row(
            EVENTNUM=5,
            EVENTMSGTYPE=1,
            PCTIMESTRING="10:10",
            SCORE="4 - 2",
            VISITORDESCRIPTION="Y 3PT Shot",
        ),
    ]
    events = parse_play_by_play(rows)
    assert len(events) == 5

    tip, dunk, miss, free_throw, three = events
    assert (tip.away_score, tip.home_score) == (0, 0)
    assert tip.scoring_side is None and tip.points == 0

    assert dunk.is_made_fg
    assert (dunk.scoring_side, dunk.points) == ("home", 2)
    assert (dunk.away_score, dunk.home_score) == (0, 2)

    # Non-scoring events carry the running score forward.
    assert (miss.away_score, miss.home_score) == (0, 2)
    assert miss.scoring_side is None and not miss.is_made_fg

    assert (free_throw.scoring_side, free_throw.points) == ("away", 1)
    assert not free_throw.is_made_fg  # free throws are never moments

    assert (three.scoring_side, three.points) == ("away", 3)
    assert three.is_made_fg
    assert (three.away_score, three.home_score) == (4, 2)
    assert three.seconds_remaining == 610.0

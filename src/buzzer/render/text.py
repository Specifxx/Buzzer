"""Every string a poster may carry is derived here, from MomentFacts only.

All output is factual by construction (numbers, dates, cities, periods)
and additionally validated by ``buzzer.render.validate`` after rendering.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from buzzer.models import MomentFacts

_MONTHS = [
    "JANUARY",
    "FEBRUARY",
    "MARCH",
    "APRIL",
    "MAY",
    "JUNE",
    "JULY",
    "AUGUST",
    "SEPTEMBER",
    "OCTOBER",
    "NOVEMBER",
    "DECEMBER",
]


@dataclass(frozen=True)
class PosterText:
    """Validated, display-ready strings for the templates."""

    date_line: str  # "JUNE 4, 2026"
    period_line: str  # "Q4" / "OT" / "2OT"
    clock_line: str  # "0:01"
    cities_line: str  # "DENVER AT BOSTON"
    score_line: str  # "DENVER 100 — BOSTON 101" (away first)
    stakes_line: str  # "PLAYOFFS" / "REGULAR SEASON"
    story_lines: tuple[str, ...]  # short factual phrases
    distance_line: str  # "27 FT" or ""
    margin_phrase: str  # "BOSTON BY 1" / "TIED 94"
    deficit_value: str  # "13" or ""
    points_value: str  # "3"
    clock_value: str  # alias of clock for the big numerals


def period_display(period: int) -> str:
    if period <= 4:
        return f"Q{period}"
    overtimes = period - 4
    return "OT" if overtimes == 1 else f"{overtimes}OT"


def date_display(iso_date: str) -> str:
    d = date.fromisoformat(iso_date)
    return f"{_MONTHS[d.month - 1]} {d.day}, {d.year}"


def _city(city: str | None, fallback: str) -> str:
    return city.upper() if city else fallback


def margin_phrase(facts: MomentFacts) -> str:
    margin = facts.home_score - facts.away_score
    if margin == 0:
        return f"TIED {facts.home_score}"
    leader = _city(
        facts.home_city if margin > 0 else facts.away_city, "HOME" if margin > 0 else "AWAY"
    )
    return f"{leader} BY {abs(margin)}"


def story_lines(facts: MomentFacts) -> tuple[str, ...]:
    lines: list[str] = []
    if facts.deficit_overcome >= 5 and (facts.takes_lead or facts.ties_game):
        lines.append(f"TRAILED BY {facts.deficit_overcome}")
    if facts.shot_distance_ft is not None and facts.shot_distance_ft >= 1:
        lines.append(f"A {facts.shot_distance_ft:.0f}-FOOT SHOT")
    else:
        lines.append(f"A {facts.points}-POINT FIELD GOAL")
    if facts.takes_lead:
        lines.append("FOR THE LEAD")
    elif facts.ties_game:
        lines.append("TO TIE THE GAME")
    lines.append(f"{facts.clock} ON THE CLOCK")
    return tuple(lines)


def poster_text(facts: MomentFacts) -> PosterText:
    away = _city(facts.away_city, "AWAY")
    home = _city(facts.home_city, "HOME")
    return PosterText(
        date_line=date_display(facts.game_date),
        period_line=period_display(facts.period),
        clock_line=facts.clock,
        cities_line=f"{away} AT {home}",
        score_line=f"{away} {facts.away_score} — {home} {facts.home_score}",
        stakes_line="PLAYOFFS" if facts.is_playoff else "REGULAR SEASON",
        story_lines=story_lines(facts),
        distance_line=(
            f"{facts.shot_distance_ft:.0f} FT" if facts.shot_distance_ft is not None else ""
        ),
        margin_phrase=margin_phrase(facts),
        deficit_value=(
            str(facts.deficit_overcome)
            if facts.deficit_overcome >= 5 and (facts.takes_lead or facts.ties_game)
            else ""
        ),
        points_value=str(facts.points),
        clock_value=facts.clock,
    )

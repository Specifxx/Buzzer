"""Content-safety validation — the legal firewall for rendered output.

Strategy (two independent layers, both must pass):

1. **Input side** — every string template variable is checked against
   blocklists before rendering: league marks, team nicknames and full
   team names (from nba_api static data), full player names (likewise),
   and generic venue words ("Arena", "Garden", ...) that would indicate
   an arena name smuggled into a city field.

2. **Output side** — the rendered SVG is parsed and every alphabetic
   token of every text node must appear on a hand-curated ALLOWLIST of
   factual vocabulary (months, "PLAYOFFS", "CLOCK", ...) or in the city
   names the facts carry. Numbers, dates and punctuation are always
   fine. Anything else — a player name, a nickname, an arena — fails
   closed. The SVG may not embed images or external references at all.

If a poster ever ships with a trademark on it, both layers failed.
"""

from __future__ import annotations

import logging
import re
from functools import cache
from xml.etree import ElementTree

logger = logging.getLogger(__name__)


class ContentViolationError(Exception):
    """Rendered output (or a template variable) violated content rules."""

    def __init__(self, violations: list[str]) -> None:
        self.violations = violations
        super().__init__("content rules violated: " + "; ".join(violations))


# --- vocabulary ------------------------------------------------------------

MONTHS = {
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
}

# Every alphabetic word that may ever appear on a poster. Curated by hand;
# extending it is a deliberate, reviewable act.
ALLOWED_WORDS: frozenset[str] = frozenset(
    MONTHS
    | {
        # game state
        "PLAYOFFS",
        "POSTSEASON",
        "OVERTIME",
        "OT",
        "REGULAR",
        "SEASON",
        "FINAL",
        "SCORE",
        "GAME",
        "PERIOD",
        "QUARTER",
        "CLOCK",
        "TIME",
        "REMAINING",
        "ROUND",
        "TIP",
        "LEFT",
        "BUZZER",
        "FREE",
        "THROW",
        "FIELD",
        "GOAL",
        "SHOT",
        "MADE",
        "POINT",
        "POINTS",
        "POINTER",
        "FOOT",
        "FEET",
        "FT",
        "TRAILED",
        "DEFICIT",
        "COMEBACK",
        "LEAD",
        "TIE",
        "TIED",
        "TIES",
        "AHEAD",
        "GO",
        "UP",
        "DOWN",
        "BY",
        "FOR",
        "THE",
        "OF",
        "ON",
        "AT",
        "IN",
        "TO",
        "AND",
        "A",
        "AN",
        "VS",
        "HOME",
        "AWAY",
        # blueprint / drawing furniture
        "PLAN",
        "VIEW",
        "HALF",
        "COURT",
        "BASELINE",
        "BASKET",
        "BALL",
        "DETAIL",
        "RIM",
        "ORIGIN",
        "COORDINATES",
        "DISTANCE",
        "SCALE",
        "SHEET",
        "TITLE",
        "DATE",
        "LOCATION",
        "DRAWING",
        "NO",
        "DATA",
        "ART",
        "SERIES",
        "MINIMAL",
        "MOMENT",
        "SECOND",
        "SECONDS",
        "MINUTE",
        "MINUTES",
        # listing copy (catalogue titles, descriptions, SEO tags)
        "BEATER",
        "AFTER",
        "TRAILING",
        "THAT",
        "IT",
        "FROM",
        "WITH",
        "TWO",
        "THREE",
        "BASKETBALL",
        "POSTER",
        "PRINT",
        "MINIMALIST",
        "SPORTS",
        "WALL",
        "DECOR",
        "GIFT",
        "CLUTCH",
        # product style names (generic descriptive words)
        "TRAJECTORY",
        "BLUEPRINT",
        "TYPE",
        "STYLE",
        "ORIGINAL",
    }
)

LEAGUE_MARKS = ("NBA", "NATIONAL BASKETBALL ASSOCIATION", "WNBA")

# Generic venue words: any of these inside a supposedly-geographic field
# means an arena name is being smuggled onto a poster.
VENUE_WORDS = frozenset(
    {
        "ARENA",
        "GARDEN",
        "CENTER",
        "CENTRE",
        "FORUM",
        "FIELDHOUSE",
        "COLISEUM",
        "DOME",
        "PAVILION",
        "PALACE",
        "STADIUM",
    }
)

_TOKEN_RE = re.compile(r"[A-Za-z]+")


@cache
def _team_marks() -> frozenset[str]:
    """Team nicknames and full team names, uppercased (offline static data)."""
    from nba_api.stats.static import teams as static_teams

    marks: set[str] = set()
    for team in static_teams.get_teams():
        marks.add(str(team["nickname"]).upper())
        marks.add(str(team["full_name"]).upper())
    return frozenset(marks)


@cache
def _player_names() -> frozenset[str]:
    """All historical player full names, uppercased (offline static data)."""
    from nba_api.stats.static import players as static_players

    return frozenset(str(p["full_name"]).upper() for p in static_players.get_players())


def _tokens(text: str) -> list[str]:
    return [t.upper() for t in _TOKEN_RE.findall(text)]


# --- layer 1: template variable validation ---------------------------------


def validate_text_value(value: str, field: str = "value") -> None:
    """Reject a template variable containing names, nicknames or marks."""
    upper = value.upper()
    violations: list[str] = []

    for mark in LEAGUE_MARKS:
        if mark in _tokens(value) or (len(mark) > 4 and mark in upper):
            violations.append(f"{field}: league mark {mark!r} in {value!r}")

    for token in _tokens(value):
        if token in _team_marks():
            violations.append(f"{field}: team mark {token!r} in {value!r}")
        if token in VENUE_WORDS:
            violations.append(f"{field}: venue word {token!r} in {value!r}")

    for name in _player_names():
        if name in upper:
            violations.append(f"{field}: player name {name!r} in {value!r}")

    if violations:
        raise ContentViolationError(violations)


def validate_listing_text(value: str, allowed_cities: tuple[str | None, ...] = ()) -> None:
    """Validate customer-facing listing copy (titles, descriptions, tags).

    Applies the input blocklists AND the output allowlist: listings are
    public text, so they get the same treatment as poster text.
    """
    validate_text_value(value, field="listing")
    city_words = _allowed_city_words(allowed_cities)
    violations = [
        f"listing token {token!r} not in factual allowlist (in {value!r})"
        for token in _tokens(value)
        if len(token) > 1 and token not in ALLOWED_WORDS and token not in city_words
    ]
    if violations:
        raise ContentViolationError(violations)


# --- layer 2: rendered SVG validation ---------------------------------------


def _allowed_city_words(cities: tuple[str | None, ...]) -> frozenset[str]:
    words: set[str] = set()
    for city in cities:
        if city:
            words.update(_tokens(city))
    return frozenset(words)


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def validate_svg(svg: str, allowed_cities: tuple[str | None, ...] = ()) -> None:
    """Validate a rendered SVG document against the content rules.

    * no embedded images, scripts, foreignObject, or href references
    * every alphabetic token in text content is on the allowlist or part
      of an explicitly allowed city name
    """
    violations: list[str] = []
    try:
        root = ElementTree.fromstring(svg)
    except ElementTree.ParseError as exc:
        raise ContentViolationError([f"not parseable XML: {exc}"]) from exc

    city_words = _allowed_city_words(allowed_cities)
    text_chunks: list[str] = []
    for element in root.iter():
        tag = _local_tag(element.tag)
        if tag in {"image", "script", "foreignobject", "use"}:
            violations.append(f"forbidden element <{tag}>")
        for attr in element.attrib:
            if attr.rsplit("}", 1)[-1].lower() == "href":
                violations.append(f"forbidden reference attribute on <{tag}>")
        if element.text and element.text.strip():
            text_chunks.append(element.text.strip())
        if element.tail and element.tail.strip():
            text_chunks.append(element.tail.strip())

    for chunk in text_chunks:
        for token in _tokens(chunk):
            if len(token) == 1:  # coordinate labels: X, Y, N...
                continue
            if token in ALLOWED_WORDS or token in city_words:
                continue
            violations.append(f"token {token!r} not in factual allowlist (in {chunk!r})")

    if violations:
        logger.error("SVG validation failed: %s", violations)
        raise ContentViolationError(violations)

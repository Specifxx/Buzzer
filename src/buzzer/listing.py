"""Customer-facing listing copy: titles, descriptions, SEO tags.

Built only from MomentFacts and validated through the same content
firewall as poster text — listings are public, so the same trademark
rules apply. Nothing here may name a team, a player, an arena or the
league; cities, dates and numbers carry the story.
"""

from __future__ import annotations

from buzzer.models import MomentFacts
from buzzer.pbp import parse_clock
from buzzer.render.text import date_display, period_display
from buzzer.render.validate import validate_listing_text

BUZZER_WINDOW_S = 1.5


def _is_buzzer(facts: MomentFacts) -> bool:
    return facts.period >= 4 and parse_clock(facts.clock) <= BUZZER_WINDOW_S


def title_for(facts: MomentFacts) -> str:
    if facts.takes_lead and _is_buzzer(facts):
        base = "Buzzer-Beater"
    elif facts.takes_lead:
        base = "The Go-Ahead Shot"
    elif facts.ties_game:
        base = "The Shot That Tied It"
    else:
        base = f"A {facts.points}-Point Shot"

    if facts.shot_distance_ft is not None and facts.shot_distance_ft >= 25:
        base += f" From {facts.shot_distance_ft:.0f} Feet"

    if facts.deficit_overcome >= 8 and (facts.takes_lead or facts.ties_game):
        base = f"Down {facts.deficit_overcome}: {base}"

    where = f"{facts.home_city}, " if facts.home_city else ""
    title = f"{base} — {where}{date_display(facts.game_date).title()}"
    validate_listing_text(title, allowed_cities=(facts.home_city, facts.away_city))
    return title


def description_for(facts: MomentFacts) -> str:
    parts = [f"{period_display(facts.period)}, {facts.clock} remaining."]

    if facts.shot_distance_ft is not None and facts.shot_distance_ft >= 1:
        shot = f"A {facts.shot_distance_ft:.0f}-foot shot"
    else:
        shot = f"A {facts.points}-point shot"
    if facts.takes_lead:
        shot += " for the lead"
    elif facts.ties_game:
        shot += " to tie the game"
    parts.append(shot + ".")

    if facts.deficit_overcome >= 5 and (facts.takes_lead or facts.ties_game):
        parts.append(f"After trailing by {facts.deficit_overcome}.")

    away = facts.away_city or "Away"
    home = facts.home_city or "Home"
    parts.append(f"{away} {facts.away_score}, {home} {facts.home_score}.")
    parts.append(
        f"{'Playoffs' if facts.is_playoff else 'Regular season'}, "
        f"{date_display(facts.game_date).title()}."
    )
    description = " ".join(parts)
    validate_listing_text(description, allowed_cities=(facts.home_city, facts.away_city))
    return description


def tags_for(facts: MomentFacts) -> list[str]:
    tags = [
        "basketball poster",
        "minimalist basketball art",
        "basketball data art",
        "sports wall art",
        "basketball print",
        "basketball gift",
        "clutch shot art",
    ]
    if facts.home_city:
        tags.append(f"{facts.home_city.lower()} basketball art")
    if facts.is_playoff:
        tags.append("playoffs poster")
    if facts.takes_lead and _is_buzzer(facts):
        tags.append("buzzer beater poster")
    if facts.period > 4:
        tags.append("overtime basketball")
    for tag in tags:
        validate_listing_text(tag, allowed_cities=(facts.home_city, facts.away_city))
    return tags

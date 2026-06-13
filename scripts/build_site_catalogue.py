"""Build the static Buzzer Studio site catalogue.

Generates a deterministic set of synthetic-but-plausible playoff moments
(clearly labelled demo data — this environment cannot reach
stats.nba.com), runs each one through the REAL pipeline — scoring,
listing copy, SVG renderer, content firewall — and writes:

    site/posters/<id>_<style>_<size>.svg     (216 files for 36 moments)
    site/catalogue.js                        (window.BUZZER_CATALOGUE = {...})

``catalogue.js`` instead of ``.json`` so the site also works opened
straight from disk (file:// fetch is blocked by browsers).

Usage: uv run python scripts/build_site_catalogue.py [out_dir] [count]
"""

from __future__ import annotations

import json
import math
import random
import sys
from datetime import date
from pathlib import Path
from typing import Any

from buzzer.listing import description_for, tags_for, title_for
from buzzer.models import MomentFacts
from buzzer.pbp import parse_clock
from buzzer.publish.pricing import retail_price_usd
from buzzer.render import STYLES, render_svg
from buzzer.scoring import ScoringInputs, score_moment

SITE_SIZES = ("18x24", "24x36")
PRINT_COSTS = {"12x16": 9.50, "18x24": 13.75, "24x36": 19.00}
SEED = 20260612
MIN_KEEP_SCORE = 55

CITIES = [
    "Atlanta",
    "Boston",
    "Brooklyn",
    "Charlotte",
    "Chicago",
    "Cleveland",
    "Dallas",
    "Denver",
    "Detroit",
    "Houston",
    "Indianapolis",
    "Los Angeles",
    "Memphis",
    "Miami",
    "Milwaukee",
    "Minneapolis",
    "New Orleans",
    "New York",
    "Oklahoma City",
    "Orlando",
    "Philadelphia",
    "Phoenix",
    "Portland",
    "Sacramento",
    "Salt Lake City",
    "San Antonio",
    "San Francisco",
    "Toronto",
    "Washington",
]


def _clock_string(rng: random.Random) -> str:
    bucket = rng.random()
    if bucket < 0.28:
        seconds = rng.choice([0, 0, 1])  # buzzer beaters dominate the catalogue
    elif bucket < 0.60:
        seconds = rng.randint(2, 10)
    elif bucket < 0.85:
        seconds = rng.randint(11, 60)
    else:
        seconds = rng.randint(61, 240)
    return f"{seconds // 60}:{seconds % 60:02d}"


def _shot(rng: random.Random, points: int, clock: str) -> tuple[float, float, float]:
    """(distance_ft, x, y) in shot-chart units, geometrically consistent."""
    if points == 3:
        roll = rng.random()
        if roll < 0.10 and parse_clock(clock) <= 1:
            dist = rng.uniform(40.0, 65.0)  # desperation heave
        elif roll < 0.30:
            dist = rng.uniform(30.0, 38.0)
        elif roll < 0.42:
            dist = rng.uniform(22.0, 23.7)  # corner three
        else:
            dist = rng.uniform(23.8, 29.5)
    else:
        dist = rng.uniform(1.0, 20.0)

    if points == 3 and dist < 23.75:  # corners: pinned to the sideline
        y = rng.uniform(5.0, 85.0)
        x = math.copysign(math.sqrt(max((dist * 10) ** 2 - y**2, 0.0)), rng.uniform(-1, 1))
    else:
        theta = math.radians(rng.uniform(-60.0, 60.0))
        x = dist * 10 * math.sin(theta)
        y = dist * 10 * math.cos(theta)
    return round(dist, 1), round(x, 1), round(y, 1)


def _margins(rng: random.Random, points: int) -> tuple[int, bool, bool]:
    """(margin_before, takes_lead, ties_game), mutually consistent."""
    roll = rng.random()
    if roll < 0.62:  # the shot takes the lead
        margin_before = rng.randint(1 - points, 0)
        return margin_before, True, False
    if roll < 0.82:  # the shot ties it
        return -points, False, True
    margin_before = rng.choice([1, 2, 3, -points - 1, -points - 2])
    return margin_before, False, False


def make_moment(rng: random.Random) -> tuple[MomentFacts, int]:
    period = rng.choices([4, 5, 6], weights=[72, 20, 8])[0]
    clock = _clock_string(rng)
    points = 3 if rng.random() < 0.62 else 2
    dist, x, y = _shot(rng, points, clock)
    margin_before, takes_lead, ties = _margins(rng, points)
    margin_after = margin_before + points

    base = rng.randint(86, 122) + (period - 4) * 7
    team_after, opp_after = base, base - margin_after
    side = rng.choice(["home", "away"])
    home_score, away_score = (team_after, opp_after) if side == "home" else (opp_after, team_after)
    deficit = rng.choices(
        [0, rng.randint(5, 9), rng.randint(10, 16), rng.randint(17, 24)],
        weights=[30, 35, 25, 10],
    )[0]

    year = rng.randint(1996, 2025)
    month = rng.choices([4, 5, 6], weights=[35, 40, 25])[0]
    home, away = rng.sample(CITIES, 2)
    playoff_round = rng.choices([1, 2, 3, 4], weights=[38, 26, 20, 16])[0]
    series_game = rng.choices([1, 2, 3, 4, 5, 6, 7], weights=[10, 11, 12, 13, 13, 15, 26])[0]

    facts = MomentFacts(
        game_date=date(year, month, rng.randint(1, 28)).isoformat(),
        home_city=home,
        away_city=away,
        period=period,
        clock=clock,
        home_score=home_score,
        away_score=away_score,
        scoring_side=side,  # type: ignore[arg-type]
        points=points,
        margin_before=margin_before,
        takes_lead=takes_lead,
        ties_game=ties,
        deficit_overcome=deficit if (takes_lead or ties) else min(deficit, 4),
        is_playoff=True,
        shot_distance_ft=dist,
        shot_x=x,
        shot_y=y,
        playoff_round=playoff_round,
        series_game=series_game,
    )
    score = score_moment(
        ScoringInputs(
            period=period,
            seconds_remaining=parse_clock(clock),
            margin_before=margin_before,
            takes_lead=takes_lead,
            ties_game=ties,
            is_playoff=True,
            deficit_overcome=facts.deficit_overcome,
            shot_distance_ft=dist,
            playoff_round=playoff_round,
            series_game=series_game,
        )
    )
    return facts, score


def _badges(facts: MomentFacts) -> list[str]:
    badges = []
    if facts.series_game == 7:
        badges.append("GAME-7")
    if facts.playoff_round == 4:
        badges.append("ROUND-4")
    if parse_clock(facts.clock) <= 1:
        badges.append("BUZZER")
    if facts.takes_lead:
        badges.append("GO-AHEAD")
    elif facts.ties_game:
        badges.append("TIES-IT")
    if facts.period > 4:
        badges.append("OT" if facts.period == 5 else f"{facts.period - 4}OT")
    if facts.deficit_overcome >= 10 and (facts.takes_lead or facts.ties_game):
        badges.append(f"COMEBACK-{facts.deficit_overcome}")
    if facts.shot_distance_ft is not None and facts.shot_distance_ft >= 30:
        badges.append("DEEP")
    return badges


def build_site(out_dir: Path, count: int = 36, seed: int = SEED) -> dict[str, Any]:
    rng = random.Random(seed)
    kept: list[tuple[MomentFacts, int]] = []
    attempts = 0
    while len(kept) < count and attempts < count * 60:
        attempts += 1
        facts, score = make_moment(rng)
        if score >= MIN_KEEP_SCORE:
            kept.append((facts, score))
    kept.sort(key=lambda pair: pair[1], reverse=True)

    posters_dir = out_dir / "posters"
    posters_dir.mkdir(parents=True, exist_ok=True)

    prices = {size: retail_price_usd(cost, 0.60) for size, cost in PRINT_COSTS.items()}
    entries: list[dict[str, Any]] = []
    for rank, (facts, score) in enumerate(kept, start=1):
        moment_id = f"demo-{rank:03d}"
        files: dict[str, dict[str, str]] = {}
        for style in STYLES:
            files[style] = {}
            for size in SITE_SIZES:
                svg = render_svg(facts, style, size)
                name = f"{moment_id}_{style}_{size}.svg"
                (posters_dir / name).write_text(svg)
                files[style][size] = f"posters/{name}"
        entries.append(
            {
                "id": moment_id,
                "rank": rank,
                "score": score,
                "title": title_for(facts),
                "description": description_for(facts),
                "tags": tags_for(facts),
                "badges": _badges(facts),
                "city": facts.home_city,
                "year": int(facts.game_date[:4]),
                "facts": facts.to_dict(),
                "files": files,
            }
        )
        print(f"  {moment_id}  score {score:3d}  {entries[-1]['title']}")

    catalogue = {
        "generated_for": "Buzzer Studio (demonstration data — synthetic games)",
        "styles": list(STYLES),
        "sizes": list(SITE_SIZES),
        "prices_usd": prices,
        "count": len(entries),
        "moments": entries,
    }
    payload = "window.BUZZER_CATALOGUE = " + json.dumps(catalogue, indent=1) + ";\n"
    (out_dir / "catalogue.js").write_text(payload)
    print(f"wrote {out_dir / 'catalogue.js'} ({len(entries)} moments)")
    return catalogue


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("site")
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 36
    build_site(target, count=n)

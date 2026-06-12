"""Buzzer command-line interface.

Phase 1: ``buzzer scan`` — rank poster-worthy moments for a season or game.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import click

from buzzer.detect import (
    DEFAULT_CACHE_DIR,
    DEFAULT_MIN_SCORE,
    build_source,
    detect_moments,
    find_moment,
)
from buzzer.detect import scan_season as run_scan_season
from buzzer.logsetup import configure_logging
from buzzer.models import Moment

SEASON_RE = re.compile(r"^\d{4}-\d{2}$")


def _format_table(moments: list[Moment]) -> str:
    header = (
        f"{'#':>3}  {'SCORE':>5}  {'MOMENT ID':<17} {'DATE':<10}  "
        f"{'MATCHUP':<11} {'PER':>3}  {'CLOCK':>5}  {'GAME SCORE':<11} NOTES"
    )
    lines = [header, "-" * len(header)]
    for rank, m in enumerate(moments, start=1):
        f = m.facts
        notes = _notes(m)
        lines.append(
            f"{rank:>3}  {m.score:>5}  {m.moment_id:<17} {f.game_date:<10}  "
            f"{m.context.matchup:<11} {f.period:>3}  {f.clock:>5}  "
            f"{f.away_score:>3}-{f.home_score:<3}     {' '.join(notes)}"
        )
    return "\n".join(lines)


def _notes(m: Moment) -> list[str]:
    f = m.facts
    notes = []
    if f.takes_lead:
        notes.append("GO-AHEAD")
    elif f.ties_game:
        notes.append("TIES-IT")
    if f.clock in ("0:00", "0:01"):
        notes.append("BUZZER")
    if f.period > 4:
        notes.append(f"OT{f.period - 4}")
    if f.deficit_overcome >= 8 and (f.takes_lead or f.ties_game):
        notes.append(f"COMEBACK-{f.deficit_overcome}")
    if f.shot_distance_ft is not None and f.shot_distance_ft >= 25:
        notes.append(f"{f.shot_distance_ft:.0f}FT")
    if f.is_playoff:
        notes.append("PLAYOFFS")
    return notes


@click.group()
@click.option("-v", "--verbose", is_flag=True, help="Debug logging.")
def main(verbose: bool) -> None:
    """Buzzer: iconic basketball moments as minimalist data-art posters."""
    configure_logging(verbose)


@main.command()
@click.option("--season", help="Season like 2025-26. Scans every game of the season.")
@click.option("--game", "game_id", help="Single game ID, e.g. 0042500401.")
@click.option("--playoffs", is_flag=True, help="Playoff games only (with --season).")
@click.option("--top", default=20, show_default=True, help="How many moments to show.")
@click.option(
    "--min-score",
    default=DEFAULT_MIN_SCORE,
    show_default=True,
    help="Drop moments scoring below this.",
)
@click.option(
    "--cache-dir",
    type=click.Path(path_type=Path),
    default=DEFAULT_CACHE_DIR,
    show_default=True,
    help="Directory for cached API responses.",
)
@click.option("--offline", is_flag=True, help="Never hit the network; use cache only.")
@click.option("--as-json", "as_json", is_flag=True, help="Emit JSON instead of a table.")
def scan(
    season: str | None,
    game_id: str | None,
    playoffs: bool,
    top: int,
    min_score: int,
    cache_dir: Path,
    offline: bool,
    as_json: bool,
) -> None:
    """Rank poster-worthy moments for a season or a single game."""
    if bool(season) == bool(game_id):
        raise click.UsageError("provide exactly one of --season or --game")
    if season and not SEASON_RE.match(season):
        raise click.UsageError("season must look like 2025-26")

    source = build_source(cache_dir=cache_dir, offline=offline)
    if season:
        moments = run_scan_season(season, playoffs, source=source, min_score=min_score)
    else:
        assert game_id is not None
        moments = detect_moments(game_id, source=source, min_score=min_score)
    moments = moments[:top]

    if as_json:
        click.echo(json.dumps([m.to_dict() for m in moments], indent=2))
    elif moments:
        click.echo(_format_table(moments))
    else:
        click.echo("No moments at or above the score threshold.", err=True)
        sys.exit(1)


@main.command()
@click.option("--moment", "moment_id", required=True, help="Moment id, e.g. 0042500401:350.")
@click.option(
    "--style",
    default="all",
    show_default=True,
    type=click.Choice(["trajectory", "blueprint", "type", "all"]),
)
@click.option(
    "--size",
    default="18x24",
    show_default=True,
    type=click.Choice(["12x16", "18x24", "24x36", "all"]),
)
@click.option(
    "--out-dir",
    type=click.Path(path_type=Path),
    default=Path("renders"),
    show_default=True,
)
@click.option("--no-print-files", is_flag=True, help="Skip the 300-DPI print PNGs (faster).")
@click.option(
    "--cache-dir",
    type=click.Path(path_type=Path),
    default=DEFAULT_CACHE_DIR,
    show_default=True,
)
@click.option("--offline", is_flag=True, help="Never hit the network; use cache only.")
def render(
    moment_id: str,
    style: str,
    size: str,
    out_dir: Path,
    no_print_files: bool,
    cache_dir: Path,
    offline: bool,
) -> None:
    """Render a moment as poster SVG + print-ready PNG + web preview."""
    from buzzer.render import SIZES, STYLES, render_moment

    source = build_source(cache_dir=cache_dir, offline=offline)
    moment = find_moment(moment_id, source=source)
    styles = list(STYLES) if style == "all" else [style]
    sizes = sorted(SIZES) if size == "all" else [size]

    outputs: list[Path] = []
    for one_style in styles:
        for one_size in sizes:
            outputs.extend(
                render_moment(moment, one_style, one_size, out_dir, print_file=not no_print_files)
            )
    for path in outputs:
        click.echo(str(path))


if __name__ == "__main__":
    main()

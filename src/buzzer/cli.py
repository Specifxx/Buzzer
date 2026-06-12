"""Buzzer command-line interface.

scan       rank poster-worthy moments for a season or game
render     one moment -> SVG + 300-DPI print PNG + web preview
catalogue  bulk back-catalogue with manifest.json
ship       detect -> render -> validate -> publish (dry-run by default)
daily      morning scan -> draft products + approval notification
approve    the human yes: publish a drafted moment to the store
printify   live catalogue helpers (shops / blueprints / variants)
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import click

if TYPE_CHECKING:
    from buzzer.publish.printify import PrintifyClient
    from buzzer.publish.ship import ShipPlan

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


@main.command()
@click.option(
    "--seasons-back",
    "n_seasons",
    default=30,
    show_default=True,
    help="How many playoff seasons to scan, counting back from the current one.",
)
@click.option("--top", default=100, show_default=True, help="How many moments to keep.")
@click.option(
    "--styles",
    default="all",
    show_default=True,
    type=click.Choice(["trajectory", "blueprint", "type", "all"]),
)
@click.option(
    "--sizes",
    default="18x24",
    show_default=True,
    type=click.Choice(["12x16", "18x24", "24x36", "all"]),
)
@click.option(
    "--print-files",
    is_flag=True,
    help="Also export 300-DPI print PNGs (large; default is SVG + preview only).",
)
@click.option("--min-score", default=DEFAULT_MIN_SCORE, show_default=True)
@click.option(
    "--out-dir", type=click.Path(path_type=Path), default=Path("catalogue"), show_default=True
)
@click.option(
    "--cache-dir", type=click.Path(path_type=Path), default=DEFAULT_CACHE_DIR, show_default=True
)
@click.option("--offline", is_flag=True, help="Never hit the network; use cache only.")
def catalogue(
    n_seasons: int,
    top: int,
    styles: str,
    sizes: str,
    print_files: bool,
    min_score: int,
    out_dir: Path,
    cache_dir: Path,
    offline: bool,
) -> None:
    """Build the back-catalogue: scan playoff seasons, render top moments."""
    from buzzer.catalogue import build_catalogue, seasons_back
    from buzzer.render import SIZES, STYLES

    source = build_source(cache_dir=cache_dir, offline=offline)
    result = build_catalogue(
        seasons=seasons_back(n_seasons),
        top_n=top,
        out_dir=out_dir,
        source=source,
        styles=STYLES if styles == "all" else (styles,),
        sizes=tuple(sorted(SIZES)) if sizes == "all" else (sizes,),
        print_files=print_files,
        min_score=min_score,
    )
    click.echo(f"catalogue: {len(result.moments)} moments -> {result.manifest_path}")
    if result.seasons_skipped:
        click.echo(
            f"skipped {len(result.seasons_skipped)} season(s) with no cached data "
            f"(offline): {', '.join(result.seasons_skipped)}",
            err=True,
        )


def _format_ship_plan(plan: ShipPlan) -> str:
    lines = [f"SHIP PLAN — game {plan.game_id}"]
    for warning in plan.warnings:
        lines.append(f"  ! {warning}")
    for item in plan.items:
        action = f"UPDATE {item.existing_product_id}" if item.existing_product_id else "CREATE"
        lines.append(f"\n[{action}] {item.title}")
        lines.append(f"  key: {item.key}")
        lines.append(f"  tags: {', '.join(item.tags)}")
        for v in item.variants:
            lines.append(
                f"  {v.size}: cost ${v.cost_usd:.2f} -> price ${v.price_usd:.2f} "
                f"(variant {v.variant_id or 'UNSET'})"
            )
    return "\n".join(lines)


@main.command()
@click.option("--game", "game_id", required=True, help="Game ID, e.g. 0042500401.")
@click.option("--top", default=1, show_default=True, help="Ship the top N moments of the game.")
@click.option(
    "--style",
    default="all",
    show_default=True,
    type=click.Choice(["trajectory", "blueprint", "type", "all"]),
)
@click.option("--min-score", default=60, show_default=True)
@click.option(
    "--live", is_flag=True, help="Actually create draft products on Printify (default: dry run)."
)
@click.option(
    "--publish",
    is_flag=True,
    help="With --live: also publish to the connected store (extra confirmation).",
)
@click.option("--yes", is_flag=True, help="Skip confirmations (for automation).")
@click.option(
    "--out-dir", type=click.Path(path_type=Path), default=Path("renders"), show_default=True
)
@click.option(
    "--state-file",
    type=click.Path(path_type=Path),
    default=None,
    help="Idempotency state file. [default: state/printify_products.json]",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(path_type=Path),
    default=None,
    help="Publishing config. [default: config/buzzer.toml]",
)
@click.option(
    "--cache-dir", type=click.Path(path_type=Path), default=DEFAULT_CACHE_DIR, show_default=True
)
@click.option("--offline", is_flag=True, help="Never hit stats.nba.com; use cache only.")
def ship(
    game_id: str,
    top: int,
    style: str,
    min_score: int,
    live: bool,
    publish: bool,
    yes: bool,
    out_dir: Path,
    state_file: Path | None,
    config_path: Path | None,
    cache_dir: Path,
    offline: bool,
) -> None:
    """Detect, render, validate and publish a game's best moments.

    Dry run by default: shows the full plan (products, prices, files)
    and creates local renders, but makes NO API calls. Add --live to
    create Printify drafts, and --live --publish to go live on the
    store. Every live step asks for confirmation unless --yes.
    """
    from buzzer.publish import PrintifyClient, PublishState, execute_plan, load_config, plan_ship
    from buzzer.publish.config import DEFAULT_CONFIG_PATH, load_secrets
    from buzzer.publish.state import DEFAULT_STATE_PATH
    from buzzer.render import STYLES

    config = load_config(config_path or DEFAULT_CONFIG_PATH)
    state = PublishState.load(state_file or DEFAULT_STATE_PATH)
    source = build_source(cache_dir=cache_dir, offline=offline)

    plan = plan_ship(
        game_id,
        source=source,
        config=config,
        state=state,
        out_dir=out_dir,
        top=top,
        styles=STYLES if style == "all" else (style,),
        min_score=min_score,
    )
    click.echo(_format_ship_plan(plan))
    if not plan.items:
        sys.exit(1)

    if not live:
        click.echo("\nDRY RUN — no API calls were made. Re-run with --live to create drafts.")
        return

    token, shop_id = load_secrets()
    client = PrintifyClient(token=token, shop_id=shop_id)
    confirm = (lambda message: True) if yes else (lambda message: click.confirm(message))
    report = execute_plan(plan, client, config, state, confirm=confirm, publish=publish)
    if report.aborted:
        click.echo("aborted — nothing further was sent.", err=True)
        sys.exit(2)
    click.echo(
        f"\ndone: {len(report.created)} created, {len(report.updated)} updated, "
        f"{len(report.published)} published "
        f"({'drafts only' if not publish else 'live on store'})"
    )


@main.command()
@click.option(
    "--date", "date_iso", default=None, help="Date to scan (YYYY-MM-DD). [default: yesterday]"
)
@click.option(
    "--min-score",
    default=70,
    show_default=True,
    help="Draft a product only for moments at or above this score.",
)
@click.option("--top-per-game", default=1, show_default=True)
@click.option(
    "--notify",
    "notify_channel",
    default="github",
    show_default=True,
    type=click.Choice(["github", "log"]),
)
@click.option("--no-drafts", is_flag=True, help="Render and notify only; never touch Printify.")
@click.option(
    "--out-dir", type=click.Path(path_type=Path), default=Path("renders"), show_default=True
)
@click.option("--state-file", type=click.Path(path_type=Path), default=None)
@click.option("--config", "config_path", type=click.Path(path_type=Path), default=None)
@click.option(
    "--cache-dir", type=click.Path(path_type=Path), default=DEFAULT_CACHE_DIR, show_default=True
)
@click.option("--offline", is_flag=True, help="Never hit stats.nba.com; use cache only.")
def daily(
    date_iso: str | None,
    min_score: int,
    top_per_game: int,
    notify_channel: str,
    no_drafts: bool,
    out_dir: Path,
    state_file: Path | None,
    config_path: Path | None,
    cache_dir: Path,
    offline: bool,
) -> None:
    """Morning scan: render last night's best moments, open DRAFT products,
    and notify for approval. Never publishes anything by itself."""
    from buzzer.daily import build_daily_client, run_daily, yesterday
    from buzzer.notify import build_notifier
    from buzzer.publish import PublishState, load_config
    from buzzer.publish.config import DEFAULT_CONFIG_PATH
    from buzzer.publish.state import DEFAULT_STATE_PATH

    result = run_daily(
        date_iso or yesterday(),
        source=build_source(cache_dir=cache_dir, offline=offline),
        config=load_config(config_path or DEFAULT_CONFIG_PATH),
        state=PublishState.load(state_file or DEFAULT_STATE_PATH),
        out_dir=out_dir,
        notifier=build_notifier(notify_channel),
        client=None if no_drafts else build_daily_client(),
        min_score=min_score,
        top_per_game=top_per_game,
    )
    click.echo(
        f"{result.date_iso}: {result.games_scanned} game(s) scanned, "
        f"{len(result.moments)} moment(s) >= {min_score}, "
        f"{len(result.drafted_keys)} draft(s) created, "
        f"notified={'yes' if result.notified else 'no'}"
    )
    if result.drafts_skipped_reason:
        click.echo(f"drafts skipped: {result.drafts_skipped_reason}", err=True)


@main.command()
@click.option("--moment", "moment_id", required=True, help="Moment id, e.g. 0042500401:350.")
@click.option(
    "--style",
    default="all",
    show_default=True,
    type=click.Choice(["trajectory", "blueprint", "type", "all"]),
)
@click.option("--yes", is_flag=True, help="Skip the confirmation prompt.")
@click.option("--state-file", type=click.Path(path_type=Path), default=None)
def approve(moment_id: str, style: str, yes: bool, state_file: Path | None) -> None:
    """Publish a drafted moment to the live store (the human-approval step)."""
    from buzzer.publish import PrintifyClient, PublishState
    from buzzer.publish.config import load_secrets
    from buzzer.publish.state import DEFAULT_STATE_PATH, product_key
    from buzzer.render import STYLES

    state = PublishState.load(state_file or DEFAULT_STATE_PATH)
    styles = STYLES if style == "all" else (style,)
    drafts: list[tuple[str, str, str]] = []  # (key, product_id, title)
    for one_style in styles:
        key = product_key(moment_id, one_style)
        record = state.product(key)
        if record is None:
            click.echo(f"no draft recorded for {key} — run the daily scan or ship first", err=True)
            continue
        if record.get("published"):
            click.echo(f"already published: {key}")
            continue
        drafts.append((key, record["product_id"], record["title"]))

    if not drafts:
        sys.exit(1)
    click.echo("about to publish LIVE:")
    for _key, product_id, title in drafts:
        click.echo(f"  {product_id}  {title}")
    if not (yes or click.confirm("publish these to the connected store?")):
        click.echo("aborted — drafts remain unpublished.")
        sys.exit(2)

    token, shop_id = load_secrets()
    client = PrintifyClient(token=token, shop_id=shop_id)
    for key, product_id, _title in drafts:
        client.publish_product(product_id)
        state.mark_published(key)
        click.echo(f"published {key} ({product_id})")


@main.group()
def printify() -> None:
    """Live Printify helpers (require PRINTIFY_API_TOKEN in .env)."""


def _printify_client(need_shop: bool = True) -> PrintifyClient:
    import os

    from dotenv import load_dotenv

    from buzzer.publish import PrintifyClient

    load_dotenv()
    token = os.environ.get("PRINTIFY_API_TOKEN", "")
    if not token:
        raise click.UsageError("PRINTIFY_API_TOKEN is not set (see .env.example)")
    shop_id = os.environ.get("PRINTIFY_SHOP_ID", "")
    if need_shop and not shop_id:
        raise click.UsageError("PRINTIFY_SHOP_ID is not set; run `buzzer printify shops` first")
    return PrintifyClient(token=token, shop_id=shop_id)


@printify.command()
def shops() -> None:
    """List connected shops (use the id as PRINTIFY_SHOP_ID)."""
    for shop in _printify_client(need_shop=False).shops():
        click.echo(f"{shop['id']}  {shop.get('title', '')}  ({shop.get('sales_channel', '')})")


@printify.command()
@click.option("--search", default="poster", show_default=True)
def blueprints(search: str) -> None:
    """Find poster blueprints in the Printify catalogue."""
    for bp in _printify_client(need_shop=False).blueprints():
        if search.lower() in str(bp.get("title", "")).lower():
            click.echo(f"{bp['id']}  {bp['title']}")


@printify.command()
@click.option("--blueprint", "blueprint_id", required=True, type=int)
@click.option(
    "--provider",
    "provider_id",
    type=int,
    default=None,
    help="Print provider id; omit to list providers first.",
)
def variants(blueprint_id: int, provider_id: int | None) -> None:
    """List print providers / variant ids for a blueprint."""
    client = _printify_client(need_shop=False)
    if provider_id is None:
        for provider in client.print_providers(blueprint_id):
            click.echo(f"provider {provider['id']}  {provider.get('title', '')}")
        return
    data = client.variants(blueprint_id, provider_id)
    for variant in data.get("variants", []):
        click.echo(f"{variant['id']}  {variant.get('title', '')}")


if __name__ == "__main__":
    main()

"""The morning routine: scan last night's games, draft posters, ask a human.

For every finished game on the date, moments scoring at or above the
threshold are rendered and (when Printify credentials are configured)
created as DRAFT products. Nothing is ever published from here — the
human approves with ``buzzer approve --moment <id>``, which is the only
path from draft to live store. That is the human-in-the-loop guarantee.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from buzzer.datasource import DataSource
from buzzer.listing import title_for
from buzzer.models import Moment
from buzzer.notify import Notifier
from buzzer.publish.config import ConfigError, PublishConfig, load_secrets
from buzzer.publish.printify import PrintifyClient
from buzzer.publish.ship import execute_plan, plan_ship
from buzzer.publish.state import PublishState

logger = logging.getLogger(__name__)

DAILY_MIN_SCORE = 70


@dataclass
class DailyResult:
    date_iso: str
    games_scanned: int = 0
    moments: list[Moment] = field(default_factory=list)
    drafted_keys: list[str] = field(default_factory=list)
    drafts_skipped_reason: str | None = None
    notified: bool = False


def yesterday() -> str:
    return (date.today() - timedelta(days=1)).isoformat()


def _notification_body(result: DailyResult, out_dir: Path) -> str:
    lines = [
        f"Buzzer found {len(result.moments)} poster-worthy moment(s) in the "
        f"{result.games_scanned} finished game(s) of {result.date_iso}.",
        "",
    ]
    for moment in result.moments:
        facts = moment.facts
        lines += [
            f"## {title_for(facts)}",
            f"- moment: `{moment.moment_id}` — iconic-ness **{moment.score}/100**",
            f"- game: `{moment.context.matchup}` ({moment.game_id})",
            f"- {facts.clock} left in period {facts.period}, {facts.away_score}-{facts.home_score}",
            f"- renders: `{out_dir / moment.moment_id.replace(':', '-')}`",
            "",
        ]
    if result.drafted_keys:
        lines += [
            f"{len(result.drafted_keys)} draft product(s) are waiting on Printify (NOT published).",
            "",
            "Approve and publish with:",
            "```",
            *(f"uv run buzzer approve --moment {moment.moment_id}" for moment in result.moments),
            "```",
        ]
    elif result.drafts_skipped_reason:
        lines += [
            f"No drafts were created: {result.drafts_skipped_reason}",
            "Renders are on disk; ship manually with `uv run buzzer ship --game <id> --live`.",
        ]
    return "\n".join(lines)


def run_daily(
    date_iso: str,
    source: DataSource,
    config: PublishConfig,
    state: PublishState,
    out_dir: Path,
    notifier: Notifier,
    client: PrintifyClient | None = None,
    min_score: int = DAILY_MIN_SCORE,
    top_per_game: int = 1,
) -> DailyResult:
    """Scan one date. ``client=None`` means render-only (no Printify)."""
    result = DailyResult(date_iso=date_iso)
    games = source.games_for_date(date_iso)
    result.games_scanned = len(games)
    logger.info("daily %s: %d finished games", date_iso, len(games))

    for game in games:
        plan = plan_ship(
            game.game_id,
            source=source,
            config=config,
            state=state,
            out_dir=out_dir,
            top=top_per_game,
            min_score=min_score,
        )
        if not plan.items:
            continue
        seen: set[str] = set()
        for item in plan.items:
            if item.moment.moment_id not in seen:
                seen.add(item.moment.moment_id)
                result.moments.append(item.moment)

        if client is None:
            result.drafts_skipped_reason = (
                "Printify credentials not configured (PRINTIFY_API_TOKEN/PRINTIFY_SHOP_ID)"
            )
            continue
        try:
            config.require_catalogue_ids()
        except ConfigError as exc:
            result.drafts_skipped_reason = str(exc)
            logger.warning("drafts skipped: %s", exc)
            continue
        # Drafts are not customer-facing; publishing stays behind `approve`.
        report = execute_plan(plan, client, config, state, confirm=lambda _msg: True, publish=False)
        result.drafted_keys.extend(report.created + report.updated)

    if result.moments:
        subject = f"Buzzer: {len(result.moments)} moment(s) from {date_iso} await approval"
        notifier.notify(subject, _notification_body(result, out_dir))
        result.notified = True
    else:
        logger.info("daily %s: nothing above score %d — no notification", date_iso, min_score)
    return result


def build_daily_client() -> PrintifyClient | None:
    """Printify client from the environment, or None for render-only mode."""
    try:
        token, shop_id = load_secrets()
    except ConfigError as exc:
        logger.warning("running without Printify: %s", exc)
        return None
    return PrintifyClient(token=token, shop_id=shop_id)

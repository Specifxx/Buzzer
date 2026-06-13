"""Moment detection: turn one game's play-by-play into ranked Moments.

Every made field goal is scored by ``buzzer.scoring`` and anything at or
above ``min_score`` is returned. The rules the score reflects: time left
(final 10 seconds weigh most), lead changes, score margin, playoff games,
comeback size, and shot distance.
"""

from __future__ import annotations

import logging
from pathlib import Path

from buzzer.datasource import DataSource, Row
from buzzer.models import GameInfo, Moment, MomentContext, MomentFacts, PlayEvent
from buzzer.pbp import parse_play_by_play
from buzzer.scoring import ScoringInputs, score_moment

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path(".buzzer_cache")
DEFAULT_MIN_SCORE = 40


def build_source(cache_dir: Path = DEFAULT_CACHE_DIR, offline: bool = False) -> DataSource:
    """Default data source: file cache in front of the live nba_api client."""
    from buzzer.datasource import CachedSource

    if offline:
        return CachedSource(cache_dir, upstream=None)
    from buzzer.nba_source import NbaApiSource

    return CachedSource(cache_dir, upstream=NbaApiSource())


def _shot_index(shot_rows: list[Row]) -> dict[int, Row]:
    return {int(row["GAME_EVENT_ID"]): row for row in shot_rows}


def _series_info(game_id: str) -> tuple[int | None, int | None]:
    """(round 1-4, game 1-7) decoded from a playoff game id 004YY00RMG."""
    if game_id.startswith("004") and len(game_id) == 10:
        round_digit, game_digit = int(game_id[7]), int(game_id[9])
        if 1 <= round_digit <= 4 and 1 <= game_digit <= 7:
            return round_digit, game_digit
    return None, None


def _moment_for_event(
    event: PlayEvent,
    game: GameInfo,
    shot: Row | None,
    max_deficit_before: dict[str, int],
) -> Moment:
    side = event.scoring_side
    assert side is not None  # callers only pass scoring events
    if side == "home":
        team_after, opp_after = event.home_score, event.away_score
    else:
        team_after, opp_after = event.away_score, event.home_score
    margin_after = team_after - opp_after
    margin_before = margin_after - event.points
    playoff_round, series_game = _series_info(game.game_id)

    facts = MomentFacts(
        game_date=game.game_date,
        home_city=game.home_city,
        away_city=game.away_city,
        period=event.period,
        clock=event.clock,
        home_score=event.home_score,
        away_score=event.away_score,
        scoring_side=side,
        points=event.points,
        margin_before=margin_before,
        takes_lead=margin_before <= 0 < margin_after,
        ties_game=margin_after == 0,
        deficit_overcome=max_deficit_before[side],
        is_playoff=game.is_playoff,
        shot_distance_ft=float(shot["SHOT_DISTANCE"]) if shot else None,
        shot_x=float(shot["LOC_X"]) if shot else None,
        shot_y=float(shot["LOC_Y"]) if shot else None,
        playoff_round=playoff_round,
        series_game=series_game,
    )
    score = score_moment(
        ScoringInputs(
            period=event.period,
            seconds_remaining=event.seconds_remaining,
            margin_before=margin_before,
            takes_lead=facts.takes_lead,
            ties_game=facts.ties_game,
            is_playoff=game.is_playoff,
            deficit_overcome=facts.deficit_overcome,
            shot_distance_ft=facts.shot_distance_ft,
            playoff_round=playoff_round,
            series_game=series_game,
        )
    )
    context = MomentContext(
        season=game.season,
        matchup=f"{game.away_tricode} @ {game.home_tricode}",
        home_tricode=game.home_tricode,
        away_tricode=game.away_tricode,
        description=event.description,
    )
    return Moment(
        moment_id=f"{game.game_id}:{event.event_num}",
        game_id=game.game_id,
        event_num=event.event_num,
        score=score,
        facts=facts,
        context=context,
    )


def detect_moments(
    game_id: str,
    source: DataSource | None = None,
    min_score: int = DEFAULT_MIN_SCORE,
) -> list[Moment]:
    """Return this game's poster-worthy moments, highest score first."""
    if source is None:
        source = build_source()

    game = source.game_summary(game_id)
    events = parse_play_by_play(source.play_by_play(game_id))
    shots = _shot_index(source.shot_chart(game_id))

    moments: list[Moment] = []
    # Largest deficit each side has faced so far (before the current event).
    max_deficit = {"home": 0, "away": 0}
    for event in events:
        if event.is_made_fg and event.scoring_side is not None:
            moment = _moment_for_event(event, game, shots.get(event.event_num), max_deficit)
            if moment.score >= min_score:
                moments.append(moment)
        margin_home = event.home_score - event.away_score
        max_deficit["home"] = max(max_deficit["home"], -margin_home)
        max_deficit["away"] = max(max_deficit["away"], margin_home)

    moments.sort(key=lambda m: m.score, reverse=True)
    logger.info("game %s: %d moments >= %d", game_id, len(moments), min_score)
    return moments


def find_moment(moment_id: str, source: DataSource | None = None) -> Moment:
    """Look up one moment by its ``<game_id>:<event_num>`` id."""
    game_id, _, event_str = moment_id.partition(":")
    if not event_str:
        raise ValueError(f"moment id must look like '0042500401:350', got {moment_id!r}")
    event_num = int(event_str)
    for moment in detect_moments(game_id, source=source, min_score=0):
        if moment.event_num == event_num:
            return moment
    raise LookupError(f"event {event_num} of game {game_id} is not a made field goal")


def scan_season(
    season: str,
    playoffs: bool,
    source: DataSource | None = None,
    min_score: int = DEFAULT_MIN_SCORE,
) -> list[Moment]:
    """Run moment detection across every game of a season, ranked."""
    if source is None:
        source = build_source()
    games = source.season_games(season, playoffs)
    moments: list[Moment] = []
    for i, game in enumerate(games, start=1):
        logger.info("scanning game %d/%d: %s", i, len(games), game.game_id)
        try:
            moments.extend(detect_moments(game.game_id, source=source, min_score=min_score))
        except Exception:
            # One bad game must not kill a whole season scan.
            logger.exception("failed to scan game %s — skipping", game.game_id)
    moments.sort(key=lambda m: m.score, reverse=True)
    return moments

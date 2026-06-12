"""Live DataSource backed by the nba_api package (stats.nba.com).

stats.nba.com throttles aggressively, so every request goes through one
choke point (``_call``) with a polite delay and retry with backoff.
nba_api imports are kept inside methods so the rest of the package
(parsing, scoring, tests) never needs network or the heavy import.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from buzzer.models import GameInfo
from buzzer.teams import city_for_tricode

logger = logging.getLogger(__name__)

Row = dict[str, Any]

# Game IDs encode the season type in their prefix: 001 preseason,
# 002 regular season, 003 all-star, 004 playoffs, 005 play-in.
PLAYOFF_PREFIX = "004"


def rows_from_result_sets(payload: dict[str, Any], name: str) -> list[Row]:
    """Convert one named resultSet of a stats.nba.com payload to row dicts."""
    for result_set in payload.get("resultSets", []):
        if result_set.get("name") == name:
            headers = result_set["headers"]
            return [dict(zip(headers, row, strict=True)) for row in result_set["rowSet"]]
    raise KeyError(f"resultSet {name!r} not found in payload")


class SourceUnavailableError(RuntimeError):
    """stats.nba.com could not be reached after retries.

    Usually means the caller's IP range is blocked (datacenter/CI
    runners) or the site is down — an environmental condition, not a
    bug. Callers may treat it as "try again from somewhere else".
    """


class NbaApiSource:
    """DataSource implementation that talks to stats.nba.com via nba_api."""

    def __init__(self, request_delay_s: float = 0.7, retries: int = 3, timeout_s: int = 30):
        self.request_delay_s = request_delay_s
        self.retries = retries
        self.timeout_s = timeout_s
        self._last_call = 0.0

    def _call(self, endpoint_factory: Any, **kwargs: Any) -> dict[str, Any]:
        """Run one nba_api endpoint with rate limiting and retry."""
        wait = self.request_delay_s - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        last_error: Exception | None = None
        for attempt in range(1, self.retries + 1):
            try:
                logger.info("nba_api call %s %s", endpoint_factory.__name__, kwargs)
                endpoint = endpoint_factory(timeout=self.timeout_s, **kwargs)
                self._last_call = time.monotonic()
                payload: dict[str, Any] = endpoint.get_dict()
                return payload
            except Exception as exc:  # nba_api raises a zoo of request errors
                last_error = exc
                backoff = 2.0**attempt
                logger.warning(
                    "nba_api call failed (attempt %d/%d): %s — retrying in %.0fs",
                    attempt,
                    self.retries,
                    exc,
                    backoff,
                )
                time.sleep(backoff)
        raise SourceUnavailableError(
            f"stats.nba.com unreachable after {self.retries} attempts "
            "(their servers often block datacenter/CI IPs; try from another network)"
        ) from last_error

    # -- DataSource implementation ----------------------------------------

    def play_by_play(self, game_id: str) -> list[Row]:
        from nba_api.stats.endpoints import playbyplayv2

        payload = self._call(
            playbyplayv2.PlayByPlayV2, game_id=game_id, start_period=1, end_period=10
        )
        return rows_from_result_sets(payload, "PlayByPlay")

    def shot_chart(self, game_id: str) -> list[Row]:
        from nba_api.stats.endpoints import shotchartdetail

        payload = self._call(
            shotchartdetail.ShotChartDetail,
            game_id_nullable=game_id,
            team_id=0,
            player_id=0,
            context_measure_simple="FGA",
            season_type_all_star="Playoffs"
            if game_id.startswith(PLAYOFF_PREFIX)
            else ("Regular Season"),
        )
        return rows_from_result_sets(payload, "Shot_Chart_Detail")

    def game_summary(self, game_id: str) -> GameInfo:
        from nba_api.stats.endpoints import boxscoresummaryv2
        from nba_api.stats.static import teams as static_teams

        payload = self._call(boxscoresummaryv2.BoxScoreSummaryV2, game_id=game_id)
        summary = rows_from_result_sets(payload, "GameSummary")[0]

        def tricode(team_id: int) -> str:
            team = static_teams.find_team_name_by_id(team_id)
            return str(team["abbreviation"]) if team else "UNK"

        home = tricode(summary["HOME_TEAM_ID"])
        away = tricode(summary["VISITOR_TEAM_ID"])
        season_start = int(summary["SEASON"])
        return GameInfo(
            game_id=game_id,
            game_date=str(summary["GAME_DATE_EST"])[:10],
            season=f"{season_start}-{(season_start + 1) % 100:02d}",
            is_playoff=game_id.startswith(PLAYOFF_PREFIX),
            home_tricode=home,
            away_tricode=away,
            home_city=city_for_tricode(home),
            away_city=city_for_tricode(away),
        )

    def games_for_date(self, date_iso: str) -> list[GameInfo]:
        """Finished games on one date, from the scoreboard endpoint."""
        from nba_api.stats.endpoints import scoreboardv2
        from nba_api.stats.static import teams as static_teams

        payload = self._call(scoreboardv2.ScoreboardV2, game_date=date_iso)
        rows = rows_from_result_sets(payload, "GameHeader")

        def tricode(team_id: int) -> str:
            team = static_teams.find_team_name_by_id(team_id)
            return str(team["abbreviation"]) if team else "UNK"

        games: list[GameInfo] = []
        for row in rows:
            if int(row.get("GAME_STATUS_ID", 0)) != 3:  # 3 == final
                logger.info("skipping unfinished game %s", row.get("GAME_ID"))
                continue
            home = tricode(int(row["HOME_TEAM_ID"]))
            away = tricode(int(row["VISITOR_TEAM_ID"]))
            season_start = int(row["SEASON"])
            games.append(
                GameInfo(
                    game_id=str(row["GAME_ID"]),
                    game_date=date_iso,
                    season=f"{season_start}-{(season_start + 1) % 100:02d}",
                    is_playoff=str(row["GAME_ID"]).startswith(PLAYOFF_PREFIX),
                    home_tricode=home,
                    away_tricode=away,
                    home_city=city_for_tricode(home),
                    away_city=city_for_tricode(away),
                )
            )
        return games

    def season_games(self, season: str, playoffs: bool) -> list[GameInfo]:
        from nba_api.stats.endpoints import leaguegamelog

        payload = self._call(
            leaguegamelog.LeagueGameLog,
            season=season,
            season_type_all_star="Playoffs" if playoffs else "Regular Season",
        )
        rows = rows_from_result_sets(payload, "LeagueGameLog")

        # One row per team per game; keep the home-team row ("X vs. Y").
        games: dict[str, GameInfo] = {}
        for row in rows:
            matchup = str(row["MATCHUP"])
            if " vs. " not in matchup:
                continue
            home, away = (part.strip() for part in matchup.split(" vs. "))
            games[str(row["GAME_ID"])] = GameInfo(
                game_id=str(row["GAME_ID"]),
                game_date=str(row["GAME_DATE"])[:10],
                season=season,
                is_playoff=playoffs,
                home_tricode=home,
                away_tricode=away,
                home_city=city_for_tricode(home),
                away_city=city_for_tricode(away),
            )
        result = sorted(games.values(), key=lambda g: (g.game_date, g.game_id))
        logger.info(
            "season %s (%s): %d games", season, "playoffs" if playoffs else "regular", len(result)
        )
        return result

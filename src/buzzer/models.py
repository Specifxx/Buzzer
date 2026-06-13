"""Core data models.

The single most important design rule in this project:

    ``MomentFacts``   -> renderable. May contain ONLY factual, non-trademark data:
                         scores, dates, clock times, periods, city names,
                         distances, coordinates.
    ``MomentContext`` -> operator-only. Team tricodes, raw play-by-play text
                         (which contains player names). It exists so a human
                         can identify a moment in the CLI. It must NEVER be
                         passed to a poster template. Phase 2 adds a validator
                         that rejects any rendered output containing it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

Side = Literal["home", "away"]


@dataclass(frozen=True)
class GameInfo:
    """Identity of one game, as needed for scanning and labelling."""

    game_id: str
    game_date: str  # ISO "YYYY-MM-DD"
    season: str  # e.g. "2025-26"
    is_playoff: bool
    home_tricode: str  # operator context only — never rendered
    away_tricode: str  # operator context only — never rendered
    home_city: str | None = None  # factual, allowed in renders
    away_city: str | None = None


@dataclass(frozen=True)
class PlayEvent:
    """One parsed play-by-play event with the running score carried forward."""

    event_num: int
    event_type: int  # nba_api EVENTMSGTYPE; 1 == made field goal
    period: int
    clock: str  # "MM:SS" remaining in period
    seconds_remaining: float  # within the period
    away_score: int
    home_score: int
    scoring_side: Side | None  # which side's score increased on this event
    points: int  # score delta on this event (0 if none)
    is_made_fg: bool
    description: str  # raw text, may contain player names — operator only
    team_tricode: str | None


@dataclass(frozen=True)
class MomentFacts:
    """Everything a poster is allowed to say. Numbers, dates, cities. Nothing else."""

    game_date: str
    home_city: str | None
    away_city: str | None
    period: int
    clock: str
    home_score: int  # final score of this play (after the shot)
    away_score: int
    scoring_side: Side
    points: int
    margin_before: int  # scoring team's perspective; negative == trailing
    takes_lead: bool
    ties_game: bool
    deficit_overcome: int  # largest deficit the scoring team faced earlier
    is_playoff: bool
    shot_distance_ft: float | None
    shot_x: float | None  # tenths of feet from basket centre (nba_api LOC_X)
    shot_y: float | None
    # Playoff series position, decoded from the game id (004YY00RMG):
    # round 1-4 and game 1-7. "Game 7" is the single biggest recognition
    # trigger a factual poster can carry.
    playoff_round: int | None = None
    series_game: int | None = None
    # Putbacks/tip-ins (from the shot chart's action type). A buzzer
    # tip-in is its own genre of moment and deserves its own language.
    is_tip: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MomentContext:
    """Operator-only identification. NEVER rendered — see module docstring."""

    season: str
    matchup: str  # "AWY @ HOM" tricodes
    home_tricode: str
    away_tricode: str
    description: str  # raw play-by-play text

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Moment:
    """A poster-worthy play with its iconic-ness score (0-100)."""

    moment_id: str  # "<game_id>:<event_num>"
    game_id: str
    event_num: int
    score: int
    facts: MomentFacts
    context: MomentContext

    def to_dict(self) -> dict[str, Any]:
        return {
            "moment_id": self.moment_id,
            "game_id": self.game_id,
            "event_num": self.event_num,
            "score": self.score,
            "facts": self.facts.to_dict(),
            "context": self.context.to_dict(),
        }

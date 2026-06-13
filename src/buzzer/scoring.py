"""Iconic-ness scoring: pure function from facts about a play to 0-100.

Deliberately boring and transparent: a handful of additive components with
named weights, so a score can always be explained ("40 clutch + 20 go-ahead
+ 15 playoff + 8 distance"). Tune ``ScoringWeights``, not the code.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoringInputs:
    period: int
    seconds_remaining: float  # in the period
    margin_before: int  # scoring team's perspective; negative == trailing
    takes_lead: bool
    ties_game: bool
    is_playoff: bool
    deficit_overcome: int  # largest deficit the scoring team faced earlier
    shot_distance_ft: float | None
    playoff_round: int | None = None  # 1-4, from the game id
    series_game: int | None = None  # 1-7


@dataclass(frozen=True)
class ScoringWeights:
    clutch_max: float = 40.0  # made FG at the final buzzer
    takes_lead: float = 20.0
    ties_game: float = 10.0
    playoff: float = 15.0
    overtime: float = 5.0
    comeback_max: float = 15.0  # 1 point per point of deficit, capped
    distance_30ft: float = 8.0
    distance_25ft: float = 5.0
    closeness_max: float = 5.0
    round_step: float = 2.0  # per playoff round beyond the first
    game_seven: float = 8.0


DEFAULT_WEIGHTS = ScoringWeights()


def _clutch_points(period: int, t: float, w: ScoringWeights) -> float:
    """Time pressure. Only the final period and overtime count."""
    if period < 4:
        return 0.0
    if t <= 10:  # the "final 10 seconds" rule: 35..40 points
        return (w.clutch_max - 5.0) + 5.0 * (10.0 - t) / 10.0
    if t <= 60:  # final minute: 20..35
        return 20.0 + 15.0 * (60.0 - t) / 50.0
    if t <= 300:  # last five minutes: 0..20
        return 20.0 * (300.0 - t) / 240.0
    return 0.0


def _margin_factor(margin_before: int) -> float:
    """Blowout dampener: a buzzer shot in a 15-point game is not iconic."""
    margin = abs(margin_before)
    if margin <= 3:
        return 1.0
    if margin <= 6:
        return 0.5
    return 0.15


def score_moment(inputs: ScoringInputs, weights: ScoringWeights = DEFAULT_WEIGHTS) -> int:
    """Score one made field goal 0-100 for how poster-worthy it is."""
    score = _clutch_points(inputs.period, inputs.seconds_remaining, weights)
    score *= _margin_factor(inputs.margin_before)

    # Lead changes and ties only carry full weight late in the game;
    # a go-ahead bucket in the first quarter is not a poster.
    late_factor = 1.0 if inputs.period >= 4 else 0.4
    if inputs.takes_lead:
        score += weights.takes_lead * late_factor
    elif inputs.ties_game:
        score += weights.ties_game * late_factor

    # A close game raises the stakes even without a lead change.
    score += max(0.0, weights.closeness_max - abs(inputs.margin_before))

    if inputs.is_playoff:
        score += weights.playoff
    if inputs.period > 4:
        score += weights.overtime

    # Series stakes: deeper rounds and decisive games are more iconic.
    # Game 7 of round 4 is the biggest stage the sport has.
    if inputs.playoff_round is not None:
        score += (inputs.playoff_round - 1) * weights.round_step
    if inputs.series_game == 7:
        score += weights.game_seven

    # Comebacks only count if this shot actually ties or takes the lead.
    if inputs.takes_lead or inputs.ties_game:
        score += min(float(inputs.deficit_overcome), weights.comeback_max) * late_factor

    if inputs.shot_distance_ft is not None:
        if inputs.shot_distance_ft >= 30:
            score += weights.distance_30ft
        elif inputs.shot_distance_ft >= 25:
            score += weights.distance_25ft

    return max(0, min(100, round(score)))

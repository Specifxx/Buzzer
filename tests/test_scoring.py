from dataclasses import replace

from buzzer.scoring import ScoringInputs, score_moment

BUZZER_BEATER = ScoringInputs(
    period=4,
    seconds_remaining=1.0,
    margin_before=-2,
    takes_lead=True,
    ties_game=False,
    is_playoff=True,
    deficit_overcome=13,
    shot_distance_ft=27.0,
)

EARLY_GAME = ScoringInputs(
    period=1,
    seconds_remaining=500.0,
    margin_before=4,
    takes_lead=False,
    ties_game=False,
    is_playoff=False,
    deficit_overcome=0,
    shot_distance_ft=12.0,
)


def test_playoff_buzzer_beater_scores_very_high() -> None:
    assert score_moment(BUZZER_BEATER) >= 90


def test_early_game_shot_scores_low() -> None:
    assert score_moment(EARLY_GAME) < 20


def test_less_time_remaining_scores_higher() -> None:
    scores = [
        score_moment(replace(BUZZER_BEATER, seconds_remaining=t))
        for t in (1.0, 9.0, 45.0, 200.0, 400.0)
    ]
    assert scores == sorted(scores, reverse=True)
    assert scores[0] > scores[-1]


def test_lead_change_beats_tie_beats_neither() -> None:
    go_ahead = score_moment(BUZZER_BEATER)
    tie = score_moment(replace(BUZZER_BEATER, takes_lead=False, ties_game=True))
    neither = score_moment(replace(BUZZER_BEATER, takes_lead=False, ties_game=False))
    assert go_ahead > tie > neither


def test_playoff_flag_adds_points() -> None:
    assert score_moment(BUZZER_BEATER) > score_moment(replace(BUZZER_BEATER, is_playoff=False))


def test_comeback_only_counts_when_shot_ties_or_takes_lead() -> None:
    no_lead = replace(BUZZER_BEATER, takes_lead=False, ties_game=False)
    assert score_moment(no_lead) == score_moment(replace(no_lead, deficit_overcome=0))


def test_score_is_clamped_to_0_100() -> None:
    maxed = replace(
        BUZZER_BEATER, seconds_remaining=0.0, deficit_overcome=30, shot_distance_ft=35.0
    )
    assert score_moment(maxed) == 100
    dud = ScoringInputs(
        period=2,
        seconds_remaining=700.0,
        margin_before=20,
        takes_lead=False,
        ties_game=False,
        is_playoff=False,
        deficit_overcome=0,
        shot_distance_ft=2.0,
    )
    assert 0 <= score_moment(dud) <= 10

import json

from buzzer.datasource import CachedSource
from buzzer.detect import detect_moments

from .conftest import FINALS_GAME, QUIET_GAME


def test_finals_game_top_moment_is_the_buzzer_beater(source: CachedSource) -> None:
    moments = detect_moments(FINALS_GAME, source=source)
    assert moments, "expected moments in the synthetic finals game"
    top = moments[0]

    assert top.score >= 90
    f = top.facts
    assert f.clock == "0:01"
    assert f.period == 4
    assert f.takes_lead and not f.ties_game
    assert f.points == 3
    assert f.margin_before == -2
    assert f.deficit_overcome == 13
    assert f.is_playoff
    assert f.shot_distance_ft == 27.0
    assert f.shot_x is not None and f.shot_y is not None
    assert (f.home_score, f.away_score) == (101, 100)
    assert f.game_date == "2026-06-04"
    assert (f.home_city, f.away_city) == ("Boston", "Denver")
    assert top.moment_id == f"{FINALS_GAME}:{top.event_num}"


def test_moments_are_ranked_descending(source: CachedSource) -> None:
    moments = detect_moments(FINALS_GAME, source=source, min_score=0)
    scores = [m.score for m in moments]
    assert scores == sorted(scores, reverse=True)
    assert len(moments) > 20  # every made FG is scored when min_score=0


def test_min_score_filters(source: CachedSource) -> None:
    moments = detect_moments(FINALS_GAME, source=source, min_score=40)
    assert 1 <= len(moments) <= 10
    assert all(m.score >= 40 for m in moments)
    # The two game-tying shots and the late lay-in made the cut too.
    assert any(m.facts.ties_game for m in moments)


def test_quiet_game_has_no_moments(source: CachedSource) -> None:
    assert detect_moments(QUIET_GAME, source=source) == []


def test_facts_never_contain_names_or_team_marks(source: CachedSource) -> None:
    """The legal firewall: renderable facts must hold only factual data.

    Fixture play-by-play is full of (fictional) player names and team
    tricodes; none of it may survive into MomentFacts.
    """
    forbidden = [
        "Fakesmith",
        "Mockwell",
        "Testman",
        "Samplevich",  # player names
        "BOS",
        "DEN",
        "MIN",
        "UTA",  # team tricodes (case-sensitive)
        "Jump Shot",
        "REBOUND",  # raw play-by-play text
    ]
    for game_id in (FINALS_GAME, QUIET_GAME):
        for moment in detect_moments(game_id, source=source, min_score=0):
            blob = json.dumps(moment.facts.to_dict())
            for term in forbidden:
                assert term not in blob, f"{term!r} leaked into facts of {moment.moment_id}"


def test_context_is_clearly_separated(source: CachedSource) -> None:
    top = detect_moments(FINALS_GAME, source=source)[0]
    # Context exists for the operator and DOES carry identification...
    assert top.context.matchup == "DEN @ BOS"
    assert "Fakesmith" in top.context.description or "Mockwell" in top.context.description
    # ...and serialization keeps it in a separate, droppable branch.
    assert set(top.to_dict().keys()) == {
        "moment_id",
        "game_id",
        "event_num",
        "score",
        "facts",
        "context",
    }

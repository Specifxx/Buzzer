import json
from datetime import date
from pathlib import Path

import pytest

from buzzer.catalogue import build_catalogue, current_season, seasons_back
from buzzer.datasource import CachedSource
from buzzer.listing import description_for, tags_for, title_for
from buzzer.render.validate import ContentViolationError, validate_listing_text

from .conftest import FINALS_GAME, requires_cairo
from .test_render import make_facts


def test_current_season_rolls_in_october() -> None:
    assert current_season(date(2026, 6, 12)) == "2025-26"
    assert current_season(date(2026, 10, 25)) == "2026-27"
    assert current_season(date(2000, 1, 5)) == "1999-00"


def test_seasons_back() -> None:
    seasons = seasons_back(30, latest="2025-26")
    assert len(seasons) == 30
    assert seasons[0] == "1996-97"
    assert seasons[-1] == "2025-26"


# --- listing copy ------------------------------------------------------------


def test_title_for_buzzer_beater() -> None:
    title = title_for(make_facts())
    assert title == "Down 13: Buzzer-Beater From 27 Feet — Boston, June 4, 2026"


def test_title_variants() -> None:
    tie = title_for(make_facts(takes_lead=False, ties_game=True, clock="2:30"))
    assert "Tied It" in tie
    plain = title_for(
        make_facts(takes_lead=False, ties_game=False, deficit_overcome=0, shot_distance_ft=8.0)
    )
    assert "3-Point Shot" in plain


def test_description_is_factual_and_validated() -> None:
    description = description_for(make_facts())
    assert "Q4, 0:01 remaining." in description
    assert "After trailing by 13." in description
    assert "Denver 100, Boston 101." in description
    assert "Playoffs" in description


def test_tags_have_no_marks_and_include_city() -> None:
    tags = tags_for(make_facts())
    assert "boston basketball art" in tags
    assert "buzzer beater poster" in tags
    blob = " ".join(tags).upper()
    for mark in ("NBA", "CELTICS", "NUGGETS", "FINALS"):
        assert mark not in blob


def test_listing_validator_rejects_marks() -> None:
    with pytest.raises(ContentViolationError):
        validate_listing_text("vintage Bulls poster")
    with pytest.raises(ContentViolationError):
        validate_listing_text("NBA playoffs print")
    # And words simply not on the allowlist fail closed:
    with pytest.raises(ContentViolationError):
        validate_listing_text("limited edition collectible")


# --- catalogue build ---------------------------------------------------------


@requires_cairo
def test_build_catalogue_offline(source: CachedSource, tmp_path: Path) -> None:
    result = build_catalogue(
        seasons=["2024-25", "2025-26"],  # 2024-25 has no fixture data -> skipped
        top_n=3,
        out_dir=tmp_path / "catalogue",
        source=source,
        styles=("trajectory", "type"),
        sizes=("18x24",),
        print_files=False,
    )
    assert result.seasons_scanned == ["2025-26"]
    assert result.seasons_skipped == ["2024-25"]
    assert len(result.moments) == 3

    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["count"] == 3
    assert manifest["moments"][0]["rank"] == 1
    top = manifest["moments"][0]
    assert top["moment_id"].startswith(FINALS_GAME)
    assert top["score"] >= 90
    assert "Buzzer-Beater" in top["title"]

    # files exist and are organised by rank
    for style in ("trajectory", "type"):
        for kind in ("svg", "preview"):
            rel = top["files"][style]["18x24"][kind]
            assert rel.startswith("001_")
            assert (tmp_path / "catalogue" / rel).exists()

    # the manifest must be safe: no tricodes, no play-by-play text, no marks
    blob = result.manifest_path.read_text()
    for forbidden in ("BOS", "DEN", "context", "Fakesmith", "NBA"):
        assert forbidden not in blob


@requires_cairo
def test_catalogue_rerun_is_clean(source: CachedSource, tmp_path: Path) -> None:
    out = tmp_path / "catalogue"
    for _ in range(2):
        result = build_catalogue(
            seasons=["2025-26"],
            top_n=1,
            out_dir=out,
            source=source,
            styles=("type",),
            sizes=("18x24",),
        )
    manifest = json.loads(result.manifest_path.read_text())
    assert manifest["count"] == 1

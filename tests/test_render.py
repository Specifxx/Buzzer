from pathlib import Path
from typing import Any
from xml.etree import ElementTree

import pytest

from buzzer.datasource import CachedSource
from buzzer.detect import find_moment
from buzzer.models import MomentFacts
from buzzer.render import (
    SIZES,
    STYLES,
    ContentViolationError,
    render_moment,
    render_svg,
    validate_svg,
    validate_text_value,
)

from .conftest import FINALS_GAME


def make_facts(**overrides: Any) -> MomentFacts:
    base: dict[str, Any] = {
        "game_date": "2026-06-04",
        "home_city": "Boston",
        "away_city": "Denver",
        "period": 4,
        "clock": "0:01",
        "home_score": 101,
        "away_score": 100,
        "scoring_side": "home",
        "points": 3,
        "margin_before": -2,
        "takes_lead": True,
        "ties_game": False,
        "deficit_overcome": 13,
        "is_playoff": True,
        "shot_distance_ft": 27.0,
        "shot_x": -221.0,
        "shot_y": 155.0,
    }
    base.update(overrides)
    return MomentFacts(**base)


# --- rendering ---------------------------------------------------------------


@pytest.mark.parametrize("style", STYLES)
@pytest.mark.parametrize("size", sorted(SIZES))
def test_every_style_and_size_renders_valid_svg(style: str, size: str) -> None:
    svg = render_svg(make_facts(), style, size)
    root = ElementTree.fromstring(svg)
    inches_w, inches_h = SIZES[size]
    assert root.attrib["width"] == f"{inches_w * 100}.0"
    assert root.attrib["height"] == f"{inches_h * 100}.0"
    assert "0:01" in svg
    assert "JUNE 4, 2026" in svg
    assert "BOSTON" in svg and "DENVER" in svg


@pytest.mark.parametrize("style", STYLES)
def test_variant_facts_render(style: str) -> None:
    variants = [
        make_facts(takes_lead=False, ties_game=True),  # game-tying shot
        make_facts(takes_lead=False, ties_game=False, deficit_overcome=0),
        make_facts(is_playoff=False, period=5, clock="0:00"),  # OT, regular season
        make_facts(shot_x=None, shot_y=None),  # synthesized shot point
        make_facts(shot_x=None, shot_y=None, shot_distance_ft=None),
        make_facts(shot_y=550.0, shot_distance_ft=55.0),  # halfcourt heave
        make_facts(home_city=None, away_city=None),  # unknown historic teams
    ]
    for facts in variants:
        svg = render_svg(facts, style, "18x24")
        assert svg.startswith("<svg")


def test_unknown_style_or_size_rejected() -> None:
    with pytest.raises(ValueError):
        render_svg(make_facts(), "photorealistic", "18x24")
    with pytest.raises(ValueError):
        render_svg(make_facts(), "trajectory", "11x17")


def test_render_moment_writes_svg_and_preview(source: CachedSource, tmp_path: Path) -> None:
    moment = find_moment(f"{FINALS_GAME}:350", source=source)
    outputs = render_moment(moment, "trajectory", "18x24", tmp_path, print_file=False)
    suffixes = [p.name for p in outputs]
    assert any(name.endswith(".svg") for name in suffixes)
    assert any(name.endswith("_preview.png") for name in suffixes)
    preview = next(p for p in outputs if p.name.endswith("_preview.png"))
    assert preview.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_print_png_is_300dpi_sized(tmp_path: Path) -> None:
    from PIL import Image

    from buzzer.render.renderer import export_png

    svg = render_svg(make_facts(), "type", "12x16")
    out = export_png(svg, tmp_path / "p.png", width_px=600)  # scaled-down smoke test
    with Image.open(out) as image:
        assert image.width == 600
        assert image.height == 800  # 12x16 aspect preserved
        assert round(image.info.get("dpi", (300, 300))[0]) == 300


# --- the legal firewall ------------------------------------------------------


def test_player_name_in_variable_rejected() -> None:
    with pytest.raises(ContentViolationError, match="player name"):
        validate_text_value("LeBron James game winner", field="title")


def test_team_nickname_in_variable_rejected() -> None:
    with pytest.raises(ContentViolationError, match="team mark"):
        validate_text_value("Lakers at Celtics", field="cities")


def test_league_mark_rejected() -> None:
    with pytest.raises(ContentViolationError, match="league mark"):
        validate_text_value("NBA Finals 2026", field="title")


def test_arena_name_rejected_via_venue_words() -> None:
    with pytest.raises(ContentViolationError, match="venue word"):
        validate_text_value("Madison Square Garden", field="city")


def test_injected_player_name_in_city_field_fails_render() -> None:
    facts = make_facts(home_city="Kobe Bryant")
    with pytest.raises(ContentViolationError):
        render_svg(facts, "type", "18x24")


def test_injected_nickname_in_city_field_fails_render() -> None:
    facts = make_facts(away_city="Golden State Warriors")
    with pytest.raises(ContentViolationError):
        render_svg(facts, "blueprint", "18x24")


def test_svg_with_embedded_image_rejected() -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><image href="photo.jpg"/></svg>'
    with pytest.raises(ContentViolationError, match="forbidden element"):
        validate_svg(svg)


def test_svg_with_unlisted_word_rejected() -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><text>Air Jordan</text></svg>'
    with pytest.raises(ContentViolationError, match="not in factual allowlist"):
        validate_svg(svg)


def test_city_words_only_allowed_when_passed() -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><text>OKLAHOMA CITY</text></svg>'
    validate_svg(svg, allowed_cities=("Oklahoma City",))
    with pytest.raises(ContentViolationError):
        validate_svg(svg, allowed_cities=("Boston",))


def test_rendered_output_has_no_marks_anywhere() -> None:
    """Belt and suspenders: scan full rendered SVGs for known mark fragments."""
    for style in STYLES:
        svg = render_svg(make_facts(), style, "18x24").upper()
        for mark in ("NBA", "CELTICS", "NUGGETS", "FINALS"):
            assert mark not in svg, f"{mark} appeared in {style}"

"""The Buzzer Studio site generator must produce valid, firewall-clean output."""

import json
from pathlib import Path

from buzzer.render.validate import validate_svg

from .test_site_helpers import load_built_site


def test_site_catalogue_builds_and_validates(tmp_path: Path) -> None:
    catalogue = load_built_site(tmp_path, count=4)

    assert catalogue["count"] == 4
    moments = catalogue["moments"]
    scores = [m["score"] for m in moments]
    assert scores == sorted(scores, reverse=True)
    assert all(m["score"] >= 55 for m in moments)

    top = moments[0]
    assert top["id"] == "demo-001"
    assert top["title"]
    assert top["tags"]
    assert "facts" in top and "context" not in top  # never operator data

    # every referenced file exists and passes the firewall
    for moment in moments:
        cities = (moment["facts"]["home_city"], moment["facts"]["away_city"])
        for style_files in moment["files"].values():
            for rel in style_files.values():
                svg_path = tmp_path / rel
                assert svg_path.exists(), rel
                validate_svg(svg_path.read_text(), allowed_cities=cities)


def test_site_catalogue_is_deterministic(tmp_path: Path) -> None:
    one = load_built_site(tmp_path / "a", count=3)
    two = load_built_site(tmp_path / "b", count=3)
    assert json.dumps(one["moments"]) == json.dumps(two["moments"])


def test_catalogue_js_is_loadable_as_json(tmp_path: Path) -> None:
    load_built_site(tmp_path, count=2)
    payload = (tmp_path / "catalogue.js").read_text()
    assert payload.startswith("window.BUZZER_CATALOGUE = ")
    body = payload.removeprefix("window.BUZZER_CATALOGUE = ").rstrip().rstrip(";")
    parsed = json.loads(body)
    assert parsed["count"] == 2

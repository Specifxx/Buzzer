from pathlib import Path

import pytest

from buzzer.datasource import CachedSource

FIXTURES_DIR = Path(__file__).parent / "fixtures"

FINALS_GAME = "0042500401"  # synthetic playoff thriller (see generate_fixtures.py)
QUIET_GAME = "0022500123"  # synthetic regular-season blowout, no moments


@pytest.fixture()
def source() -> CachedSource:
    """Offline DataSource backed by the generated fixtures."""
    return CachedSource(FIXTURES_DIR, upstream=None)


@pytest.fixture(autouse=True)
def fast_print_exports(monkeypatch: pytest.MonkeyPatch) -> None:
    """Rasterize tiny PNGs in tests; full 300-DPI export has its own test
    (test_print_png_is_300dpi_sized) and is exercised in real runs."""
    from buzzer.render import renderer

    monkeypatch.setattr(renderer, "DPI", 25)
    monkeypatch.setattr(renderer, "PREVIEW_WIDTH_PX", 300)

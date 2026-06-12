import os
from pathlib import Path

import pytest

from buzzer.datasource import CachedSource

FIXTURES_DIR = Path(__file__).parent / "fixtures"

FINALS_GAME = "0042500401"  # synthetic playoff thriller (see generate_fixtures.py)
QUIET_GAME = "0022500123"  # synthetic regular-season blowout, no moments


def _cairo_available() -> bool:
    """True if cairosvg can actually rasterize (system Cairo present).

    On Windows without the GTK runtime the import succeeds but the first
    render raises OSError("no library called cairo-2 was found"), so we
    probe with a 1px render rather than trusting the import. Set
    BUZZER_SKIP_CAIRO_TESTS=1 to force-skip the rendering tests.
    """
    if os.environ.get("BUZZER_SKIP_CAIRO_TESTS"):
        return False
    try:
        import cairosvg

        cairosvg.svg2png(
            bytestring=b'<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>'
        )
    except Exception:
        return False
    return True


CAIRO_AVAILABLE = _cairo_available()

requires_cairo = pytest.mark.skipif(
    not CAIRO_AVAILABLE,
    reason="needs system Cairo (libcairo2 / GTK runtime on Windows / use WSL) to rasterize PNGs",
)


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

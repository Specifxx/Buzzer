"""Register the bundled OFL fonts with fontconfig before cairosvg runs.

Anton, Space Grotesk and Space Mono ship inside the package (SIL Open
Font License — see LICENSE-* next to the .ttf files), so print renders
look identical on every machine instead of falling back to whatever the
OS has. We point fontconfig at the bundled directory via a generated
config that still includes the system fonts.
"""

from __future__ import annotations

import logging
import os
import tempfile
from functools import cache
from pathlib import Path

logger = logging.getLogger(__name__)

FONTS_DIR = Path(__file__).parent / "fonts"

_FONTCONFIG_TEMPLATE = """<?xml version="1.0"?>
<!DOCTYPE fontconfig SYSTEM "fonts.dtd">
<fontconfig>
  <dir>{fonts_dir}</dir>
  <include ignore_missing="yes">/etc/fonts/fonts.conf</include>
  <cachedir>{cache_dir}</cachedir>
</fontconfig>
"""


@cache
def ensure_fonts_registered() -> None:
    """Set FONTCONFIG_FILE so cairo sees the bundled fonts.

    Must run before the first cairosvg/cairo text operation. Respects an
    operator-provided FONTCONFIG_FILE.
    """
    if os.environ.get("FONTCONFIG_FILE"):
        logger.debug("FONTCONFIG_FILE already set; leaving fonts alone")
        return
    if not FONTS_DIR.exists():  # pragma: no cover - packaging error
        logger.warning("bundled fonts missing at %s; using system fonts", FONTS_DIR)
        return
    conf_dir = Path(tempfile.gettempdir()) / "buzzer-fontconfig"
    conf_dir.mkdir(parents=True, exist_ok=True)
    conf_path = conf_dir / "fonts.conf"
    conf_path.write_text(
        _FONTCONFIG_TEMPLATE.format(fonts_dir=FONTS_DIR, cache_dir=conf_dir / "cache")
    )
    os.environ["FONTCONFIG_FILE"] = str(conf_path)
    logger.debug("fontconfig configured with bundled fonts: %s", conf_path)

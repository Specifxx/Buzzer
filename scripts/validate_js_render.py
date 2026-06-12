"""Validate the JS-rendered SVGs with the Python content firewall.

Run after scripts/check_js_render.mjs. Every SVG the browser renderer can
produce must parse as XML and pass the same allowlist validation as the
Python pipeline output — the legal rules apply to the preview app too.
"""

from __future__ import annotations

import sys
from pathlib import Path

from buzzer.render.validate import validate_svg

CITIES = ("Boston", "Denver", "Phoenix", "Dallas", "Cleveland", "Orlando")


def main() -> int:
    out_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/js_render_check")
    svgs = sorted(out_dir.glob("*.svg"))
    if not svgs:
        print(f"no SVGs found in {out_dir} — run check_js_render.mjs first", file=sys.stderr)
        return 1
    for path in svgs:
        validate_svg(path.read_text(), allowed_cities=CITIES)
    print(f"python validation: {len(svgs)} JS-rendered SVGs are well-formed and firewall-clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
